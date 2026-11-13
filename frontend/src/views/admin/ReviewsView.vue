<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { pageBookings, reviewBooking, reviewCancelBooking } from '@/api/booking'
import { pageLabs } from '@/api/lab'
import {
  bookingReason,
  bookingTypeText,
  statusTagType,
  statusText
} from '@/utils/booking'

const activeTab = ref('pending')
const processedStatus = ref('approved')
const loading = ref(false)
const rows = ref([])
const total = ref(0)
const labs = ref([])
const detail = ref(null)
const detailVisible = ref(false)

const query = reactive({
  page: 1,
  size: 10,
  keyword: '',
  labId: ''
})

const tabs = [
  { name: 'pending', label: '待审核' },
  { name: 'conflict', label: '冲突待协调' },
  { name: 'processed', label: '已处理' }
]

const PROCESSED_STATUSES = [
  { value: 'approved', label: '已通过' },
  { value: 'rejected', label: '已驳回' },
  { value: 'cancelled', label: '已取消' }
]

async function loadLabs() {
  try {
    const data = await pageLabs({ page: 1, size: 50 })
    labs.value = data.items
  } catch {
    labs.value = []
  }
}

function currentStatus() {
  if (activeTab.value === 'processed') return processedStatus.value
  return activeTab.value
}

async function load() {
  loading.value = true
  try {
    const data = await pageBookings({
      page: query.page,
      size: query.size,
      status: currentStatus(),
      labId: query.labId || undefined,
      keyword: query.keyword.trim() || undefined
    })
    rows.value = data.items
    total.value = data.total
  } catch (error) {
    ElMessage.error(error.message || '预约列表加载失败')
  } finally {
    loading.value = false
  }
}

function search() {
  query.page = 1
  load()
}

function reset() {
  query.keyword = ''
  query.labId = ''
  query.page = 1
  load()
}

watch(activeTab, () => {
  query.page = 1
  load()
})

watch(processedStatus, () => {
  query.page = 1
  load()
})

function openDetail(row) {
  detail.value = row
  detailVisible.value = true
}

async function approve(row) {
  try {
    await ElMessageBox.confirm(
      `通过后学生会看到「已通过」，预约号 ${row.code}。若该时段已有通过的预约会提示冲突。`,
      '通过预约',
      { type: 'warning', confirmButtonText: '通过', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await reviewBooking(row.id, { action: 'approve' })
    ElMessage.success('已通过')
    load()
  } catch (error) {
    ElMessage.error(error.message || '操作失败')
  }
}

async function reject(row) {
  let reason
  try {
    const result = await ElMessageBox.prompt('请填写驳回理由，学生会在预约详情里看到。', '驳回预约', {
      inputPlaceholder: '例如：人数超过容纳上限，请调整后重新提交',
      confirmButtonText: '驳回',
      cancelButtonText: '取消',
      inputValidator: (text) => (text && text.trim() ? true : '驳回理由不能为空')
    })
    reason = result.value.trim()
  } catch {
    return
  }
  try {
    await reviewBooking(row.id, { action: 'reject', reason })
    ElMessage.warning('已驳回并记录理由')
    load()
  } catch (error) {
    ElMessage.error(error.message || '操作失败')
  }
}

async function approveCancel(row) {
  try {
    await ElMessageBox.confirm(
      `同意后预约 ${row.code} 将变为「已取消」，同时会释放因它产生的冲突单。`,
      '同意取消申请',
      { type: 'warning', confirmButtonText: '同意取消', cancelButtonText: '再想想' }
    )
  } catch {
    return
  }
  try {
    await reviewCancelBooking(row.id, { approve: true })
    ElMessage.success('已同意取消')
    load()
  } catch (error) {
    ElMessage.error(error.message || '操作失败')
  }
}

async function rejectCancel(row) {
  let reason
  try {
    const result = await ElMessageBox.prompt('请填写不同意取消的理由，会写入预约备注。', '拒绝取消申请', {
      inputPlaceholder: '例如：该时段已有其他安排，建议按原时间使用',
      confirmButtonText: '拒绝',
      cancelButtonText: '取消',
      inputValidator: (text) => (text && text.trim() ? true : '理由不能为空')
    })
    reason = result.value.trim()
  } catch {
    return
  }
  try {
    await reviewCancelBooking(row.id, { approve: false, reason })
    ElMessage.warning('已拒绝取消申请')
    load()
  } catch (error) {
    ElMessage.error(error.message || '操作失败')
  }
}

onMounted(async () => {
  await loadLabs()
  await load()
})
</script>

<template>
  <section>
    <header class="page-head">
      <div>
        <h2 class="page-head__title">预约审核</h2>
        <p class="page-head__desc">
          冲突的预约会进入「冲突待协调」，由管理员决定保留哪一单；学生 12 小时内的取消申请也会出现在这里。
        </p>
      </div>
    </header>

    <div class="table-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane v-for="tab in tabs" :key="tab.name" :name="tab.name" :label="tab.label" />
      </el-tabs>

      <div class="toolbar">
        <el-select
          v-if="activeTab === 'processed'"
          v-model="processedStatus"
          style="width: 130px"
        >
          <el-option v-for="item in PROCESSED_STATUSES" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="query.labId" placeholder="全部实验室" clearable style="width: 160px">
          <el-option v-for="item in labs" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
        <el-input
          v-model="query.keyword"
          placeholder="搜索预约号 / 申请人 / 用途"
          clearable
          style="width: 260px"
          @keyup.enter="search"
          @clear="search"
        />
        <el-button type="primary" plain @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <span class="toolbar__total">共 {{ total }} 条</span>
      </div>

      <el-table v-loading="loading" :data="rows" stripe>
        <el-table-column prop="code" label="预约号" width="146" />
        <el-table-column prop="labName" label="实验室" min-width="130" />
        <el-table-column label="时间" width="152">
          <template #default="{ row }">{{ row.bookingDate.slice(5) }} {{ row.startTime }}-{{ row.endTime }}</template>
        </el-table-column>
        <el-table-column label="人数 / 类型" width="108">
          <template #default="{ row }">{{ row.peopleCount }} 人 · {{ bookingTypeText(row.bookingType) }}</template>
        </el-table-column>
        <el-table-column prop="userName" label="申请人" width="78" />
        <el-table-column label="设备" min-width="104">
          <template #default="{ row }">
            {{ row.devices.map((item) => item.name).join('、') || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="136">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
            <el-tag v-if="row.cancelRequested && row.status === 'approved'" type="warning" size="small" class="tag-gap">
              取消申请
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="原因 / 备注" width="108">
          <template #default="{ row }">
            <el-popover v-if="bookingReason(row)" placement="left" :width="330" trigger="click">
              <template #reference>
                <el-button link type="primary" size="small">查看</el-button>
              </template>
              <p class="reason-title">{{ row.status === 'conflict' ? '冲突说明' : '原因 / 备注' }}</p>
              <p class="reason-text">{{ bookingReason(row) }}</p>
              <p class="reason-meta">{{ row.code }} · {{ row.labName }} · {{ row.bookingDate }}</p>
            </el-popover>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
            <template v-if="['pending', 'conflict'].includes(row.status)">
              <el-button link type="success" size="small" @click="approve(row)">通过</el-button>
              <el-button link type="danger" size="small" @click="reject(row)">驳回</el-button>
            </template>
            <template v-else-if="row.status === 'approved' && row.cancelRequested">
              <el-button link type="warning" size="small" @click="approveCancel(row)">同意取消</el-button>
              <el-button link type="danger" size="small" @click="rejectCancel(row)">拒绝申请</el-button>
            </template>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty :image-size="64" description="当前分类下暂无预约" />
        </template>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="sizes, prev, pager, next, jumper"
          @size-change="search"
          @current-change="load"
        />
      </div>
    </div>

    <el-drawer v-model="detailVisible" title="预约详情" size="440px">
      <template v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="预约号">{{ detail.code }}</el-descriptions-item>
          <el-descriptions-item label="实验室">{{ detail.labName }}</el-descriptions-item>
          <el-descriptions-item label="时间">
            {{ detail.bookingDate }} {{ detail.startTime }}-{{ detail.endTime }}（{{ detail.durationMinutes }} 分钟）
          </el-descriptions-item>
          <el-descriptions-item label="人数 / 类型">
            {{ detail.peopleCount }} 人 · {{ bookingTypeText(detail.bookingType) }}
          </el-descriptions-item>
          <el-descriptions-item label="申请人">{{ detail.userName }}</el-descriptions-item>
          <el-descriptions-item label="设备">
            {{ detail.devices.map((item) => item.name).join('、') || '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="用途">{{ detail.purpose || '—' }}</el-descriptions-item>
          <el-descriptions-item label="联系人">{{ detail.contactName }} · {{ detail.contactPhone }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(detail.status)" size="small">{{ statusText(detail.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item v-if="bookingReason(detail)" label="原因 / 备注">
            {{ bookingReason(detail) }}
          </el-descriptions-item>
          <el-descriptions-item label="提交时间">
            {{ detail.createTime?.replace('T', ' ').slice(0, 19) }}
          </el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </section>
</template>

<style scoped>
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-head__title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.page-head__desc {
  margin-top: 6px;
  font-size: 13px;
  color: #909399;
}

.table-card {
  padding: 8px 16px 16px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.toolbar__total {
  margin-left: auto;
  font-size: 13px;
  color: #909399;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.muted {
  font-size: 12px;
  color: #c0c4cc;
}

.tag-gap {
  margin-left: 6px;
}

.reason-title {
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.reason-text {
  font-size: 13px;
  line-height: 1.7;
  color: #606266;
  word-break: break-word;
}

.reason-meta {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed #e4e7ed;
  font-size: 12px;
  color: #909399;
}
</style>
