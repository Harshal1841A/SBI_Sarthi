import os
import structlog
from typing import Dict, Any

logger = structlog.get_logger()

class FeatureFlags:
    def __init__(self):
        # In production: connect to Unleash or LaunchDarkly
        self.api_url = os.environ.get("UNLEASH_API_URL")
        self.api_token = os.environ.get("UNLEASH_API_TOKEN")
        self.app_name = os.environ.get("APP_NAME", "sarthi-backend")
        
        # Local defaults for fallback
        self.flags = {
            "enable_yono_voice": True,
            "enable_kyc_vision": True,
            "enable_gemma_fallback": True,
            "enable_whatsapp_channel": False
        }
        
    def is_enabled(self, flag_name: str, context: dict = None) -> bool:
        """Check if a feature flag is enabled."""
        # Simple local implementation for prototype
        is_on = self.flags.get(flag_name, False)
        logger.debug("Feature flag checked", flag=flag_name, enabled=is_on)
        return is_on
        
    def get_all_flags(self) -> Dict[str, bool]:
        """Get all feature flags."""
        return self.flags

feature_flags = FeatureFlags()
