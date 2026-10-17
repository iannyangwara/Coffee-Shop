from django import forms
from django.contrib.auth.password_validation import validate_password

from .models import Customer, Enquiry


def _clean_phone(value):
    phone = value.strip()
    if phone:
        digits = sum(c.isdigit() for c in phone)
        if digits < 7 or any(c not in "0123456789 +-()" for c in phone):
            raise forms.ValidationError("Please enter a phone number we can call.")
    return phone


class EnquiryForm(forms.ModelForm):
    # Hidden from people; bots that fill in every box give themselves away.
    website = forms.CharField(
        required=False,
        label="Leave this empty",
        widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}),
    )

    class Meta:
        model = Enquiry
        fields = ["kind", "name", "email", "phone", "order_code", "message"]
        labels = {
            "kind": "What's it about?",
            "name": "Your name",
            "email": "Email",
            "phone": "Phone",
            "order_code": "Order code (optional)",
            "message": "Your message",
        }
        help_texts = {"order_code": "The 4-letter code from your order, if this is about one."}
        widgets = {
            "kind": forms.RadioSelect,
            "name": forms.TextInput(attrs={"autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel"}),
            "order_code": forms.TextInput(attrs={"autocapitalize": "characters", "maxlength": 6}),
            "message": forms.Textarea(attrs={"rows": 5}),
        }

    def clean_name(self):
        return " ".join(self.cleaned_data["name"].split())

    def clean_phone(self):
        return _clean_phone(self.cleaned_data["phone"])

    def clean_order_code(self):
        return self.cleaned_data["order_code"].strip().upper()

    def clean(self):
        data = super().clean()
        if not data.get("email") and not data.get("phone"):
            raise forms.ValidationError("Please leave an email or phone number so the café can get back to you.")
        return data


class SignUpForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="At least 10 characters.",
    )

    class Meta:
        model = Customer
        fields = ["name", "email", "phone", "wants_news"]
        labels = {"name": "Your name", "phone": "Phone (optional)", "wants_news": "Tell me about news and offers"}
        help_texts = {"wants_news": ""}
        widgets = {
            "name": forms.TextInput(attrs={"autocomplete": "name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
            "phone": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel"}),
        }

    def __init__(self, *args, cafe, **kwargs):
        super().__init__(*args, **kwargs)
        self.cafe = cafe

    def clean_name(self):
        return " ".join(self.cleaned_data["name"].split())

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Customer.objects.filter(cafe=self.cafe, email__iexact=email).exists():
            raise forms.ValidationError("There's already an account with this email. Try signing in instead.")
        return email

    def clean_phone(self):
        return _clean_phone(self.cleaned_data["phone"])

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password

    def save(self, commit=True):
        customer = super().save(commit=False)
        customer.cafe = self.cafe
        customer.set_password(self.cleaned_data["password"])
        if commit:
            customer.save()
        return customer


class SignInForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))


class AccountForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "phone", "wants_news"]
        labels = {"name": "Your name", "phone": "Phone", "wants_news": "Tell me about news and offers"}
        help_texts = {"wants_news": ""}

    def clean_name(self):
        return " ".join(self.cleaned_data["name"].split())

    def clean_phone(self):
        return _clean_phone(self.cleaned_data["phone"])
