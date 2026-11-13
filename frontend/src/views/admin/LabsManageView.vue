<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { changeLabStatus, createLab, deleteLab, pageLabs, updateLab } from '@/api/lab'
import {
  LAB_CATEGORY_OPTIONS,
  formatTime,
  labCategoryTagType,
  labCategoryText,
  labStatusTagType,
  labStatusText,
  openTimeText
} from '@/utils/lab'

const loading = ref(false)
const rows = ref([])
const total = ref(0)

const query = reactive({
  page: 1,
  size: 10,
  keyword: '',
  category: '',
  status: ''
})

/** 按当前筛选条件拉取列表 */
async function load() {
  loading.value = true
  try {
    const params = { page: query.page, size: query.size }
    if (query.keyword.trim()) params.keyword = query.keyword.trim()
    if (query.category) params.category = query.category
    if (query.status) params.status = query.status
    const data = await pageLabs(params)
    rows.value = data.items
    total.value = data.total
  } catch (error) {
    ElMessage.error(error.message || '实验室列表加载失败')
  } finally {
    loading.value = false
  }
}

function search() {
  query.page = 1
  load()
}

function reset() {
  query.keyword = ''
  query.category = ''
  query.status = ''
  query.page = 1
  query.size = 10
  load()
}

// ---------------- 新增 / 编辑 ----------------

const dialogVisible = ref(false)
const dialogMode = ref('create')
const submitting = ref(false)
const formRef = ref()
const form = reactive(emptyForm())

function emptyForm() {
  return {
    id: null,
    name: '',
    category: 'ai',
    location: '',
    capacity: 20,
    openDays: '1-5',
    openTime: '08:00:00',
    closeTime: '22:00:00',
    rule: '',
    description: '',
    status: 'enabled',
    sortOrder: 0
  }
}

const rules = {
  name: [{ required: true, message: '请输入实验室名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择实验室类型', trigger: 'change' }],
  capacity: [{ required: true, message: '请输入容纳人数', trigger: 'blur' }],
  openDays: [{ required: true, message: '请选择开放日', trigger: 'change' }],
  openTime: [{ required: true, message: '请选择开放开始时间', trigger: 'change' }],
  closeTime: [{ required: true, message: '请选择开放结束时间', trigger: 'change' }]
}

function openCreate() {
  dialogMode.value = 'create'
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(row) {
  dialogMode.value = 'edit'
  Object.assign(form, emptyForm(), row, {
    openTime: formatTime(row.openTime),
    closeTime: formatTime(row.closeTime)
  })
  // time 字段需要 HH:mm:ss，formatTime 只保留到分，这里补回秒
  if (form.openTime && form.openTime.length === 5) form.openTime += ':00'
  if (form.closeTime && form.closeTime.length === 5) form.closeTime += ':00'
  dialogVisible.value = true
}

async function submit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const payload = {
      name: form.name,
      category: form.category,
      location: form.location,
      capacity: Number(form.capacity),
      openDays: form.openDays,
      openTime: form.openTime,
      closeTime: form.closeTime,
      rule: form.rule || null,
      description: form.description || null,
      status: form.status,
      sortOrder: Number(form.sortOrder)
    }
    if (dialogMode.value === 'create') {
      await createLab(payload)
      ElMessage.success('实验室已创建')
    } else {
      await updateLab(form.id, payload)
      ElMessage.success('实验室已更新')
    }
    dialogVisible.value = false
    load()
  } catch (error) {
    ElMessage.error(error.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

// ---------------- 启停 / 删除 ----------------

async function toggleStatus(row) {
  const next = row.status === 'enabled' ? 'disabled' : 'enabled'
  if (next === 'disabled') {
    const confirmed = await ElMessageBox.confirm(
      `停用后「${row.name}」在学生端将不可见，确定停用？`,
      '停用实验室',
      { type: 'warning', confirmButtonText: '停用', cancelButtonText: '取消' }
    ).catch(() => false)
    if (!confirmed) return
  }
  try {
    await changeLabStatus(row.id, next)
    ElMessage.success(next === 'enabled' ? '已启用' : '已停用')
    load()
  } catch (error) {
    ElMessage.error(error.message || '状态切换失败')
  }
}

async function remove(row) {
  const confirmed = await ElMessageBox.confirm(`确定删除「${row.name}」？删除后不可恢复。`, '删除实验室', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消'
  }).catch(() => false)
  if (!confirmed) return
  try {
    await deleteLab(row.id)
    ElMessage.success('实验室已删除')
    // 删掉当前页最后一条时回补一页
    if (rows.value.length === 1 && query.page > 1) query.page -= 1
    load()
  } catch (error) {
    ElMessage.error(error.message || '删除失败')
  }
}

onMounted(load)
</script>

<template>
  <section>
    <header class="page-head">
      <div>
        <h2 class="page-head__title">实验室管理</h2>
        <p class="page-head__desc">维护实验室的容纳人数、开放时间与使用规则。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增实验室</el-button>
    </header>

    <div class="table-card">
      <div class="toolbar">
        <el-input
          v-model="query.keyword"
          class="toolbar__search"
          placeholder="搜索名称 / 位置"
          clearable
          @keyup.enter="search"
          @clear="search"
        />
        <el-select v-model="query.category" class="toolbar__select" placeholder="全部类型" clearable>
          <el-option
            v-for="item in LAB_CATEGORY_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-select v-model="query.status" class="toolbar__select" placeholder="全部状态" clearable>
          <el-option label="启用" value="enabled" />
          <el-option label="停用" value="disabled" />
        </el-select>
        <el-button type="primary" plain @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <span class="toolbar__total">共 {{ total }} 间</span>
      </div>

      <el-table v-loading="loading" :data="rows" stripe>
        <el-table-column prop="id" label="ID" width="64" />
        <el-table-column label="实验室" min-width="180">
          <template #default="{ row }">
            <div class="cell-main">{{ row.name }}</div>
            <div class="cell-sub">{{ row.location || '未填写位置' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            <el-tag :type="labCategoryTagType(row.category)" size="small">
              {{ labCategoryText(row.category) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="容纳人数" width="100">
          <template #default="{ row }">{{ row.capacity }} 人</template>
        </el-table-column>
        <el-table-column label="开放时间" min-width="200">
          <template #default="{ row }">{{ openTimeText(row) }}</template>
        </el-table-column>
        <el-table-column label="使用规则" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ row.rule || '—' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="labStatusTagType(row.status)" size="small">
              {{ labStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="warning" @click="toggleStatus(row)">
              {{ row.status === 'enabled' ? '停用' : '启用' }}
            </el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.size"
          background
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          :page-sizes="[10, 20, 50]"
          @current-change="load"
          @size-change="search"
        />
      </div>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新增实验室' : '编辑实验室'"
      width="600px"
      top="5vh"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="92px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如：人工智能实验室" maxlength="64" />
        </el-form-item>
        <el-form-item label="类型" prop="category">
          <el-select v-model="form.category" class="full">
            <el-option
              v-for="item in LAB_CATEGORY_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="位置">
          <el-input v-model="form.location" placeholder="如：实验楼 A301" maxlength="128" />
        </el-form-item>
        <el-form-item label="容纳人数" prop="capacity">
          <el-input-number v-model="form.capacity" :min="1" :max="500" />
        </el-form-item>
        <el-form-item label="开放日" prop="openDays">
          <el-select v-model="form.openDays" class="full">
            <el-option label="周一至周五" value="1-5" />
            <el-option label="周一至周六" value="1-6" />
            <el-option label="每天" value="1-7" />
            <el-option label="仅周日" value="7" />
          </el-select>
        </el-form-item>
        <el-form-item label="开放时段" prop="openTime">
          <div class="time-range">
            <el-time-picker
              v-model="form.openTime"
              placeholder="开始时间"
              format="HH:mm"
              value-format="HH:mm:ss"
            />
            <span class="time-range__sep">至</span>
            <el-time-picker
              v-model="form.closeTime"
              placeholder="结束时间"
              format="HH:mm"
              value-format="HH:mm:ss"
            />
          </div>
        </el-form-item>
        <el-form-item label="使用规则">
          <el-input
            v-model="form.rule"
            type="textarea"
            :rows="2"
            maxlength="2000"
            show-word-limit
            placeholder="如：需提前一天预约；离开前关闭电源。"
          />
        </el-form-item>
        <el-form-item label="简介">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            maxlength="2000"
            show-word-limit
            placeholder="一句话介绍实验室的用途。"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio value="enabled">启用</el-radio>
            <el-radio value="disabled">停用</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sortOrder" :min="0" :max="9999" />
          <span class="hint">数字越小越靠前</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">
          {{ dialogMode === 'create' ? '创建' : '保存' }}
        </el-button>
      </template>
    </el-dialog>
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
  gap: 10px;
  margin-bottom: 14px;
}

.toolbar__search {
  width: 240px;
}

.toolbar__select {
  width: 130px;
}

.toolbar__total {
  margin-left: auto;
  font-size: 13px;
  color: #909399;
}

.cell-main {
  font-size: 14px;
  color: #303133;
}

.cell-sub {
  margin-top: 2px;
  font-size: 12px;
  color: #909399;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}

.full {
  width: 100%;
}

.time-range {
  display: flex;
  align-items: center;
  gap: 8px;
}

.time-range :deep(.el-date-editor) {
  width: 124px;
}

.time-range__sep {
  color: #909399;
}

.hint {
  margin-left: 10px;
  font-size: 12px;
  color: #909399;
}
</style>
