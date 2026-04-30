from typing import Dict, Any, Optional


class UserIdentifier:
    """基于手机号或邮箱识别用户的占位实现。"""

    def identify(self, contact_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        phone = contact_info.get("phone")
        email = contact_info.get("email")
        if not phone and not email:
            return None
        return {
            "phone": phone,
            "email": email,
        }
