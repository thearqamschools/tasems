"""Gives users the permissions of the roles they hold (through RoleAssignment).

`user.has_perm("people.view_student")` answers "may this user do this anywhere?".
Which branches it applies to is answered by `user.has_branch_perm(...)` and
`Model.objects.for_user(user)`.
"""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission


class RoleBackend(ModelBackend):
    def get_group_permissions(self, user_obj, obj=None):
        if not user_obj.is_active or user_obj.is_anonymous or obj is not None:
            return set()
        if not hasattr(user_obj, "_tasems_role_perm_cache"):
            role_ids = user_obj.active_assignments().values_list("role_id", flat=True)
            perms = (
                Permission.objects.filter(tasems_roles__id__in=role_ids)
                .values_list("content_type__app_label", "codename")
                .distinct()
            )
            user_obj._tasems_role_perm_cache = {f"{app}.{code}" for app, code in perms}
        return user_obj._tasems_role_perm_cache
