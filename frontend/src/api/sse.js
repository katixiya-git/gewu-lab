/**
 * 【导读】极简 SSE 解析器：把网络分片拼起来的文本切成完整事件块。
 *
 * 在链路里的位置：`api/ai.js` 的 `streamChat()` 每收到一片字节就调一次；
 * 这里只做两件事：按空行切块、块内按行取值，事件含义交给 `chatEvents.js`。
 *
 * SSE 是什么：服务器保持连接不断，有事就往下推一行行文本，浏览器边收边处理。
 * 后端按 `event: {type}\ndata: {json}\n\n` 推送，中间夹 `: ping` 心跳保活。
 *
 * 为什么这么写：网络送来的文本是碎的，可能停在半行甚至 \r\n 中间，
 * 所以只解析「已经以空行收尾」的块，尾巴留在 `rest` 等下一片拼上。
 *
 * @param {string} buffer 累积到的文本（可以包含不完整的尾部）
 * @returns {{ events: { event: string, data: string }[], rest: string }}
 *   `events` 是已完整的事件；`rest` 是要留到下次解析的尾巴。
 */
export function parseSSEChunk(buffer) {
  // 先统一换行：分片可能正好切在 \r\n 中间，下一次调用会把它拼回去
  const text = String(buffer).replace(/\r\n/g, '\n')
  // 事件之间用空行（\n\n）分隔，所以按两个换行切成若干块
  const blocks = text.split('\n\n')
  // 最后一段没有以空行结尾，说明事件还没收完
  // pop() 顺手把它从数组里摘走，免得被后面当成完整事件解析
  const rest = blocks.pop()
  const events = []

  // 逐块解析；没有 data 的块（例如只有心跳）会被 parseBlock 丢掉
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
  // 没写 event: 行时，规范规定默认事件名是 message
  let event = 'message'
  const dataLines = []

  // 块内一行一个字段：event: 名字、data: JSON 内容
  for (const rawLine of block.split('\n')) {
    // 兜底去掉行尾孤零零的 \r：上面整体换过 \r\n，可能还剩裸 \r
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

  // 整块没有 data 就没有负载，直接丢弃：心跳注释走的就是这条路
  if (!dataLines.length) return null
  return { event, data: dataLines.join('\n') }
}
