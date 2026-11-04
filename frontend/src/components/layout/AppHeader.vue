<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDown, Bell, Expand, Fold } from '@element-plus/icons-vue'
import { notices } from '@/mock/data'

const props = defineProps({
  nav: { type: Array, default: () => [] },
  home: { type: String, default: '/chat' },
  userName: { type: String, default: '学生账号' },
  roleText: { type: String, default: '学生' },
  toggleable: { type: Boolean, default: false },
  collapsed: { type: Boolean, default: false }
})

const emit = defineEmits(['update:collapsed'])
const router = useRouter()

const unreadCount = computed(() => notices.filter((item) => !item.read).length)

function toggle() {
  emit('update:collapsed', !props.collapsed)
}

function logout() {
  router.push('/login')
}
</script>

<template>
  <div class="app-header">
    <div class="app-header__left">
      <el-button
        v-if="toggleable"
        text
        class="app-header__toggle"
        :title="collapsed ? '展开菜单' : '收起菜单'"
        @click="toggle"
      >
        <el-icon :size="18"><component :is="collapsed ? Expand : Fold" /></el-icon>
      </el-button>

      <RouterLink class="app-header__brand" :to="home">
        <span class="app-header__mark">格物</span>
        <span class="app-header__sub">实验室智能预约</span>
      </RouterLink>

      <nav v-if="nav.length" class="app-header__nav">
        <RouterLink v-for="item in nav" :key="item.path" :to="item.path">{{ item.title }}</RouterLink>
      </nav>
    </div>

    <div class="app-header__right">
      <el-popover placement="bottom-end" :width="300" trigger="click">
        <template #reference>
          <el-badge :value="unreadCount" :hidden="unreadCount === 0" class="app-header__bell">
            <el-icon :size="18"><Bell /></el-icon>
          </el-badge>
        </template>

        <div class="notice-list">
          <div v-for="item in notices" :key="item.id" class="notice-item">
            <span class="notice-item__dot" :class="{ 'is-read': item.read }" />
            <div class="notice-item__body">
              <p class="notice-item__title">{{ item.title }}</p>
              <p class="notice-item__time">{{ item.time }}</p>
            </div>
          </div>
        </div>
      </el-popover>

      <el-dropdown>
        <span class="app-header__user">
          <el-avatar :size="28">{{ userName.slice(0, 1) }}</el-avatar>
          <span class="app-header__name">{{ userName }}</span>
          <el-icon><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item disabled>{{ roleText }} · 个人设置待接</el-dropdown-item>
            <el-dropdown-item divided @click="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  padding: 0 16px 0 8px;
}

.app-header__left,
.app-header__right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.app-header__brand {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.app-header__mark {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 2px;
  color: #303133;
}

.app-header__sub {
  font-size: 12px;
  color: #909399;
}

.app-header__nav {
  display: flex;
  gap: 4px;
  margin-left: 16px;
}

.app-header__nav a {
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 14px;
  color: #606266;
}

.app-header__nav a:hover {
  background: #f5f7fa;
}

.app-header__nav a.router-link-active {
  color: #409eff;
  background: #ecf5ff;
}

.app-header__bell {
  cursor: pointer;
  color: #606266;
}

.app-header__user {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #606266;
}

.app-header__name {
  font-size: 13px;
}

.notice-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.notice-item {
  display: flex;
  gap: 8px;
}

.notice-item__dot {
  width: 6px;
  height: 6px;
  margin-top: 6px;
  border-radius: 50%;
  background: #409eff;
  flex: none;
}

.notice-item__dot.is-read {
  background: #dcdfe6;
}

.notice-item__title {
  font-size: 13px;
  line-height: 1.5;
  color: #303133;
}

.notice-item__time {
  font-size: 12px;
  color: #909399;
}
</style>
