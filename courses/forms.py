"""
Forms for the courses application.

All forms enforce server-side validation and use Bootstrap 5 widgets
for consistent styling with the design system.
"""
from decimal import Decimal

from django import forms

from .models import Course, FeeCategory


# ---------- Widget base classes for consistent styling ----------
TEXT_INPUT = {'class': 'form-control'}
TEXTAREA_INPUT = {'class': 'form-control', 'rows': 3}
NUMBER_INPUT = {'class': 'form-control'}
CHECKBOX_INPUT = {'class': 'form-check-input'}
SELECT_INPUT = {'class': 'form-select'}


class CourseForm(forms.ModelForm):
    """
    Create / update form for Course.

    Extra validation:
    - Code is auto-uppercased.
    - Name uniqueness handled by DB constraint, but we pre-check for a friendly message.
    - Duration must be >= 1.
    """

    class Meta:
        model = Course
        fields = ('name', 'code', 'duration_months', 'description', 'is_active')
        widgets = {
            'name': forms.TextInput(attrs={
                **TEXT_INPUT,
                'placeholder': 'e.g. Diploma in Information Technology',
                'autofocus': True,
            }),
            'code': forms.TextInput(attrs={
                **TEXT_INPUT,
                'placeholder': 'e.g. DIT',
                'style': 'text-transform: uppercase;',
            }),
            'duration_months': forms.NumberInput(attrs={
                **NUMBER_INPUT,
                'min': 1,
                'max': 120,
                'placeholder': 'e.g. 12',
            }),
            'description': forms.Textarea(attrs={
                **TEXTAREA_INPUT,
                'placeholder': 'Optional notes about this course.',
            }),
            'is_active': forms.CheckboxInput(attrs=CHECKBOX_INPUT),
        }
        help_texts = {
            'code': 'Short uppercase code (letters and digits only, no spaces).',
            'duration_months': 'Total duration in months (e.g. 12 for DIT, 6 for CIT).',
        }

    def clean_code(self):
        code = (self.cleaned_data.get('code') or '').strip().upper()
        if not code:
            raise forms.ValidationError("Course code required hai.")
        if not code.replace('-', '').isalnum():
            raise forms.ValidationError(
                "Code mein sirf letters, digits aur dashes (-) allow hain."
            )
        # Uniqueness check with friendly message
        qs = Course.objects.filter(code=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Yeh course code pehle se use ho raha hai.")
        return code

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if not name:
            raise forms.ValidationError("Course name required hai.")
        qs = Course.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Yeh course name pehle se maujood hai.")
        return name

    def clean_duration_months(self):
        months = self.cleaned_data.get('duration_months')
        if months is None or months < 1:
            raise forms.ValidationError("Duration kam az kam 1 month hona chahiye.")
        if months > 120:
            raise forms.ValidationError("Duration 120 months se zyada nahi ho sakta.")
        return months


class FeeCategoryForm(forms.ModelForm):
    """
    Create / update form for FeeCategory.
    Sirf Category Name aur Status. Amount baad mein staff dalega.
    """

    class Meta:
        model = FeeCategory
        fields = ('name', 'is_active')
        widgets = {
            'name': forms.TextInput(attrs={
                **TEXT_INPUT,
                'placeholder': "e.g. 'Admission Fee', 'Registration Fee', 'Sem 1 Fee'",
                'autofocus': True,
            }),
            'is_active': forms.CheckboxInput(attrs=CHECKBOX_INPUT),
        }
        help_texts = {
            'name': "Fee category ka naam. Amount aap baad mein student ki profile se dalenge.",
        }

    def __init__(self, *args, **kwargs):
        self.course = kwargs.pop('course', None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if not name:
            raise forms.ValidationError("Fee category name required hai.")

        # Uniqueness per course
        course = self.course or getattr(self.instance, 'course', None)
        if course:
            qs = FeeCategory.objects.filter(course=course, name__iexact=name)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    "Is course mein yeh category pehle se maujood hai."
                )
        return name

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.course:
            instance.course = self.course
        if commit:
            instance.save()
        return instance