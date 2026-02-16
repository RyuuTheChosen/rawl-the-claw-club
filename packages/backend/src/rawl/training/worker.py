from __future__ import annotations

import logging

from rawl.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="rawl.training.worker.run_training", bind=True)
def run_training(self, job_id: str):
    """Training is off-platform.

    Users rent their own GPUs and run the open-source training package.
    The platform only handles match execution.
    See: https://github.com/rawl-ai/training (placeholder)
    """
    raise NotImplementedError(
        "On-platform training has been removed. "
        "Use the external training package to train fighters, "
        "then submit checkpoints via POST /api/gateway/submit."
    )
