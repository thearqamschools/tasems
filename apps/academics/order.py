"""The order of a class's subjects (R19-6, project lead 27 Nov 2026): set once in Setup → Classes and sections →
Class subjects by dragging, and used on result cards, marks tables, sheets, Excel and reports."""

SUMMER_WORK = "summer-vacation-work"


def subject_order(class_level):
    """{subject id: position} for the class; subjects not in the class's list come after, by name."""
    from .models import CurriculumSubject

    return {
        sid: i
        for i, sid in enumerate(
            CurriculumSubject.objects.filter(class_level=class_level)
            .order_by("sort_order", "subject__name")
            .values_list("subject_id", flat=True)
        )
    }


def sort_key(order):
    """A key for anything with a .subject (a paper): Summer Vacation Work first, then the class's order, then name."""

    def key(item):
        subject = item.subject
        if subject.code == SUMMER_WORK and subject.id not in order:
            return (-1, "")
        return (order.get(subject.id, 999), subject.name.lower())

    return key
