<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchLab } from '@/api/lab'
import { formatTime, labCategoryTagType, labCategoryText, openDaysText } from '@/utils/lab'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const lab = ref(null)
const notFound = ref(false)

async function load() {
  loading.value = true
  notFound.value = false
  try {
    lab.value = await fetchLab(route.params.id)
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
        <el-empty :image-size="72" description="设备管理模块开发中，可先到对话里说明所需设备" />
      </div>

      <div class="detail-actions">
        <el-button @click="router.push('/labs')">返回列表</el-button>
        <el-button type="primary" @click="router.push('/chat')">去预约这间实验室</el-button>
      </div>
    </template>

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
