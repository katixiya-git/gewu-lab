<script setup>
import { nextTick, ref } from 'vue'
import { ElMessage } from 'element-plus'

const draft = {
  labName: '人工智能实验室',
  date: '2026-11-05',
  start: '14:00',
  end: '16:00',
  people: 6,
  type: '小组',
  devices: ['GPU 服务器', '深度学习工作站'],
  purpose: '课程项目模型训练'
}

const messages = ref([
  {
    role: 'assistant',
    type: 'text',
    content: '你好，我是格物实验室助手。告诉我你想约哪间实验室、什么时间、多少人、需要什么设备，我来帮你查。'
  },
  {
    role: 'user',
    type: 'text',
    content: '明天下午 2 点到 4 点，6 个人，要用 GPU 服务器训练模型。'
  },
  {
    role: 'assistant',
    type: 'text',
    content: '查到人工智能实验室该时段空闲，且满足 6 人 + GPU 服务器的要求，帮你生成了这份预约方案：'
  },
  {
    role: 'assistant',
    type: 'card',
    booking: draft
  }
])

const input = ref('')
const listRef = ref(null)
const confirmed = ref(false)

async function scrollToBottom() {
  await nextTick()
  const el = listRef.value
  if (el) el.scrollTop = el.scrollHeight
}

async function send() {
  const text = input.value.trim()
  if (!text) return

  messages.value.push({ role: 'user', type: 'text', content: text })
  input.value = ''
  await scrollToBottom()

  messages.value.push({
    role: 'assistant',
    type: 'text',
    content: '（对话接口尚未接入，这里之后会返回校验结果和新的预约方案。）'
  })
  await scrollToBottom()
}

function confirmBooking() {
  confirmed.value = true
  ElMessage.success('预约已提交，等待管理员审核（演示数据，不落库）')
}

function editBooking() {
  input.value = '我想调整一下时间：'
}
</script>

<template>
  <section class="chat-page">
    <div ref="listRef" class="chat-list">
      <div v-for="(msg, index) in messages" :key="index" class="msg" :class="msg.role">
        <div v-if="msg.type === 'text'" class="bubble">{{ msg.content }}</div>

        <div v-else class="booking-card">
          <div class="booking-card__head">
            <span class="booking-card__title">预约方案</span>
            <el-tag size="small" type="warning">待确认</el-tag>
          </div>

          <div class="booking-card__grid">
            <span class="label">实验室</span><span>{{ msg.booking.labName }}</span>
            <span class="label">时间</span>
            <span>{{ msg.booking.date }} {{ msg.booking.start }} - {{ msg.booking.end }}</span>
            <span class="label">人数 / 类型</span>
            <span>{{ msg.booking.people }} 人 · {{ msg.booking.type }}</span>
            <span class="label">设备</span><span>{{ msg.booking.devices.join('、') }}</span>
            <span class="label">用途</span><span>{{ msg.booking.purpose }}</span>
          </div>

          <div class="booking-card__actions">
            <el-button :disabled="confirmed" type="primary" @click="confirmBooking">
              {{ confirmed ? '已确认' : '确认创建' }}
            </el-button>
            <el-button @click="editBooking">继续修改</el-button>
          </div>
        </div>
      </div>
    </div>

    <div class="composer">
      <el-input
        v-model="input"
        type="textarea"
        :rows="2"
        resize="none"
        placeholder="例如：明天下午想用有 GPU 的实验室，6 个人，两小时"
        @keydown.enter.exact.prevent="send"
      />
      <el-button type="primary" @click="send">发送</el-button>
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
  line-height: 1.6;
  white-space: pre-wrap;
}

.msg.user .bubble {
  background: #409eff;
  color: #fff;
}

.booking-card {
  width: 420px;
  padding: 14px 16px;
  border: 1px solid #d9ecff;
  border-radius: 8px;
  background: #f4f9ff;
}

.booking-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.booking-card__title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.booking-card__grid {
  display: grid;
  grid-template-columns: 76px 1fr;
  gap: 6px 8px;
  font-size: 13px;
  line-height: 1.6;
  color: #303133;
}

.booking-card__grid .label {
  color: #909399;
}

.booking-card__actions {
  display: flex;
  gap: 8px;
  margin-top: 14px;
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
