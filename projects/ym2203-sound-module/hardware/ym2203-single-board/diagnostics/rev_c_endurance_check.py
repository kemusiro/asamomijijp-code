# SPDX-License-Identifier: MIT
# Copyright (c) 2026 MicroPython Web Lab contributors
"""Three-minute six-voice stream with telemetry deferred until capture stops."""
import rev_c_fm_live as live
import rev_c_six_voice_check as six
from rev_c_fm_ssg_check import hold


# 16,000 x 11.25 ms = 180 s of nominal audio, with six fixed-size records.
SEGMENT_BLOCKS = (2667, 2667, 2666, 2667, 2667, 2666)
MIN_FREE_BYTES = 65536  # diagnostic recovery margin, not an application limit


def memory_snapshot(stream):
    # v1 overran its short DMA deadline after in-flight GC/USB reporting.
    # Keep heap walks strictly outside capture. Automatic GC remains enabled.
    if stream.running:
        raise RuntimeError("Memory sampling requires stopped FM capture")
    started = live.time.ticks_us()
    live.gc.collect()
    free = live.gc.mem_free()
    pause = live.time.ticks_diff(live.time.ticks_us(), started)
    if free < MIN_FREE_BYTES:
        raise RuntimeError("Post-GC free memory below diagnostic recovery margin")
    return free, pause


def sequence(bus, stream, pcm, audio, silence):
    bus.line_allow.value(0)
    bus.dac_allow.value(0)
    stream.stop()
    bus.configure_three()
    elapsed_records = [0] * len(SEGMENT_BLOCKS)
    peak_records = [0] * len(SEGMENT_BLOCKS)
    baseline, pre_scan_us = memory_snapshot(stream)
    print("MEMORY BASELINE / capture stopped / post-GC free=%d scan_us=%d" %
          (baseline, pre_scan_us))
    print("ENDURANCE START / FM C4-E4-G4 + SSG C3-E3-G3 / 180 seconds")
    print("No intentional gaps. No progress logs during playback; all six reports follow after mute.")
    six.prepare(bus, stream, pcm, audio, silence, (0, 1, 2), bass=True)

    started = live.time.ticks_us()
    completed = peak = 0
    for index, blocks in enumerate(SEGMENT_BLOCKS):
        for unused in range(blocks):
            value = live.step(stream, pcm, audio)
            if value < 128:
                raise RuntimeError("FM signal disappeared during endurance run")
            peak = max(peak, value)
        completed += blocks
        elapsed_records[index] = live.time.ticks_diff(live.time.ticks_us(), started) // 1000
        peak_records[index] = peak
        stream.check()

    # Stop under mute before the longer final report. The whole 180 s above used
    # one uninterrupted capture start, unchanged keys, and both output gates high.
    six.gap(bus, stream, audio, silence)
    free, post_scan_us = memory_snapshot(stream)
    print("REPORTS / recorded during playback; printed after capture stopped")
    reported = 0
    for index, blocks in enumerate(SEGMENT_BLOCKS):
        reported += blocks
        print("ENDURANCE %d/6 / elapsed_ms=%d blocks=%d peak=%d" %
              (index + 1, elapsed_records[index], reported, peak_records[index]))
    print("ENDURANCE COMPLETE / blocks=%d nominal_ms=%d peak=%d baseline_free=%d final_free=%d delta=%d post_scan_us=%d" %
          (completed, completed * live.BLOCK_US // 1000, peak, baseline,
           free, free - baseline, post_scan_us))
    print("SOURCES OFF / DAC and line enabled / should be silent / 2 seconds")
    six.prepare(bus, stream, pcm, audio, silence, ())
    if hold(stream, pcm, audio) > 64:
        raise RuntimeError("Sources did not return to silence after endurance run")
    bus.line_allow.value(0)
    stream.stop()


def run():
    live.run(
        bus_factory=six.SixVoiceBus, sequence=sequence,
        title="YM2203 Rev C / six-voice endurance check v1.1",
        description="Three-minute chord; progress logs appear AFTER mute. Sound starts in about 5 seconds.",
        completion="DONE: report continuous L/R chord, no dropouts/distortion, memory reports and final silence."
    )


if __name__ == "__main__":
    run()
