/**
 * 【导读】事件归约：把 SSE 事件逐条应用到「本轮助手消息」对象上。
 *
 * 谁调它：`ChatView.vue` 的 `onEvent` 回调，每来一条事件调一次。
 * 它调谁：不碰网络，只改内存里的普通对象。
 *
 * 归约（reduce）是什么：一条流上有几十条事件，每条都新建一个 DOM 会很乱，
 * 于是先建「一条空的助手消息」，再把事件逐条合并进去（拼文字、记工具、
 * 挂卡片）。对象被就地修改后，Vue 的响应式会自动重渲染。
 *
 * 为什么单独抽成 .js：对话区里出现的全部内容（用户消息确认、增量文字、
 * 工具进度、预约卡片）都由这条流驱动，抽出来既方便用 node 直接跑用例，
 * 也避免把状态规则散落在模板和回调里。
 */

/**
 * 预约卡片的去重键：同一实验室、同一天、同一时段视为同一张单。
 * @param {object} card 后端下发的卡片数据
 * @returns {string}
 */
export function cardKey(card) {
  // 拼成一个字符串当键：内容相同就必然得到同一个 key
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
    content: '', // 把 token 事件逐条追加出来的正文
    pending: true, // true = 还在生成，气泡显示「正在查询…」
    finished: false, // 收到 done 才置 true，用来判断有没有断流
    seq: undefined, // 最后一条事件的序号，用来发现跳号丢包
    tools: [], // tool_call 报上来的工具名，用于显示进度文案
    executed: [], // tool 结果，记录每个工具成没成功
    cards: [], // booking_card 挂在这里，模板遍历渲染
    error: '' // error 事件的文案，渲染成气泡下方的红字
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
    // 跳号多半是网络丢包或代理截断；提示一次，但不断流
    if (typeof message.seq === 'number' && seq > message.seq + 1) {
      warning = `有 ${seq - message.seq - 1} 条消息可能没有收到`
    }
    message.seq = seq
  }

  switch (event) {
    case 'token':
      // 增量不是全量：直接往后接，所以文字的先后完全由流决定
      message.content += payload.content || ''
      message.pending = false
      break
    case 'tool_call':
      // 后端一次可能并发调多个工具，用新数组整体替换
      message.tools = payload.names || []
      break
    case 'tool':
      if (payload.name) {
        // ok !== false：后端没给 ok 就按成功算，少个字段不至于误判
        message.executed.push({ name: payload.name, ok: payload.ok !== false })
      }
      break
    case 'booking_card': {
      const card = payload.card
      if (!card) break
      const key = cardKey(card)
      // 同一轮里出现新卡片，之前的单子一律作废，免得用户点到过期的条件
      for (const item of message.cards) item.superseded = true
      // 条件完全一样的卡片算同一张，只刷新内容，不另起一张
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
      // error 事件不抛异常，只把文案存下来，流通常还会走到 done
      message.error = payload.message || '对话中断，请稍后再试'
      break
    case 'done':
      // done 是正常收尾；一直没等到它的，最后会被判成「连接中断」
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
  // 从后往前找最近一条用户消息；更早的同文消息可能是上一轮问过的
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (message.role === 'user') {
      if (message.content === content) {
        message.confirmed = true
        return false
      }
      // 最近一条对不上就停：说明这条回显是新的，不该翻旧账
      break
    }
  }
  messages.push({ role: 'user', type: 'text', content, confirmed: true })
  return true
}
