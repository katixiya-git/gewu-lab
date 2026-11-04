<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { labs, devices } from '@/mock/data'

const route = useRoute()
const router = useRouter()

const lab = computed(() => labs.find((item) => item.id === Number(route.params.id)))
const labDevices = computed(() => {
  if (!lab.value) return []
  return lab.value.deviceIds
    .map((id) => devices.find((device) => device.id === id))
    .filter(Boolean)
})
</script>

<template>
  <section v-if="lab">
    <el-page-header class="detail-back" @back="router.push('/labs')">
      <template #content>
        <span class="detail-title">{{ lab.name }}</span>
      </template>
    </el-page-header>

    <div class="detail-grid">
      <div class="detail-card">
        <h3 class="detail-card__title">基本信息</h3>
        <dl class="detail-card__meta">
          <div><dt>容纳人数</dt><dd>{{ lab.capacity }} 人</dd></div>
          <div><dt>开放时间</dt><dd>{{ lab.openTime }}</dd></div>
          <div><dt>用途说明</dt><dd>{{ lab.description }}</dd></div>
        </dl>
      </div>

      <div class="detail-card">
        <h3 class="detail-card__title">使用规则</h3>
        <p class="detail-card__rule">{{ lab.rule }}</p>
      </div>
    </div>

    <div class="detail-card">
      <h3 class="detail-card__title">实验设备</h3>
      <el-table :data="labDevices" size="small">
        <el-table-column prop="name" label="设备名称" min-width="140" />
        <el-table-column prop="model" label="型号" min-width="160" />
        <el-table-column prop="count" label="数量" width="80" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === '正常' ? 'success' : 'warning'" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="detail-actions">
      <el-button @click="router.push('/labs')">返回列表</el-button>
      <el-button type="primary" @click="router.push('/chat')">去预约这间实验室</el-button>
    </div>
  </section>

  <el-empty v-else description="实验室不存在">
    <el-button type="primary" @click="router.push('/labs')">返回列表</el-button>
  </el-empty>
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
}

.detail-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
