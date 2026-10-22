"""The background worker (D-074): jobs live in PostgreSQL, so no extra service is needed. `run_jobs` takes the
oldest waiting job with FOR UPDATE SKIP LOCKED, so two workers never take the same job.

A job kind is registered with @handler("kind"); the handler gets the job and a `progress(done, total)`
function, and returns (file name, PDF bytes)."""

import datetime as dt
import logging

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from .models import Job

log = logging.getLogger(__name__)
HANDLERS = {}
KEEP_DAYS = 7  # finished files are removed after a week


def handler(kind):
    def register(func):
        HANDLERS[kind] = func
        return func

    return register


def _load_handlers():
    from apps.fees import jobs  # noqa: F401 - registers the fee printing jobs


def _claim():
    with transaction.atomic():
        job = (
            Job.objects.select_for_update(skip_locked=True)
            .filter(status=Job.Status.QUEUED)
            .order_by("created_at")
            .first()
        )
        if job is None:
            return None
        job.status, job.started_at = Job.Status.RUNNING, timezone.now()
        job.save(update_fields=["status", "started_at", "updated_at"])
        return job


def run_one():
    """Runs the oldest waiting job. Returns it, or None when nothing is waiting."""
    _load_handlers()
    job = _claim()
    if job is None:
        return None

    def progress(done, total):
        Job.objects.filter(pk=job.pk).update(done=done, total=total, updated_at=timezone.now())

    try:
        name, content = HANDLERS[job.kind](job, progress)
        job.refresh_from_db()
        job.file.save(name, ContentFile(content), save=False)
        job.status, job.done = Job.Status.DONE, job.total
    except Exception as exc:  # noqa: BLE001 - any failure is shown to the person, never a silent hang
        log.exception("Job %s failed", job.pk)
        job.refresh_from_db()
        job.status, job.error = Job.Status.FAILED, str(exc)[:300]
    job.finished_at = timezone.now()
    job.save()
    return job


def requeue_stuck(minutes=30):
    """A job left running by a restart goes back to the queue."""
    cutoff = timezone.now() - dt.timedelta(minutes=minutes)
    return Job.objects.filter(status=Job.Status.RUNNING, updated_at__lt=cutoff).update(status=Job.Status.QUEUED)


def clean_old():
    cutoff = timezone.now() - dt.timedelta(days=KEEP_DAYS)
    old = Job.objects.filter(created_at__lt=cutoff)
    for job in old:
        if job.file:
            job.file.delete(save=False)
    return old.delete()[0]
