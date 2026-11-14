/**
 * 事件归约：把 SSE 事件逐条应用到「本轮助手消息」对象上。
 *
 * 对话区里出现的全部内容（用户消息确认、增量文字、工具进度、预约卡片）
 * 都由这条流驱动，所以把归约逻辑单独抽出来，方便用 node 直接跑用例，
 * 也避免把状态规则散落在模板和回调里。
 */

/**
 * 预约卡片的去重键：同一实验室、同一天、同一时段视为同一张单。
 * @param {object} card 后端下发的卡片数据
 * @returns {string}
 */
export function cardKey(card) {
  return [card.labId, card.bookingDate, card.startTime, card.endTime].join('|')
}

/**
 * 新建一条「正在生成」的助手消息。
 * @returns {object}
 */
export function createAssistantMessage() {
  return {
    role: 'assistant',
    type: 'text',
    content: '',
    pending: true,
    finished: false,
    seq: undefined,
    tools: [],
    executed: [],
    cards: [],
    error: ''
  }
}

/**
 * 把一条 SSE 事件应用到助手消息上（就地修改）。
 *
 * @param {object} message 助手消息（`createAssistantMessage()` 的产物）
 * @param {string} event 事件名
 * @param {object} data 事件负载
 * @returns {string | null} 需要提示给用户的文案（目前只有「事件序号跳号」）
 */
export function applyEvent(message, event, data) {
  const payload = data || {}
  let warning = null

  // 序号连续性：跳号说明中间丢了事件，提示一次即可，不中断接收
  const seq = payload.seq
  if (typeof seq === 'number') {
    if (typeof message.seq === 'number' && seq > message.seq + 1) {
      warning = `有 ${seq - message.seq - 1} 条消息可能没有收到`
    }
    message.seq = seq
  }

  switch (event) {
    case 'token':
      message.content += payload.content || ''
      message.pending = false
      break
    case 'tool_call':
      message.tools = payload.names || []
      break
    case 'tool':
      if (payload.name) {
        message.executed.push({ name: payload.name, ok: payload.ok !== false })
      }
      break
    case 'booking_card': {
      const card = payload.card
      if (!card) break
      const key = cardKey(card)
      // 同一轮里出现新卡片，之前的单子一律作废，免得用户点到过期的条件
      for (const item of message.cards) item.superseded = true
      const existing = message.cards.find((item) => item.key === key)
      if (existing) {
        existing.card = card
        existing.superseded = false
      } else {
        message.cards.push({ key, card, superseded: false })
      }
      break
    }
    case 'error':
      message.error = payload.message || '对话中断，请稍后再试'
      break
    case 'done':
      message.pending = false
      message.finished = true
      break
    default:
      break
  }

  return warning
}

/**
 * 用服务端回显的 user_message 确认本地那条用户消息。
 *
 * 前端是乐观渲染（点发送就显示），服务端回显只用来确认「已进入会话」；
 * 对不上时补一条，保证会话内容与流顺序一致。
 *
 * @param {object[]} messages 消息列表（就地修改）
 * @param {string} content 回显的文本
 * @returns {boolean} 是否补了一条新消息
 */
export function confirmUserMessage(messages, content) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (message.role === 'user') {
      if (message.content === content) {
        message.confirmed = true
        return false
      }
      break
    }
  }
  messages.push({ role: 'user', type: 'text', content, confirmed: true })
  return true
}
