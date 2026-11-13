<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createBooking } from '@/api/booking'
import { getUser } from '@/utils/auth'
import { formatTime } from '@/utils/lab'
import { BOOKING_TYPE_OPTIONS } from '@/utils/booking'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  lab: { type: Object, default: null },
  devices: { type: Array, default: () => [] }
})
const emit = defineEmits(['update:modelValue', 'created'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const formRef = ref(null)
const submitting = ref(false)
const form = reactive({
  bookingDate: '',
  startTime: '',
  endTime: '',
  peopleCount: 1,
  bookingType: 'personal',
  purpose: '',
  contactName: '',
  contactPhone: '',
  deviceIds: []
})

const rules = {
  bookingDate: [{ required: true, message: '请选择预约日期', trigger: 'change' }],
  startTime: [{ required: true, message: '请选择开始时间', trigger: 'change' }],
  endTime: [
    { required: true, message: '请选择结束时间', trigger: 'change' },
    {
      validator: (_rule, value, callback) => {
        if (!value || !form.startTime) return callback()
        callback(value > form.startTime ? undefined : new Error('结束时间必须晚于开始时间'))
      },
      trigger: 'change'
    }
  ],
  peopleCount: [{ required: true, message: '请填写人数', trigger: 'change' }],
  contactName: [{ required: true, message: '请填写联系人', trigger: 'blur' }],
  contactPhone: [
    { required: true, message: '请填写联系电话', trigger: 'blur' },
    { min: 6, max: 20, message: '联系电话长度应为 6–20 位', trigger: 'blur' }
  ]
}

/** 可预约的实验室设备：维护中的设备不让学生勾选 */
const selectableDevices = computed(() => props.devices.filter((item) => item.status === 'normal'))

/** 按实验室开放时间生成 30 分钟一档的时段选项 */
const timeOptions = computed(() => {
  if (!props.lab) return []
  const start = formatTime(props.lab.openTime)
  const end = formatTime(props.lab.closeTime)
  const toMinutes = (text) => {
    const [hour, minute] = text.split(':').map(Number)
    return hour * 60 + minute
  }
  const fmt = (minutes) =>
    `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`
  const options = []
  for (let minute = toMinutes(start); minute <= toMinutes(end); minute += 30) {
    options.push(fmt(minute))
  }
  return options
})

function reset() {
  const user = getUser()
  form.bookingDate = ''
  form.startTime = ''
  form.endTime = ''
  form.peopleCount = 1
  form.bookingType = 'personal'
  form.purpose = ''
  form.contactName = user?.name || ''
  form.contactPhone = user?.phone || ''
  form.deviceIds = []
  formRef.value?.clearValidate()
}

watch(visible, (value) => {
  if (value) reset()
})

function disabledDate(date) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return date.getTime() < today.getTime()
}

async function submit() {
  if (!props.lab) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  if (form.peopleCount > props.lab.capacity) {
    ElMessage.warning(`该实验室最多容纳 ${props.lab.capacity} 人`)
    return
  }
  submitting.value = true
  try {
    const data = await createBooking({
      labId: props.lab.id,
      bookingDate: form.bookingDate,
      startTime: form.startTime,
      endTime: form.endTime,
      peopleCount: form.peopleCount,
      bookingType: form.bookingType,
      purpose: form.purpose || null,
      contactName: form.contactName,
      contactPhone: form.contactPhone,
      deviceIds: form.deviceIds
    })
    if (data.status === 'conflict') {
      ElMessage.warning('该时段已有通过的预约，你的申请已提交并进入「冲突待协调」')
    } else {
      ElMessage.success('预约已提交，等待管理员审核')
    }
    visible.value = false
    emit('created', data)
  } catch (error) {
    ElMessage.error(error.message || '预约提交失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="预约实验室" width="620px" top="5vh" destroy-on-close>
    <div v-if="lab" class="lab-brief">
      <span class="lab-brief__name">{{ lab.name }}</span>
      <span class="lab-brief__meta">
        {{ formatTime(lab.openTime) }}–{{ formatTime(lab.closeTime) }} · 可容纳
        {{ lab.capacity }} 人
      </span>
    </div>

    <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
      <el-form-item label="预约日期" prop="bookingDate">
        <el-date-picker
          v-model="form.bookingDate"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="选择日期"
          :disabled-date="disabledDate"
          style="width: 220px"
        />
      </el-form-item>

      <el-form-item label="预约时段" required>
        <div class="time-range">
          <el-select v-model="form.startTime" placeholder="开始" style="width: 120px">
            <el-option v-for="item in timeOptions" :key="item" :label="item" :value="item" />
          </el-select>
          <span class="time-range__sep">至</span>
          <el-select v-model="form.endTime" placeholder="结束" style="width: 120px">
            <el-option v-for="item in timeOptions" :key="item" :label="item" :value="item" />
          </el-select>
        </div>
      </el-form-item>

      <el-form-item label="人数" prop="peopleCount">
        <el-input-number v-model="form.peopleCount" :min="1" :max="lab?.capacity || 500" />
        <span class="form-hint">最多 {{ lab?.capacity }} 人</span>
      </el-form-item>

      <el-form-item label="预约类型">
        <el-radio-group v-model="form.bookingType">
          <el-radio v-for="item in BOOKING_TYPE_OPTIONS" :key="item.value" :value="item.value">
            {{ item.label }}
          </el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="使用设备">
        <el-checkbox-group v-model="form.deviceIds" class="device-group">
          <el-checkbox v-for="item in selectableDevices" :key="item.id" :value="item.id">
            {{ item.name }}
          </el-checkbox>
        </el-checkbox-group>
        <div v-if="selectableDevices.length === 0" class="form-hint">该实验室暂无可选设备</div>
      </el-form-item>

      <el-form-item label="用途说明">
        <el-input
          v-model="form.purpose"
          type="textarea"
          :rows="2"
          maxlength="255"
          show-word-limit
          placeholder="例如：课程项目模型训练"
        />
      </el-form-item>

      <el-form-item label="联系人" prop="contactName">
        <el-input v-model="form.contactName" maxlength="32" placeholder="预约单上的联系人" />
      </el-form-item>

      <el-form-item label="联系电话" prop="contactPhone">
        <el-input v-model="form.contactPhone" maxlength="20" placeholder="用于接收审核结果" />
      </el-form-item>

      <el-alert
        v-if="lab?.rule"
        :title="`使用规则：${lab.rule}`"
        type="info"
        :closable="false"
        show-icon
      />
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">提交预约</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.lab-brief {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 10px 12px;
  margin-bottom: 14px;
  background: #f5f7fa;
  border-radius: 6px;
}

.lab-brief__name {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.lab-brief__meta {
  font-size: 12px;
  color: #909399;
}

.time-range {
  display: flex;
  align-items: center;
  gap: 8px;
}

.time-range__sep {
  color: #909399;
  font-size: 13px;
}

.form-hint {
  margin-left: 10px;
  font-size: 12px;
  color: #909399;
}

.device-group {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
}
</style>
