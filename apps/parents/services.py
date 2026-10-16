import datetime as dt
import secrets

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import AuditEvent
from apps.people.models import Guardian, Student, StudentGuardian

from .models import AccessCode, ParentAccount

CODE_DAYS = 14
ISSUE_PERM = "people.change_guardian"


def account_for(user):
    if user is None or not user.is_authenticated:
        return None
    return ParentAccount.objects.filter(user=user).first()


def children(phone):
    """Active students linked to a parent's mobile number, in any branch."""
    return (
        Student.objects.filter(guardian_links__guardian__phone=phone, status=Student.Status.ACTIVE)
        .select_related("branch")
        .distinct()
        .order_by("first_name")
    )


def branch_ids_for(user):
    """Branches whose rows a parent's requests may read (their children's branches)."""
    account = account_for(user)
    if account is None:
        return set()
    return set(Guardian.objects.filter(phone=account.phone).values_list("branch_id", flat=True))


def new_code():
    return f"{secrets.randbelow(10**8):08d}"


@transaction.atomic
def issue_code(phone, branch, user):
    """Makes a fresh code for this mobile number; any earlier unused code stops working."""
    AccessCode.objects.filter(phone=phone, used_at__isnull=True).update(expires_at=timezone.now())
    code = new_code()
    AccessCode.objects.create(
        phone=phone,
        code_hash=make_password(code),
        expires_at=timezone.now() + dt.timedelta(days=CODE_DAYS),
        branch=branch,
        created_by=user,
    )
    AuditEvent.objects.create(
        actor=user,
        action=AuditEvent.Action.CREATE,
        model_label="parents.AccessCode",
        object_id=phone,
        object_repr=f"Parent access code for {phone}",
        branch_id=branch.id,
    )
    return code


def primary_phones(students):
    """Distinct primary-contact mobile numbers of these students, with their children's names."""
    out = {}
    for link in StudentGuardian.objects.filter(student__in=students, is_primary_contact=True).select_related(
        "guardian", "student"
    ):
        entry = out.setdefault(link.guardian.phone, {"guardian": link.guardian, "students": []})
        entry["students"].append(link.student)
    return out


def check_code(phone, code):
    now = timezone.now()
    for ac in AccessCode.objects.filter(phone=phone, used_at__isnull=True, expires_at__gt=now)[:3]:
        if check_password(code, ac.code_hash):
            return ac
    return None


@transaction.atomic
def redeem(access_code, password):
    """Creates the parent's account (or resets its password) and uses up the code."""
    phone = access_code.phone
    account = ParentAccount.objects.filter(phone=phone).select_related("user").first()
    if account is None:
        user = User.objects.create_user(username=f"parent-{phone}", password=password)
        account = ParentAccount.objects.create(user=user, phone=phone)
    else:
        account.user.set_password(password)
        account.user.is_active = True
        account.user.save()
    access_code.used_at = timezone.now()
    access_code.save(update_fields=["used_at", "updated_at"])
    return account
