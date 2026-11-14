<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createBooking } from '@/api/booking'
import { bookingTypeText, statusTagType, statusText } from '@/utils/booking'

/**
 * 对话里的预约确认单。
 *
 * 卡片数据来自后端 propose_booking 的工具结果（SSE 的 booking_card 事件），
 * 这里只做展示与「确认后提交」：校验规则仍由 POST /api/bookings 判断，
 * 提交成功（含冲突待协调）后卡片原地变成结果态，不再允许重复提交。
 */
const props = defineProps({
  card: { type: Object, required: true }
})

const router = useRouter()
const submitting = ref(false)
const created = ref(null)
const errorText = ref('')

const timeRange = computed(() => `${props.card.startTime}–${props.card.endTime}`)
const typeText = computed(
  () => props.card.bookingTypeText || bookingTypeText(props.card.bookingType)
)
const deviceText = computed(() =>
  props.card.deviceNames?.length ? props.card.deviceNames.join('、') : '无'
)

async function confirm() {
  if (submitting.value || created.value) return
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
  router.push({ name: 'lab-detail', params: { id: props.card.labId } })
}

function goBookings() {
  router.push({ name: 'bookings' })
}
</script>

<template>
  <div class="booking-card" :class="{ 'booking-card--done': created }">
    <div class="booking-card__head">
      <span class="booking-card__title">{{ created ? '预约已提交' : '预约确认单' }}</span>
      <el-tag v-if="created" :type="statusTagType(created.status)" size="small">
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
      <el-button v-if="created" type="primary" @click="goBookings">去我的预约</el-button>
      <template v-else>
        <el-button type="primary" :loading="submitting" @click="confirm">确认预约</el-button>
        <el-button :disabled="submitting" @click="goLab">去实验室详情页</el-button>
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
  gap: 8px;
  margin-top: 12px;
}
</style>
