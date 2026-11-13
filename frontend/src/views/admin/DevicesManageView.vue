<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  changeDeviceStatus,
  createDevice,
  deleteDevice,
  pageDevices,
  updateDevice
} from '@/api/device'
import { pageLabs } from '@/api/lab'
import { DEVICE_STATUS_OPTIONS, deviceStatusTagType, deviceStatusText } from '@/utils/device'

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const labOptions = ref([])

const query = reactive({
  page: 1,
  size: 10,
  keyword: '',
  labId: '',
  status: ''
})

/** 拉取实验室下拉选项（管理员能看到全部，包括停用的） */
async function loadLabs() {
  try {
    const data = await pageLabs({ page: 1, size: 50 })
    labOptions.value = data.items
  } catch (error) {
    ElMessage.error(error.message || '实验室列表加载失败')
  }
}

/** 按当前筛选条件拉取设备列表 */
async function load() {
  loading.value = true
  try {
    const params = { page: query.page, size: query.size }
    if (query.keyword.trim()) params.keyword = query.keyword.trim()
    if (query.labId) params.labId = query.labId
    if (query.status) params.status = query.status
    const data = await pageDevices(params)
    rows.value = data.items
    total.value = data.total
  } catch (error) {
    ElMessage.error(error.message || '设备列表加载失败')
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
  query.labId = ''
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
    labId: null,
    name: '',
    model: '',
    totalCount: 1,
    status: 'normal',
    note: '',
    sortOrder: 0
  }
}

const rules = {
  labId: [{ required: true, message: '请选择所属实验室', trigger: 'change' }],
  name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }],
  totalCount: [{ required: true, message: '请输入数量', trigger: 'blur' }]
}

function openCreate() {
  dialogMode.value = 'create'
  Object.assign(form, emptyForm())
  if (labOptions.value.length === 1) form.labId = labOptions.value[0].id
  dialogVisible.value = true
}

function openEdit(row) {
  dialogMode.value = 'edit'
  Object.assign(form, emptyForm(), row, {
    model: row.model ?? '',
    note: row.note ?? ''
  })
  dialogVisible.value = true
}

async function submit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const payload = {
      labId: Number(form.labId),
      name: form.name,
      model: form.model || null,
      totalCount: Number(form.totalCount),
      status: form.status,
      note: form.note || null,
      sortOrder: Number(form.sortOrder)
    }
    if (dialogMode.value === 'create') {
      await createDevice(payload)
      ElMessage.success('设备已创建')
    } else {
      await updateDevice(form.id, payload)
      ElMessage.success('设备已更新')
    }
    dialogVisible.value = false
    load()
  } catch (error) {
    ElMessage.error(error.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

// ---------------- 状态 / 删除 ----------------

async function setStatus(row, status) {
  if (status === row.status) return
  const label = DEVICE_STATUS_OPTIONS.find((item) => item.value === status)?.label ?? status
  const confirmed = await ElMessageBox.confirm(
    `确定把「${row.name}」切换为「${label}」？`,
    '切换设备状态',
    { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
  ).catch(() => false)
  if (!confirmed) return
  try {
    await changeDeviceStatus(row.id, status)
    ElMessage.success(`已切换为「${label}」`)
    load()
  } catch (error) {
    ElMessage.error(error.message || '状态切换失败')
  }
}

async function remove(row) {
  const confirmed = await ElMessageBox.confirm(`确定删除「${row.name}」？删除后不可恢复。`, '删除设备', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消'
  }).catch(() => false)
  if (!confirmed) return
  try {
    await deleteDevice(row.id)
    ElMessage.success('设备已删除')
    if (rows.value.length === 1 && query.page > 1) query.page -= 1
    load()
  } catch (error) {
    ElMessage.error(error.message || '删除失败')
  }
}

onMounted(() => {
  loadLabs()
  load()
})
</script>

<template>
  <section>
    <header class="page-head">
      <div>
        <h2 class="page-head__title">设备管理</h2>
        <p class="page-head__desc">维护各实验室下的设备型号、数量与可用状态。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增设备</el-button>
    </header>

    <div class="table-card">
      <div class="toolbar">
        <el-input
          v-model="query.keyword"
          class="toolbar__search"
          placeholder="搜索设备名 / 型号 / 备注"
          clearable
          @keyup.enter="search"
          @clear="search"
        />
        <el-select v-model="query.labId" class="toolbar__select" placeholder="全部实验室" clearable>
          <el-option v-for="lab in labOptions" :key="lab.id" :label="lab.name" :value="lab.id" />
        </el-select>
        <el-select v-model="query.status" class="toolbar__select" placeholder="全部状态" clearable>
          <el-option
            v-for="item in DEVICE_STATUS_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-button type="primary" plain @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
        <span class="toolbar__total">共 {{ total }} 台</span>
      </div>

      <el-table v-loading="loading" :data="rows" stripe>
        <el-table-column prop="id" label="ID" width="64" />
        <el-table-column label="设备" min-width="190">
          <template #default="{ row }">
            <div class="cell-main">{{ row.name }}</div>
            <div class="cell-sub">{{ row.model || '未填写型号' }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="labName" label="所属实验室" min-width="150" />
        <el-table-column label="数量" width="90">
          <template #default="{ row }">{{ row.totalCount }} 台</template>
        </el-table-column>
        <el-table-column label="状态" width="96">
          <template #default="{ row }">
            <el-tag :type="deviceStatusTagType(row.status)" size="small">
              {{ deviceStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.note || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <div class="ops">
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-dropdown trigger="click" @command="(status) => setStatus(row, status)">
                <el-button link type="warning">状态</el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item
                      v-for="item in DEVICE_STATUS_OPTIONS"
                      :key="item.value"
                      :command="item.value"
                      :disabled="row.status === item.value"
                    >
                      {{ item.label }}
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-button link type="danger" @click="remove(row)">删除</el-button>
            </div>
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
      :title="dialogMode === 'create' ? '新增设备' : '编辑设备'"
      width="560px"
      top="8vh"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
        <el-form-item label="所属实验室" prop="labId">
          <el-select v-model="form.labId" class="full" placeholder="请选择实验室">
            <el-option v-for="lab in labOptions" :key="lab.id" :label="lab.name" :value="lab.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备名称" prop="name">
          <el-input v-model="form.name" placeholder="如：GPU 服务器" maxlength="64" />
        </el-form-item>
        <el-form-item label="型号">
          <el-input v-model="form.model" placeholder="如：NVIDIA A100 × 4" maxlength="64" />
        </el-form-item>
        <el-form-item label="数量" prop="totalCount">
          <el-input-number v-model="form.totalCount" :min="1" :max="999" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio v-for="item in DEVICE_STATUS_OPTIONS" :key="item.value" :value="item.value">
              {{ item.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="form.note"
            type="textarea"
            :rows="2"
            maxlength="255"
            show-word-limit
            placeholder="如：需两人在场；使用前找管理员登记。"
          />
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
  width: 150px;
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

.hint {
  margin-left: 10px;
  font-size: 12px;
  color: #909399;
}

.ops {
  display: flex;
  align-items: center;
  gap: 12px;
}

.ops :deep(.el-button + .el-button) {
  margin-left: 0;
}
</style>
