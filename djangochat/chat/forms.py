from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User

from .models import Room, Message


class SignupForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.help_text = ""

    class Meta:
        model = User
        fields = ("username", "password1", "password2")
        help_texts = {
            "username": "",
            "password1": "",
            "password2": "",
        }


class CustomAuthenticationForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "Identifiants incorrects.",
        "inactive": "Compte inactif.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")



class RoomCreateForm(forms.ModelForm):
    class Meta:
        model = Room
        fields = ("name", "password")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nom du salon"}),
            "password": forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Mot de passe (optionnel)"}),
        }
        labels = {
            "name": "Nom du salon",
            "password": "Mot de passe (optionnel)",
        }
        error_messages = {
            "name": {
                "unique": "Ce nom de salon est déjà pris.",
            }
        }


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ("content",)
        widgets = {
            "content": forms.TextInput(attrs={"class": "form-control", "placeholder": "Écris un message… 😄"}),
        }
