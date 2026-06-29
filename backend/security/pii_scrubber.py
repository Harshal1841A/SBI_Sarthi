import re
from typing import Tuple, List
import structlog

logger = structlog.get_logger("pii_scrubber")

# ────────────────────────────────────────────────────────────────
# PII Scrubber — RBI Data Localisation Compliance Layer
# Strips ALL personally identifiable information before any
# external API call (Gemma, NIM, Bhashini, etc.)
# ────────────────────────────────────────────────────────────────

PII_PATTERNS = {
    "aadhaar": re.compile(r'\b\d{12}\b'),
    "account_number": re.compile(r'\b\d{10,16}\b'),
    "phone": re.compile(r'\b[6-9]\d{9}\b'),
    "amount_rs": re.compile(r'Rs\.?\s?\d+[\d,]*'),
    "amount_inr": re.compile(r'₹\s?\d+[\d,]*'),
    "pan": re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b'),
    # Narrowed to known Indian bank UPI handles only (FIX: was too broad)
    "upi_id": re.compile(
        r'\b[\w.+-]+@(?:upi|okaxis|okhdfcbank|okicici|oksbi|paytm|ybl|apl|ibl|'
        r'barodampay|aubank|kotak|federal|axisbank|sbi|icici|hdfc|pnb|bob)\b',
        re.IGNORECASE
    ),
    # Additional patterns for comprehensive coverage
    "credit_card": re.compile(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12}|(?:2131|1800|35\d{3})\d{11})\b'),
    "ifsc": re.compile(r'\b[A-Z]{4}0[A-Z0-9]{6}\b'),
    "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    "dob": re.compile(r'\b\d{2}[-/]\d{2}[-/]\d{4}\b'),
}

# Replacement tokens that preserve semantic meaning for LLM while protecting PII
REPLACEMENTS = {
    "aadhaar": "[AADHAAR]",
    "account_number": "[ACCOUNT]",
    "phone": "[PHONE]",
    "amount_rs": "[AMOUNT]",
    "amount_inr": "[AMOUNT]",
    "pan": "[PAN]",
    "upi_id": "[UPI]",
    "credit_card": "[CARD]",
    "ifsc": "[IFSC]",
    "email": "[EMAIL]",
    "dob": "[DOB]",
}


def scrub_pii(text: str) -> str:
    """Remove all PII from text before external API calls.
    
    Returns the scrubbed text. Scrubbing is NON-RECOVERABLE — 
    the original text is NOT stored in the scrubbed output.
    The original is retained in the state's `messages` field.
    
    Coverage: 100% of external API calls per RBI data localisation.
    """
    if not text:
        return text
    
    # Ordered scrubbing: more specific patterns before general ones
    # Phone (10 digits starting with 6-9) must come BEFORE account_number (10-16 digits)
    scrub_order = [
        "aadhaar", "phone", "pan", "upi_id", "credit_card", "ifsc",
        "account_number", "amount_rs", "amount_inr", "email", "dob"
    ]
    
    for pii_type in scrub_order:
        pattern = PII_PATTERNS[pii_type]
        if pattern.search(text):
            logger.info("PII scrubbed", pii_type=pii_type)
        text = pattern.sub(REPLACEMENTS[pii_type], text)
    
    return text


def detect_pii(text: str) -> Tuple[bool, List[str]]:
    """Detect whether PII exists in text without scrubbing.
    Returns (has_pii, list_of_pii_types_found).
    """
    found_types = []
    scrub_order = [
        "aadhaar", "phone", "pan", "upi_id", "credit_card", "ifsc",
        "account_number", "amount_rs", "amount_inr", "email", "dob"
    ]
    for pii_type in scrub_order:
        pattern = PII_PATTERNS[pii_type]
        if pattern.search(text):
            found_types.append(pii_type)
            
    if found_types:
        logger.warning("PII detected", types=found_types)
        
    return len(found_types) > 0, found_types


def scrub_pii_strict(text: str) -> Tuple[str, dict]:
    """Strict scrubbing with full audit trail.
    Returns (scrubbed_text, scrub_report) where scrub_report contains
    counts of each PII type detected.
    """
    report = {}
    scrub_order = [
        "aadhaar", "phone", "pan", "upi_id", "credit_card", "ifsc",
        "account_number", "amount_rs", "amount_inr", "email", "dob"
    ]
    for pii_type in scrub_order:
        pattern = PII_PATTERNS[pii_type]
        matches = pattern.findall(text)
        if matches:
            report[pii_type] = len(matches)
            text = pattern.sub(REPLACEMENTS[pii_type], text)
    return text, report
