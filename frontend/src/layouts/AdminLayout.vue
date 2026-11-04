<script setup>
import { ref } from 'vue'
import AppHeader from '@/components/layout/AppHeader.vue'
import AppAside from '@/components/layout/AppAside.vue'

const collapsed = ref(false)
</script>

<template>
  <el-container class="admin-layout">
    <el-header class="admin-layout__header" height="56px">
      <AppHeader
        v-model:collapsed="collapsed"
        toggleable
        home="/admin/reviews"
        user-name="陈管理员"
        role-text="管理员"
      />
    </el-header>

    <el-container class="admin-layout__body">
      <el-aside class="admin-layout__aside" :width="collapsed ? '64px' : '208px'">
        <AppAside :collapsed="collapsed" />
      </el-aside>

      <el-main class="admin-layout__main">
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.admin-layout {
  height: 100vh;
}

.admin-layout__header {
  padding: 0;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  z-index: 10;
}

.admin-layout__body {
  min-height: 0;
}

.admin-layout__aside {
  background: #fff;
  transition: width 0.2s;
  overflow: hidden;
}

.admin-layout__main {
  padding: 20px;
  background: #f5f7fa;
  overflow-y: auto;
}
</style>
