<script setup>
import { nextTick, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { chatWithAi } from '@/api/ai'

const WELCOME = '你好，我是格物实验室助手。你可以问我预约流程，或让我介绍怎么查实验室和设备。'

const messages = ref([{ role: 'assistant', type: 'text', content: WELCOME }])
const input = ref('')
const sending = ref(false)
const listRef = ref(null)

async function scrollToBottom() {
  await nextTick()
  const el = listRef.value
  if (el) el.scrollTop = el.scrollHeight
}

async function send() {
  const text = input.value.trim()
  if (!text || sending.value) return

  messages.value.push({ role: 'user', type: 'text', content: text })
  input.value = ''
  sending.value = true

  const placeholder = { role: 'assistant', type: 'text', content: '', pending: true }
  const history = messages.value
    .slice(0, -1)
    .filter((m) => m.type === 'text' && m.content)
    .slice(-20)
    .map((m) => ({ role: m.role, content: m.content }))
  messages.value.push(placeholder)
  await scrollToBottom()

  try {
    const data = await chatWithAi({ message: text, history })
    placeholder.content = data.reply
  } catch (error) {
    placeholder.content = `抱歉，我这边暂时没能回答：${error?.message || '请稍后再试'}`
    ElMessage.error('对话失败，请稍后再试')
  } finally {
    placeholder.pending = false
    sending.value = false
    await scrollToBottom()
  }
}

function onKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    send()
  }
}
</script>

<template>
  <section class="chat-page">
    <div ref="listRef" class="chat-list">
      <div v-for="(msg, index) in messages" :key="index" class="msg" :class="msg.role">
        <div class="bubble" :class="{ 'bubble--pending': msg.pending }">
          <span v-if="msg.pending" class="typing">正在思考<span>.</span><span>.</span><span>.</span></span>
          <span v-else>{{ msg.content }}</span>
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
        placeholder="例如：预约流程是什么？怎么查看实验室开放时间？"
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

.bubble {
  max-width: 72%;
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
