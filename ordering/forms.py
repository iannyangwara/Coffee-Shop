from django import forms

from .models import Sugar
from .services import MAX_QUANTITY, NOTE_LENGTH


class AddToBasketForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, max_value=MAX_QUANTITY, initial=1)
    sugar = forms.ChoiceField(choices=Sugar.choices, required=False, widget=forms.RadioSelect, initial=Sugar.NORMAL)
    note = forms.CharField(
        label="Special request",
        max_length=NOTE_LENGTH,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "e.g. oat milk, extra hot, no foam"}),
    )

    def __init__(self, *args, item, **kwargs):
        super().__init__(*args, **kwargs)
        if not item.asks_sugar:
            del self.fields["sugar"]


class CheckoutForm(forms.Form):
    name = forms.CharField(max_length=80, label="Your name", widget=forms.TextInput(attrs={"autocomplete": "name"}))
    phone = forms.CharField(
        max_length=30,
        label="Phone number",
        help_text="So the café can call you about your order.",
        widget=forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel"}),
    )
    pickup = forms.ChoiceField(
        label="Pickup time",
        error_messages={"invalid_choice": "That pickup time isn't available any more. Please choose another."},
    )

    def __init__(self, *args, asap, slots, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [("asap", "As soon as possible")] if asap else []
        choices += [(s.isoformat(), f"Today at {s:%H:%M}") for s in slots]
        self.fields["pickup"].choices = choices

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        digits = sum(c.isdigit() for c in phone)
        if digits < 7 or any(c not in "0123456789 +-()" for c in phone):
            raise forms.ValidationError("Please enter a phone number we can call.")
        return phone

    def clean_name(self):
        return " ".join(self.cleaned_data["name"].split())
