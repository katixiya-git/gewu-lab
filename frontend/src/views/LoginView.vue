<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <h1 class="login-card__title">格物 · 实验室智能预约</h1>
      <p class="login-card__desc">选择入口进入（登录接口未接入，先按角色预览）</p>

      <div class="login-card__entries">
        <button class="entry entry--student" @click="router.push('/chat')">
          <span class="entry__icon">学</span>
          <span class="entry__title">学生入口</span>
          <span class="entry__desc">对话预约 · 查看实验室 · 我的预约</span>
        </button>

        <button class="entry entry--admin" @click="router.push('/admin/reviews')">
          <span class="entry__icon">管</span>
          <span class="entry__title">管理员入口</span>
          <span class="entry__desc">预约审核 · 实验室 / 设备 / 用户管理</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(160deg, #eef5ff 0%, #f7f9fc 55%, #eef7f2 100%);
}

.login-card {
  width: 720px;
  padding: 40px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 30px rgb(31 45 61 / 8%);
  text-align: center;
}

.login-card__title {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.login-card__desc {
  margin: 10px 0 32px;
  font-size: 13px;
  color: #909399;
}

.login-card__entries {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.entry {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 20px;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  background: #fafcff;
  cursor: pointer;
  text-align: left;
  transition:
    border-color 0.2s,
    transform 0.2s;
}

.entry:hover {
  border-color: #409eff;
  transform: translateY(-2px);
}

.entry__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  margin-bottom: 4px;
  border-radius: 8px;
  background: #409eff;
  color: #fff;
  font-size: 16px;
}

.entry--admin .entry__icon {
  background: #67c23a;
}

.entry__title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.entry__desc {
  font-size: 12px;
  color: #909399;
}
</style>
