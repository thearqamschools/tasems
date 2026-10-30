from django import forms
from django.utils.translation import gettext_lazy as _

from apps.academics.models import ClassLevel

from .models import Event, EventExpense

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class EventForm(forms.ModelForm):
    """The event, and a ticket price for each class that takes part (empty: the class does not take part)."""

    class Meta:
        model = Event
        fields = ["name", "kind", "date", "venue", "guest_price", "notes", "is_open"]
        widgets = {"date": DATE, "notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, prices=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.levels = list(ClassLevel.objects.filter(is_active=True).order_by("sort_order"))
        prices = prices or {}
        for level in self.levels:
            self.fields[f"price_{level.id}"] = forms.DecimalField(
                label=str(level), required=False, min_value=0, max_digits=12, decimal_places=2,
                initial=prices.get(level.id),
            )  # fmt: skip

    def price_fields(self):
        return [self[f"price_{level.id}"] for level in self.levels]

    def prices(self):
        return {
            level: self.cleaned_data[f"price_{level.id}"]
            for level in self.levels
            if self.cleaned_data.get(f"price_{level.id}") is not None
        }

    def clean(self):
        data = super().clean()
        if not any(data.get(f"price_{level.id}") is not None for level in self.levels):
            raise forms.ValidationError(_("Give a ticket price for at least one class."))
        return data


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = EventExpense
        fields = ["head", "description", "amount", "paid_to", "date"]
        widgets = {"date": DATE}
