"""Copy to main.py to start the ray-tracing worker after power-on."""

import ray_worker


ray_worker.run_forever()
