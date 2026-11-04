<script setup>
import { ElMessage } from 'element-plus'
import { devices, labs } from '@/mock/data'

function labName(labId) {
  return labs.find((lab) => lab.id === labId)?.name ?? '—'
}

function todo() {
  ElMessage.info('增删改接口待接后端')
}
</script>

<template>
  <section>
    <header class="page-head">
      <div>
        <h2 class="page-head__title">设备管理</h2>
        <p class="page-head__desc">维护各实验室下的设备型号、数量与可用状态。</p>
      </div>
      <el-button type="primary" @click="todo">新增设备</el-button>
    </header>

    <div class="table-card">
      <el-table :data="devices" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="设备名称" min-width="150" />
        <el-table-column label="所属实验室" min-width="150">
          <template #default="{ row }">{{ labName(row.labId) }}</template>
        </el-table-column>
        <el-table-column prop="model" label="型号" min-width="160" />
        <el-table-column prop="count" label="数量" width="80" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === '正常' ? 'success' : 'warning'" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default>
            <el-button link type="primary" @click="todo">编辑</el-button>
            <el-button link type="danger" @click="todo">删除</el-button>
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
