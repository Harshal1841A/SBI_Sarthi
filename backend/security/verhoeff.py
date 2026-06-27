import re
from typing import Union

# ────────────────────────────────────────────────────────────────
# Verhoeff Algorithm — Aadhaar Checksum Validation (UIDAI Standard)
# The Aadhaar number is a 12-digit number with a Verhoeff check digit.
# This is NOT optional — it is mandatory for all digital KYC flows.
# ────────────────────────────────────────────────────────────────

VERHOEFF_TABLE_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
]

VERHOEFF_TABLE_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]
]


def verhoeff_check(number: str) -> bool:
    """Validate a number using the Verhoeff checksum algorithm.
    
    Args:
        number: String of digits to validate.
        
    Returns:
        True if the number passes the Verhoeff check.
    """
    c = 0
    for i, digit in enumerate(reversed(number)):
        c = VERHOEFF_TABLE_D[c][VERHOEFF_TABLE_P[i % 8][int(digit)]]
    return c == 0


class AadhaarValidationError(ValueError):
    """Raised when Aadhaar validation fails."""
    pass


class AadhaarField(str):
    """Pydantic-compatible Aadhaar validator.
    
    Validates:
    1. 12 digits
    2. Does NOT start with 0 or 1 (UIDAI rule)
    3. Verhoeff checksum passes
    """
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v: Union[str, int]) -> "AadhaarField":
        if isinstance(v, int):
            v = str(v)
        if not isinstance(v, str):
            raise AadhaarValidationError("Aadhaar must be a string or integer")
        
        # Remove any whitespace
        v = v.replace(" ", "").replace("-", "")
        
        # UIDAI format: 12 digits, first digit NOT 0 or 1
        if not re.match(r'^[2-9]\d{11}$', v):
            raise AadhaarValidationError(
                "Invalid Aadhaar format: must be 12 digits, not starting with 0 or 1"
            )
        
        # Verhoeff checksum
        if not verhoeff_check(v):
            raise AadhaarValidationError(
                "Invalid Aadhaar checksum: Verhoeff algorithm failed"
            )
        
        return cls(v)
    
    @property
    def masked(self) -> str:
        """Return masked form: XXXX XXXX XXXX last4"""
        return f"XXXX XXXX {self[-4:]}"
    
    @property
    def last4(self) -> str:
        """Return last 4 digits for display."""
        return self[-4:]


class PANField(str):
    """Pydantic-compatible PAN validator.
    
    Validates:
    1. Format: AAAAA9999A (5 letters, 4 digits, 1 letter)
    2. 4th character indicates type (P=Individual, C=Company, etc.)
    """
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v: Union[str, None]) -> "PANField":
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("PAN must be a string")
        
        v = v.upper().replace(" ", "")
        
        if not re.match(r'^[A-Z]{5}\d{4}[A-Z]$', v):
            raise ValueError("Invalid PAN format: must be AAAAA9999A")
        
        # Validate 4th character (type)
        valid_types = {'P', 'C', 'H', 'A', 'B', 'G', 'J', 'L', 'F', 'T'}
        if v[3] not in valid_types:
            raise ValueError(f"Invalid PAN 4th character: {v[3]} not in valid types")
        
        return cls(v)


def validate_aadhaar(number: str) -> dict:
    """Full Aadhaar validation with detailed result.
    Returns dict with validation status and details.
    """
    result = {
        "valid": False,
        "format_ok": False,
        "checksum_ok": False,
        "masked": None,
        "last4": None,
        "error": None
    }
    
    try:
        cleaned = str(number).replace(" ", "").replace("-", "")
        
        # Format check
        if not re.match(r'^[2-9]\d{11}$', cleaned):
            result["error"] = "Invalid format: must be 12 digits, not starting with 0/1"
            return result
        result["format_ok"] = True
        
        # Checksum check
        if not verhoeff_check(cleaned):
            result["error"] = "Invalid checksum: Verhoeff algorithm failed"
            return result
        result["checksum_ok"] = True
        result["valid"] = True
        result["masked"] = f"XXXX XXXX {cleaned[-4:]}"
        result["last4"] = cleaned[-4:]
        
    except Exception as e:
        result["error"] = str(e)
    
    return result


def validate_pan(number: str) -> dict:
    """Full PAN validation with detailed result.
    Returns dict with validation status and details.
    """
    result = {
        "valid": False,
        "format_ok": False,
        "error": None
    }
    
    try:
        cleaned = str(number).upper().replace(" ", "")
        
        if not re.match(r'^[A-Z]{5}\d{4}[A-Z]$', cleaned):
            result["error"] = "Invalid PAN format: must be AAAAA9999A"
            return result
        
        valid_types = {'P', 'C', 'H', 'A', 'B', 'G', 'J', 'L', 'F', 'T'}
        if cleaned[3] not in valid_types:
            result["error"] = f"Invalid PAN 4th character: {cleaned[3]}"
            return result
        
        result["format_ok"] = True
        result["valid"] = True
        
    except Exception as e:
        result["error"] = str(e)
    
    return result
