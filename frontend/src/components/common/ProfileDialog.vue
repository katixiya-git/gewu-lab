<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { updateProfile } from '@/api/auth'
import FileUpload from '@/components/common/FileUpload.vue'
import { fetchMe } from '@/api/auth'
import { getToken, getUser, setAuth } from '@/utils/auth'
import { roleTagType, roleText } from '@/utils/dict'

const props = defineProps({
  modelValue: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue', 'updated'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const user = ref(getUser() || {})
const editing = ref(false)
const saving = ref(false)
const formRef = ref()
const form = reactive({ name: '', phone: '', email: '' })
const avatar = ref('')

const rules = {
  name: [
    { required: true, message: '请输入姓名', trigger: 'blur' },
    { max: 32, message: '姓名最多 32 个字符', trigger: 'blur' }
  ],
  phone: [{ pattern: /^1[3-9]\d{9}$/, message: '请输入 11 位手机号', trigger: 'blur' }],
  email: [{ type: 'email', message: '邮箱格式不正确', trigger: 'blur' }]
}

const initial = computed(() => (user.value.name || user.value.username || '?').slice(0, 1))
const createTimeText = computed(() => (user.value.createTime || '').slice(0, 16).replace('T', ' '))

watch(visible, async (open) => {
  if (!open) return
  editing.value = false
  user.value = getUser() || {}
  // 打开时用后端最新数据刷新一次，避免别处改过头像后这里还是旧的
  if (getToken()) {
    try {
      user.value = await fetchMe()
      setAuth({ token: getToken(), user: user.value })
    } catch {
      /* token 失效交给路由守卫处理 */
    }
  }
})

function startEdit() {
  form.name = user.value.name || ''
  form.phone = user.value.phone || ''
  form.email = user.value.email || ''
  avatar.value = user.value.avatar || ''
  editing.value = true
}

async function save() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    const data = await updateProfile({
      name: form.name,
      phone: form.phone || null,
      email: form.email || null,
      avatar: avatar.value || null
    })
    setAuth({ token: getToken(), user: data })
    user.value = data
    emit('updated', data)
    editing.value = false
    ElMessage.success('资料已更新')
  } catch (error) {
    ElMessage.error(error.message || '保存失败，请重试')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="个人信息" width="560px" class="profile-dialog">
    <template v-if="!editing">
      <div class="profile__top">
        <el-avatar :size="72" :src="user.avatar || ''">{{ initial }}</el-avatar>
        <div class="profile__meta">
          <h3>{{ user.name || '未命名' }}</h3>
          <p>@{{ user.username }}</p>
          <el-tag size="small" :type="roleTagType(user.role)">{{ roleText(user.role) }}</el-tag>
        </div>
      </div>

      <el-descriptions :column="1" border size="default" class="profile__desc">
        <el-descriptions-item label="手机号">{{ user.phone || '—' }}</el-descriptions-item>
        <el-descriptions-item label="邮箱">{{ user.email || '—' }}</el-descriptions-item>
        <el-descriptions-item label="注册时间">{{ createTimeText || '—' }}</el-descriptions-item>
      </el-descriptions>

    </template>

    <template v-else>
      <div class="profile__edit">
        <div class="profile__avatar">
          <FileUpload
            v-model="avatar"
            biz-type="avatar"
            image-only
            round
            :max-size-mb="2"
            tip="支持 jpg / png / gif / webp，不超过 2MB"
          />
        </div>

        <el-form ref="formRef" :model="form" :rules="rules" label-width="72px" class="profile__form">
          <el-form-item label="姓名" prop="name">
            <el-input v-model.trim="form.name" placeholder="用于预约单显示" />
          </el-form-item>
          <el-form-item label="手机号" prop="phone">
            <el-input v-model.trim="form.phone" placeholder="选填，用于接收审核通知" />
          </el-form-item>
          <el-form-item label="邮箱" prop="email">
            <el-input v-model.trim="form.email" placeholder="选填" />
          </el-form-item>
        </el-form>
      </div>

    </template>

    <template #footer>
      <template v-if="!editing">
        <el-button @click="visible = false">关闭</el-button>
        <el-button type="primary" @click="startEdit">修改个人信息</el-button>
      </template>
      <template v-else>
        <el-button @click="editing = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </template>
  </el-dialog>
</template>

<style scoped>
.profile__top {
  display: flex;
  align-items: center;
  gap: 20px;
  padding-bottom: 18px;
  border-bottom: 1px solid #eef2f7;
}

.profile__meta h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1f2d3d;
}

.profile__meta p {
  margin: 4px 0 8px;
  font-size: 13px;
  color: #909399;
}

.profile__desc {
  margin-top: 18px;
}

.profile__edit {
  display: grid;
  grid-template-columns: 130px 1fr;
  gap: 24px;
  align-items: start;
}

.profile__avatar {
  display: flex;
  justify-content: center;
  width: 130px;
}

.profile__avatar :deep(.uploader) {
  width: 110px;
}

.profile__avatar :deep(.uploader__tip) {
  text-align: center;
  line-height: 1.5;
}

.profile__form {
  padding-top: 4px;
}
</style>
