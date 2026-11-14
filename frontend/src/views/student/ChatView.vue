<script setup>
/**
 * 【导读】学生对话页：整条链路的起点与终点。
 *
 * 位置：用户在这里输入 → `api/ai.js` 的 `streamChat()` 发 POST 并读流
 * → `api/sse.js` 切出事件 → `chatEvents.js` 的 `applyEvent` 归约到消息对象
 * → Vue 响应式地把消息渲染成气泡与预约卡片。
 *
 * 三个关键 ref：`messages` 是消息数组（模板 v-for 它）、`input` 是输入框、
 * `sending` 控制「生成中」的禁用与 loading。
 * `ref()` 把普通值包成响应式对象：JS 里读写 `.value`，模板里自动解包。
 *
 * 卡片为什么先出现、确认才下单：模型只负责「提议」，`booking_card` 事件
 * 只是渲染一张确认单；用户点「确认预约」才真的 POST /api/bookings，
 * 避免模型理解偏差直接建错单。
 */
import { nextTick, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { streamChat } from '@/api/ai'
import BookingCard from '@/components/booking/BookingCard.vue'
import { applyEvent, confirmUserMessage, createAssistantMessage } from './chatEvents'

const WELCOME = '你好，我是格物实验室助手。你可以直接问我实验室、设备、空档与预约规则，我会查完再回答。'
// 会话 id 存 sessionStorage：刷新页面还能接着聊，关掉标签页就重置
const SESSION_KEY = 'gewu:ai:session'

/** 工具名 → 给用户看的动作文案 */
// 工具名是后端的英文标识，直接显示太生硬，这里翻成中文短语
const TOOL_LABELS = {
  list_labs: '实验室列表',
  get_lab: '实验室详情',
  list_devices: '设备清单',
  find_free_slots: '空闲时段',
  list_my_bookings: '我的预约',
  validate_booking_draft: '预约草稿校验',
  propose_booking: '预约单',
  search_knowledge: '知识库'
}

function newSessionId() {
  // crypto.randomUUID 只在安全上下文（https 或 localhost）可用，否则降级手写
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return `s-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
}

const sessionId = ref(sessionStorage.getItem(SESSION_KEY) || newSessionId())
sessionStorage.setItem(SESSION_KEY, sessionId.value)

// 整页只有这一个数据源：模板 v-for 它，对象里字段一变就自动重渲染
const messages = ref([{ role: 'assistant', type: 'text', content: WELCOME }])
const input = ref('')
const sending = ref(false)
const listRef = ref(null)
let controller = null

async function scrollToBottom() {
  // nextTick：等 Vue 把新消息真的渲染进 DOM，再量高度才滚得到底
  await nextTick()
  const el = listRef.value
  if (el) el.scrollTop = el.scrollHeight
}

function toolHint(names) {
  // 还没有工具名，说明模型正在想、没决定调什么
  const labels = (names || []).map((name) => TOOL_LABELS[name] || name)
  return labels.length ? `正在查询：${labels.join('、')}` : '正在思考'
}

function resetConversation() {
  if (sending.value) return
  sessionId.value = newSessionId()
  sessionStorage.setItem(SESSION_KEY, sessionId.value)
  messages.value = [{ role: 'assistant', type: 'text', content: WELCOME }]
}

async function send() {
  const text = input.value.trim()
  if (!text || sending.value) return

  // 先本地插一条用户消息（乐观渲染），服务端回显只负责确认入库
  messages.value.push({ role: 'user', type: 'text', content: text })
  input.value = ''
  sending.value = true

  // 先建一条空的助手消息：后面每个 token 都往它身上拼，Vue 边拼边显示
  const placeholder = createAssistantMessage()
  messages.value.push(placeholder)
  await scrollToBottom()

  // AbortController 是「取消开关」，把 signal 交给 fetch 就能掐断请求
  controller = new AbortController()
  // 标记「是我们自己取消的」，好和真正的网络断开区分开
  let stopped = false
  try {
    await streamChat({
      message: text,
      sessionId: sessionId.value,
      signal: controller.signal,
      onEvent(event, data) {
        // 每条事件都先过归约器：序号校验、文字累加、工具进度、卡片去重都在里面
        const warning = applyEvent(placeholder, event, data)
        // 归约器只在丢事件时返回文案，弹一次提示就够
        if (warning) ElMessage.warning(warning)
        if (event === 'user_message') {
          // 回显对不上（例如刷新过页面）就补一条，保证会话顺序不乱
          confirmUserMessage(messages.value, data.content || '')
        }
        if (event === 'error') {
          // error 事件不 throw：流还会继续，等 done 时统一收尾
          ElMessage.error(placeholder.error || '对话失败，请稍后再试')
        }
        scrollToBottom()
      }
    })
  } catch (error) {
    stopped = true
    if (error?.name === 'AbortError') {
      // 主动取消不算失败：留个「已取消」就好，不弹红色错误
      placeholder.content = placeholder.content || '（已取消）'
    } else {
      placeholder.content = placeholder.content || `抱歉，我这边暂时没能回答：${error?.message || '请稍后再试'}`
      ElMessage.error('对话失败，请稍后再试')
    }
  } finally {
    // 没收到 done 就结束了：多半是连接被掐断，保留已有文字并提示可重试
    // 只有「既没收到 done，也不是我们取消」才算真断流
    if (!placeholder.finished && !stopped) {
      placeholder.content = placeholder.content
        ? `${placeholder.content}\n（连接中断，请重试）`
        : '（连接中断，请重试）'
      ElMessage.warning('连接中断，请重试')
    }
    placeholder.pending = false
    sending.value = false
    controller = null
    await scrollToBottom()
  }
}

function onKeydown(event) {
  // isComposing：中文输入法选字时按 Enter 是确认候选，不能当成发送
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    send()
  }
}

onBeforeUnmount(() => {
  // 离开页面必须掐断连接，否则流会在后台继续跑，回调还在改已卸载的组件
  controller?.abort()
})
</script>

<template>
  <section class="chat-page">
    <div class="chat-head">
      <span class="chat-title">实验室助手</span>
      <el-button link type="primary" :disabled="sending" @click="resetConversation">新对话</el-button>
    </div>

    <!-- 消息列表：ref 供滚到底部用；生成中的那条就是一个占位对象 -->
    <div ref="listRef" class="chat-list">
      <div v-for="(msg, index) in messages" :key="index" class="msg" :class="msg.role">
        <div class="msg-body">
          <div v-if="msg.content || msg.pending" class="bubble" :class="{ 'bubble--pending': msg.pending }">
            <!-- 还没吐字时显示「正在查询：xx」；后面三个点是纯 CSS 闪烁动画 -->
            <span v-if="msg.pending && !msg.content" class="typing">
              {{ toolHint(msg.tools) }}<span>.</span><span>.</span><span>.</span>
            </span>
            <span v-else>{{ msg.content }}</span>
          </div>
          <!-- 卡片跟着消息对象走；被同一轮新卡片取代的那张会变灰并禁用按钮 -->
          <BookingCard
            v-for="item in msg.cards"
            :key="item.key"
            :card="item.card"
            :pending="msg.pending"
            :superseded="item.superseded"
          />
          <div v-if="msg.error" class="msg-error">{{ msg.error }}</div>
        </div>
      </div>
    </div>

    <div class="composer">
      <el-input
        v-model="input"
        type="textarea"
        :rows="2"
        resize="none"
        :disabled="sending"
        placeholder="例如：明天下午人工智能实验室有空档吗？"
        @keydown="onKeydown"
      />
      <el-button type="primary" :loading="sending" @click="send">发送</el-button>
    </div>
  </section>
</template>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 56px - 40px);
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
}

.chat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid #f0f2f5;
}

.chat-title {
  font-weight: 600;
  color: #303133;
}

.chat-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px;
  overflow-y: auto;
}

.msg {
  display: flex;
}

.msg.user {
  justify-content: flex-end;
}

/* 气泡 + 留言里的预约卡片共用一个宽度上限，卡片才不会撑满整行 */
.msg-body {
  display: flex;
  flex-direction: column;
  max-width: 72%;
}

.bubble {
  max-width: 100%;
  width: fit-content;
  padding: 10px 14px;
  border-radius: 8px;
  background: #f5f7fa;
  color: #303133;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.msg.user .bubble {
  background: #409eff;
  color: #fff;
}

.bubble--pending {
  color: #909399;
}

/* 后端事件里带回来的错误（error 事件），用红色小字挂在气泡下面 */
.msg-error {
  margin-top: 6px;
  color: #f56c6c;
  font-size: 12px;
  line-height: 1.6;
}

.typing span {
  animation: blink 1.2s infinite;
}

.typing span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes blink {
  0%, 60%, 100% {
    opacity: 0.2;
  }
  30% {
    opacity: 1;
  }
}

.composer {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  border-top: 1px solid #e4e7ed;
}

.composer .el-button {
  align-self: flex-end;
}
</style>
