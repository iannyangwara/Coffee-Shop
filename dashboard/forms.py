from django import forms
from django.forms import modelformset_factory

from cafes.models import Cafe, Closure, MenuCategory, MenuItem, OpeningHours


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
            "brand_colour",
            "is_published",
        ]
        widgets = {
            "about": forms.Textarea(attrs={"rows": 5}),
            "brand_colour": forms.TextInput(attrs={"type": "color"}),
        }
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
            "photo",
            "is_available",
            "is_featured",
            "is_vegetarian",
            "position",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, cafe, **kwargs):
        super().__init__(*args, **kwargs)
        # Only this café's sections can be chosen; anything else fails validation.
        self.fields["category"].queryset = MenuCategory.objects.filter(cafe=cafe)
        self.fields["category"].empty_label = None
        self.fields["price"].label = f"Price ({cafe.currency})"


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
