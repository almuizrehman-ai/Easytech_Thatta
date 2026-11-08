"""
Forms for the reports application.

CollectionReportForm — filter bar for the reports page.
"""
from datetime import date, timedelta

from django import forms
from django.utils import timezone

from accounts.models import CustomUser
from batches.models import Batch
from courses.models import Course
from fees import constants as FC


SELECT_INPUT = {'class': 'form-select'}
DATE_INPUT = {'class': 'form-control', 'type': 'date'}
TEXT_INPUT = {'class': 'form-control'}


# Preset choices for date_range
DATE_RANGE_CHOICES = (
    ('today', 'Today'),
    ('yesterday', 'Yesterday'),
    ('last_7', 'Last 7 Days'),
    ('last_30', 'Last 30 Days'),
    ('this_month', 'This Month'),
    ('last_month', 'Last Month'),
    ('custom', 'Custom Range'),
)


class CollectionReportForm(forms.Form):
    """
    Filter form for Collection Reports.

    Resolution rules:
        - 'custom' -> start_date + end_date required
        - presets  -> computed from today
    """

    date_range = forms.ChoiceField(
        choices=DATE_RANGE_CHOICES,
        initial='this_month',
        widget=forms.Select(attrs=SELECT_INPUT),
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs=DATE_INPUT),
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs=DATE_INPUT),
    )

    course = forms.ModelChoiceField(
        queryset=Course.objects.all(),
        required=False,
        empty_label='All Courses',
        widget=forms.Select(attrs=SELECT_INPUT),
    )
    batch = forms.ModelChoiceField(
        queryset=Batch.objects.select_related('course').all(),
        required=False,
        empty_label='All Batches',
        widget=forms.Select(attrs=SELECT_INPUT),
    )
    staff = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(role='staff', is_active=True),
        required=False,
        empty_label='All Staff',
        widget=forms.Select(attrs=SELECT_INPUT),
    )
    payment_method = forms.ChoiceField(
        choices=(('', 'All Methods'),) + FC.PAYMENT_METHOD_CHOICES,
        required=False,
        widget=forms.Select(attrs=SELECT_INPUT),
    )
    search = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            **TEXT_INPUT,
            'placeholder': 'Student name, ID, or txn…',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Restrict batch queryset to active courses + active batches
        self.fields['batch'].queryset = Batch.objects.select_related('course').order_by('course', 'start_month')

        # Restrict course queryset to keep dropdown manageable
        self.fields['course'].queryset = Course.objects.order_by('name')

        # Restrict staff to portal staff (exclude Principal)
        self.fields['staff'].queryset = CustomUser.objects.filter(
            role='staff', is_active=True,
        ).order_by('username')

    def clean(self):
        cleaned = super().clean()
        date_range = cleaned.get('date_range')
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')

        if date_range == 'custom':
            if not start or not end:
                raise forms.ValidationError(
                    "Custom range ke liye start aur end date dono required hain."
                )
            if start > end:
                raise forms.ValidationError(
                    "Start date end date se pehle honi chahiye."
                )

        return cleaned

    def resolved_range(self):
        """
        Return (start_date, end_date) tuple of Python dates.

        Handles all presets. Falls back to current month if form invalid.
        """
        if not self.is_valid():
            today = timezone.localdate()
            return (today.replace(day=1), today)

        data = self.cleaned_data
        preset = data.get('date_range') or 'this_month'
        today = timezone.localdate()

        if preset == 'today':
            return (today, today)
        if preset == 'yesterday':
            y = today - timedelta(days=1)
            return (y, y)
        if preset == 'last_7':
            return (today - timedelta(days=6), today)
        if preset == 'last_30':
            return (today - timedelta(days=29), today)
        if preset == 'this_month':
            return (today.replace(day=1), today)
        if preset == 'last_month':
            first_this = today.replace(day=1)
            last_month_end = first_this - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            return (last_month_start, last_month_end)
        if preset == 'custom':
            return (data.get('start_date'), data.get('end_date'))

        # Fallback
        return (today.replace(day=1), today)

    def range_label(self):
        """Human label for current range (for report header)."""
        start, end = self.resolved_range()
        if not start or not end:
            return '—'
        if start == end:
            return start.strftime('%d %b %Y')
        return f"{start.strftime('%d %b %Y')} – {end.strftime('%d %b %Y')}"