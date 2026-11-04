<script setup>
import { useRouter } from 'vue-router'
import { labs, devices } from '@/mock/data'

const router = useRouter()

function deviceCount(lab) {
  return lab.deviceIds.reduce((sum, id) => {
    const device = devices.find((item) => item.id === id)
    return sum + (device?.count ?? 0)
  }, 0)
}
</script>

<template>
  <section>
    <header class="page-head">
      <div>
        <h2 class="page-head__title">实验室</h2>
        <p class="page-head__desc">共 {{ labs.length }} 间实验室，点击查看设备与使用规则。</p>
      </div>
      <el-button type="primary" plain @click="router.push('/chat')">去对话预约</el-button>
    </header>

    <div class="lab-grid">
      <article
        v-for="lab in labs"
        :key="lab.id"
        class="lab-card"
        @click="router.push(`/labs/${lab.id}`)"
      >
        <h3 class="lab-card__name">{{ lab.name }}</h3>
        <p class="lab-card__desc">{{ lab.description }}</p>

        <dl class="lab-card__meta">
          <div>
            <dt>容纳人数</dt>
            <dd>{{ lab.capacity }} 人</dd>
          </div>
          <div>
            <dt>开放时间</dt>
            <dd>{{ lab.openTime }}</dd>
          </div>
          <div>
            <dt>设备数量</dt>
            <dd>{{ deviceCount(lab) }} 台</dd>
          </div>
        </dl>

        <span class="lab-card__more">查看详情 →</span>
      </article>
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

.lab-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.lab-card {
  padding: 18px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  cursor: pointer;
  transition:
    border-color 0.2s,
    transform 0.2s;
}

.lab-card:hover {
  border-color: #409eff;
  transform: translateY(-2px);
}

.lab-card__name {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.lab-card__desc {
  margin: 6px 0 14px;
  font-size: 12px;
  line-height: 1.6;
  color: #909399;
}

.lab-card__meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0 0 14px;
}

.lab-card__meta div {
  display: flex;
  gap: 8px;
  font-size: 13px;
}

.lab-card__meta dt {
  width: 64px;
  flex: none;
  color: #909399;
}

.lab-card__meta dd {
  margin: 0;
  color: #303133;
}

.lab-card__more {
  font-size: 13px;
  color: #409eff;
}
</style>
