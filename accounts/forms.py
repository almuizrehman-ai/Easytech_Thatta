"""
Forms for the accounts app.
"""
from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm


class PortalLoginForm(AuthenticationForm):
    """
    Custom login form for all portals (Staff, Principal, Student).
    """

    username = forms.CharField(
        max_length=50,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Username',
                'autofocus': True,
                'autocomplete': 'username',
                'id': 'id_username',
            }
        ),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Password',
                'autocomplete': 'current-password',
                'id': 'id_password',
            }
        ),
    )

    error_messages = {
        'invalid_login': (
            "Username ya password ghalat hai. Dobara koshish karein."
        ),
        'inactive': (
            "Yeh account deactivate hai. Principal se rabta karein."
        ),
    }

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')

        if username and password:
            username = username.strip().lower()
            self.user_cache = authenticate(
                self.request,
                username=username,
                password=password,
            )
            if self.user_cache is None:
                raise forms.ValidationError(
                    self.error_messages['invalid_login'],
                    code='invalid_login',
                )
            if not self.user_cache.is_active:
                raise forms.ValidationError(
                    self.error_messages['inactive'],
                    code='inactive',
                )
        return cleaned_data

    def get_user(self):
        return getattr(self, 'user_cache', None)


class ForgotPasswordForm(forms.Form):
    username = forms.CharField(
        max_length=50,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Apna Username likhein',
            }
        ),
    )
    mobile = forms.CharField(
        max_length=20,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Registered Mobile Number',
            }
        ),
    )

    def clean(self):
        cleaned = super().clean()
        username = (cleaned.get('username') or '').strip().lower()
        mobile = (cleaned.get('mobile') or '').strip()

        if username and mobile:
            from accounts.models import CustomUser
            try:
                user = CustomUser.objects.get(username=username)
                user_mobile = ""
                if user.role == 'student' and getattr(user, 'linked_student', None):
                    user_mobile = user.linked_student.student_mobile
                elif user.phone:
                    user_mobile = user.phone

                if user_mobile and user_mobile[-10:] != mobile[-10:]:
                    raise forms.ValidationError(
                        "Username aur Mobile number match nahi kar rahe."
                    )

                self.user_cache = user
            except CustomUser.DoesNotExist:
                raise forms.ValidationError("Yeh username mojood nahi hai.")
        return cleaned


class CustomPasswordResetForm(forms.Form):
    new_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Naya Password',
            }
        )
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Naya Password dobara likhein',
            }
        )
    )

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('new_password')
        p2 = cleaned.get('confirm_password')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Dono passwords match nahi kar rahe.")
        if p1 and len(p1) < 6:
            raise forms.ValidationError(
                "Password kam az kam 6 characters ka hona chahiye."
            )
        return cleaned