<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  cancelBooking,
  pageBookings,
  requestCancelBooking
} from '@/api/booking'
import {
  bookingReason,
  bookingTypeText,
  canCancelDirectly,
  needsCancelRequest,
  statusTagType,
  statusText
} from '@/utils/booking'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const detail = ref(null)
const detailVisible = ref(false)

const query = reactive({
  page: 1,
  size: 10,
  status: '',
  keyword: ''
})

const STATUS_FILTERS = [
  { value: '', label: '全部状态' },
  { value: 'pending', label: '待审核' },
  { value: 'approved', label: '已通过' },
  { value: 'conflict', label: '冲突待协调' },
  { value: 'rejected', label: '已驳回' },
  { value: 'cancelled', label: '已取消' }
]

async function load() {
  loading.value = true
  try {
    const data = await pageBookings({
      page: query.page,
      size: query.size,
      status: query.status || undefined,
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
  query.status = ''
  query.keyword = ''
  query.page = 1
  load()
}

function openDetail(row) {
  detail.value = row
  detailVisible.value = true
}

/** 取消 / 申请取消共用的理由输入框 */
async function askReason(title, placeholder) {
  try {
    const { value } = await ElMessageBox.prompt('理由可以不填，管理员会在审核记录里看到。', title, {
      inputPlaceholder: placeholder,
      confirmButtonText: '提交',
      cancelButtonText: '先不提交'
    })
    return value ?? ''
  } catch {
    return null
  }
}

async function cancelDirectly(row) {
  const reason = await askReason(`取消预约 ${row.code}`, '例如：临时有事，不再使用')
  if (reason === null) return
  try {
    await cancelBooking(row.id, reason || null)
    ElMessage.success('预约已取消')
    load()
  } catch (error) {
    ElMessage.error(error.message || '取消失败')
  }
}

async function requestCancel(row) {
  const reason = await askReason(`申请取消 ${row.code}`, '例如：课程临时调整，申请取消')
  if (reason === null) return
  try {
    await requestCancelBooking(row.id, reason || null)
    ElMessage.success('取消申请已提交，等待管理员处理')
    load()
  } catch (error) {
    ElMessage.error(error.message || '提交失败')
  }
}

function rebook(row) {
  window.location.href = `/labs/${row.labId}`
}

onMounted(load)
</script>

<template>
  <section>
    <header class="page-head">
      <div>
        <h2 class="page-head__title">我的预约</h2>
        <p class="page-head__desc">
          开始前 12 小时内不能直接取消「已通过」的预约，需要提交取消申请由管理员处理。
        </p>
      </div>
      <el-button type="primary" plain @click="$router.push('/labs')">新建预约</el-button>
    </header>

    <div class="table-card">
      <div class="toolbar">
        <el-select v-model="query.status" placeholder="全部状态" style="width: 140px" @change="search">
          <el-option v-for="item in STATUS_FILTERS" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-input
          v-model="query.keyword"
          placeholder="搜索预约号 / 实验室 / 用途"
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
        <el-table-column prop="code" label="预约号" width="158" />
        <el-table-column prop="labName" label="实验室" min-width="120" />
        <el-table-column label="时间" min-width="186">
          <template #default="{ row }">
            {{ row.bookingDate }} {{ row.startTime }}-{{ row.endTime }}
          </template>
        </el-table-column>
        <el-table-column label="人数 / 类型" width="106">
          <template #default="{ row }">{{ row.peopleCount }} 人 · {{ bookingTypeText(row.bookingType) }}</template>
        </el-table-column>
        <el-table-column label="设备" min-width="130">
          <template #default="{ row }">
            {{ row.devices.map((item) => item.name).join('、') || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="150">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
            <el-tag v-if="row.cancelRequested && row.status === 'approved'" type="warning" size="small" class="tag-gap">
              取消申请待处理
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="原因 / 备注" min-width="150">
          <template #default="{ row }">
            <el-popover v-if="bookingReason(row)" placement="left" :width="320" trigger="click">
              <template #reference>
                <el-button link type="primary" size="small">查看</el-button>
              </template>
              <p class="reason-title">{{ row.status === 'conflict' ? '冲突说明' : '原因 / 备注' }}</p>
              <p class="reason-text">{{ bookingReason(row) }}</p>
            </el-popover>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="188">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
            <template v-if="canCancelDirectly(row)">
              <el-button link type="danger" size="small" @click="cancelDirectly(row)">取消预约</el-button>
            </template>
            <template v-else-if="needsCancelRequest(row)">
              <el-button link type="warning" size="small" @click="requestCancel(row)">申请取消</el-button>
            </template>
            <template v-else-if="row.status === 'rejected'">
              <el-button link type="primary" size="small" @click="rebook(row)">重新发起</el-button>
            </template>
            <span v-else-if="row.cancelRequested" class="muted">等待管理员</span>
            <span v-else-if="row.status === 'conflict'" class="muted">等待协调</span>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty :image-size="64" description="还没有预约记录" />
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

    <el-drawer v-model="detailVisible" title="预约详情" size="420px">
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
          <el-descriptions-item label="提交时间">{{ detail.createTime?.replace('T', ' ').slice(0, 19) }}</el-descriptions-item>
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
  padding: 16px;
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
</style>
