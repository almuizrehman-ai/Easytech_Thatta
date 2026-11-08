"""
Forms for the fees application.
"""
from decimal import Decimal

from django import forms

from courses.models import Course, FeeCategory
from . import constants as C
from .models import FeeObligation


# ---------- Widget base classes ----------
TEXT_INPUT = {'class': 'form-control'}
TEXTAREA_INPUT = {'class': 'form-control', 'rows': 3}
NUMBER_INPUT = {'class': 'form-control'}
SELECT_INPUT = {'class': 'form-select'}
DATETIME_LOCAL_INPUT = {'class': 'form-control', 'type': 'datetime-local'}


# ============================================================
# PHASE 5 — Payment Recording
# ============================================================
class PaymentForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={**NUMBER_INPUT, 'step': '0.01', 'min': '0.01', 'placeholder': '0.00', 'autofocus': True}),
        help_text="Payment amount outstanding se zyada nahi ho sakti.",
    )
    payment_method = forms.ChoiceField(
        choices=C.PAYMENT_METHOD_CHOICES, widget=forms.Select(attrs=SELECT_INPUT), initial=C.METHOD_CASH,
    )
    payment_date = forms.DateTimeField(
        required=False, widget=forms.DateTimeInput(attrs=DATETIME_LOCAL_INPUT),
        help_text="Leave blank to use current date & time.",
    )
    notes = forms.CharField(
        required=False, max_length=500,
        widget=forms.Textarea(attrs={**TEXTAREA_INPUT, 'rows': 2, 'placeholder': 'Optional notes…'}),
    )

    def __init__(self, *args, obligation: FeeObligation = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.obligation = obligation
        if obligation:
            self.fields['amount'].widget.attrs['max'] = str(obligation.outstanding_amount)
            self.fields['amount'].help_text = f"Outstanding: Rs. {obligation.outstanding_amount:.2f} — partial payments allowed."
            if not self.is_bound and 'amount' not in self.initial:
                self.initial['amount'] = obligation.outstanding_amount

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount <= C.ZERO:
            raise forms.ValidationError("Amount 0 se zyada honi chahiye.")
        if self.obligation:
            if self.obligation.is_waived:
                raise forms.ValidationError("Yeh obligation waive ho chuki hai.")
            outstanding = self.obligation.outstanding_amount
            if outstanding <= C.ZERO:
                raise forms.ValidationError("Yeh obligation already fully paid hai.")
            if amount > outstanding:
                raise forms.ValidationError(f"Amount outstanding (Rs. {outstanding:.2f}) se zyada hai.")
        return amount


# ============================================================
# PHASE 5 — Waiver & Concession
# ============================================================
class WaiverForm(forms.Form):
    reason = forms.CharField(
        max_length=1000,
        widget=forms.Textarea(attrs={**TEXTAREA_INPUT, 'rows': 3, 'placeholder': 'e.g. Orphan student…', 'autofocus': True}),
        help_text="Audit trail ke liye reason zaroori hai.",
    )
    def __init__(self, *args, obligation: FeeObligation = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.obligation = obligation
    def clean(self):
        cleaned = super().clean()
        if self.obligation and self.obligation.is_waived:
            raise forms.ValidationError("Yeh obligation pehle se waive hai.")
        return cleaned


class ConcessionForm(forms.Form):
    adjustment_type = forms.ChoiceField(
        choices=((C.ADJUSTMENT_CONCESSION, 'Concession'), (C.ADJUSTMENT_DISCOUNT, 'Discount')),
        widget=forms.Select(attrs=SELECT_INPUT), initial=C.ADJUSTMENT_CONCESSION,
    )
    amount = forms.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={**NUMBER_INPUT, 'step': '0.01', 'min': '0.01', 'placeholder': '0.00', 'autofocus': True}),
    )
    reason = forms.CharField(
        max_length=1000,
        widget=forms.Textarea(attrs={**TEXTAREA_INPUT, 'rows': 3, 'placeholder': 'e.g. Sibling discount…'}),
    )
    def __init__(self, *args, obligation: FeeObligation = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.obligation = obligation
        if obligation:
            max_reduction = (obligation.effective_amount - obligation.paid_amount)
            self.fields['amount'].widget.attrs['max'] = str(max_reduction)
            self.fields['amount'].help_text = f"Max reduction allowed: Rs. {max_reduction:.2f}"
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount <= C.ZERO:
            raise forms.ValidationError("Amount 0 se zyada honi chahiye.")
        if self.obligation:
            if self.obligation.is_waived:
                raise forms.ValidationError("Waive-shuda obligation pe concession apply nahi hoti.")
            max_reduction = (self.obligation.effective_amount - self.obligation.paid_amount)
            if amount > max_reduction:
                raise forms.ValidationError(f"Amount max allowed (Rs. {max_reduction:.2f}) se zyada hai.")
        return amount


# ============================================================
# PHASE 8 — Corrections
# ============================================================
class CorrectionRequestForm(forms.Form):
    correction_type = forms.ChoiceField(choices=(), widget=forms.Select(attrs=SELECT_INPUT))
    new_amount = forms.DecimalField(max_digits=10, decimal_places=2, required=False, widget=forms.NumberInput(attrs=NUMBER_INPUT))
    new_payment_method = forms.ChoiceField(choices=(('', '— Select —'),) + C.PAYMENT_METHOD_CHOICES, required=False, widget=forms.Select(attrs=SELECT_INPUT))
    new_payment_date = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs=DATETIME_LOCAL_INPUT))
    reason = forms.CharField(widget=forms.Textarea(attrs=TEXTAREA_INPUT))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={**TEXTAREA_INPUT, 'rows': 2}))

    def __init__(self, *args, payment=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.payment = payment
        from .models import PaymentCorrectionRequest
        self.fields['correction_type'].choices = (('', '— Select Type —'),) + PaymentCorrectionRequest.TYPE_CHOICES


class CorrectionReviewForm(forms.Form):
    decision = forms.ChoiceField(choices=(('approve', 'Approve'), ('reject', 'Reject')), widget=forms.RadioSelect(attrs={'class': 'form-check-input'}))
    review_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={**TEXTAREA_INPUT, 'rows': 3}))

class ManualFeeForm(forms.Form):
    fee_category = forms.ModelChoiceField(
        queryset=FeeCategory.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_fee_category'}),
        label="Select Fee Type",
        empty_label="— Select Fee Type —"
    )
    
    month = forms.DateField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_month'}),
        label="Select Month",
        help_text="Sirf Monthly/Semester fee ke liye zaroori hai."
    )
    
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_amount'}),
        label="Amount (Rs)"
    )
    
    due_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Due Date"
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        label="Description / Notes (Optional)"
    )
    
    is_paid = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Mark as Paid (Cash Received)"
    )

    def __init__(self, *args, student=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student
        
        if student:
            # Sirf student ke course ki categories load karein
            self.fields['fee_category'].queryset = FeeCategory.objects.filter(
                course=student.course, is_active=True
            ).order_by('name')

            # Month dropdown generate karein (Batch Start se End tak)
            month_choices = [('', '— Select Month —')]
            current = student.batch.start_month
            
            # Batch ki duration tak loop chalayein
            duration = student.batch.duration_months
            for _ in range(duration):
                month_choices.append(
                    (current.strftime('%Y-%m-%d'), current.strftime('%b %Y'))
                )
                # Agla mahina
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)
            
            self.fields['month'].widget.choices = month_choices