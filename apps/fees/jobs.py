"""Fee printing jobs (M6): vouchers for a whole branch or month, made in parts of CHUNK so the page can show
progress, then joined into one PDF."""

from django.http import QueryDict
from django.template.loader import render_to_string

from apps.jobs.runner import handler

CHUNK = 100


def _join(htmls_and_counts, progress, total):
    from django.conf import settings
    from weasyprint import HTML

    documents, done = [], 0
    for html, count in htmls_and_counts:
        documents.append(HTML(string=html, base_url=str(settings.BASE_DIR)).render())
        done += count
        progress(done, total)
    pages = [page for doc in documents for page in doc.pages]
    return documents[0].copy(pages).write_pdf()


@handler("vouchers")
def vouchers(job, progress):
    from . import views

    class _Request:  # the same filters as the Vouchers page, read from the saved address
        GET = QueryDict(job.params.get("query", ""))

    qs, month, _sections, _status = views._filtered_vouchers(_Request, job.branch)
    voucher_list = list(qs.select_related("student"))
    if not voucher_list:
        raise ValueError("No vouchers match these filters any more.")
    progress(0, len(voucher_list))

    def parts():
        for i in range(0, len(voucher_list), CHUNK):
            part = voucher_list[i : i + CHUNK]
            yield render_to_string("fees/voucher_document.html", views._voucher_context(job.branch, part)), len(part)

    return f"Vouchers-{month:%Y-%m}.pdf", _join(parts(), progress, len(voucher_list))


@handler("family_vouchers")
def family_vouchers(job, progress):
    import datetime as dt

    from . import views
    from .models import FamilyVoucher

    month = dt.date.fromisoformat(job.params["month"])
    items = list(
        views._family_qs(job.branch).filter(month=month, status=FamilyVoucher.Status.OPEN).order_by("father_name")
    )
    if not items:
        raise ValueError("No open family vouchers for this month any more.")
    progress(0, len(items))

    def parts():
        for i in range(0, len(items), CHUNK):
            part = items[i : i + CHUNK]
            yield views.family_pdf_html(job.branch, part), len(part)

    return f"Family-vouchers-{month:%Y-%m}.pdf", _join(parts(), progress, len(items))
