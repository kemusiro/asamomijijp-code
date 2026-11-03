"""Start the resident watchdog-enabled ray-tracing worker."""

import ray_worker


ray_worker.run_forever()
