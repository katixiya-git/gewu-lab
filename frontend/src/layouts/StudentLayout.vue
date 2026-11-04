<script setup>
import AppHeader from '@/components/layout/AppHeader.vue'
import { studentNav } from '@/config/menu'
</script>

<template>
  <div class="student-layout">
    <header class="student-layout__header">
      <AppHeader :nav="studentNav" home="/chat" />
    </header>

    <main class="student-layout__main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.student-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.student-layout__header {
  flex: none;
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  z-index: 10;
}

.student-layout__main {
  flex: 1;
  min-height: 0;
  padding: 20px;
  overflow-y: auto;
  background: #f5f7fa;
}
</style>
