import re


def mask_phone(text: str) -> str:
    """将文本中的手机号替换为脱敏格式（138****1234）"""
    if not text:
        return text
    return re.sub(r"(1[3-9]\d)\d{4}(\d{4})", r"\1****\2", text)


def mask_dict_phone(data: dict, key: str = "phone") -> dict:
    """对字典中指定 key 的手机号字段脱敏，返回新字典"""
    if not data:
        return data
    result = dict(data)
    if key in result and isinstance(result[key], str):
        result[key] = mask_phone(result[key])
    return result
