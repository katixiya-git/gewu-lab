<script setup>
import { ElMessage } from 'element-plus'
import { labs } from '@/mock/data'

function todo() {
  ElMessage.info('增删改接口待接后端')
}
</script>

<template>
  <section>
    <header class="page-head">
      <div>
        <h2 class="page-head__title">实验室管理</h2>
        <p class="page-head__desc">维护实验室的容纳人数、开放时间与使用规则。</p>
      </div>
      <el-button type="primary" @click="todo">新增实验室</el-button>
    </header>

    <div class="table-card">
      <el-table :data="labs" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="实验室名称" min-width="150" />
        <el-table-column prop="capacity" label="容纳人数" width="100" />
        <el-table-column prop="openTime" label="开放时间" min-width="180" />
        <el-table-column prop="rule" label="使用规则" min-width="260" show-overflow-tooltip />
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
