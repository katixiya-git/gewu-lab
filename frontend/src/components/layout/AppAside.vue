<script setup>
import { useRoute } from 'vue-router'
import { adminMenu } from '@/config/menu'

defineProps({
  collapsed: { type: Boolean, default: false }
})

const route = useRoute()
</script>

<template>
  <div class="app-aside">
    <el-menu
      :default-active="route.path"
      :collapse="collapsed"
      :collapse-transition="false"
      router
      class="app-aside__menu"
    >
      <el-menu-item v-for="item in adminMenu" :key="item.path" :index="item.path">
        <el-icon><component :is="item.icon" /></el-icon>
        <template #title>{{ item.title }}</template>
      </el-menu-item>
    </el-menu>

    <div v-if="!collapsed" class="app-aside__footer">格物 · v0.1 开发中</div>
  </div>
</template>

<style scoped>
.app-aside {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  border-right: 1px solid #e4e7ed;
}

.app-aside__menu {
  flex: 1;
  border-right: none;
}

.app-aside__footer {
  padding: 12px 16px;
  font-size: 12px;
  color: #c0c4cc;
  border-top: 1px solid #f2f3f5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
