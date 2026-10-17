import secrets
import re
from datetime import datetime, timezone

def normalize_indian_mobile(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) != 10:
        raise ValueError("Enter a valid Indian mobile number")
    return digits

def application_number():
    return f"USK-{datetime.now(timezone.utc):%y%m%d}-{secrets.token_hex(3).upper()}"

def object_id_string(value):
    return str(value)
