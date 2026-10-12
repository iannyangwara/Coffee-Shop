from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.forms import modelformset_factory

from cafes.models import Cafe, Closure, MenuCategory, MenuItem, OpeningHours, StaffMembership


class CafeSettingsForm(forms.ModelForm):
    class Meta:
        model = Cafe
        fields = [
            "name",
            "tagline",
            "about",
            "phone",
            "email",
            "whatsapp",
            "instagram",
            "address",
            "town",
            "latitude",
            "longitude",
            "logo",
            "cover_photo",
            "stock_cover",
            "brand_colour",
            "clock_in_radius_m",
            "accepts_orders",
            "is_published",
        ]
        widgets = {
            "about": forms.Textarea(attrs={"rows": 5}),
            "brand_colour": forms.TextInput(attrs={"type": "color"}),
            "stock_cover": forms.RadioSelect,
        }
        labels = {"cover_photo": "Your own cover photo", "stock_cover": "Or pick a built-in cover photo"}
        help_texts = {
            "latitude": "Find it by right-clicking the café on Google Maps.",
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = MenuCategory
        fields = ["name", "description", "position"]

    def __init__(self, *args, cafe, **kwargs):
        super().__init__(*args, **kwargs)
        self.cafe = cafe

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        clash = MenuCategory.objects.filter(cafe=self.cafe, name__iexact=name).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("You already have a section with that name.")
        return name

    def save(self, commit=True):
        self.instance.cafe = self.cafe
        return super().save(commit)


class MenuItemForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = [
            "category",
            "name",
            "description",
            "price",
            "cost",
            "photo",
            "stock_image",
            "is_available",
            "is_featured",
            "is_vegetarian",
            "asks_sugar",
            "position",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3}), "stock_image": forms.RadioSelect}
        labels = {"photo": "Your own photo", "stock_image": "Or pick a built-in photo"}

    def __init__(self, *args, cafe, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["stock_image"].choices = [("", "No picture")] + list(self.fields["stock_image"].choices)[1:]
        # Only this café's sections can be chosen; anything else fails validation.
        self.fields["category"].queryset = MenuCategory.objects.filter(cafe=cafe)
        self.fields["category"].empty_label = None
        self.fields["price"].label = f"Price ({cafe.currency})"
        self.fields["cost"].label = f"Cost to make ({cafe.currency})"


class OpeningHoursForm(forms.ModelForm):
    class Meta:
        model = OpeningHours
        fields = ["is_closed", "opens", "closes"]
        widgets = {
            "opens": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "closes": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }
        labels = {"is_closed": "Closed"}

    def clean(self):
        data = super().clean()
        if data.get("is_closed"):
            data["opens"] = data["closes"] = None
            self.instance.opens = self.instance.closes = None
        return data


OpeningHoursFormSet = modelformset_factory(OpeningHours, form=OpeningHoursForm, extra=0, can_delete=False)


class ClosureForm(forms.ModelForm):
    class Meta:
        model = Closure
        fields = ["date", "note"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, cafe, **kwargs):
        super().__init__(*args, **kwargs)
        self.cafe = cafe

    def clean_date(self):
        date = self.cleaned_data["date"]
        if Closure.objects.filter(cafe=self.cafe, date=date).exists():
            raise forms.ValidationError("That day is already marked closed.")
        return date

    def save(self, commit=True):
        self.instance.cafe = self.cafe
        return super().save(commit)


class StaffForm(forms.Form):
    """Create a login for a new worker. Owners hand them the username and password."""

    first_name = forms.CharField(max_length=150, label="Their name")
    username = forms.CharField(max_length=150, help_text="What they'll type to log in, e.g. mary.k")
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False), help_text="At least 10 characters. They can change it later."
    )
    role = forms.ChoiceField(choices=StaffMembership.Role.choices, initial=StaffMembership.Role.STAFF)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        UsernameField = get_user_model()._meta.get_field("username")
        for validator in UsernameField.validators:
            validator(username)
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is taken. Try adding a number or surname.")
        return username

    def clean(self):
        data = super().clean()
        if data.get("password"):
            # Check the password even when the username was rejected, so both problems show at once.
            username = data.get("username") or self.data.get("username", "")
            user = get_user_model()(username=username, first_name=data.get("first_name", ""))
            try:
                validate_password(data["password"], user)
            except forms.ValidationError as error:
                self.add_error("password", error)
        return data
