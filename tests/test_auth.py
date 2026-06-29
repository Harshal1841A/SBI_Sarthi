import pytest
import os
import sys

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from security.verhoeff import verhoeff_check, validate_aadhaar, AadhaarField
from security.pii_scrubber import scrub_pii, detect_pii
from security.consent import create_consent_artifact, store_consent_artifact, verify_consent_chain, CONSENT_PURPOSES


class TestVerhoeff:
    def test_verhoeff_valid(self):
        assert verhoeff_check("234123412000") == True
        assert verhoeff_check("123456789012") == False

    def test_aadhaar_format_validation(self):
        result = validate_aadhaar("234123412000")
        assert result["valid"] == True
        assert result["last4"] == "2000"
        assert result["masked"] == "**** **** 2000"

    def test_aadhaar_invalid_start_digit(self):
        result = validate_aadhaar("012345678901")
        assert result["valid"] == False
        assert "starting with 0/1" in result["error"]

    def test_pydantic_aadhaar_field(self):
        valid = AadhaarField.validate("234123412000")
        assert valid.last4 == "2000"
        with pytest.raises(ValueError):
            AadhaarField.validate("012345678901")


class TestPIIScrubber:
    def test_aadhaar_scrubbing(self):
        text = "My Aadhaar is 234123412000"
        result = scrub_pii(text)
        assert "[AADHAAR]" in result
        assert "234123412000" not in result

    def test_pan_scrubbing(self):
        text = "PAN number ABCDE1234F"
        result = scrub_pii(text)
        assert "[PAN]" in result
        assert "ABCDE1234F" not in result

    def test_phone_scrubbing(self):
        text = "Call me at 9876543210"
        result = scrub_pii(text)
        assert "[PHONE]" in result

    def test_upi_scrubbing(self):
        text = "Send to user@oksbi"
        result = scrub_pii(text)
        assert "[UPI]" in result

    def test_detect_pii(self):
        text = "Aadhaar 234123412000 phone 9876543210"
        has_pii, types = detect_pii(text)
        assert has_pii == True
        assert "aadhaar" in types

    def test_phone_not_eaten_by_account(self):
        text = "Phone 9876543210"
        result = scrub_pii(text)
        assert "[PHONE]" in result, f"Got: {result}"
        assert "9876543210" not in result


class TestConsent:
    def test_create_consent_artifact(self):
        os.environ["SARTHI_HMAC_SECRET"] = "a" * 64
        artifact = create_consent_artifact("usr_123", "P001", "hi", True)
        assert artifact["user_id"] == "usr_123"
        assert artifact["granted"] == True
        assert "hash" in artifact
        assert "hmac_sig" in artifact

    def test_consent_chain_verification(self):
        os.environ["SARTHI_HMAC_SECRET"] = "a" * 64
        art1 = create_consent_artifact("usr_123", "P001", "hi", True)
        store_consent_artifact(art1)
        art2 = create_consent_artifact("usr_123", "P002", "hi", True, prev_hash=art1["hash"])
        store_consent_artifact(art2)
        assert verify_consent_chain([art1, art2]) == True

    def test_consent_purpose_definitions(self):
        assert CONSENT_PURPOSES["P001"]["mandatory"] == True
        assert CONSENT_PURPOSES["P003"]["revocable"] == True
