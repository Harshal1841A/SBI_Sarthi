from typing import Dict
import hashlib
import time

# ────────────────────────────────────────────────────────────────
# Mock KYC Middleware Integration
# SBI already has contracts with Digilocker, CAMS, NSDL.
# Sarthi calls SBI middleware, NOT direct UIDAI.
# This is a regulatory requirement — direct UIDAI calls are prohibited.
# ────────────────────────────────────────────────────────────────

_mock_kyc_db: Dict[str, dict] = {}


class KYCError(Exception):
    """KYC verification error."""
    pass


class KYCAPI:
    """Mock KYC Middleware API (SBI internal, not direct UIDAI)."""
    
    @staticmethod
    def verify_aadhaar(aadhaar_number: str, name: str) -> dict:
        """Verify Aadhaar via SBI middleware (Digilocker/CAMS/NSDL).
        
        Args:
            aadhaar_number: 12-digit Aadhaar (already Verhoeff-validated)
            name: Name as per Aadhaar
            
        Returns:
            {"status": "verified", "kyc_token": str, "name_match": bool}
        """
        # In production: SBI middleware calls Digilocker/e-KYC service
        # For prototype: mock verification
        
        kyc_token = f"KYC_{hashlib.sha256((aadhaar_number + name).encode()).hexdigest()[:16]}"
        
        result = {
            "status": "verified",
            "kyc_token": kyc_token,
            "name_match": True,
            "aadhaar_hash": hashlib.sha256(aadhaar_number.encode()).hexdigest()[:16],
            "verification_source": "SBI_MIDDLEWARE_DIGILOCKER",
            "timestamp": time.time()
        }
        
        _mock_kyc_db[aadhaar_number] = result
        return result
    
    @staticmethod
    def verify_pan(pan_number: str, name: str) -> dict:
        """Verify PAN via NSDL through SBI middleware."""
        result = {
            "status": "verified",
            "pan_valid": True,
            "name_match": True,
            "verification_source": "SBI_MIDDLEWARE_NSDL",
            "timestamp": time.time()
        }
        
        return result
    
    @staticmethod
    def verify_digilocker_consent(user_id: str, aadhaar_number: str) -> dict:
        """Check if user has Digilocker consent for document fetch.
        This is REQUIRED before any document retrieval.
        """
        return {
            "consent_granted": True,
            "consent_expiry": "2027-06-18",
            "documents_available": ["aadhaar", "pan", "driving_license"]
        }
    
    @staticmethod
    def get_vkyc_session(user_id: str, kyc_token: str) -> dict:
        """Initiate a V-KYC (Video KYC) session.
        
        Returns session details for the V-KYC video call.
        """
        session_id = f"VKYC_{user_id[:8]}_{int(time.time())}"
        
        return {
            "session_id": session_id,
            "kyc_token": kyc_token,
            "status": "pending",
            "video_url": f"https://vkyc.sbi.co.in/session/{session_id}",
            "officer_id": None,  # Will be assigned by supervisor dashboard
            "expiry": int(time.time()) + 3600,  # 1 hour expiry
            "rbi_compliant": True
        }
    
    @staticmethod
    def complete_vkyc(session_id: str, officer_id: str, approved: bool) -> dict:
        """Complete V-KYC session after officer review."""
        return {
            "session_id": session_id,
            "officer_id": officer_id,
            "status": "approved" if approved else "rejected",
            "completion_time": time.time(),
            "rbi_compliant": True
        }
    
    @staticmethod
    def check_kyc_status(kyc_token: str) -> dict:
        """Check KYC verification status."""
        for aadhaar, record in _mock_kyc_db.items():
            if record.get("kyc_token") == kyc_token:
                return {
                    "kyc_token": kyc_token,
                    "status": record["status"],
                    "verified_at": record["timestamp"]
                }
        
        return {
            "kyc_token": kyc_token,
            "status": "not_found",
            "verified_at": None
        }


kyc_api = KYCAPI()
