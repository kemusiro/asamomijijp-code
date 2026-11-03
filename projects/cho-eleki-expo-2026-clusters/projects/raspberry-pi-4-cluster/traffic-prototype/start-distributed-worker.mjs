import {createEvaluationServer, listen} from './distributed-worker.mjs';

function option(name, fallback) {
  const index = process.argv.indexOf(name);
  if (index < 0) return fallback;
  if (!process.argv[index + 1]) throw Error(`${name}の値が必要です`);
  return process.argv[index + 1];
}

const host = option('--host', '127.0.0.1');
const port = Number(option('--port', '8787'));
const workerId = option('--worker-id', process.env.HOSTNAME || 'worker');
if (!Number.isInteger(port) || port < 1 || port > 65535) throw Error('--portは1から65535で指定してください');

const server = createEvaluationServer({workerId});
const address = await listen(server, {host, port});
console.log(`worker=${workerId} listening=${address.address}:${address.port}`);

let stopping = false;
function stop(signal) {
  if (stopping) return;
  stopping = true;
  console.log(`worker=${workerId} signal=${signal} stopping`);
  server.close(error => {
    if (error) {
      console.error(error);
      process.exitCode = 1;
    }
  });
}
process.on('SIGINT', () => stop('SIGINT'));
process.on('SIGTERM', () => stop('SIGTERM'));
