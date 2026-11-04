<script setup>
import { ElMessage } from 'element-plus'
import { users } from '@/mock/data'

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
      <el-table :data="users" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="姓名" min-width="120" />
        <el-table-column prop="role" label="角色" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.role === '管理员' ? 'danger' : 'info'">
              {{ row.role }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="account" label="账号" min-width="130" />
        <el-table-column prop="phone" label="手机号" min-width="130" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === '正常' ? 'success' : 'info'">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
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
</style>
