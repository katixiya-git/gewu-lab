<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { bookings } from '@/mock/data'
import { statusTagType, statusText } from '@/utils/status'

const route = useRoute()
const activeTab = ref(route.query.tab === 'conflict' ? 'conflict' : 'pending')

const tabs = [
  { name: 'pending', label: '待审核' },
  { name: 'conflict', label: '冲突待协调' },
  { name: 'processed', label: '已处理' }
]

const filtered = computed(() => {
  if (activeTab.value === 'processed') {
    return bookings.filter((row) => ['approved', 'rejected', 'cancelled'].includes(row.status))
  }
  return bookings.filter((row) => row.status === activeTab.value)
})

function approve(row) {
  ElMessage.success(`已通过 ${row.id}（演示数据，不落库）`)
}

async function reject(row) {
  try {
    const { value } = await ElMessageBox.prompt('请填写驳回理由，学生会看到这条理由', '驳回预约', {
      inputPlaceholder: '例如：人数超过容纳上限，请调整后重新提交',
      inputValidator: (text) => (text && text.trim() ? true : '驳回理由不能为空')
    })
    ElMessage.warning(`已驳回 ${row.id}：${value}`)
  } catch {
    // 用户取消，不处理
  }
}
</script>

<template>
  <section>
    <header class="page-head">
      <div>
        <h2 class="page-head__title">预约审核</h2>
        <p class="page-head__desc">冲突的预约会进入「冲突待协调」，由管理员决定保留哪一单。</p>
      </div>
    </header>

    <div class="table-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane v-for="tab in tabs" :key="tab.name" :name="tab.name" :label="tab.label" />
      </el-tabs>

      <el-table :data="filtered" stripe>
        <el-table-column prop="id" label="预约号" width="158" />
        <el-table-column prop="labName" label="实验室" min-width="130" />
        <el-table-column label="时间" min-width="196">
          <template #default="{ row }">{{ row.date }} {{ row.start }}-{{ row.end }}</template>
        </el-table-column>
        <el-table-column label="人数 / 类型" width="110">
          <template #default="{ row }">{{ row.people }} 人 · {{ row.type }}</template>
        </el-table-column>
        <el-table-column prop="applicant" label="申请人" width="90" />
        <el-table-column label="设备" min-width="140">
          <template #default="{ row }">{{ row.devices.join('、') }}</template>
        </el-table-column>
        <el-table-column label="冲突原因" width="112">
          <template #default="{ row }">
            <el-popover v-if="row.reason" placement="left" :width="340" trigger="click">
              <template #reference>
                <el-button
                  link
                  size="small"
                  :type="row.status === 'conflict' ? 'warning' : 'primary'"
                >
                  查看原因
                </el-button>
              </template>
              <div class="reason-pop">
                <p class="reason-pop__title">
                  {{ row.status === 'conflict' ? '冲突原因' : '备注' }}
                </p>
                <p class="reason-pop__text">{{ row.reason }}</p>
                <p class="reason-pop__meta">{{ row.id }} · {{ row.labName }} · {{ row.date }}</p>
              </div>
            </el-popover>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <template v-if="['pending', 'conflict'].includes(row.status)">
              <el-button link type="success" @click="approve(row)">通过</el-button>
              <el-button link type="danger" @click="reject(row)">驳回</el-button>
            </template>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="filtered.length === 0" description="暂无数据" />
    </div>
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

.muted {
  font-size: 12px;
  color: #c0c4cc;
}

.reason-pop__title {
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.reason-pop__text {
  font-size: 13px;
  line-height: 1.7;
  color: #606266;
  word-break: break-word;
}

.reason-pop__meta {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed #e4e7ed;
  font-size: 12px;
  color: #909399;
}
</style>
