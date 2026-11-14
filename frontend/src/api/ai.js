import http from './request'
import { getToken } from '@/utils/auth'

/**
 * 与实验室助手对话（非流式，保留给脚本或调试用）。
 * @param {{ message: string, sessionId?: string }} payload
 */
export function chatWithAi(payload) {
  return http.post('/ai/chat', payload)
}

/**
 * 流式对话：解析后端 SSE（event: token/tool_call/tool/booking_card/error/done）。
 *
 * booking_card 事件的 data.card 是可直接渲染的预约单，点卡片上的「确认预约」
 * 才会真正创建预约（走 POST /api/bookings）。
 *
 * @param {object} options
 * @param {string} options.message 用户本轮输入
 * @param {string} [options.sessionId] 会话 id，同一 id 共享多轮记忆
 * @param {(event: string, data: object) => void} options.onEvent 事件回调
 * @param {AbortSignal} [options.signal] 用于取消请求
 * @returns {Promise<void>}
 */
export async function streamChat({ message, sessionId, onEvent, signal }) {
  const response = await fetch('/api/ai/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken() || ''}`
    },
    body: JSON.stringify({ message, sessionId }),
    signal
  })

  if (!response.ok) {
    let detail = '对话失败，请稍后再试'
    try {
      const body = await response.json()
      detail = body?.message || detail
    } catch {
      // 非 JSON 错误体（例如代理层返回的 HTML），保留默认文案
    }
    throw new Error(detail)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let index = buffer.indexOf('\n\n')
    while (index >= 0) {
      const block = buffer.slice(0, index)
      buffer = buffer.slice(index + 2)
      index = buffer.indexOf('\n\n')

      let event = 'message'
      let data = ''
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) data += line.slice(5).trim()
      }
      if (!data) continue
      try {
        onEvent(event, JSON.parse(data))
      } catch {
        // 单个事件解析失败不影响后续接收
      }
    }
  }
}
