"""
Forms for staff management.

Staff accounts are CustomUser records with role='staff' and is_staff=False.
Principal creates/edits/deactivates them here.

Design:
    - role is always 'staff' (never principal) — enforced in save()
    - is_staff (Django admin) is always False — never exposed
    - Passwords validated with Django's validators
    - Username unique
"""
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from accounts.models import CustomUser


TEXT_INPUT = {'class': 'form-control'}
CHECKBOX_INPUT = {'class': 'form-check-input'}


class StaffCreateForm(forms.ModelForm):
    """
    Create a new staff account.
    """

    password = forms.CharField(
        required=True,
        min_length=8,
        widget=forms.PasswordInput(attrs={
            **TEXT_INPUT,
            'autocomplete': 'new-password',
            'placeholder': 'Kam az kam 8 characters',
        }),
        help_text="Kam az kam 8 characters. Aap yeh password staff ko denge.",
    )
    password_confirm = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            **TEXT_INPUT,
            'autocomplete': 'new-password',
            'placeholder': 'Password dobara likhein',
        }),
        label='Confirm Password',
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'full_name', 'phone', 'is_active')
        widgets = {
            'username': forms.TextInput(attrs={
                **TEXT_INPUT,
                'placeholder': 'e.g. staff01',
                'autofocus': True,
            }),
            'full_name': forms.TextInput(attrs={
                **TEXT_INPUT,
                'placeholder': 'Full name',
            }),
            'phone': forms.TextInput(attrs={
                **TEXT_INPUT,
                'placeholder': '03001234567',
            }),
            'is_active': forms.CheckboxInput(attrs=CHECKBOX_INPUT),
        }
        help_texts = {
            'username': "Login username (unique). Letters, digits, aur underscores allowed.",
            'is_active': "Inactive staff login nahi kar sakta.",
        }

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if not username:
            raise forms.ValidationError("Username required hai.")
        if not username.replace('_', '').isalnum():
            raise forms.ValidationError(
                "Username mein sirf letters, digits aur underscores allow hain."
            )
        if CustomUser.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Yeh username pehle se use ho raha hai.")
        return username

    def clean(self):
        cleaned = super().clean()
        pwd = cleaned.get('password')
        confirm = cleaned.get('password_confirm')

        if pwd and confirm and pwd != confirm:
            raise forms.ValidationError("Passwords match nahi kar rahe.")

        if pwd:
            # Run Django's password validators on a temp user
            temp_user = CustomUser(
                username=cleaned.get('username') or '',
                full_name=cleaned.get('full_name') or '',
            )
            try:
                validate_password(pwd, user=temp_user)
            except ValidationError as e:
                raise forms.ValidationError({'password': e.messages})

        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'staff'          # Force staff
        user.is_staff = False        # Never Django admin
        user.is_superuser = False
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class StaffEditForm(forms.ModelForm):
    """
    Edit existing staff (no password field — use StaffPasswordResetForm).
    """

    class Meta:
        model = CustomUser
        fields = ('full_name', 'phone', 'is_active')
        widgets = {
            'full_name': forms.TextInput(attrs={
                **TEXT_INPUT,
                'autofocus': True,
            }),
            'phone': forms.TextInput(attrs=TEXT_INPUT),
            'is_active': forms.CheckboxInput(attrs=CHECKBOX_INPUT),
        }
        help_texts = {
            'is_active': "Inactive staff login nahi kar sakta. Records preserved.",
        }

    def clean(self):
        cleaned = super().clean()
        # Defensive: ensure we're not editing a Principal
        if self.instance.pk and self.instance.role != 'staff':
            raise forms.ValidationError(
                "Yeh form sirf staff accounts ke liye hai. Principals yahan edit nahi hote."
            )
        return cleaned


class StaffPasswordResetForm(forms.Form):
    """
    Principal resets staff password (no old password needed).
    """

    new_password = forms.CharField(
        required=True,
        min_length=8,
        widget=forms.PasswordInput(attrs={
            **TEXT_INPUT,
            'autocomplete': 'new-password',
            'placeholder': 'Naya password',
            'autofocus': True,
        }),
        help_text="Kam az kam 8 characters.",
    )
    new_password_confirm = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            **TEXT_INPUT,
            'autocomplete': 'new-password',
            'placeholder': 'Naya password dobara',
        }),
        label='Confirm New Password',
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean(self):
        cleaned = super().clean()
        pwd = cleaned.get('new_password')
        confirm = cleaned.get('new_password_confirm')

        if pwd and confirm and pwd != confirm:
            raise forms.ValidationError("Passwords match nahi kar rahe.")

        if pwd and self.user:
            try:
                validate_password(pwd, user=self.user)
            except ValidationError as e:
                raise forms.ValidationError({'new_password': e.messages})

        return cleaned

    def save(self):
        self.user.set_password(self.cleaned_data['new_password'])
        self.user.save(update_fields=['password'])
        return self.user