<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchLab } from '@/api/lab'
import { pageDevices } from '@/api/device'
import BookingDialog from '@/components/booking/BookingDialog.vue'
import { formatTime, labCategoryTagType, labCategoryText, openDaysText } from '@/utils/lab'
import { deviceStatusTagType, deviceStatusText } from '@/utils/device'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const lab = ref(null)
const notFound = ref(false)
const devices = ref([])
const devicesLoading = ref(false)
const bookingVisible = ref(false)

/** 设备列表随实验室一起加载；学生只会拿到正常/维护中的设备 */
async function loadDevices() {
  devicesLoading.value = true
  try {
    const data = await pageDevices({ page: 1, size: 50, labId: route.params.id })
    devices.value = data.items
  } catch (error) {
    ElMessage.error(error.message || '设备列表加载失败')
  } finally {
    devicesLoading.value = false
  }
}

async function load() {
  loading.value = true
  notFound.value = false
  try {
    lab.value = await fetchLab(route.params.id)
    await loadDevices()
  } catch (error) {
    if (error.status === 404) {
      notFound.value = true
    } else {
      ElMessage.error(error.message || '实验室详情加载失败')
    }
  } finally {
    loading.value = false
  }
}

function openBooking() {
  bookingVisible.value = true
}

function onBooked() {
  router.push('/bookings')
}

onMounted(load)
</script>

<template>
  <section v-loading="loading">
    <template v-if="lab">
      <el-page-header class="detail-back" @back="router.push('/labs')">
        <template #content>
          <span class="detail-title">{{ lab.name }}</span>
          <el-tag :type="labCategoryTagType(lab.category)" size="small" class="detail-tag">
            {{ labCategoryText(lab.category) }}
          </el-tag>
        </template>
      </el-page-header>

      <div class="detail-grid">
        <div class="detail-card">
          <h3 class="detail-card__title">基本信息</h3>
          <dl class="detail-card__meta">
            <div><dt>位置</dt><dd>{{ lab.location || '—' }}</dd></div>
            <div><dt>容纳人数</dt><dd>{{ lab.capacity }} 人</dd></div>
            <div>
              <dt>开放时间</dt>
              <dd>
                {{ openDaysText(lab.openDays) }} {{ formatTime(lab.openTime) }}-{{
                  formatTime(lab.closeTime)
                }}
              </dd>
            </div>
            <div><dt>用途说明</dt><dd>{{ lab.description || '—' }}</dd></div>
          </dl>
        </div>

        <div class="detail-card">
          <h3 class="detail-card__title">使用规则</h3>
          <p class="detail-card__rule">{{ lab.rule || '暂无规则说明' }}</p>
        </div>
      </div>

      <div class="detail-card">
        <h3 class="detail-card__title">实验设备</h3>
        <el-table v-loading="devicesLoading" :data="devices" stripe>
          <el-table-column prop="name" label="设备名称" min-width="170" />
          <el-table-column label="型号" min-width="180">
            <template #default="{ row }">{{ row.model || '—' }}</template>
          </el-table-column>
          <el-table-column label="数量" width="90">
            <template #default="{ row }">{{ row.totalCount }} 台</template>
          </el-table-column>
          <el-table-column label="状态" width="96">
            <template #default="{ row }">
              <el-tag :type="deviceStatusTagType(row.status)" size="small">
                {{ deviceStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="备注" min-width="180">
            <template #default="{ row }">{{ row.note || '—' }}</template>
          </el-table-column>
          <template #empty>
            <el-empty :image-size="64" description="该实验室暂未登记设备" />
          </template>
        </el-table>
      </div>

      <div class="detail-actions">
        <el-button @click="router.push('/labs')">返回列表</el-button>
        <el-button type="primary" @click="openBooking">去预约这间实验室</el-button>
      </div>
    </template>

    <BookingDialog
      v-if="lab"
      v-model="bookingVisible"
      :lab="lab"
      :devices="devices"
      @created="onBooked"
    />

    <el-empty v-else-if="notFound" description="实验室不存在或已停用">
      <el-button type="primary" @click="router.push('/labs')">返回列表</el-button>
    </el-empty>
  </section>
</template>

<style scoped>
.detail-back {
  margin-bottom: 16px;
}

.detail-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.detail-tag {
  margin-left: 8px;
  vertical-align: middle;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.detail-card {
  padding: 18px;
  margin-bottom: 16px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
}

.detail-grid .detail-card {
  margin-bottom: 0;
}

.detail-card__title {
  margin-bottom: 12px;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.detail-card__meta {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0;
}

.detail-card__meta div {
  display: flex;
  gap: 10px;
  font-size: 13px;
  line-height: 1.6;
}

.detail-card__meta dt {
  width: 72px;
  flex: none;
  color: #909399;
}

.detail-card__meta dd {
  margin: 0;
  color: #303133;
}

.detail-card__rule {
  font-size: 13px;
  line-height: 1.8;
  color: #303133;
  white-space: pre-line;
}

.detail-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
