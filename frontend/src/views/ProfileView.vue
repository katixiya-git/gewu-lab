<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { updateProfile } from '@/api/auth'
import FileUpload from '@/components/common/FileUpload.vue'
import { getToken, getUser, setAuth } from '@/utils/auth'

const router = useRouter()
const saving = ref(false)
const formRef = ref()
const user = ref(getUser() || {})
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

onMounted(() => {
  form.name = user.value.name || ''
  form.phone = user.value.phone || ''
  form.email = user.value.email || ''
  avatar.value = user.value.avatar || ''
})

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
    ElMessage.success('资料已保存')
  } catch (error) {
    ElMessage.error(error.message || '保存失败，请重试')
  } finally {
    saving.value = false
  }
}

function goBack() {
  const home = user.value.role === 'admin' ? '/admin/reviews' : '/chat'
  router.replace(home)
}
</script>

<template>
  <div class="profile">
    <div class="profile__card">
      <header class="profile__head">
        <button type="button" class="profile__back" @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </button>
        <div>
          <h2>个人设置</h2>
          <p>头像、姓名与联系方式会显示在预约单和审核记录里</p>
        </div>
      </header>

      <div class="profile__body">
        <div class="profile__avatar">
          <FileUpload
            v-model="avatar"
            biz-type="avatar"
            image-only
            round
            :max-size-mb="2"
            tip="支持 jpg / png / gif / webp，不超过 2MB"
          />
          <p class="profile__username">@{{ user.username }}</p>
          <el-tag size="small" :type="user.role === 'admin' ? 'danger' : 'info'">
            {{ user.role === 'admin' ? '管理员' : '学生' }}
          </el-tag>
        </div>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-width="80px"
          class="profile__form"
        >
          <el-form-item label="姓名" prop="name">
            <el-input v-model.trim="form.name" placeholder="用于预约单显示" />
          </el-form-item>
          <el-form-item label="手机号" prop="phone">
            <el-input v-model.trim="form.phone" placeholder="选填，用于接收审核通知" />
          </el-form-item>
          <el-form-item label="邮箱" prop="email">
            <el-input v-model.trim="form.email" placeholder="选填" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="saving" @click="save">保存修改</el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.profile {
  display: flex;
  justify-content: center;
  min-height: 100vh;
  padding: 48px 24px;
  background: #f7f9fc;
}

.profile__card {
  width: 100%;
  max-width: 720px;
  height: fit-content;
  padding: 28px 32px 32px;
  background: #fff;
  border: 1px solid #e8eef5;
  border-radius: 14px;
  box-shadow: 0 12px 40px rgb(16 42 67 / 8%);
}

.profile__head {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding-bottom: 18px;
  border-bottom: 1px solid #eef2f7;
}

.profile__back {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  font-size: 13px;
  color: #606266;
  cursor: pointer;
}

.profile__head h2 {
  font-size: 20px;
  font-weight: 600;
  color: #1f2d3d;
}

.profile__head p {
  margin-top: 6px;
  font-size: 13px;
  color: #909399;
}

.profile__body {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 32px;
  padding-top: 24px;
}

.profile__avatar {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  width: 150px;
}

.profile__avatar :deep(.uploader) {
  width: 120px;
}

.profile__avatar :deep(.uploader__tip) {
  text-align: center;
  line-height: 1.5;
}

.profile__username {
  font-size: 13px;
  color: #909399;
}

.profile__form {
  padding-top: 8px;
}

@media (max-width: 720px) {
  .profile__body {
    grid-template-columns: 1fr;
  }
}
</style>
