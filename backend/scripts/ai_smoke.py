r"""AI 冒烟脚本：验证模型 API、系统提示词与多轮消息拼装。

用法（在 backend 下）：

    .\.venv\Scripts\python.exe -m scripts.ai_smoke
"""

import asyncio

from app.config import get_settings
from app.schemas.ai import ChatMessage
from app.services.ai_service import AiService


def _mask(key: str) -> str:
    """Key 只显示前后各 4 位，避免日志泄露。"""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}…{key[-4:]}"


async def main() -> None:
    settings = get_settings()
    print(f"model={settings.ai_model} base_url={settings.ai_base_url}")
    print(f"api_key={_mask(settings.ai_api_key)} ready={settings.ai_ready}")

    service = AiService()
    history: list[ChatMessage] = []

    # 第一轮：验证系统提示词是否生效（应当自我介绍为格物实验室助手）
    question = "你好，你是做什么的？"
    reply = await service.chat(question, history, user_name="张同学")
    print(f"\n用户：{question}\n助手：{reply.reply}")
    print(f"usage：{reply.usage.model_dump()}")

    history += [
        ChatMessage(role="user", content=question),
        ChatMessage(role="assistant", content=reply.reply),
    ]

    # 第二轮：带历史，验证多轮上下文（应当记得刚才自称的身份/能力）
    question = "那我想约明天下午的人工智能实验室，该准备什么？"
    reply = await service.chat(question, history, user_name="张同学")
    print(f"\n用户：{question}\n助手：{reply.reply}")

    # 流式：验证 stream_chat 逐段产出
    print("\n流式输出：", end="")
    async for piece in service.stream_chat("用一句话介绍你的预约规则", history, user_name="张同学"):
        print(piece, end="", flush=True)
    print()


if __name__ == "__main__":
    asyncio.run(main())
