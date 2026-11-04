<template>
  <section class="not-found">
    <p class="not-found__code">404</p>
    <p class="not-found__desc">地址可能输入有误，或者这个页面还没做。</p>
    <el-button type="primary" @click="$router.push('/chat')">回到对话预约</el-button>
  </section>
</template>

<style scoped>
.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  gap: 12px;
}

.not-found__code {
  font-size: 56px;
  font-weight: 700;
  color: #dcdfe6;
}

.not-found__desc {
  font-size: 14px;
  color: #909399;
}
</style>
