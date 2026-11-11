<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { users } from '@/mock/data'
import {
  roleTagType,
  roleText,
  userStatusTagType,
  userStatusText
} from '@/utils/dict'

const keyword = ref('')

const rows = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return users
  return users.filter((u) =>
    [u.username, u.name, u.phone, u.email].some((v) => (v ?? '').toLowerCase().includes(kw))
  )
})

function initial(name) {
  return (name ?? '?').slice(0, 1)
}

function todo() {
  ElMessage.info('增删改接口待接后端')
}
</script>

<template>
  <section>
    <header class="page-head">
      <div>
        <h2 class="page-head__title">用户管理</h2>
        <p class="page-head__desc">维护学生、教师与管理员账号及其状态。</p>
      </div>
      <el-button type="primary" @click="todo">新增用户</el-button>
    </header>

    <div class="table-card">
      <div class="toolbar">
        <el-input
          v-model="keyword"
          placeholder="搜索用户名 / 姓名 / 手机号 / 邮箱"
          clearable
          style="width: 320px"
        />
        <span class="toolbar__count">共 {{ rows.length }} 人</span>
      </div>

      <el-table :data="rows" stripe>
        <el-table-column prop="id" label="ID" width="70" />

        <el-table-column label="用户" min-width="180">
          <template #default="{ row }">
            <div class="user-cell">
              <el-avatar :size="28" :src="row.avatar ?? undefined">
                {{ initial(row.name) }}
              </el-avatar>
              <div class="user-cell__text">
                <span class="user-cell__name">{{ row.name }}</span>
                <span class="user-cell__account">@{{ row.username }}</span>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="角色" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="roleTagType(row.role)">{{ roleText(row.role) }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="phone" label="手机号" min-width="130">
          <template #default="{ row }">{{ row.phone ?? '—' }}</template>
        </el-table-column>

        <el-table-column prop="email" label="邮箱" min-width="180">
          <template #default="{ row }">{{ row.email ?? '—' }}</template>
        </el-table-column>

        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="userStatusTagType(row.status)">
              {{ userStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="createTime" label="创建时间" width="170" />

        <el-table-column label="操作" width="150">
          <template #default>
            <el-button link type="primary" @click="todo">编辑</el-button>
            <el-button link type="warning" @click="todo">停用</el-button>
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

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.toolbar__count {
  font-size: 13px;
  color: #909399;
}

.user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-cell__text {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}

.user-cell__name {
  font-size: 14px;
  color: #303133;
}

.user-cell__account {
  font-size: 12px;
  color: #a8abb2;
}
</style>
