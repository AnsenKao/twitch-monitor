import re

# Windows 檔名不允許的字元
_ILLEGAL_CHARS = r'\/:*?"<>|'
# 常見 emoji 區段（補充平面 + 雜項符號 + 裝飾符號）
_EMOJI_PATTERN = re.compile(r'[\U00010000-\U0010ffff\u2600-\u26FF\u2700-\u27BF]+')
_CONTROL_PATTERN = re.compile(r'[\x00-\x1f\x7f]')
_WHITESPACE_PATTERN = re.compile(r'\s+')


def sanitize_filename(name: str, fallback: str = "") -> str:
    """
    把影片標題轉成可用的檔名（不含副檔名）。

    :param name: 原始標題
    :param fallback: 淨化後為空時使用的名稱
    :return: 淨化後的檔名
    """
    sanitized = name or ""
    for ch in _ILLEGAL_CHARS:
        sanitized = sanitized.replace(ch, "_")
    sanitized = sanitized.replace("@", "feat")
    sanitized = _EMOJI_PATTERN.sub("", sanitized)
    sanitized = _CONTROL_PATTERN.sub("", sanitized)
    # emoji 移除後常留下連續空白
    sanitized = _WHITESPACE_PATTERN.sub(" ", sanitized).strip()
    # Windows 不允許檔名結尾是點或空白
    sanitized = sanitized.rstrip(". ")
    return sanitized or fallback
