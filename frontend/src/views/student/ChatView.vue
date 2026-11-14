<script setup>
import { nextTick, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { streamChat } from '@/api/ai'
import BookingCard from '@/components/booking/BookingCard.vue'

const WELCOME = '你好，我是格物实验室助手。你可以直接问我实验室、设备、空档与预约规则，我会查完再回答。'
const SESSION_KEY = 'gewu:ai:session'

/** 工具名 → 给用户看的动作文案 */
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
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return `s-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
}

const sessionId = ref(sessionStorage.getItem(SESSION_KEY) || newSessionId())
sessionStorage.setItem(SESSION_KEY, sessionId.value)

const messages = ref([{ role: 'assistant', type: 'text', content: WELCOME }])
const input = ref('')
const sending = ref(false)
const listRef = ref(null)
let controller = null

async function scrollToBottom() {
  await nextTick()
  const el = listRef.value
  if (el) el.scrollTop = el.scrollHeight
}

function toolHint(names) {
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

  messages.value.push({ role: 'user', type: 'text', content: text })
  input.value = ''
  sending.value = true

  const placeholder = { role: 'assistant', type: 'text', content: '', pending: true, tools: [] }
  messages.value.push(placeholder)
  await scrollToBottom()

  controller = new AbortController()
  try {
    await streamChat({
      message: text,
      sessionId: sessionId.value,
      signal: controller.signal,
      onEvent(event, data) {
        if (event === 'token') {
          placeholder.content += data.content || ''
          placeholder.pending = false
          scrollToBottom()
        } else if (event === 'tool_call') {
          placeholder.tools = data.names || []
          scrollToBottom()
        } else if (event === 'booking_card' && data.card) {
          // 卡片挂在本轮助手消息上，和文字回答一起渲染（不单独起气泡）
          placeholder.card = data.card
          scrollToBottom()
        } else if (event === 'error') {
          placeholder.content = placeholder.content || `抱歉，我这边暂时没能回答：${data.message || '请稍后再试'}`
          ElMessage.error(data.message || '对话失败，请稍后再试')
        } else if (event === 'done') {
          placeholder.pending = false
        }
      }
    })
  } catch (error) {
    if (error?.name === 'AbortError') {
      placeholder.content = placeholder.content || '（已取消）'
    } else {
      placeholder.content = placeholder.content || `抱歉，我这边暂时没能回答：${error?.message || '请稍后再试'}`
      ElMessage.error('对话失败，请稍后再试')
    }
  } finally {
    placeholder.pending = false
    sending.value = false
    controller = null
    await scrollToBottom()
  }
}

function onKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    send()
  }
}

onBeforeUnmount(() => {
  controller?.abort()
})
</script>

<template>
  <section class="chat-page">
    <div class="chat-head">
      <span class="chat-title">实验室助手</span>
      <el-button link type="primary" :disabled="sending" @click="resetConversation">新对话</el-button>
    </div>

    <div ref="listRef" class="chat-list">
      <div v-for="(msg, index) in messages" :key="index" class="msg" :class="msg.role">
        <div class="msg-body">
          <div v-if="msg.content || msg.pending" class="bubble" :class="{ 'bubble--pending': msg.pending }">
            <span v-if="msg.pending && !msg.content" class="typing">
              {{ toolHint(msg.tools) }}<span>.</span><span>.</span><span>.</span>
            </span>
            <span v-else>{{ msg.content }}</span>
          </div>
          <BookingCard v-if="msg.card" :card="msg.card" />
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
