from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.academics.models import ClassLevel

from .models import Item, StockMove

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ["name", "category", "class_level", "barcode", "sale_price", "reorder_level", "is_active"]
        labels = {
            "name": _("Item name"),
            "category": _("Category"),
            "class_level": _("For class"),
            "barcode": _("Barcode"),
            "sale_price": _("Sale price (Rs)"),
            "reorder_level": _("Reorder level"),
            "is_active": _("In use"),
        }
        help_texts = {"class_level": _("Leave empty for items not tied to one class.")}
        widgets = {"barcode": forms.TextInput(attrs={"dir": "ltr", "autocomplete": "off"})}

    def __init__(self, *args, branch, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.branch = branch
        self.fields["class_level"].queryset = ClassLevel.objects.filter(is_active=True)

    def clean_barcode(self):
        code = self.cleaned_data["barcode"].strip()
        if (
            code
            and Item.objects.filter(branch=self.instance.branch, barcode=code).exclude(pk=self.instance.pk).exists()
        ):
            raise forms.ValidationError(_("Another item already has this barcode."))
        return code


class StockForm(forms.Form):
    KINDS = [
        (StockMove.Kind.RECEIVED, _("Stock received")),
        (StockMove.Kind.ISSUE, _("Issued free (e.g. to a teacher)")),
        (StockMove.Kind.CORRECTION, _("Stock count correction")),
    ]
    item = forms.ModelChoiceField(label=_("Item"), queryset=Item.objects.none())
    kind = forms.ChoiceField(label=_("What happened"), choices=KINDS, widget=forms.RadioSelect)
    quantity = forms.IntegerField(
        label=_("Quantity"),
        help_text=_("For a correction: + for extra found, − for missing."),
        widget=forms.NumberInput(attrs={"dir": "ltr"}),
    )
    unit_cost = forms.DecimalField(
        label=_("Purchase price per item (Rs)"), required=False, min_value=0, max_digits=12, decimal_places=2
    )
    date = forms.DateField(label=_("Date"), widget=DATE)
    note = forms.CharField(label=_("Note"), max_length=200, required=False, help_text=_("e.g. supplier, bill number"))

    def __init__(self, *args, branch, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = Item.objects.filter(branch=branch, is_active=True).select_related("class_level")

    def clean_date(self):
        value = self.cleaned_data["date"]
        if value > timezone.localdate():
            raise forms.ValidationError(_("The date is in the future."))
        return value

    def clean(self):
        data = super().clean()
        if data.get("quantity") == 0:
            self.add_error("quantity", _("Quantity cannot be zero."))
        if data.get("kind") != StockMove.Kind.CORRECTION and data.get("quantity", 0) < 0:
            self.add_error("quantity", _("Enter the quantity without a minus sign."))
        return data
