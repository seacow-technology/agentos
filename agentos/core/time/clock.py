"""
AgentOS 统一时钟模块

全局时间获取规则:
1. 系统内部时间一律使用 UTC
2. 禁止使用 datetime.now() 或 datetime.utcnow()
3. 使用本模块提供的函数获取时间

Time & Timestamp Contract (ADR-XXXX):
- 内部存储: aware UTC datetime 或 epoch_ms
- API 传输: ISO 8601 UTC with Z suffix
- 前端显示: 浏览器本地时区
"""

from datetime import datetime, timezone
from typing import Optional



def utc_now() -> datetime:
    """
    获取当前 UTC 时间 (timezone-aware)

    Returns:
        datetime: aware UTC datetime object

    Example:
        >>> now = utc_now()
        >>> now.tzinfo  # timezone.utc
        >>> now.tzname()  # 'UTC'
    """
    return datetime.now(timezone.utc)


def utc_now_ms() -> int:
    """
    获取当前 UTC 时间戳 (毫秒)

    Returns:
        int: epoch milliseconds since 1970-01-01T00:00:00Z

    Example:
        >>> ts = utc_now_ms()
        >>> ts  # 1738329600000
        >>> type(ts)  # <class 'int'>
    """
    return int(utc_now().timestamp() * 1000)


def utc_now_iso() -> str:
    """
    获取当前 UTC 时间的 ISO 8601 字符串 (带 Z 后缀)

    Returns:
        str: ISO 8601 format with Z suffix (YYYY-MM-DDTHH:MM:SS.ffffffZ)

    Example:
        >>> utc_now_iso()
        '2026-01-31T12:34:56.789012Z'
    """
    return utc_now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def from_epoch_ms(ms: int) -> datetime:
    """
    从 epoch 毫秒转换为 aware UTC datetime

    Args:
        ms: milliseconds since epoch (1970-01-01T00:00:00Z)

    Returns:
        datetime: aware UTC datetime

    Example:
        >>> dt = from_epoch_ms(1769860800000)
        >>> dt.year  # 2026
        >>> dt.tzinfo  # timezone.utc
    """
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def to_epoch_ms(dt: datetime) -> int:
    """
    将 datetime 转换为 epoch 毫秒

    Args:
        dt: datetime object (aware or naive)

    Returns:
        int: epoch milliseconds

    Note:
        If naive, assumes UTC (声明为 UTC，不转换)

    Example:
        >>> dt = datetime(2026, 1, 31, 12, 0, 0, tzinfo=timezone.utc)
        >>> to_epoch_ms(dt)
        1769860800000
    """
    if dt.tzinfo is None:
        # Naive datetime - declare as UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def from_epoch_s(s: float) -> datetime:
    """
    从 epoch 秒转换为 aware UTC datetime

    Args:
        s: seconds since epoch (1970-01-01T00:00:00Z)

    Returns:
        datetime: aware UTC datetime

    Example:
        >>> dt = from_epoch_s(1769860800)
        >>> dt.year  # 2026
    """
    return datetime.fromtimestamp(s, tz=timezone.utc)


def to_epoch_s(dt: datetime) -> float:
    """
    将 datetime 转换为 epoch 秒

    Args:
        dt: datetime object (aware or naive)

    Returns:
        float: epoch seconds

    Note:
        If naive, assumes UTC
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    确保 datetime 是 timezone-aware UTC

    Args:
        dt: datetime object (aware/naive) or None

    Returns:
        Timezone-aware UTC datetime or None

    Behavior:
        - None → None
        - naive datetime → attach UTC timezone (declares as UTC, does not convert)
        - aware non-UTC → convert to UTC
        - aware UTC → return as-is

    Example:
        >>> from datetime import datetime, timezone
        >>> # Naive datetime - declares as UTC
        >>> naive = datetime(2026, 1, 31, 12, 0, 0)
        >>> result = ensure_utc(naive)
        >>> result.tzinfo == timezone.utc
        True
    """
    if dt is None:
        return None

    if dt.tzinfo is None:
        # Naive datetime - declare as UTC (do not convert)
        return dt.replace(tzinfo=timezone.utc)
    else:
        # Aware datetime - convert to UTC
        return dt.astimezone(timezone.utc)


def iso_z(dt: Optional[datetime]) -> Optional[str]:
    """
    将 datetime 转换为 ISO 8601 UTC 字符串 (带 Z 后缀)

    这是硬契约函数,保证输出总是以 'Z' 结尾 (或返回 None)
    防止前端时区误解析

    输出格式: YYYY-MM-DDTHH:MM:SS.ffffffZ

    Args:
        dt: datetime object or None

    Returns:
        ISO 8601 string with Z suffix, or None

    Example:
        >>> from datetime import datetime, timezone
        >>> dt = datetime(2026, 1, 31, 12, 34, 56, 789012, tzinfo=timezone.utc)
        >>> iso_z(dt)
        '2026-01-31T12:34:56.789012Z'
    """
    if dt is None:
        return None

    # Ensure UTC first
    utc_dt = ensure_utc(dt)
    if utc_dt is None:
        return None

    # Format with Z suffix (microseconds always included)
    return utc_dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def parse_db_time(value: Optional[str]) -> Optional[datetime]:
    """
    解析数据库时间值为 timezone-aware UTC datetime

    支持多种数据库存储格式:
    - "2026-01-31 12:34:56" (SQLite CURRENT_TIMESTAMP) → 视为 UTC
    - "2026-01-31T12:34:56" (ISO without timezone) → 视为 UTC
    - "2026-01-31T12:34:56Z" (ISO with Z) → 解析为 UTC
    - "2026-01-31T12:34:56+00:00" (ISO with offset) → 转换为 UTC
    - None → None

    Args:
        value: 数据库中的时间值 (字符串或 datetime)

    Returns:
        Timezone-aware UTC datetime or None

    Example:
        >>> parse_db_time("2026-01-31 12:34:56")
        datetime.datetime(2026, 1, 31, 12, 34, 56, tzinfo=datetime.timezone.utc)
    """
    if value is None:
        return None

    # Handle datetime objects
    if isinstance(value, datetime):
        return ensure_utc(value)

    # Handle string formats
    if isinstance(value, str):
        # Try various formats

        # 1. ISO format with Z or offset
        if 'T' in value and (value.endswith('Z') or '+' in value or value.count('-') > 2):
            try:
                # Handle 'Z' suffix
                value = value.replace('Z', '+00:00')
                dt = datetime.fromisoformat(value)
                return ensure_utc(dt)
            except ValueError:
                pass

        # 2. ISO format without timezone (treat as UTC)
        if 'T' in value:
            try:
                dt = datetime.fromisoformat(value)
                return ensure_utc(dt)
            except ValueError:
                pass

        # 3. SQLite format "YYYY-MM-DD HH:MM:SS" (treat as UTC)
        if ' ' in value and len(value) >= 19:
            try:
                dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        # 4. Try with microseconds
        if ' ' in value and '.' in value:
            try:
                dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S.%f')
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                pass

    return None
