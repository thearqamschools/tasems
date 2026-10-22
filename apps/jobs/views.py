from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import render

from .models import Job


def _mine(request):
    return Job.objects.filter(requested_by=request.user).select_related("branch")


@login_required
def index(request):
    return render(request, "jobs/index.html", {"jobs": _mine(request)[:50]})


@login_required
def detail(request, job_id):
    job = _mine(request).filter(pk=job_id).first()
    if job is None:
        raise Http404
    return render(request, "jobs/detail.html", {"job": job})


@login_required
def download(request, job_id):
    """Only the person who asked can download the file (it may hold many students' details)."""
    job = _mine(request).filter(pk=job_id, status=Job.Status.DONE).first()
    if job is None or not job.file:
        raise Http404
    name = f"{job.title}{Path(job.file.name).suffix}".replace("/", "-").replace(",", "")
    return FileResponse(job.file.open("rb"), filename=name, content_type="application/pdf")
