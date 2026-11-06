from django import forms
from django.forms import inlineformset_factory
from .models import Contract, License


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


class ContractForm(forms.ModelForm):
    class Meta:
        model = Contract
        fields = ["number", "signed_on", "vendor", "currency", "total_amount", "notes"]
        widgets = {"signed_on": DateInput(), "notes": forms.Textarea(attrs={"rows": 3}),
            "number": forms.TextInput(attrs={"placeholder": "Например, 24/2026-ПО"}),
            "vendor": forms.TextInput(attrs={"placeholder": "Название организации"}),
            "total_amount": forms.NumberInput(attrs={"min": "0", "step": "0.01"})}


class LicenseForm(forms.ModelForm):
    class Meta:
        model = License
        fields = ["contract", "software", "quantity", "cost", "starts_on", "ends_on", "perpetual", "notes"]
        widgets = {"starts_on": DateInput(), "ends_on": DateInput(),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "software": forms.TextInput(attrs={"placeholder": "Например, nanoCAD СПДС"}),
            "cost": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "quantity": forms.NumberInput(attrs={"min": "1"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # A contract's currency defines the recorded historical price.
            self.fields.pop("contract")


ContractLicenseFormSet = inlineformset_factory(
    Contract, License, form=LicenseForm,
    fields=["software", "quantity", "cost", "starts_on", "ends_on", "perpetual"],
    extra=0, can_delete=True, min_num=1, validate_min=True,
    max_num=200, validate_max=True,
)
