"""
Forms for the batches application.
"""
from datetime import date, datetime
from decimal import Decimal

from django import forms
from django.db import models

from courses.models import Course
from .models import Batch

MONTH_INPUT = {'class': 'form-control', 'type': 'text'}  # Type text kiya hai taake har browser support kare
TEXT_INPUT = {'class': 'form-control'}
NUMBER_INPUT = {'class': 'form-control'}
SELECT_INPUT = {'class': 'form-select'}
CHECKBOX_INPUT = {'class': 'form-check-input'}


class BatchForm(forms.ModelForm):
    start_month = forms.CharField(
        max_length=7,
        required=True,
        widget=forms.TextInput(attrs={
            **MONTH_INPUT,
            'placeholder': 'YYYY-MM',
            'autofocus': True,
        }),
        help_text="Select the starting month (format YYYY-MM, e.g. 2027-03).",
        error_messages={
            'required': "Start Month dena zaroori hai (Format: YYYY-MM)."
        }
    )

    class Meta:
        model = Batch
        fields = (
    'course',
    'name',
    'start_month',
    'monthly_fee',
    'is_active',
)
        widgets = {
            'course': forms.Select(attrs={**SELECT_INPUT, 'id': 'id_course_for_batch'}),
            'name': forms.TextInput(attrs={**TEXT_INPUT, 'placeholder': 'Optional — auto-generated if blank.'}),
            'monthly_fee': forms.NumberInput(attrs={**NUMBER_INPUT, 'min': 0, 'step': '0.01', 'placeholder': '0.00'}),
            'is_active': forms.CheckboxInput(attrs=CHECKBOX_INPUT),
        }
        help_texts = {
            'name': 'Optional display label. Auto-generated if left blank.',
            'monthly_fee': 'Monthly fee charged to students in this batch (PKR).',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_course_id = getattr(self.instance, 'course_id', None)
        if current_course_id:
            self.fields['course'].queryset = Course.objects.filter(
                models.Q(is_active=True) | models.Q(pk=current_course_id)
            ).order_by('-is_active', 'name')
        else:
            self.fields['course'].queryset = Course.objects.filter(is_active=True).order_by('name')

        if self.instance and self.instance.pk and self.instance.start_month:
            self.initial['start_month'] = self.instance.start_month.strftime('%Y-%m')

    def clean_start_month(self):
        raw = (self.cleaned_data.get('start_month') or '').strip()
        if not raw:
            raise forms.ValidationError("Start Month khali nahi ho sakta. Format: YYYY-MM")
        
        try:
            # Yahan hum "2026-02" ko Date(2026, 2, 1) mein convert kar rahe hain
            parsed = datetime.strptime(raw, '%Y-%m')
            normalized = date(parsed.year, parsed.month, 1)
        except (ValueError, TypeError):
            raise forms.ValidationError("Sahi format mein enter karein (YYYY-MM).")
            
        if normalized.year < 2000 or normalized.year > 2100:
            raise forms.ValidationError("Year 2000 aur 2100 ke darmiyan hona chahiye.")
            
        return normalized

    def clean(self):
        cleaned = super().clean()
        course = cleaned.get('course')
        start_month = cleaned.get('start_month')

        if course and start_month:
            qs = Batch.objects.filter(course=course, start_month=start_month)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Is course ke liye yeh starting month pehle se use ho raha hai.")
        return cleaned

    def clean_monthly_fee(self):
        fee = self.cleaned_data.get('monthly_fee')
        if fee is None or fee < Decimal('0.00'):
            raise forms.ValidationError("Monthly fee valid honi chahiye.")
        return fee