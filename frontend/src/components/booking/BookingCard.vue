<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createBooking } from '@/api/booking'
import { bookingTypeText, statusTagType, statusText } from '@/utils/booking'

/**
 * 【导读】对话里的预约确认单：只负责「展示 + 确认后提交」。
 *
 * 卡片数据来自后端 propose_booking 的工具结果（SSE 的 booking_card 事件），
 * 由 `chatEvents.js` 挂到助手消息的 `cards` 上，再由 `ChatView.vue` 渲染。
 *
 * 这里只做展示与「确认后提交」：校验规则仍由 POST /api/bookings 判断，
 * 提交成功（含冲突待协调）后卡片原地变成结果态，不再允许重复提交。
 *
 * 为什么用 `computed` 而不是 `watch`：文案是由 card 算出来的，不该再存一份
 * 状态；computed 只在依赖变化时重算，也不会出现「两份数据对不上」。
 *
 * `props` 是父组件传进来的只读数据，子组件改不了，只能用本地 ref 记结果。
 */
const props = defineProps({
  card: { type: Object, required: true },
  /** 本轮回复还在生成中（流未收到 done）：此时不允许提交，避免提交半截状态 */
  pending: { type: Boolean, default: false },
  /** 同一轮后来又生成了新卡片，这张已被取代 */
  superseded: { type: Boolean, default: false }
})

const router = useRouter()
// 本地状态三件套：请求中 / 已建单 / 报错文案，三者决定按钮和抬头长什么样
const submitting = ref(false)
const created = ref(null)
const errorText = ref('')

// 起个语义名：被取代 = 整卡锁定，后面每个入口都先查它
const locked = computed(() => props.superseded)

const timeRange = computed(() => `${props.card.startTime}–${props.card.endTime}`)
const typeText = computed(
  () => props.card.bookingTypeText || bookingTypeText(props.card.bookingType)
)
// 设备名是数组，展示时用「、」连起来；一个都没有就显示「无」
const deviceText = computed(() =>
  props.card.deviceNames?.length ? props.card.deviceNames.join('、') : '无'
)

async function confirm() {
  // 三重闸门：请求中、已建单、被取代，任一命中都不许重复提交
  if (submitting.value || created.value || locked.value) return
  submitting.value = true
  errorText.value = ''
  try {
    const data = await createBooking({
      labId: props.card.labId,
      bookingDate: props.card.bookingDate,
      startTime: props.card.startTime,
      endTime: props.card.endTime,
      peopleCount: props.card.peopleCount,
      bookingType: props.card.bookingType || 'personal',
      purpose: props.card.purpose || null,
      contactName: props.card.contactName,
      contactPhone: props.card.contactPhone,
      deviceIds: props.card.deviceIds || []
    })
    created.value = data
    if (data.status === 'conflict') {
      ElMessage.warning('该时段已有通过的预约，已提交为「冲突待协调」')
    } else {
      ElMessage.success('预约已提交，等待管理员审核')
    }
  } catch (error) {
    // 409 = 本人该时段已有预约；其余是规则不满足或服务异常，原样展示后端文案
    errorText.value = error?.message || '提交失败，请稍后再试'
  } finally {
    submitting.value = false
  }
}

function goLab() {
  // 作废的卡片不允许跳详情，免得用户照着过期的条件去查看
  if (locked.value) return
  router.push({ name: 'lab-detail', params: { id: props.card.labId } })
}

function goBookings() {
  router.push({ name: 'bookings' })
}
</script>

<template>
  <div class="booking-card" :class="{ 'booking-card--done': created, 'booking-card--void': superseded }">
    <!-- 抬头三种形态：已作废 / 已提交（带状态标签）/ 未提交（带预约类型） -->
    <div class="booking-card__head">
      <span class="booking-card__title">{{ created ? '预约已提交' : '预约确认单' }}</span>
      <el-tag v-if="superseded" type="info" size="small">已作废</el-tag>
      <el-tag v-else-if="created" :type="statusTagType(created.status)" size="small">
        {{ statusText(created.status) }}
      </el-tag>
      <el-tag v-else type="info" size="small">{{ typeText }}</el-tag>
    </div>

    <el-descriptions :column="1" size="small" border>
      <el-descriptions-item label="实验室">{{ card.labName }}</el-descriptions-item>
      <el-descriptions-item label="日期">{{ card.bookingDate }}</el-descriptions-item>
      <el-descriptions-item label="时间">{{ timeRange }}</el-descriptions-item>
      <el-descriptions-item label="人数">{{ card.peopleCount }} 人</el-descriptions-item>
      <el-descriptions-item label="类型">{{ typeText }}</el-descriptions-item>
      <el-descriptions-item label="设备">{{ deviceText }}</el-descriptions-item>
      <el-descriptions-item v-if="card.purpose" label="用途">{{ card.purpose }}</el-descriptions-item>
      <el-descriptions-item label="联系人">
        {{ card.contactName }}（{{ card.contactPhone }}）
      </el-descriptions-item>
      <el-descriptions-item v-if="created" label="预约号">{{ created.code }}</el-descriptions-item>
    </el-descriptions>

    <el-alert
      v-if="card.conflict && !created"
      class="booking-card__alert"
      type="warning"
      :closable="false"
      show-icon
      title="该时段已有通过的预约，提交后会进入「冲突待协调」"
    />
    <el-alert
      v-if="errorText"
      class="booking-card__alert"
      type="error"
      :closable="false"
      show-icon
      :title="errorText"
    />

    <div class="booking-card__actions">
      <!-- 建单成功后只剩一个入口：去列表看审核状态 -->
      <el-button v-if="created" type="primary" @click="goBookings">去我的预约</el-button>
      <template v-else>
        <el-button type="primary" :loading="submitting" :disabled="superseded || pending" @click="confirm">
          确认预约
        </el-button>
        <el-button :disabled="submitting || superseded || pending" @click="goLab">去实验室详情页</el-button>
        <span v-if="pending && !superseded" class="booking-card__hint">回复生成中，稍后可提交</span>
      </template>
    </div>
  </div>
</template>

<style scoped>
.booking-card {
  margin-top: 8px;
  padding: 12px 14px;
  border: 1px solid #dcdfe6;
  border-left: 3px solid #409eff;
  border-radius: 8px;
  background: #fff;
}

.booking-card--done {
  border-left-color: #67c23a;
}

/* 被同一轮的新卡片取代：整卡降透明度，按钮全部禁用 */
.booking-card--void {
  opacity: 0.6;
  border-left-color: #c0c4cc;
}

.booking-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.booking-card__title {
  font-weight: 600;
  color: #303133;
}

.booking-card__alert {
  margin-top: 10px;
}

.booking-card__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}

.booking-card__hint {
  color: #909399;
  font-size: 12px;
}
</style>
