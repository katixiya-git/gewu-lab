/**
 * 极简 SSE 解析器：把网络分片拼起来的文本切成完整事件块。
 *
 * 后端用 `event: {type}\ndata: {json}\n\n` 的格式推送，中间还会夹 `: ping`
 * 注释心跳。这里只做两件事：按空行切块、块内按行取值；不完整的那一段
 * 留在 `rest` 里等下一个分片。
 *
 * @param {string} buffer 累积到的文本（可以包含不完整的尾部）
 * @returns {{ events: { event: string, data: string }[], rest: string }}
 *   `events` 是已完整的事件；`rest` 是要留到下次解析的尾巴。
 */
export function parseSSEChunk(buffer) {
  // 先统一换行：分片可能正好切在 \r\n 中间，下一次调用会把它拼回去
  const text = String(buffer).replace(/\r\n/g, '\n')
  const blocks = text.split('\n\n')
  // 最后一段没有以空行结尾，说明事件还没收完
  const rest = blocks.pop()
  const events = []

  for (const block of blocks) {
    const parsed = parseBlock(block)
    if (parsed) events.push(parsed)
  }

  return { events, rest }
}

/**
 * 解析单个事件块。
 * @param {string} block
 * @returns {{ event: string, data: string } | null}
 */
function parseBlock(block) {
  let event = 'message'
  const dataLines = []

  for (const rawLine of block.split('\n')) {
    const line = rawLine.replace(/\r$/, '')
    // 空行与 `: ping` 心跳都是规范里的「忽略」语法，直接跳过
    if (!line || line.startsWith(':')) continue
    if (line.startsWith('event:')) {
      event = line.slice('event:'.length).trim()
    } else if (line.startsWith('data:')) {
      // 规范规定去掉冒号后的一个空格，多行 data 用换行拼接
      dataLines.push(line.slice('data:'.length).replace(/^ /, ''))
    }
  }

  if (!dataLines.length) return null
  return { event, data: dataLines.join('\n') }
}
