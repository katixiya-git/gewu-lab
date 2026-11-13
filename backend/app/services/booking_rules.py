"""预约相关的纯函数规则。

这里只放不依赖数据库、不依赖 FastAPI 的计算：开放日解析、30 分钟对齐、
时长、时段重叠、开放时间包含、距开始的小时数。方便单独写断言脚本验证，
也方便 service 复用。
"""

from datetime import date, datetime, time

# 单次预约允许的最短 / 最长时长（分钟）
MIN_DURATION_MINUTES = 30
MAX_DURATION_MINUTES = 4 * 60


def parse_open_days(value: str) -> set[int]:
    """把 ``"1-5"`` / ``"1-6"`` / ``"7"`` 解析成星期集合。

    Args:
        value: 数据库里的开放日字符串，1=周一、7=周日。

    Returns:
        set[int]: 开放的星期编号集合；格式异常时返回空集合（service 会当作不开放）。
    """
    parts = value.strip().split("-")
    try:
        start = int(parts[0])
        end = int(parts[-1])
    except ValueError:
        return set()
    if not (1 <= start <= 7 and 1 <= end <= 7) or start > end:
        return set()
    return set(range(start, end + 1))


def is_open_on(open_days: str, day: date) -> bool:
    """判断某天是否在开放日范围内（``isoweekday``：周一=1，周日=7）。"""
    return day.isoweekday() in parse_open_days(open_days)


def is_aligned(moment: time) -> bool:
    """时间是否按 30 分钟对齐（秒和微秒都为 0）。"""
    return moment.minute in (0, 30) and moment.second == 0 and moment.microsecond == 0


def duration_minutes(start: time, end: time) -> int:
    """计算两个时间点之间的分钟数，结束早于开始时返回负数。"""
    return (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)


def overlaps(
    a_start: time,
    a_end: time,
    b_start: time,
    b_end: time,
) -> bool:
    """判断两个时段是否重叠（首尾相接不算重叠）。"""
    return a_start < b_end and b_start < a_end


def within_open_hours(start: time, end: time, open_time: time, close_time: time) -> bool:
    """判断预约时段是否完整落在实验室开放时段内。"""
    return open_time <= start and end <= close_time


def hours_until(booking_date: date, start_time: time, now: datetime) -> float:
    """预约开始时间距 ``now`` 还有多少小时（已开始则为负数）。"""
    start_at = datetime.combine(booking_date, start_time)
    return (start_at - now).total_seconds() / 3600
