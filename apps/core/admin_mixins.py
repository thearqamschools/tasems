"""Admin helpers so staff only see and pick branches they are allowed to."""


class ScopedAdminMixin:
    """For admin screens of branch-owned data.

    `branch_field` is the path to the branch id: "branch_id" for most models,
    "id" for the Branch model itself.
    """

    branch_field = "branch_id"
    scope_permission_action = "view"

    def _branch_ids(self, request):
        perm = f"{self.model._meta.app_label}.{self.scope_permission_action}_{self.model._meta.model_name}"
        return request.user.accessible_branch_ids(perm)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(**{f"{self.branch_field}__in": self._branch_ids(request)})

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "branch" and not request.user.is_superuser:
            from apps.organisation.models import Branch

            kwargs["queryset"] = Branch.objects.filter(id__in=self._branch_ids(request))
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
