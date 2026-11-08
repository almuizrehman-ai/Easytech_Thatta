"""
Custom validators for the students application.

Centralized so that mobile number and photo rules stay consistent
across every form that touches student data.
"""
import re

from django.core.exceptions import ValidationError
from PIL import Image


# ---------- Mobile ----------
MOBILE_REGEX = re.compile(r'^(?:\+?92|0)(\d{10})$')


def normalize_mobile(value):
    """
    Normalize a Pakistani mobile number to the local 03XXXXXXXXX format.

    Accepts:
        03001234567      -> 03001234567
        +923001234567    -> 03001234567
        923001234567     -> 03001234567
        +92 300 1234567  -> 03001234567 (spaces stripped first)

    Raises ValidationError for invalid input.
    """
    if not value:
        raise ValidationError("Mobile number required hai.")

    cleaned = re.sub(r'[\s\-()]', '', str(value))
    match = MOBILE_REGEX.match(cleaned)

    if not match:
        raise ValidationError(
            "Sahi mobile number dein (e.g. 03001234567)."
        )

    # match.group(1) contains the 10-digit body after prefix
    return f"0{match.group(1)}"


def validate_mobile(value):
    """
    Validator (raises on invalid). Use in model field validators list.
    Callers storing the value should call normalize_mobile() first.
    """
    normalize_mobile(value)


# ---------- Photo ----------
MAX_PHOTO_SIZE = 2 * 1024 * 1024  # 2 MB
ALLOWED_IMAGE_FORMATS = {'JPEG', 'PNG', 'WEBP'}


def validate_photo(file_obj):
    """
    Validate an uploaded photo:
    - Not larger than 2 MB
    - Must be JPEG/PNG/WEBP
    - Must be openable by Pillow (real image, not renamed .exe)

    Called as a field validator on Student.photo.
    Also called explicitly inside AdmissionForm.clean_photo()
    to give a user-friendly error message.
    """
    if not file_obj:
        return  # optional field

    # Size check (only if file has a size attribute)
    if hasattr(file_obj, 'size') and file_obj.size > MAX_PHOTO_SIZE:
        raise ValidationError(
            "Photo 2 MB se kam honi chahiye."
        )

    # Pillow verification (works on uploads and existing files)
    try:
        # Seek back to start in case the file was partially read
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
        img = Image.open(file_obj)
        img.verify()
    except Exception:
        raise ValidationError(
            "Photo valid image nahi hai. JPEG, PNG ya WEBP use karein."
        )
    finally:
        # Reset file pointer so Django can save it after validation
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)

    # Format check
    try:
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
        img = Image.open(file_obj)
        if img.format not in ALLOWED_IMAGE_FORMATS:
            raise ValidationError(
                "Sirf JPEG, PNG, ya WEBP images allow hain."
            )
    except ValidationError:
        raise
    except Exception:
        raise ValidationError("Photo format detect nahi ho saka.")
    finally:
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)