#!/usr/bin/env python3
"""Pi 5と特定済みPico 1～16台を使うmanager再検証。依存: mpremote 1.28.0。"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import select
import shlex
import subprocess
import time
from mpremote.transport_serial import SerialTransport

# Values are supplied by the operator after checking connected devices.
ROOT = BASE = HOST = LOG = None
RAY_ROOT = None
PORTS = NODE_IDS = None
MANAGER_PORT = None
MANAGER_HOST_OVERRIDE = None
JOB_PREFIX = None
SSH_HOST_KEY_ALIAS = None
RESTORE_RUN_FOREVER = False
QUIET_NONPARTICIPANTS = False
CYCLE_SECONDS = 40.0
MINIMUM_RESULT_DISPLAY_SECONDS = 2.0
ISOLATE_EXTERNAL_ROUTE = False


class AllWorkersUnavailableCase(RuntimeError):
    """A manager job lost every participating worker."""

    def __init__(self, job_id, worker_failures, manager_error):
        super().__init__('All workers unavailable in ' + job_id)
        self.job_id = job_id
        self.worker_failures = worker_failures
        self.manager_error = manager_error


def _manager_failure_details(errors):
    failure_types = [
        line.split(' ', 1)[1]
        for line in errors.splitlines()
        if line.startswith('FAILURE_TYPE ')
    ]
    failure_records = [
        line.split(' ', 1)[1]
        for line in errors.splitlines()
        if line.startswith('FAILURE_WORKERS ')
    ]
    failures = (
        json.loads(failure_records[0])
        if len(failure_records) == 1 else []
    )
    return failure_types[-1] if failure_types else None, failures, failure_records


def ssh_command(remote_command):
    command = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8']
    if SSH_HOST_KEY_ALIAS:
        command.extend(['-o', 'HostKeyAlias=' + SSH_HOST_KEY_ALIAS])
    command.extend([HOST, remote_command])
    return command


def worker_source(fault=None, ray=False, diagnostics=False):
    setup = '''import gc, time, network_config, pico_worker, network_protocol
original_port = network_config.MANAGER_PORT
original_host = network_config.MANAGER_HOST
original_send = network_protocol.send_frame
gc.collect()
'''
    if diagnostics:
        setup += '''original_send_all = network_protocol._send_all
original_worker_gc = pico_worker.gc
diagnostic_context = {}
diagnostic_state = {
    'send_calls': 0,
    'send_errors': 0,
    'max_send_ms': 0,
    'gc_calls': 0,
    'max_gc_ms': 0,
    'tile_result_frames': 0,
    'inject_payload_stall': False,
    'payload_stall_injected': False,
}
def diagnostic_rssi():
    try:
        wlan = pico_worker.network.WLAN(pico_worker.network.STA_IF)
        if not wlan.isconnected():
            return None
        return wlan.status('rssi')
    except Exception:
        return None
diagnostic_state['rssi_initial'] = diagnostic_rssi()
def diagnostic_emit(record_type, data):
    data['node_id'] = network_config.NODE_ID
    pico_worker._emit(record_type, data)
def diagnostic_send_all(sock, data):
    view = memoryview(data)
    sent = 0
    started = time.ticks_ms()
    free_before = gc.mem_free()
    part = diagnostic_context.get('part', 0)
    diagnostic_context['part'] = part + 1
    diagnostic_state['send_calls'] += 1
    try:
        while sent < len(view):
            chunk = view[sent:]
            injecting = (
                diagnostic_state['inject_payload_stall']
                and not diagnostic_state['payload_stall_injected']
                and diagnostic_context.get('frame_type') == 'tile_result'
                and diagnostic_context.get('frame_index') == 4
                and part == 1
            )
            if injecting:
                diagnostic_state['payload_stall_injected'] = True
                diagnostic_emit('fault_injection', {
                    'frame_type': diagnostic_context.get('frame_type'),
                    'tile_id': diagnostic_context.get('tile_id'),
                    'part': 'payload',
                    'sent': sent,
                    'stall_seconds': 10,
                    'rssi_before': diagnostic_rssi(),
                })
                time.sleep(10)
            count = sock.send(chunk)
            if count is None:
                count = len(chunk)
            if count <= 0:
                raise network_protocol.ProtocolError('socket closed while sending')
            sent += count
    except Exception as exc:
        elapsed = time.ticks_diff(time.ticks_ms(), started)
        diagnostic_state['send_errors'] += 1
        if elapsed > diagnostic_state['max_send_ms']:
            diagnostic_state['max_send_ms'] = elapsed
        diagnostic_emit('send_diagnostic', {
            'outcome': 'error',
            'frame_type': diagnostic_context.get('frame_type'),
            'tile_id': diagnostic_context.get('tile_id'),
            'part': 'header' if part == 0 else 'payload',
            'length': len(view),
            'sent': sent,
            'elapsed_ms': elapsed,
            'mem_free_before': free_before,
            'mem_free_after': gc.mem_free(),
            'rssi_after': diagnostic_rssi(),
            'error_type': type(exc).__name__,
            'error': str(exc),
        })
        raise
    elapsed = time.ticks_diff(time.ticks_ms(), started)
    if elapsed > diagnostic_state['max_send_ms']:
        diagnostic_state['max_send_ms'] = elapsed
    if elapsed >= 250:
        diagnostic_emit('send_diagnostic', {
            'outcome': 'slow',
            'frame_type': diagnostic_context.get('frame_type'),
            'tile_id': diagnostic_context.get('tile_id'),
            'part': 'header' if part == 0 else 'payload',
            'length': len(view),
            'sent': sent,
            'elapsed_ms': elapsed,
            'mem_free_before': free_before,
            'mem_free_after': gc.mem_free(),
            'rssi_after': diagnostic_rssi(),
        })
def diagnostic_send_frame(sock, message, payload=b''):
    diagnostic_context.clear()
    diagnostic_context['frame_type'] = message.get('type')
    diagnostic_context['tile_id'] = message.get('tile_id')
    if message.get('type') == 'tile_result':
        diagnostic_state['tile_result_frames'] += 1
        diagnostic_context['frame_index'] = diagnostic_state['tile_result_frames']
    diagnostic_context['part'] = 0
    try:
        return original_send(sock, message, payload)
    finally:
        diagnostic_context.clear()
class DiagnosticGc:
    def collect(self):
        started = time.ticks_ms()
        result = gc.collect()
        elapsed = time.ticks_diff(time.ticks_ms(), started)
        diagnostic_state['gc_calls'] += 1
        if elapsed > diagnostic_state['max_gc_ms']:
            diagnostic_state['max_gc_ms'] = elapsed
        if elapsed >= 100:
            diagnostic_emit('gc_diagnostic', {
                'elapsed_ms': elapsed,
                'mem_free_after': gc.mem_free(),
                'rssi_after': diagnostic_rssi(),
            })
        return result
    def mem_free(self):
        return gc.mem_free()
network_protocol._send_all = diagnostic_send_all
network_protocol.send_frame = diagnostic_send_frame
pico_worker.gc = DiagnosticGc()
'''
        if fault == 'send-stall':
            setup += "diagnostic_state['inject_payload_stall'] = True\n"
    if ray:
        setup += 'import ray_worker\n'
    if fault in ('prefix', 'header', 'payload', 'trickle'):
        setup += '''fault_count = 0
def injected_send(sock, message, payload=b''):
    global fault_count
    if message.get('type') == 'tile_result':
        fault_count += 1
        if fault_count == 21:
            frame = network_protocol.encode_frame(message, payload)
            print('FAULT_INJECTED', network_config.NODE_ID, fault_count)
'''
        if fault == 'trickle':
            setup += '''            for value in frame[:50]:
                sock.send(bytes([value]))
                time.sleep(0.2)
            return original_send(sock, message, payload)
'''
        else:
            cut = {'prefix': '1', 'header': '6', 'payload': 'len(frame)-1'}[fault]
            setup += f'''            sock.send(frame[:{cut}])
            time.sleep(10)
'''
        setup += '''    return original_send(sock, message, payload)
network_protocol.send_frame = injected_send
'''
    call = 'ray_worker.run_once()' if ray else 'pico_worker.run_once()'
    if fault == 'sleep':
        call = 'pico_worker.run_once(stall_after_tiles=20, stall_seconds=10)'
    elif fault == 'early-sleep':
        call = 'pico_worker.run_once(stall_after_tiles=1, stall_seconds=10)'
    elif fault == 'initial-sleep':
        call = 'pico_worker.run_once(stall_after_tiles=0, stall_seconds=10)'
    cleanup = ''
    if diagnostics:
        cleanup = '''    diagnostic_state['rssi_final'] = diagnostic_rssi()
    diagnostic_state['mem_free_final'] = gc.mem_free()
    network_protocol._send_all = original_send_all
    pico_worker.gc = original_worker_gc
    diagnostic_emit('validation_diagnostics', diagnostic_state)
'''
    host_assignment = ''
    if MANAGER_HOST_OVERRIDE is not None:
        host_assignment = (
            'network_config.MANAGER_HOST = %r\n' % MANAGER_HOST_OVERRIDE
        )
    return setup + f'''network_config.MANAGER_PORT = {MANAGER_PORT}
{host_assignment}try:
    result = {call}
    print('VALIDATION_COMPLETE', result)
finally:
{cleanup}    network_protocol.send_frame = original_send
    network_config.MANAGER_PORT = original_port
    network_config.MANAGER_HOST = original_host
    gc.collect()
    print('VALIDATION_RESTORED', network_config.NODE_ID, network_config.MANAGER_PORT, gc.mem_free())
'''

def run_case(
    tag,
    count,
    job='small',
    fault=None,
    ray=False,
    fault_worker=1,
    expected_failure=False,
    diagnostics=False,
    started_callback=None,
):
    job_id = JOB_PREFIX + '-' + tag
    if (LOG / (job_id + '-manager.log')).exists():
        raise RuntimeError('Log already exists; use a new job-prefix: ' + job_id)
    remote = f'''import sys, json
sys.path.insert(0, {BASE + '/mandelbrot/network'!r})
import manager
'''
    if ray:
        remote += f'''sys.path.insert(0, {RAY_ROOT + '/network'!r})
import ray_manager
assert ray_manager.cluster_manager is manager
workload = ray_manager.RayTracingWorkload({ROOT + '/' + job_id + '.png'!r})
job = ray_manager.EXHIBITION_JOB
'''
    else:
        manager_jobs = {
            'small': 'SMALL_JOB',
            'exhibition': 'EXHIBITION_JOB',
            'recovery': 'RECOVERY_JOB',
        }
        if job not in manager_jobs:
            raise ValueError('Unknown manager job: ' + job)
        remote += f'workload = None\njob = manager.{manager_jobs[job]}\n'
    max_iter = 2 if job == 'small' and not ray else (1 if job == 'recovery' else 16)
    request_window = 1 if job == 'recovery' else 4
    remote += f'''summary = manager.run_tcp_server(job, {max_iter}, '0.0.0.0', {MANAGER_PORT},
    {180 if ray else 30}, {job_id!r}, ready_callback=lambda addr: print('READY', flush=True),
    request_window={request_window}, worker_count={count}, worker_timeout=5,
    record_path={ROOT + '/' + job_id + '-trace.json'!r}, workload=workload)
with open({ROOT + '/summaries.jsonl'!r}, 'a') as stream:
    stream.write(json.dumps(summary) + '\\n')
print(json.dumps(summary), flush=True)
'''
    head, body = remote.split('summary = manager.run_tcp_server(', 1)
    body = 'summary = manager.run_tcp_server(' + body
    remote = head + 'try:' + chr(10) + ''.join('    ' + line + chr(10) for line in body.splitlines())
    remote += "except Exception as exc:\n    print('FAILURE_TYPE', type(exc).__name__, file=sys.stderr, flush=True)\n    print('FAILURE_MESSAGE', str(exc), file=sys.stderr, flush=True)\n    failures = getattr(exc, 'worker_failures', None)\n    if failures is not None:\n        print('FAILURE_WORKERS', json.dumps(failures), file=sys.stderr, flush=True)\n    raise\n"
    transports = []
    proc = None
    results = []
    original_ports = {}
    original_hosts = {}
    try:
        managed_count = len(PORTS) if QUIET_NONPARTICIPANTS else count
        for index in range(managed_count):
            board = SerialTransport(PORTS[index])
            transports.append(board)
            board.enter_raw_repl(soft_reset=False)
            identity = board.exec("import network_config; print(network_config.NODE_ID)").decode().strip()
            original_ports[index] = int(board.exec("print(network_config.MANAGER_PORT)").decode().strip())
            original_hosts[index] = board.exec(
                "print(network_config.MANAGER_HOST)"
            ).decode().strip()
            if identity != NODE_IDS[index]:
                raise RuntimeError('Unexpected identity: ' + identity)
        proc = subprocess.Popen(ssh_command(
            'timeout 220s python3 -u -c ' + shlex.quote(remote)
        ),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if not select.select([proc.stdout], [], [], 10)[0]:
            raise RuntimeError('Manager did not become ready')
        first_line = proc.stdout.readline().strip()
        if first_line != 'READY':
            raise RuntimeError('Manager startup failed: ' + first_line + proc.stderr.read())
        print('START', job_id, count, fault, flush=True)
        if started_callback is not None:
            started_callback(time.monotonic())
        participants = transports[:count]
        with ThreadPoolExecutor(max_workers=count) as pool:
            futures = [pool.submit(board.exec_raw, worker_source(
                fault if index == fault_worker else None,
                ray,
                diagnostics,
            ), 210)
                       for index, board in enumerate(participants)]
            try:
                output, errors = proc.communicate(timeout=215)
                (LOG / (job_id + '-manager.log')).write_text(output + errors)
                for index, future in enumerate(futures):
                    result, error = future.result(timeout=215)
                    (LOG / (job_id + '-pico-%02d.log' % (index + 1))).write_bytes(result + error)
                    results.append((result, error))
                failure_type, failures, failure_records = (
                    _manager_failure_details(errors)
                )
                all_workers_unavailable = (
                    proc.returncode
                    and failure_type == 'AllWorkersUnavailable'
                )
                if expected_failure:
                    if not all_workers_unavailable:
                        raise RuntimeError(
                            'Manager did not report AllWorkersUnavailable: '
                            + errors[-2000:]
                        )
                    if len(failure_records) != 1:
                        raise RuntimeError('Expected one FAILURE_WORKERS record')
                    if len(failures) != 1:
                        raise RuntimeError('Expected one failed worker')
                    failure = failures[0]
                    if (
                        failure['node_id'] != NODE_IDS[0]
                        or not failure['timed_out']
                        or failure['requeued_tiles'] != 4
                        or failure['phase'] != 'waiting_first_result'
                        or failure['first_request_fully_sent_ms'] is None
                        or failure['first_result_byte_received_ms'] is not None
                    ):
                        raise RuntimeError('Unexpected failure diagnostics: ' + failure_records[0])
                    print('PASS', job_id, 'expected failure', failure_records[0], flush=True)
                    return failure
                if proc.returncode:
                    if all_workers_unavailable:
                        raise AllWorkersUnavailableCase(
                            job_id,
                            failures,
                            errors[-2000:],
                        )
                    raise RuntimeError('Manager failed: ' + errors[-2000:])
                summary = json.loads(output.strip().splitlines()[-1])
                for index, (result, error) in enumerate(results):
                    if b'VALIDATION_RESTORED' not in result:
                        raise RuntimeError('Worker did not restore runtime configuration')
                    if error and not (fault and index == fault_worker and (b'ECONNRESET' in error or b'EPIPE' in error)):
                        raise RuntimeError('Unexpected worker error: ' + error.decode())
                expected = (
                    '4278ccd8' if ray else {
                        'small': '9bcd4fd2',
                        'exhibition': '1a26b685',
                        'recovery': 'e590a9e7',
                    }[job]
                )
                if summary['checksum32'] != expected or not summary['known_pixels_match']:
                    raise RuntimeError('Incorrect result')
                if sorted(summary['node_ids']) != sorted(NODE_IDS[:count]):
                    raise RuntimeError('Unexpected participating nodes')
                if fault:
                    if len(summary['worker_timeouts']) != 1 or summary['worker_timeouts'][0]['node_id'] != NODE_IDS[fault_worker]:
                        raise RuntimeError('Fault not correctly detected')
                    if summary['worker_count_active_at_completion'] != count - 1 or summary['requeued_tiles'] != 4:
                        raise RuntimeError('Fault reassignment did not match window')
                elif summary['worker_timeouts'] or summary['requeued_tiles'] or summary['worker_count_active_at_completion'] != count:
                    raise RuntimeError('Unexpected worker failure')
                with (LOG / 'summaries.jsonl').open('a') as stream:
                    stream.write(json.dumps(summary) + '\n')
                print('PASS', job_id, summary['e2e_ms'], summary['checksum32'],
                      'timeouts', summary['worker_timeouts'], flush=True)
                return summary
            finally:
                if proc.poll() is None:
                    proc.terminate()
                for board in participants:
                    board.serial.write(b'\x03')
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        restore_errors = []
        for index, board in enumerate(transports):
            try:
                board.enter_raw_repl(soft_reset=False)
                status = board.exec(
                    "import network_config; print('FINAL_STATE', "
                    "network_config.NODE_ID, network_config.MANAGER_HOST, "
                    "network_config.MANAGER_PORT)"
                ).decode().strip().split()
                if index in original_ports and status[-1] != str(original_ports[index]):
                    raise RuntimeError('Runtime port not restored: ' + repr(status))
                if index in original_hosts and status[-2] != original_hosts[index]:
                    raise RuntimeError('Runtime host not restored: ' + repr(status))
                if RESTORE_RUN_FOREVER:
                    board.exec_raw_no_follow(
                        "import pico_worker; pico_worker.run_forever()"
                    )
                else:
                    board.exit_raw_repl()
            except Exception as exc:
                restore_errors.append('%s: %s' % (PORTS[index], exc))
            finally:
                board.close()
        if restore_errors:
            raise RuntimeError('Check worker recovery before retrying: ' + '; '.join(restore_errors))


def _append_jsonl(path, record):
    with path.open('a') as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n')


def _write_display_state(state):
    path = LOG / (JOB_PREFIX + '-display-state.json')
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    )
    temporary.replace(path)


def _held_result(summary):
    if summary is None:
        return None
    return {
        'job_id': summary['job_id'],
        'checksum32': summary['checksum32'],
        'known_pixels_match': summary['known_pixels_match'],
    }


def _manual_recovery_actions():
    return [
        'PicoとUSB serial deviceが16台すべて列挙されていることを確認する',
        'Pico、USBハブ、給電系の発熱、異臭、給電不安定を確認する',
        '16台未満の場合はUSB resetを行わず、物理接続と給電を確認する',
        '16台が揃っている場合だけrecover16を1回実行する',
        '復旧確認後に新しいjob prefixで展示サイクルを再開する',
    ]


def _validate_recovery_summary(summary):
    if (
        summary.get('checksum32') != 'e590a9e7'
        or not summary.get('known_pixels_match')
        or summary.get('tiles_completed') != 16
        or summary.get('worker_count_started') != 16
        or summary.get('worker_count_active_at_completion') != 16
        or summary.get('worker_timeouts')
        or summary.get('requeued_tiles')
        or sorted(summary.get('node_ids', [])) != sorted(NODE_IDS)
    ):
        raise RuntimeError('Recovery verification failed: %r' % summary)


def _finalize_cycle_interval(cycle_log, record, interval_ms):
    record['next_cycle_start_interval_ms'] = round(interval_ms, 3)
    if not 30000 <= record['next_cycle_start_interval_ms'] <= 45000:
        raise RuntimeError('Exhibition cycle outside 30-45 seconds: %r' % record)
    _append_jsonl(cycle_log, record)
    print('CYCLE_PASS', json.dumps(record, sort_keys=True), flush=True)


def run_exhibition_cycles(cycle_count, fault_cycle_index=None):
    """Run display cycles and recover once when the one-node job loses its worker."""
    cycle_log = LOG / (JOB_PREFIX + '-cycles.jsonl')
    incident_log = LOG / (JOB_PREFIX + '-incidents.jsonl')
    if cycle_log.exists() or incident_log.exists():
        raise RuntimeError(
            'Cycle or incident log already exists; use a new job-prefix: '
            + JOB_PREFIX
        )
    previous_start = None
    records = []
    last_successful_result = None
    for cycle_index in range(1, cycle_count + 1):
        started = []
        failure = None
        try:
            one = run_case(
                'cycle-%02d-01n' % cycle_index,
                1,
                job='exhibition',
                fault=(
                    'initial-sleep'
                    if cycle_index == fault_cycle_index else None
                ),
                fault_worker=0,
                started_callback=started.append,
            )
        except AllWorkersUnavailableCase as exc:
            one = None
            failure = exc
        if len(started) != 1:
            raise RuntimeError('One-node start time was not recorded')
        cycle_started = started[0]
        if previous_start is not None:
            _finalize_cycle_interval(
                cycle_log,
                records[-1],
                (cycle_started - previous_start) * 1000,
            )
        previous_start = cycle_started

        if failure is not None:
            incident_id = '%s-cycle-%02d-all-workers' % (
                JOB_PREFIX,
                cycle_index,
            )
            incident = {
                'cycle_index': cycle_index,
                'incident_id': incident_id,
                'source_job_id': failure.job_id,
                'source_failure_type': 'AllWorkersUnavailable',
                'source_worker_failures': failure.worker_failures,
                'held_result': _held_result(last_successful_result),
                'recovery_attempts': 1,
                'recovery_job_id': (
                    JOB_PREFIX + '-cycle-%02d-recovery' % cycle_index
                ),
            }
            _write_display_state({
                'mode': 'recovering',
                'incident_id': incident_id,
                'held_result': incident['held_result'],
                'message': '全worker停止を検出したため、16台復旧確認を実行中です。',
            })
            try:
                recovery = run_case(
                    'cycle-%02d-recovery' % cycle_index,
                    16,
                    job='recovery',
                )
                _validate_recovery_summary(recovery)
            except Exception as exc:
                incident.update({
                    'outcome': 'manual_recovery_required',
                    'recovery_error_type': type(exc).__name__,
                    'recovery_error': str(exc),
                    'manual_recovery_actions': _manual_recovery_actions(),
                    'elapsed_ms': round(
                        (time.monotonic() - cycle_started) * 1000,
                        3,
                    ),
                })
                records.append(incident)
                _append_jsonl(incident_log, incident)
                _write_display_state({
                    'mode': 'waiting_for_manual_recovery',
                    'incident_id': incident_id,
                    'held_result': incident['held_result'],
                    'message': '自動復旧に失敗しました。機材を確認してください。',
                    'manual_recovery_actions': incident[
                        'manual_recovery_actions'
                    ],
                })
                print(
                    'WAITING_SCREEN',
                    json.dumps(incident, ensure_ascii=False, sort_keys=True),
                    flush=True,
                )
                return records

            elapsed = time.monotonic() - cycle_started
            display_seconds = max(0, CYCLE_SECONDS - elapsed)
            incident.update({
                'outcome': 'recovered',
                'recovery_checksum32': recovery['checksum32'],
                'recovery_ready_ms': recovery['startup_ready_ms'],
                'recovery_e2e_ms': recovery['e2e_ms'],
                'elapsed_ms': round(elapsed * 1000, 3),
                'held_result_display_ms': round(display_seconds * 1000, 3),
            })
            records.append(incident)
            _append_jsonl(incident_log, incident)
            _write_display_state({
                'mode': 'holding_previous_result',
                'incident_id': incident_id,
                'held_result': incident['held_result'],
                'message': '16台の復旧を確認しました。次の展示サイクルで更新します。',
            })
            print(
                'RECOVERY_PASS',
                json.dumps(incident, ensure_ascii=False, sort_keys=True),
                flush=True,
            )
            time.sleep(display_seconds)
            previous_start = None
            continue

        sixteen = run_case(
            'cycle-%02d-16n' % cycle_index,
            16,
            job='exhibition',
        )
        processing_seconds = time.monotonic() - cycle_started
        display_seconds = CYCLE_SECONDS - processing_seconds
        if display_seconds < MINIMUM_RESULT_DISPLAY_SECONDS:
            raise RuntimeError(
                'Less than %.3f seconds remain for result display: %.3f'
                % (MINIMUM_RESULT_DISPLAY_SECONDS, display_seconds)
            )
        record = {
            'cycle_index': cycle_index,
            'outcome': 'completed',
            'cycle_target_ms': round(CYCLE_SECONDS * 1000, 3),
            'minimum_result_display_ms': round(
                MINIMUM_RESULT_DISPLAY_SECONDS * 1000, 3
            ),
            'processing_and_setup_ms': round(processing_seconds * 1000, 3),
            'result_display_ms': round(display_seconds * 1000, 3),
            'one_node_job_id': one['job_id'],
            'one_node_e2e_ms': one['e2e_ms'],
            'one_node_checksum32': one['checksum32'],
            'sixteen_node_job_id': sixteen['job_id'],
            'sixteen_node_e2e_ms': sixteen['e2e_ms'],
            'sixteen_node_checksum32': sixteen['checksum32'],
        }
        records.append(record)
        last_successful_result = sixteen
        _write_display_state({
            'mode': 'result',
            'held_result': _held_result(last_successful_result),
            'message': '展示結果を表示中です。',
        })
        print('RESULT_DISPLAY', json.dumps(record, sort_keys=True), flush=True)
        time.sleep(display_seconds)

    if previous_start is not None:
        _finalize_cycle_interval(
            cycle_log,
            records[-1],
            (time.monotonic() - previous_start) * 1000,
        )
    return records


def external_probe_source():
    return '''import json, socket
def probe(address, port):
    sock = socket.socket()
    try:
        sock.settimeout(2)
        sock.connect((address, port))
        return {'address': address, 'port': port, 'connected': True}
    except Exception as exc:
        return {
            'address': address,
            'port': port,
            'connected': False,
            'error_type': type(exc).__name__,
            'error': str(exc),
        }
    finally:
        sock.close()
print(json.dumps([
    probe('1.1.1.1', 443),
    probe('8.8.8.8', 53),
]))
'''


def probe_pico_offline(index):
    board = SerialTransport(PORTS[index])
    try:
        board.enter_raw_repl(soft_reset=False)
        identity = board.exec(
            "import network_config; print(network_config.NODE_ID)"
        ).decode().strip()
        if identity != NODE_IDS[index]:
            raise RuntimeError('Unexpected identity: ' + identity)
        network_state = board.exec(
            "import json, network; wlan=network.WLAN(network.STA_IF); "
            "print(json.dumps({'connected': wlan.isconnected(), "
            "'ifconfig': wlan.ifconfig(), "
            "'rssi': wlan.status('rssi') if wlan.isconnected() else None}))"
        ).decode().strip()
        probes = board.exec(external_probe_source()).decode().strip()
        return {
            'node_id': identity,
            'network': json.loads(network_state.splitlines()[-1]),
            'external_probes': json.loads(probes.splitlines()[-1]),
        }
    finally:
        try:
            board.enter_raw_repl(soft_reset=False)
            board.exec_raw_no_follow(
                "import pico_worker; pico_worker.run_forever()"
            )
        finally:
            board.close()


def verify_offline():
    """Require local Wi-Fi connectivity and failed external TCP probes."""
    remote = external_probe_source()
    completed = subprocess.run(
        ssh_command('timeout 10s python3 -c ' + shlex.quote(remote)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=15,
    )
    if completed.returncode:
        raise RuntimeError('Pi offline probe failed: ' + completed.stderr[-1000:])
    pi_probes = json.loads(completed.stdout.strip().splitlines()[-1])
    with ThreadPoolExecutor(max_workers=len(PORTS)) as pool:
        pico_records = list(pool.map(probe_pico_offline, range(len(PORTS))))
    record = {
        'pi_external_probes': pi_probes,
        'pico_records': pico_records,
    }
    output = LOG / (JOB_PREFIX + '-offline-check.json')
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    failures = []
    if any(probe['connected'] for probe in pi_probes):
        failures.append('Pi 5 still has an external TCP path')
    for pico in pico_records:
        if not pico['network']['connected']:
            failures.append(pico['node_id'] + ' is not connected to local Wi-Fi')
        if any(probe['connected'] for probe in pico['external_probes']):
            failures.append(pico['node_id'] + ' still has an external TCP path')
    if failures:
        raise RuntimeError('; '.join(failures))
    print('OFFLINE_PASS', output, len(pico_records), flush=True)
    return record


def run_remote_checked(remote_command, timeout=15):
    completed = subprocess.run(
        ssh_command(remote_command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    if completed.returncode:
        raise RuntimeError(
            'Remote command failed: ' + completed.stderr[-1000:]
        )
    return completed.stdout


def set_pico_ifconfig(index, requested=None):
    board = SerialTransport(PORTS[index])
    try:
        board.enter_raw_repl(soft_reset=False)
        identity = board.exec(
            "import network_config; print(network_config.NODE_ID)"
        ).decode().strip()
        if identity != NODE_IDS[index]:
            raise RuntimeError('Unexpected identity: ' + identity)
        before = json.loads(board.exec(
            "import json, network; wlan=network.WLAN(network.STA_IF); "
            "print(json.dumps(wlan.ifconfig()))"
        ).decode().strip().splitlines()[-1])
        if requested is not None:
            board.exec(
                "import network; network.WLAN(network.STA_IF).ifconfig(%r)"
                % (tuple(requested),)
            )
        after = json.loads(board.exec(
            "import json, network; wlan=network.WLAN(network.STA_IF); "
            "print(json.dumps(wlan.ifconfig()))"
        ).decode().strip().splitlines()[-1])
        return {'node_id': identity, 'before': before, 'after': after}
    finally:
        try:
            board.enter_raw_repl(soft_reset=False)
            board.exec_raw_no_follow(
                "import pico_worker; pico_worker.run_forever()"
            )
        finally:
            board.close()


def isolate_external_routes():
    """Prefer temporary blackhole defaults while preserving local routes."""
    ipv4 = json.loads(run_remote_checked('ip -j -4 route show default'))
    ipv6 = json.loads(run_remote_checked('ip -j -6 route show default'))
    if not ipv4:
        raise RuntimeError('Pi 5 has no IPv4 default route to isolate')
    if any(route.get('type') == 'blackhole' for route in ipv4 + ipv6):
        raise RuntimeError('Pi 5 already has a blackhole default route')
    pico_states = []
    try:
        for index in range(len(PORTS)):
            current = set_pico_ifconfig(index)
            before = current['before']
            pico_states.append({
                'index': index,
                'node_id': current['node_id'],
                'ifconfig': before,
            })
            requested = [before[0], before[1], '0.0.0.0', before[3]]
            changed = set_pico_ifconfig(index, requested)
            if changed['after'][2] != '0.0.0.0':
                raise RuntimeError(
                    changed['node_id'] + ' did not remove its default gateway'
                )
        run_remote_checked(
            "sudo -n ip -4 route add blackhole default metric 1; "
            "sudo -n ip -6 route add blackhole default metric 1; "
            "echo routes_isolated"
        )
        remaining4 = json.loads(
            run_remote_checked('ip -j -4 route show default')
        )
        remaining6 = json.loads(
            run_remote_checked('ip -j -6 route show default')
        )
        if not any(route.get('type') == 'blackhole' for route in remaining4):
            raise RuntimeError('Pi 5 IPv4 blackhole route is missing')
        if not any(route.get('type') == 'blackhole' for route in remaining6):
            raise RuntimeError('Pi 5 IPv6 blackhole route is missing')
        state = {
            'pi_ipv4_default_routes': ipv4,
            'pi_ipv6_default_routes': ipv6,
            'picos': pico_states,
        }
        output = LOG / (JOB_PREFIX + '-route-isolation.json')
        output.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
        print('ROUTES_ISOLATED', output, len(pico_states), flush=True)
        return state
    except Exception:
        state = {
            'pi_ipv4_default_routes': ipv4,
            'pi_ipv6_default_routes': ipv6,
            'picos': pico_states,
        }
        restore_external_routes(state)
        raise


def restore_external_routes(state):
    errors = []
    try:
        run_remote_checked(
            "sudo -n ip -4 route del blackhole default metric 1 "
            "2>/dev/null || true; "
            "sudo -n ip -6 route del blackhole default metric 1 "
            "2>/dev/null || true; "
            "echo routes_restored"
        )
    except Exception as exc:
        errors.append('Pi route: ' + str(exc))
    for pico in state.get('picos', []):
        try:
            restored = set_pico_ifconfig(pico['index'], pico['ifconfig'])
            if restored['after'] != pico['ifconfig']:
                raise RuntimeError('ifconfig did not match saved state')
        except Exception as exc:
            errors.append(pico['node_id'] + ': ' + str(exc))
    if errors:
        raise RuntimeError(
            'External route recovery requires manual check: ' + '; '.join(errors)
        )
    print('ROUTES_RESTORED', len(state.get('picos', [])), flush=True)


def run_with_offline_requirement(action):
    state = None
    try:
        if ISOLATE_EXTERNAL_ROUTE:
            state = isolate_external_routes()
        verify_offline()
        return action()
    finally:
        if state is not None:
            restore_external_routes(state)


def inventory_devices():
    records = []
    for port, expected_node_id in zip(PORTS, NODE_IDS):
        board = SerialTransport(port)
        try:
            board.enter_raw_repl(soft_reset=False)
            raw = board.exec(
                "import json, network, sys, network_config\n"
                "print(json.dumps({'node_id': network_config.NODE_ID, "
                "'manager_host': network_config.MANAGER_HOST, "
                "'manager_port': network_config.MANAGER_PORT, "
                "'ifconfig': network.WLAN(network.STA_IF).ifconfig(), "
                "'implementation': str(sys.implementation), "
                "'version': sys.version}))"
            )
            record = json.loads(raw.decode().strip().splitlines()[-1])
            if record['node_id'] != expected_node_id:
                raise RuntimeError(
                    'Unexpected identity on %s: %s' % (port, record['node_id'])
                )
            record['serial_port'] = port
            record['sha256'] = {}
            for path in (
                'main.py',
                'pico_worker.py',
                'network_protocol.py',
                'mandelbrot_core.py',
                'ray_worker.py',
                'raytracer_core.py',
            ):
                if board.fs_exists(path):
                    record['sha256'][path] = board.fs_hashfile(
                        path, 'sha256'
                    ).hex()
            records.append(record)
        finally:
            try:
                board.enter_raw_repl(soft_reset=False)
                if RESTORE_RUN_FOREVER:
                    board.exec_raw_no_follow(
                        "import pico_worker; pico_worker.run_forever()"
                    )
                else:
                    board.exit_raw_repl()
            finally:
                board.close()
    output = LOG / (JOB_PREFIX + '-inventory.json')
    output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')
    print('INVENTORY', output, len(records), flush=True)
    return records


def reset_runtimes():
    restored = []
    for port, expected_node_id in zip(PORTS, NODE_IDS):
        board = SerialTransport(port)
        try:
            board.enter_raw_repl(soft_reset=True)
            status = board.exec(
                "import network_config; print(network_config.NODE_ID, "
                "network_config.MANAGER_PORT)"
            ).decode().strip().split()
            if status != [expected_node_id, '8765']:
                raise RuntimeError('Unexpected state on %s: %r' % (port, status))
            restored.append(expected_node_id)
        finally:
            try:
                board.enter_raw_repl(soft_reset=False)
                board.exec_raw_no_follow(
                    "import pico_worker; pico_worker.run_forever()"
                )
            finally:
                board.close()
    print('RESET_RUNTIME', len(restored), *restored, flush=True)
    return restored


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'phase',
        choices=[
            'inventory', 'reset-runtime', 'one', 'one-repeat', 'diagnose', 'two', 'sleep',
            'partial', 'repeat', 'ray', 'scale1', 'scale8', 'scale16',
            'repeat16', 'fault16', 'observe-smoke', 'observe1',
            'observe16', 'observe-fault2', 'observe-fault16',
            'offline-check', 'cycle-smoke', 'cycle20',
        ],
    )
    parser.add_argument('--ssh-host', required=True, help='SSH destination already verified by the operator')
    parser.add_argument(
        '--ssh-host-key-alias',
        help='known_hosts name used when the verified host changed IP address',
    )
    parser.add_argument('--remote-root', required=True, help='Dedicated remote directory containing projects/')
    parser.add_argument('--ray-root', help='Optional isolated ray-tracing directory matching the installed Pico core')
    parser.add_argument('--ports', nargs='+', required=True, help='Verified USB serial ports in node order')
    parser.add_argument('--node-ids', nargs='+', required=True, help='Expected node IDs in serial-port order')
    parser.add_argument('--manager-port', type=int, default=18765, help='Unused test TCP port')
    parser.add_argument(
        '--manager-host',
        help='temporary manager IPv4 address used only in Pico RAM',
    )
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--job-prefix', required=True, help='Unique filename-safe prefix for this validation run')
    parser.add_argument(
        '--observation-runs',
        type=int,
        default=50,
        help='number of instrumented 16-node runs for observe16 (default: 50)',
    )
    parser.add_argument(
        '--cycle-seconds',
        type=float,
        default=40.0,
        help='target interval between one-node job starts (default: 40)',
    )
    parser.add_argument(
        '--minimum-result-display-seconds',
        type=float,
        default=2.0,
        help='minimum time reserved for the result display (default: 2)',
    )
    parser.add_argument(
        '--isolate-external-route',
        action='store_true',
        help='temporarily blackhole Pi defaults and clear Pico RAM gateways',
    )
    parser.add_argument(
        '--restore-run-forever',
        action='store_true',
        help='return each selected Pico to pico_worker.run_forever() on its original port',
    )
    parser.add_argument(
        '--quiet-nonparticipants',
        action='store_true',
        help='hold supplied non-participating Pico devices in raw REPL during each job',
    )
    args = parser.parse_args()
    if not 1 <= args.manager_port <= 65535:
        parser.error('manager-port must be between 1 and 65535')
    if not 1 <= args.observation_runs <= 500:
        parser.error('observation-runs must be between 1 and 500')
    if not 30 <= args.cycle_seconds <= 45:
        parser.error('cycle-seconds must be between 30 and 45')
    if not 0 <= args.minimum_result_display_seconds <= args.cycle_seconds:
        parser.error(
            'minimum-result-display-seconds must be between 0 and cycle-seconds'
        )
    if not 1 <= len(args.ports) <= 16:
        parser.error('between 1 and 16 ports are required')
    if len(args.ports) != len(args.node_ids):
        parser.error('ports and node IDs must have the same length')
    if len(set(args.ports)) != len(args.ports):
        parser.error('ports must be distinct')
    if len(set(args.node_ids)) != len(args.node_ids):
        parser.error('node IDs must be distinct')
    if not args.remote_root.startswith('/'):
        parser.error('remote-root must be absolute')
    if args.ray_root is not None and not args.ray_root.startswith('/'):
        parser.error('ray-root must be absolute')
    if not args.job_prefix or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in args.job_prefix):
        parser.error('job-prefix must contain only letters, digits, hyphens and underscores')
    HOST = args.ssh_host
    SSH_HOST_KEY_ALIAS = args.ssh_host_key_alias
    ROOT = args.remote_root.rstrip('/')
    BASE = ROOT + '/projects/raspberry-pi-pico-cluster'
    RAY_ROOT = args.ray_root or BASE + '/raytracing'
    PORTS = args.ports
    NODE_IDS = args.node_ids
    MANAGER_PORT = args.manager_port
    MANAGER_HOST_OVERRIDE = args.manager_host
    RESTORE_RUN_FOREVER = args.restore_run_forever
    QUIET_NONPARTICIPANTS = args.quiet_nonparticipants
    CYCLE_SECONDS = args.cycle_seconds
    MINIMUM_RESULT_DISPLAY_SECONDS = args.minimum_result_display_seconds
    ISOLATE_EXTERNAL_ROUTE = args.isolate_external_route
    LOG = args.output_dir
    LOG.mkdir(parents=True, exist_ok=True)
    JOB_PREFIX = args.job_prefix
    if args.phase in ('two', 'sleep', 'partial', 'ray', 'observe-fault2') and len(PORTS) < 2:
        parser.error(args.phase + ' requires at least two Pico devices')
    if args.phase == 'scale8' and len(PORTS) < 8:
        parser.error('scale8 requires at least eight Pico devices')
    if args.phase in (
        'scale16', 'repeat16', 'fault16', 'observe16', 'observe-fault16',
        'offline-check', 'cycle-smoke', 'cycle20',
    ) and len(PORTS) != 16:
        parser.error(args.phase + ' requires exactly 16 Pico devices')
    if args.phase == 'inventory':
        inventory_devices()
    elif args.phase == 'reset-runtime':
        reset_runtimes()
    elif args.phase == 'one':
        run_case('one-small', 1)
    elif args.phase == 'one-repeat':
        for index in range(1, 21):
            run_case('one-small-%02d' % index, 1)
    elif args.phase == 'diagnose':
        run_case(
            'diagnose-initial-timeout',
            1,
            fault='initial-sleep',
            fault_worker=0,
            expected_failure=True,
        )
    elif args.phase == 'two':
        run_case('two-small', 2)
        run_case('two-normal', 2, job='exhibition')
    elif args.phase == 'sleep':
        run_case('two-sleep', 2, job='exhibition', fault='sleep')
        run_case('sleep-recovery', 2)
    elif args.phase == 'partial':
        for fault in ('prefix', 'header', 'payload', 'trickle'):
            run_case('two-' + fault, 2, job='exhibition', fault=fault)
            run_case(fault + '-recovery', 2)
    elif args.phase == 'repeat':
        for index in range(1, 21):
            run_case('repeat-%02d' % index, 2, job='exhibition')
    elif args.phase == 'ray':
        run_case('ray-normal', 2, job='exhibition', ray=True)
        run_case('ray-prefix', 2, job='exhibition', fault='prefix', ray=True)
        run_case('ray-recovery', 2)
    elif args.phase in ('scale1', 'scale8', 'scale16'):
        count = {'scale1': 1, 'scale8': 8, 'scale16': 16}[args.phase]
        for index in range(1, 6):
            run_case('%02dn-%02d' % (count, index), count, job='exhibition')
    elif args.phase == 'repeat16':
        for index in range(1, 21):
            run_case('16n-repeat-%02d' % index, 16, job='exhibition')
    elif args.phase == 'fault16':
        run_case(
            '16n-early-sleep',
            16,
            job='exhibition',
            fault='early-sleep',
            fault_worker=15,
        )
        run_case('16n-recovery', 16)
    elif args.phase == 'observe-smoke':
        run_case('observe-smoke', 1, diagnostics=True)
    elif args.phase == 'observe1':
        run_case('01n-observe', 1, job='exhibition', diagnostics=True)
    elif args.phase == 'observe16':
        for index in range(1, args.observation_runs + 1):
            run_case(
                '16n-observe-%03d' % index,
                16,
                job='exhibition',
                diagnostics=True,
            )
    elif args.phase == 'observe-fault2':
        run_case(
            '02n-observe-send-stall',
            2,
            job='exhibition',
            fault='send-stall',
            fault_worker=1,
            diagnostics=True,
        )
        run_case('02n-observe-recovery', 2, diagnostics=True)
    elif args.phase == 'observe-fault16':
        run_case(
            '16n-observe-send-stall',
            16,
            job='exhibition',
            fault='send-stall',
            fault_worker=13,
            diagnostics=True,
        )
        run_case('16n-observe-recovery', 16, diagnostics=True)
    elif args.phase == 'offline-check':
        run_with_offline_requirement(lambda: None)
    elif args.phase == 'cycle-smoke':
        run_exhibition_cycles(2)
    elif args.phase == 'cycle20':
        run_with_offline_requirement(
            lambda: run_exhibition_cycles(20)
        )
