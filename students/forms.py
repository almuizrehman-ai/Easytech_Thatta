from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from batches.models import Batch
from courses.models import Course

from .models import Student
from .validators import normalize_mobile, validate_photo


TEXT_INPUT = {'class': 'form-control'}
TEXTAREA_INPUT = {'class': 'form-control', 'rows': 2}
NUMBER_INPUT = {'class': 'form-control'}
SELECT_INPUT = {'class': 'form-select'}
CHECKBOX_INPUT = {'class': 'form-check-input'}
EMAIL_INPUT = {'class': 'form-control', 'type': 'email'}
DATE_INPUT = {'class': 'form-control', 'type': 'date'}
FILE_INPUT = {'class': 'form-control', 'accept': 'image/jpeg,image/png,image/webp'}


_STUDENT_WIDGETS = {
    'student_name': forms.TextInput(attrs={
        **TEXT_INPUT,
        'placeholder': "Student's full name",
        'autofocus': True,
    }),
    'father_name': forms.TextInput(attrs={
        **TEXT_INPUT,
        'placeholder': "Father's full name",
    }),
    'gender': forms.Select(attrs=SELECT_INPUT),
    'campus': forms.Select(attrs=SELECT_INPUT),  # <-- CAMPUS WIDGET
    'date_of_birth': forms.DateInput(attrs={**DATE_INPUT}),
    'cnic_or_bform': forms.TextInput(attrs={
        **TEXT_INPUT,
        'placeholder': '12345-1234567-1',
    }),
    'address': forms.Textarea(attrs={
        **TEXTAREA_INPUT,
        'placeholder': 'Optional residential address',
    }),
    'student_mobile': forms.TextInput(attrs={
        **TEXT_INPUT,
        'placeholder': '03001234567',
        'inputmode': 'numeric',
    }),
    'father_mobile': forms.TextInput(attrs={
        **TEXT_INPUT,
        'placeholder': '03001234567',
        'inputmode': 'numeric',
    }),
    'student_email': forms.EmailInput(attrs={
        **EMAIL_INPUT,
        'placeholder': 'optional@example.com',
    }),
    'photo': forms.FileInput(attrs=FILE_INPUT),
    'admission_fee_paid': forms.CheckboxInput(attrs=CHECKBOX_INPUT),
}


class AdmissionForm(forms.ModelForm):
    """New student admission form."""

    class Meta:
        model = Student
        fields = (
            'student_name', 'father_name',
            'gender', 'campus', 'date_of_birth', 'cnic_or_bform', 'address',
            'student_mobile', 'father_mobile', 'student_email',
            'photo',
            'course', 'batch',
            'admission_date',
            'admission_fee_paid',
            'previous_degree', 'previous_passing_year', 'previous_obtained_marks',
            'previous_total_marks', 'previous_grade', 'previous_board',
        )
        widgets = {
            **_STUDENT_WIDGETS,
            'course': forms.Select(attrs={**SELECT_INPUT, 'id': 'id_course_for_student'}),
            'batch': forms.Select(attrs={**SELECT_INPUT, 'id': 'id_batch_for_student'}),
            'admission_date': forms.DateInput(attrs={**DATE_INPUT}),
            'previous_degree': forms.TextInput(attrs=TEXT_INPUT),
            'previous_passing_year': forms.TextInput(attrs=TEXT_INPUT),
            'previous_obtained_marks': forms.TextInput(attrs=TEXT_INPUT),
            'previous_total_marks': forms.TextInput(attrs=TEXT_INPUT),
            'previous_grade': forms.TextInput(attrs=TEXT_INPUT),
            'previous_board': forms.TextInput(attrs=TEXT_INPUT),
        }
        help_texts = {
            'student_mobile': "Pakistani mobile (e.g. 03001234567).",
            'father_mobile': "Father's mobile number.",
            'admission_date': "Defaults to today. Adjust if backdated admission.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['course'].queryset = Course.objects.filter(is_active=True).order_by('name')
        self.fields['batch'].queryset = (
            Batch.objects.select_related('course').filter(is_active=True).order_by('course', 'start_month')
        )
        self.fields['course'].empty_label = "— Select Course —"
        self.fields['batch'].empty_label = "— Select Batch —"

    def clean_student_mobile(self):
        raw = self.cleaned_data.get('student_mobile') or ''
        try:
            return normalize_mobile(raw)
        except ValidationError:
            raise forms.ValidationError("Student mobile sahi format mein dein (e.g. 03001234567).")

    def clean_father_mobile(self):
        raw = self.cleaned_data.get('father_mobile') or ''
        try:
            return normalize_mobile(raw)
        except ValidationError:
            raise forms.ValidationError("Father mobile sahi format mein dein (e.g. 03001234567).")

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo:
            validate_photo(photo)
        return photo

    def clean(self):
        cleaned = super().clean()
        course = cleaned.get('course')
        batch = cleaned.get('batch')

        if course and batch and batch.course_id != course.pk:
            raise forms.ValidationError({
                'batch': "Selected batch is course ke andar nahi hai. Please course ke mutabiq batch choose karein."
            })

        if batch and not batch.is_active:
            raise forms.ValidationError({
                'batch': "Yeh batch deactivate hai. Naye admission ke liye active batch choose karein."
            })

        name = cleaned.get('student_name')
        father = cleaned.get('father_name')
        mobile = cleaned.get('student_mobile')
        if name and father and mobile:
            duplicate = Student.objects.filter(
                student_name__iexact=name.strip(),
                father_name__iexact=father.strip(),
                student_mobile=mobile,
                is_active=True,
            ).exists()
            if duplicate:
                raise forms.ValidationError(
                    "Yeh student pehle se maujood hai (same name + father + mobile). "
                    "Existing record check karein."
                )

        return cleaned

    def save(self, commit=True):
        student = super().save(commit=False)
        snapshots = Student.derive_fee_snapshots(course=student.course, batch=student.batch)
        student.admission_fee_amount = snapshots['admission_fee_amount']
        student.registration_fee_amount = snapshots['registration_fee_amount']
        student.monthly_fee_at_admission = snapshots['monthly_fee_at_admission']

        if commit:
            student.save()
            self.save_m2m()
        return student


class StudentEditForm(forms.ModelForm):
    """Edit existing student."""

    class Meta:
        model = Student
        fields = (
            'student_name', 'father_name',
            'gender', 'campus', 'date_of_birth', 'cnic_or_bform', 'address',
            'student_mobile', 'father_mobile', 'student_email',
            'photo',
            'course', 'batch',
            'admission_date',
            'enrollment_status',
            'is_active',
            'admission_fee_paid',
            'previous_degree', 'previous_passing_year', 'previous_obtained_marks',
            'previous_total_marks', 'previous_grade', 'previous_board',
        )
        widgets = {
            **_STUDENT_WIDGETS,
            'course': forms.Select(attrs={**SELECT_INPUT, 'id': 'id_course_for_student'}),
            'batch': forms.Select(attrs={**SELECT_INPUT, 'id': 'id_batch_for_student'}),
            'admission_date': forms.DateInput(attrs={**DATE_INPUT}),
            'enrollment_status': forms.Select(attrs=SELECT_INPUT),
            'is_active': forms.CheckboxInput(attrs=CHECKBOX_INPUT),
            'previous_degree': forms.TextInput(attrs=TEXT_INPUT),
            'previous_passing_year': forms.TextInput(attrs=TEXT_INPUT),
            'previous_obtained_marks': forms.TextInput(attrs=TEXT_INPUT),
            'previous_total_marks': forms.TextInput(attrs=TEXT_INPUT),
            'previous_grade': forms.TextInput(attrs=TEXT_INPUT),
            'previous_board': forms.TextInput(attrs=TEXT_INPUT),
        }
        help_texts = {
            'is_active': "Inactive students remain in records but cannot be edited or receive new obligations.",
            'enrollment_status': "Academic status: active, graduated, or dropped out.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        current_course_id = self.instance.course_id if self.instance.pk else None
        qs = Course.objects.filter(is_active=True)
        if current_course_id:
            qs = Course.objects.filter(Q(is_active=True) | Q(pk=current_course_id))
        self.fields['course'].queryset = qs.order_by('name')

        current_batch_id = self.instance.batch_id if self.instance.pk else None
        batch_qs = Batch.objects.select_related('course').filter(is_active=True)
        if current_batch_id:
            batch_qs = Batch.objects.select_related('course').filter(
                Q(is_active=True) | Q(pk=current_batch_id)
            )
        self.fields['batch'].queryset = batch_qs.order_by('course', 'start_month')

    def clean_student_mobile(self):
        raw = self.cleaned_data.get('student_mobile') or ''
        try:
            return normalize_mobile(raw)
        except ValidationError:
            raise forms.ValidationError("Student mobile sahi format mein dein (e.g. 03001234567).")

    def clean_father_mobile(self):
        raw = self.cleaned_data.get('father_mobile') or ''
        try:
            return normalize_mobile(raw)
        except ValidationError:
            raise forms.ValidationError("Father mobile sahi format mein dein (e.g. 03001234567).")

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo:
            validate_photo(photo)
        return photo

    def clean(self):
        cleaned = super().clean()
        course = cleaned.get('course')
        batch = cleaned.get('batch')

        if course and batch and batch.course_id != course.pk:
            raise forms.ValidationError({
                'batch': "Selected batch is course ke andar nahi hai. Please course ke mutabiq batch choose karein."
            })

        return cleaned