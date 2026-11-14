"""系统提示词与工具集的一致性检查。

提示词里点名了每个工具，工具改名或新增而提示词没跟上时，
模型会「知道要查但不知道叫什么」，这里把这种漂移挡在测试里。
"""

from app.ai.agent_tools import AGENT_TOOLS
from app.ai.prompts import SYSTEM_PROMPT, render_system_prompt


def test_system_prompt_mentions_every_tool():
    missing = [tool.name for tool in AGENT_TOOLS if tool.name not in SYSTEM_PROMPT]
    assert missing == [], f"提示词没提到这些工具：{missing}"


def test_system_prompt_forbids_direct_booking_creation():
    """AI 只能校验草稿，不能声称已创建预约——这条是产品约束，必须留在提示词里。"""
    assert "validate_booking_draft" in SYSTEM_PROMPT
    assert "不能直接创建" in SYSTEM_PROMPT


def test_render_system_prompt_without_context_returns_base():
    assert render_system_prompt() == SYSTEM_PROMPT
    assert render_system_prompt(None) == SYSTEM_PROMPT


def test_render_system_prompt_appends_context_block():
    text = render_system_prompt("当前时间：2026-11-14 22:30（周五）")

    assert text.startswith(SYSTEM_PROMPT)
    assert "## 当前上下文" in text
    assert "2026-11-14 22:30" in text
