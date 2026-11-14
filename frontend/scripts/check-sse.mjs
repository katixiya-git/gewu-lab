/**
 * SSE 解析器的用例脚本（零依赖，用 node 自带 assert 跑）。
 *
 * 前端没有装测试框架，而解析器是纯函数，直接用 node 跑最快：
 *   node scripts/check-sse.mjs
 *
 * 覆盖的都是「线上真踩过」的边界：网络分片切在事件中间、代理改写换行、
 * 多行 data、心跳注释、没有 data 的块。
 */

import assert from 'node:assert/strict'

import { parseSSEChunk } from '../src/api/sse.js'

const TOKEN = 'event: token\ndata: {"type":"token","content":"你好","seq":2}\n\n'

// 1. 完整事件一次到达
{
  const { events, rest } = parseSSEChunk(TOKEN)
  assert.equal(events.length, 1)
  assert.equal(events[0].event, 'token')
  assert.deepEqual(JSON.parse(events[0].data), { type: 'token', content: '你好', seq: 2 })
  assert.equal(rest, '')
}

// 2. 事件被切成两片：第一片只留尾巴，第二片才凑齐
{
  const first = parseSSEChunk(TOKEN.slice(0, 20))
  assert.equal(first.events.length, 0)
  assert.ok(first.rest.length > 0)

  const second = parseSSEChunk(first.rest + TOKEN.slice(20))
  assert.equal(second.events.length, 1)
  assert.equal(JSON.parse(second.events[0].data).content, '你好')
}

// 3. 切在 \r\n 中间也要能拼回去（代理层常见）
{
  const first = parseSSEChunk('event: token\r\n')
  const second = parseSSEChunk(`${first.rest}data: {"seq":1}\r\n\r\n`)
  assert.equal(second.events.length, 1)
  assert.equal(second.events[0].event, 'token')
  assert.deepEqual(JSON.parse(second.events[0].data), { seq: 1 })
}

// 4. 多行 data 用换行拼接（JSON 跨行输出时才不会被截断）
{
  const block = 'event: token\ndata: {"a":\ndata: 1}\n\n'
  const { events } = parseSSEChunk(block)
  assert.equal(events.length, 1)
  assert.equal(events[0].data, '{"a":\n1}')
  assert.deepEqual(JSON.parse(events[0].data), { a: 1 })
}

// 5. 心跳注释行不是事件，解析器要直接丢掉
{
  const { events } = parseSSEChunk(': ping\n\n' + TOKEN)
  assert.equal(events.length, 1)
  assert.equal(events[0].event, 'token')
}

// 6. 没有 event: 行时按规范回落成 message；没有 data: 的块不产生事件
{
  const plain = parseSSEChunk('data: {"type":"done"}\n\n')
  assert.equal(plain.events.length, 1)
  assert.equal(plain.events[0].event, 'message')

  const empty = parseSSEChunk('event: token\n\n')
  assert.equal(empty.events.length, 0)
}

// 7. 连续多个事件一次到达（工具进度 + 卡片 + done 常挤在同一个分片里）
{
  const cards =
    'event: booking_card\ndata: {"type":"booking_card","seq":5,"card":{"labId":3}}\n\n' +
    'event: done\ndata: {"type":"done","seq":6}\n\n'
  const { events } = parseSSEChunk(TOKEN + cards)
  assert.deepEqual(
    events.map((item) => item.event),
    ['token', 'booking_card', 'done']
  )
  assert.equal(JSON.parse(events[2].data).seq, 6)
}

console.log('check-sse: 7 组用例全部通过')
