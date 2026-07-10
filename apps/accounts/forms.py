from django import forms

from apps.accounts.repositories.base import ROLES

_INPUT_CLASSES = (
    "block w-full rounded-md border border-gray-300 px-3 py-2 text-sm "
    "focus:border-indigo-500 focus:ring-indigo-500"
)
_SELECT_CLASSES = _INPUT_CLASSES
_CHECKBOX_CLASSES = "rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"class": _INPUT_CLASSES, "autofocus": True}),
    )
    password = forms.CharField(widget=forms.PasswordInput(attrs={"class": _INPUT_CLASSES}))


class UserCreateForm(forms.Form):
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"class": _INPUT_CLASSES}))
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": _INPUT_CLASSES}),
        help_text="Mínimo 12 caracteres, con mayúscula, minúscula, número y símbolo.",
    )
    role = forms.ChoiceField(choices=[(r, r) for r in ROLES], widget=forms.Select(attrs={"class": _SELECT_CLASSES}))


class UserEditForm(forms.Form):
    role = forms.ChoiceField(choices=[(r, r) for r in ROLES], widget=forms.Select(attrs={"class": _SELECT_CLASSES}))
    is_active = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={"class": _CHECKBOX_CLASSES}))
