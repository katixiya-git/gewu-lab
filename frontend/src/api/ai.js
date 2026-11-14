/**
 * 【导读】AI 对话的 HTTP 入口：非流的 `chatWithAi` 与流式的 `streamChat`。
 *
 * 谁调它：`views/student/ChatView.vue` 的 `send()`；它调 `api/sse.js` 切事件。
 *
 * 为什么不用项目统一的 axios：axios 要等响应体收完才交给你，而流式回复
 * 必须边收边读，所以这里用原生 fetch，手动读 `response.body` 这条字节流。
 *
 * token 是什么：模型逐字往外吐，一个 token 可能是一个字、半个词或标点；
 * 前端只管把 `token` 事件里的文字拼到消息末尾，不去猜句子边界。
 *
 * 事件种类见下方 `streamChat` 的注释；`booking_card` 只负责渲染卡片，
 * 用户点「确认预约」才真正走 POST /api/bookings 建单。
 */
import http from './request'
import { getToken } from '@/utils/auth'
import { parseSSEChunk } from './sse'

/**
 * 与实验室助手对话（非流式，保留给脚本或调试用）。
 * @param {{ message: string, sessionId?: string }} payload
 */
export function chatWithAi(payload) {
  return http.post('/ai/chat', payload)
}

/**
 * 流式对话：解析后端 SSE。
 *
 * 事件（都带自增 seq，用于判断有没有漏收）：
 *   user_message 回显本轮输入 / token 增量文本 / tool_call 准备调用哪些工具
 *   / tool 工具执行结果 / booking_card 预约单 / error / done
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
  // signal 是「取消开关」，页面卸载或用户点停止时由调用方触发
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
    // 出错时后端会返回 JSON 错误体，尽量把后端原话透给用户
    let detail = '对话失败，请稍后再试'
    try {
      const body = await response.json()
      detail = body?.message || detail
    } catch {
      // 非 JSON 错误体（例如代理层返回的 HTML），保留默认文案
    }
    throw new Error(detail)
  }

  // 拿到「读卡器」：每次 read() 交出一片字节，流结束的时候 done 为 true
  const reader = response.body.getReader()
  // 字节不等于文字：UTF-8 里一个汉字占 3 字节，可能被切在两片之间
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  /** 分发一批已完整的事件；单条解析失败不影响后续接收 */
  function dispatch(events) {
    for (const { event, data } of events) {
      let payload
      try {
        payload = JSON.parse(data)
      } catch {
        // 解析失败就跳过这一条：宁可少一帧，也别让整轮对话崩掉
        continue
      }
      onEvent(event, payload)
    }
  }

  // 一直读到服务端关闭连接为止，每片先解码成文字再切事件
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    // stream: true 意思是「后面还有」，别把不完整的字节直接解成乱码
    buffer += decoder.decode(value, { stream: true })
    const parsed = parseSSEChunk(buffer)
    buffer = parsed.rest
    dispatch(parsed.events)
  }

  // 个别代理不发结尾空行，收流后把残留补一个空行再解一次，避免丢最后一帧
  // decode() 不带参数 = 冲出解码器里还攒着的半个字符
  buffer += decoder.decode()
  dispatch(parseSSEChunk(`${buffer}\n\n`).events)
}
