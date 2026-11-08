"""
Centralized constants for the fees application.

Never hardcode status strings elsewhere — import from here.
"""
from decimal import Decimal


# ============================================================
# OBLIGATION STATUS
# ============================================================
STATUS_PENDING = 'pending'
STATUS_PARTIAL = 'partial'
STATUS_PAID = 'paid'
STATUS_OVERDUE = 'overdue'
STATUS_WAIVED = 'waived'

STATUS_CHOICES = (
    (STATUS_PENDING, 'Pending'),
    (STATUS_PARTIAL, 'Partial'),
    (STATUS_PAID, 'Paid'),
    (STATUS_OVERDUE, 'Overdue'),
    (STATUS_WAIVED, 'Waived'),
)

# Statuses representing outstanding balance (used in queries)
OPEN_STATUSES = (STATUS_PENDING, STATUS_PARTIAL, STATUS_OVERDUE)


# ============================================================
# OBLIGATION TYPES
# ============================================================
TYPE_ADMISSION = 'admission'
TYPE_REGISTRATION = 'registration'
TYPE_MONTHLY = 'monthly'
TYPE_EXAM = 'exam'
TYPE_OTHER = 'other'

TYPE_CHOICES = (
    (TYPE_ADMISSION, 'Admission Fee'),
    (TYPE_REGISTRATION, 'Registration Fee'),
    (TYPE_MONTHLY, 'Monthly Fee'),
    (TYPE_EXAM, 'Exam Fee'),
    (TYPE_OTHER, 'Other'),
)


# ============================================================
# ADJUSTMENT TYPES (waivers, concessions)
# ============================================================
ADJUSTMENT_WAIVER = 'waiver'          # full waiver — obligation becomes waived
ADJUSTMENT_CONCESSION = 'concession'  # partial reduction — amount reduced
ADJUSTMENT_DISCOUNT = 'discount'      # small discount

ADJUSTMENT_TYPE_CHOICES = (
    (ADJUSTMENT_WAIVER, 'Full Waiver'),
    (ADJUSTMENT_CONCESSION, 'Concession'),
    (ADJUSTMENT_DISCOUNT, 'Discount'),
)


# ============================================================
# PAYMENT METHODS
# ============================================================
METHOD_CASH = 'cash'
METHOD_BANK = 'bank'
METHOD_JAZZCASH = 'jazzcash'
METHOD_EASYPAISA = 'easypaisa'
METHOD_OTHER = 'other'

PAYMENT_METHOD_CHOICES = (
    (METHOD_CASH, 'Cash'),
    (METHOD_BANK, 'Bank Transfer'),
    (METHOD_JAZZCASH, 'JazzCash'),
    (METHOD_EASYPAISA, 'EasyPaisa'),
    (METHOD_OTHER, 'Other'),
)


# ============================================================
# DUE DATE CONFIG
# ============================================================
# Monthly fee is due on this day of its month.
DUE_DAY_OF_MONTH = 10

# After this many days past due, we consider obligations "overdue"
# (already handled implicitly since due_date < today, but kept as a
#  knob for future grace-period features).
OVERDUE_GRACE_DAYS = 0


# ============================================================
# FINANCIAL
# ============================================================
ZERO = Decimal('0.00')
CENT = Decimal('0.01')


# ============================================================
# TRANSACTION ID PREFIX
# ============================================================
PAYMENT_TXN_PREFIX = 'TXN'
PAYMENT_TXN_PAD = 6  # TXN-000001