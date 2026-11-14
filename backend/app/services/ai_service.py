"""AI 对话业务：拼提示词、带历史消息调用模型，并把结果归一化。

路由层只关心「拿到回复」或「拿到错误」，不直接接触 ``openai`` 的异常类型。
"""

from collections.abc import AsyncIterator, Sequence
from datetime import datetime, timedelta, timezone

from openai import APIError, APITimeoutError, AsyncOpenAI

from app.ai.client import AiNotConfiguredError, get_ai_client
from app.ai.prompts import render_system_prompt
from app.config import Settings, get_settings
from app.schemas.ai import ChatMessage, ChatReply, ChatUsage

# 相对时间（「明天下午」）必须按用户所在时区换算。
# 中国没有夏令时，用固定 UTC+8 即可，省掉 Windows 上缺失的 tzdata 依赖。
SHANGHAI = timezone(timedelta(hours=8), name="CST")
_WEEKDAYS = "一二三四五六日"


class AiUpstreamError(RuntimeError):
    """模型调用失败（超时、限流、上游 5xx 等），路由层映射成 502。"""


class AiService:
    """对话服务：不持有请求级状态，可被并发复用。"""

    def __init__(
        self,
        settings: Settings | None = None,
        client: AsyncOpenAI | None = None,
    ) -> None:
        """初始化服务。

        Args:
            settings: 应用配置，默认从进程单例读取；测试时可注入。
            client: 模型客户端，默认懒加载；测试时可注入假客户端。
        """
        self._settings = settings or get_settings()
        self._client = client

    @property
    def client(self) -> AsyncOpenAI:
        """懒加载模型客户端，避免没用到 AI 的请求也初始化连接池。"""
        if self._client is None:
            self._client = get_ai_client()
        return self._client

    def _build_messages(
        self,
        message: str,
        history: Sequence[ChatMessage] = (),
        user_name: str | None = None,
    ) -> list[dict[str, str]]:
        """把系统提示词、历史消息、本轮输入拼成 OpenAI 消息数组。

        Args:
            message: 用户本轮输入。
            history: 历史消息（时间正序），只保留最近 N 条。
            user_name: 当前用户姓名，用于让模型称呼用户。

        Returns:
            list[dict[str, str]]: 形如 ``{"role": ..., "content": ...}`` 的列表。
        """
        now = datetime.now(SHANGHAI)
        context = f"当前时间：{now:%Y-%m-%d %H:%M}（周{_WEEKDAYS[now.weekday()]}）"
        if user_name:
            context = f"{context}\n当前用户：{user_name}"

        limit = self._settings.ai_max_history_messages
        trimmed = list(history)[-limit:] if limit > 0 else []

        return [
            {"role": "system", "content": render_system_prompt(context)},
            *[{"role": item.role, "content": item.content} for item in trimmed],
            {"role": "user", "content": message},
        ]

    async def chat(
        self,
        message: str,
        history: Sequence[ChatMessage] = (),
        user_name: str | None = None,
    ) -> ChatReply:
        """发起一次非流式对话。

        Args:
            message: 用户本轮输入。
            history: 历史消息（时间正序）。
            user_name: 当前用户姓名。

        Returns:
            ChatReply: 模型回复与 token 用量。

        Raises:
            AiNotConfiguredError: AI 未启用或未配置 Key。
            AiUpstreamError: 模型调用超时、限流或其他上游错误。
        """
        if not self._settings.ai_ready:
            raise AiNotConfiguredError("AI 未启用或未配置 API Key")

        try:
            response = await self.client.chat.completions.create(
                model=self._settings.ai_model,
                messages=self._build_messages(message, history, user_name),
                temperature=self._settings.ai_temperature,
            )
        except (APITimeoutError, APIError) as exc:
            raise AiUpstreamError(f"模型调用失败：{exc}") from exc

        choice = response.choices[0]
        usage = response.usage
        return ChatReply(
            reply=choice.message.content or "",
            model=response.model,
            usage=ChatUsage(
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            ),
        )

    async def stream_chat(
        self,
        message: str,
        history: Sequence[ChatMessage] = (),
        user_name: str | None = None,
    ) -> AsyncIterator[str]:
        """发起一次流式对话，逐段产出文本增量。

        Args:
            message: 用户本轮输入。
            history: 历史消息（时间正序）。
            user_name: 当前用户姓名。

        Yields:
            str: 模型输出的文本片段（可能为空，调用方需跳过空片段）。

        Raises:
            AiNotConfiguredError: AI 未启用或未配置 API Key。
            AiUpstreamError: 模型调用超时、限流或其他上游错误。
        """
        if not self._settings.ai_ready:
            raise AiNotConfiguredError("AI 未启用或未配置 API Key")

        try:
            stream = await self.client.chat.completions.create(
                model=self._settings.ai_model,
                messages=self._build_messages(message, history, user_name),
                temperature=self._settings.ai_temperature,
                stream=True,
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                # 有些分片只带 role/finish_reason，没有正文，跳过
                if delta:
                    yield delta
        except (APITimeoutError, APIError) as exc:
            raise AiUpstreamError(f"模型调用失败：{exc}") from exc
