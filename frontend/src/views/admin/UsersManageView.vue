<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createUser, deleteUser, pageUsers, updateUser } from '@/api/user'
import { roleTagType, roleText, userStatusTagType, userStatusText } from '@/utils/dict'

const loading = ref(false)
const rows = ref([])
const total = ref(0)

const query = reactive({
  page: 1,
  size: 10,
  keyword: '',
  role: '',
  status: ''
})

const roleOptions = [
  { value: 'student', label: '学生' },
  { value: 'admin', label: '管理员' }
]

const statusOptions = [
  { value: 'active', label: '正常' },
  { value: 'disabled', label: '停用' }
]

async function fetchList() {
  loading.value = true
  try {
    const data = await pageUsers({
      page: query.page,
      size: query.size,
      keyword: query.keyword.trim() || undefined,
      role: query.role || undefined,
      status: query.status || undefined
    })
    rows.value = data.items ?? []
    total.value = data.total ?? 0
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  fetchList()
}

function handleReset() {
  query.keyword = ''
  query.role = ''
  query.status = ''
  query.page = 1
  fetchList()
}

function handlePageChange(page) {
  query.page = page
  fetchList()
}

function handleSizeChange(size) {
  query.size = size
  query.page = 1
  fetchList()
}

function initial(name) {
  return (name ?? '?').slice(0, 1)
}

function formatTime(value) {
  if (!value) return '—'
  return String(value).replace('T', ' ').slice(0, 19)
}

// ------- 新增 / 编辑弹框 -------
const dialogVisible = ref(false)
const dialogMode = ref('create')
const submitting = ref(false)
const formRef = ref()
const editingId = ref(null)

const emptyForm = () => ({
  username: '',
  name: '',
  password: '123456',
  role: 'student',
  status: 'active',
  phone: '',
  email: ''
})

const form = reactive(emptyForm())

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 32, message: '长度 3–32 位', trigger: 'blur' },
    { pattern: /^[A-Za-z0-9_]+$/, message: '只能包含字母、数字、下划线', trigger: 'blur' }
  ],
  name: [
    { required: true, message: '请输入姓名', trigger: 'blur' },
    { max: 32, message: '最多 32 个字符', trigger: 'blur' }
  ],
  password: [{ min: 6, max: 64, message: '长度 6–64 位', trigger: 'blur' }],
  phone: [{ pattern: /^1[3-9]\d{9}$/, message: '请输入 11 位手机号', trigger: 'blur' }],
  email: [{ type: 'email', message: '邮箱格式不正确', trigger: 'blur' }]
}

function resetForm() {
  Object.assign(form, emptyForm())
  formRef.value?.clearValidate()
}

function openCreate() {
  dialogMode.value = 'create'
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row) {
  dialogMode.value = 'edit'
  editingId.value = row.id
  Object.assign(form, {
    username: row.username,
    name: row.name,
    password: '',
    role: row.role,
    status: row.status,
    phone: row.phone ?? '',
    email: row.email ?? ''
  })
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

async function submitForm() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const payload = {
      name: form.name,
      role: form.role,
      status: form.status,
      phone: form.phone || null,
      email: form.email || null
    }

    if (dialogMode.value === 'create') {
      await createUser({
        ...payload,
        username: form.username,
        password: form.password || '123456'
      })
      ElMessage.success('用户已创建')
    } else {
      await updateUser(editingId.value, payload)
      ElMessage.success('用户信息已更新')
    }

    dialogVisible.value = false
    fetchList()
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    submitting.value = false
  }
}

// ------- 停用 / 启用 / 删除 -------
async function toggleStatus(row) {
  const next = row.status === 'active' ? 'disabled' : 'active'
  const action = next === 'disabled' ? '停用' : '启用'

  try {
    await ElMessageBox.confirm(`确定${action}用户「${row.name}」吗？`, `${action}用户`, {
      type: 'warning',
      confirmButtonText: `确定${action}`,
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  try {
    await updateUser(row.id, { status: next })
    ElMessage.success(`已${action}`)
    fetchList()
  } catch (error) {
    ElMessage.error(error.message)
  }
}

async function removeUser(row) {
  try {
    await ElMessageBox.confirm(
      `删除后该用户的登录账号将不可恢复，确定删除「${row.name}」吗？`,
      '删除用户',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }

  try {
    await deleteUser(row.id)
    ElMessage.success('用户已删除')
    if (rows.value.length === 1 && query.page > 1) query.page -= 1
    fetchList()
  } catch (error) {
    ElMessage.error(error.message)
  }
}

onMounted(fetchList)
</script>

<template>
  <section>
    <header class="page-head">
      <div>
        <h2 class="page-head__title">用户管理</h2>
        <p class="page-head__desc">维护学生、教师与管理员账号及其状态。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增用户</el-button>
    </header>

    <div class="table-card">
      <div class="toolbar">
        <div class="toolbar__filters">
          <el-input
            v-model="query.keyword"
            placeholder="搜索用户名 / 姓名 / 手机号 / 邮箱"
            clearable
            style="width: 300px"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          />
          <el-select
            v-model="query.role"
            placeholder="角色"
            clearable
            style="width: 110px"
            @change="handleSearch"
          >
            <el-option
              v-for="item in roleOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <el-select
            v-model="query.status"
            placeholder="状态"
            clearable
            style="width: 110px"
            @change="handleSearch"
          >
            <el-option
              v-for="item in statusOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
          <el-button type="primary" plain @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </div>
        <span class="toolbar__count">共 {{ total }} 人</span>
      </div>

      <el-table v-loading="loading" :data="rows" stripe row-key="id">
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

        <el-table-column label="手机号" min-width="130">
          <template #default="{ row }">{{ row.phone ?? '—' }}</template>
        </el-table-column>

        <el-table-column label="邮箱" min-width="180">
          <template #default="{ row }">{{ row.email ?? '—' }}</template>
        </el-table-column>

        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="userStatusTagType(row.status)">
              {{ userStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.createTime) }}</template>
        </el-table-column>

        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button
              link
              :type="row.status === 'active' ? 'warning' : 'success'"
              @click="toggleStatus(row)"
            >
              {{ row.status === 'active' ? '停用' : '启用' }}
            </el-button>
            <el-button link type="danger" @click="removeUser(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="sizes, prev, pager, next, jumper"
          background
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogMode === 'create' ? '新增用户' : '编辑用户'"
      width="480px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            :disabled="dialogMode === 'edit'"
            placeholder="字母、数字或下划线，3–32 位"
          />
        </el-form-item>

        <el-form-item v-if="dialogMode === 'create'" label="初始密码" prop="password">
          <el-input v-model="form.password" placeholder="默认 123456，可修改" show-password />
        </el-form-item>

        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" placeholder="用于预约单和审核记录显示" />
        </el-form-item>

        <el-form-item label="角色" prop="role">
          <el-radio-group v-model="form.role">
            <el-radio value="student">学生</el-radio>
            <el-radio value="admin">管理员</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="状态" prop="status">
          <el-radio-group v-model="form.status">
            <el-radio value="active">正常</el-radio>
            <el-radio value="disabled">停用</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="选填，11 位手机号" />
        </el-form-item>

        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="选填，name@example.com" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">
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
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.toolbar__filters {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.toolbar__count {
  font-size: 13px;
  color: #909399;
  white-space: nowrap;
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

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
