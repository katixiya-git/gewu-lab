<script setup>
import { ElMessage } from 'element-plus'
import { bookings } from '@/mock/data'
import { statusTagType, statusText } from '@/utils/status'

function canDirectCancel(row) {
  return ['pending', 'approved'].includes(row.status) && row.hoursUntilStart > 12
}

function needsCancelRequest(row) {
  return ['pending', 'approved'].includes(row.status) && row.hoursUntilStart <= 12
}

function cancelDirect(row) {
  ElMessage.success(`已取消 ${row.id}（演示数据，不落库）`)
}

function requestCancel(row) {
  ElMessage.info(`已把取消申请发给管理员：${row.id}`)
}

function rebook(row) {
  ElMessage.info(`将 ${row.labName} 的原预约信息带入对话（待接后端）`)
}
</script>

<template>
  <section>
    <header class="page-head">
      <div>
        <h2 class="page-head__title">我的预约</h2>
        <p class="page-head__desc">
          开始前 12 小时内不能直接取消，需要提交取消申请由管理员处理。
        </p>
      </div>
      <el-button type="primary" plain @click="$router.push('/chat')">新建预约</el-button>
    </header>

    <div class="table-card">
      <el-table :data="bookings" stripe>
        <el-table-column prop="id" label="预约号" width="170" />
        <el-table-column prop="labName" label="实验室" min-width="130" />
        <el-table-column label="时间" min-width="170">
          <template #default="{ row }">{{ row.date }} {{ row.start }}-{{ row.end }}</template>
        </el-table-column>
        <el-table-column label="人数 / 类型" width="110">
          <template #default="{ row }">{{ row.people }} 人 · {{ row.type }}</template>
        </el-table-column>
        <el-table-column label="设备" min-width="160">
          <template #default="{ row }">{{ row.devices.join('、') }}</template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <template v-if="canDirectCancel(row)">
              <el-button link type="danger" @click="cancelDirect(row)">取消预约</el-button>
            </template>
            <template v-else-if="needsCancelRequest(row)">
              <el-button link type="warning" @click="requestCancel(row)">申请取消</el-button>
            </template>
            <template v-else-if="row.status === 'rejected'">
              <el-button link type="primary" @click="rebook(row)">重新发起</el-button>
            </template>
            <span v-else-if="row.status === 'conflict'" class="muted">等待管理员协调</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
      </el-table>
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
  padding: 16px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
}

.muted {
  font-size: 12px;
  color: #c0c4cc;
}
</style>
