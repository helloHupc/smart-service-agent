import re
from typing import Dict, Optional

class ContactExtractor:
    """联系方式提取工具"""
    
    def __init__(self):
        # 简单的正则匹配
        self.phone_pattern = re.compile(r'1[3-9]\d{9}')
        self.email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        
    def extract(self, text: str) -> Dict[str, str]:
        """从文本中提取手机号和邮箱"""
        results = {}
        
        phone_match = self.phone_pattern.search(text)
        if phone_match:
            results["phone"] = phone_match.group()
            
        email_match = self.email_pattern.search(text)
        if email_match:
            results["email"] = email_match.group()
            
        return results
