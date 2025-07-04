"""
공통 유틸리티 함수들
"""
from typing import Optional

def safe_float(value) -> Optional[float]:
    """
    문자열이나 숫자를 안전하게 float로 변환
    
    Args:
        value: 변환할 값
        
    Returns:
        float 또는 None (변환 실패 시)
    """
    if value is None:
        return None
    try:
        if isinstance(value, str):
            # 통화 기호와 콤마 제거
            value = value.replace(',', '').replace('￦', '').replace('$', '').replace('\\', '').strip()
        return float(value) if value != '' else None
    except (ValueError, TypeError, AttributeError):
        return None

def safe_int(value) -> Optional[int]:
    """
    문자열이나 숫자를 안전하게 int로 변환
    
    Args:
        value: 변환할 값
        
    Returns:
        int 또는 None (변환 실패 시)
    """
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.replace(',', '').strip()
        return int(float(value)) if value != '' else None
    except (ValueError, TypeError, AttributeError):
        return None

def safe_str(value) -> str:
    """
    값을 안전하게 문자열로 변환
    
    Args:
        value: 변환할 값
        
    Returns:
        문자열
    """
    if value is None:
        return ""
    return str(value).strip() 