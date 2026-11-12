<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Lock, Message, Phone, User } from '@element-plus/icons-vue'
import { register } from '@/api/auth'
import { setAuth } from '@/utils/auth'

const router = useRouter()

const loading = ref(false)
const formRef = ref()
const form = reactive({
  username: '',
  name: '',
  password: '',
  confirmPassword: '',
  phone: '',
  email: ''
})

function validateConfirm(rule, value, callback) {
  if (!value) return callback(new Error('请再次输入密码'))
  if (value !== form.password) return callback(new Error('两次输入的密码不一致'))
  callback()
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 32, message: '用户名长度 3–32 个字符', trigger: 'blur' },
    { pattern: /^[A-Za-z0-9_]+$/, message: '只能包含字母、数字和下划线', trigger: 'blur' }
  ],
  name: [
    { required: true, message: '请输入姓名', trigger: 'blur' },
    { min: 1, max: 32, message: '姓名最多 32 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度 6–64 个字符', trigger: 'blur' }
  ],
  confirmPassword: [{ validator: validateConfirm, trigger: 'blur' }],
  phone: [{ pattern: /^1[3-9]\d{9}$/, message: '请输入 11 位手机号', trigger: 'blur' }],
  email: [{ type: 'email', message: '邮箱格式不正确', trigger: 'blur' }]
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const data = await register({
      username: form.username,
      name: form.name,
      password: form.password,
      phone: form.phone || null,
      email: form.email || null
    })
    setAuth({ token: data.accessToken, user: data.user })
    ElMessage.success(`注册成功，欢迎你，${data.user.name}`)
    router.replace('/chat')
  } catch (error) {
    ElMessage.error(error.message || '注册失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="register">
    <section class="register__brand">
      <div class="brand__mark">格物</div>
      <h1 class="brand__title">加入格物</h1>
      <p class="brand__slogan">
        注册学生账号后，用一句话描述需求，就能查空档、校验规则、生成预约方案并提交审批。
      </p>

      <ul class="brand__points">
        <li>• 四间实验室：人工智能 / 机器人 / 云计算 / 软件工程</li>
        <li>• 设备、容量、开放时间与使用规则一目了然</li>
        <li>• 预约进度全程可查，审核结果及时通知</li>
      </ul>

      <p class="brand__footer">Gewu Lab · 校园实验室预约平台</p>
    </section>

    <section class="register__panel">
      <div class="panel">
        <header class="panel__head">
          <h2>学生注册</h2>
          <p>管理员账号由后台开通，这里只注册学生账号</p>
        </header>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          size="large"
          @submit.prevent="submit"
        >
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model.trim="form.username"
              placeholder="字母、数字或下划线，3–32 位"
              :prefix-icon="User"
              autocomplete="username"
            />
          </el-form-item>

          <el-form-item label="姓名" prop="name">
            <el-input v-model.trim="form.name" placeholder="用于预约单和审核显示" />
          </el-form-item>

          <div class="panel__grid">
            <el-form-item label="密码" prop="password">
              <el-input
                v-model="form.password"
                type="password"
                show-password
                placeholder="至少 6 位"
                :prefix-icon="Lock"
                autocomplete="new-password"
              />
            </el-form-item>

            <el-form-item label="确认密码" prop="confirmPassword">
              <el-input
                v-model="form.confirmPassword"
                type="password"
                show-password
                placeholder="再输入一次"
                :prefix-icon="Lock"
                autocomplete="new-password"
              />
            </el-form-item>
          </div>

          <div class="panel__grid">
            <el-form-item label="手机号（选填）" prop="phone">
              <el-input
                v-model.trim="form.phone"
                placeholder="用于接收审核通知"
                :prefix-icon="Phone"
              />
            </el-form-item>

            <el-form-item label="邮箱（选填）" prop="email">
              <el-input
                v-model.trim="form.email"
                placeholder="name@example.com"
                :prefix-icon="Message"
              />
            </el-form-item>
          </div>

          <el-button
            type="primary"
            class="panel__submit"
            :loading="loading"
            native-type="submit"
          >
            注 册
          </el-button>
        </el-form>

        <p class="panel__footer">
          已经有账号了？
          <button type="button" class="panel__link" @click="router.push('/login')">去登录</button>
        </p>
      </div>

      <p class="register__copyright">© 2026 格物 · Gewu Lab</p>
    </section>
  </div>
</template>

<style scoped>
.register {
  display: grid;
  grid-template-columns: minmax(340px, 42%) 1fr;
  min-height: 100vh;
}

.register__brand {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 18px;
  padding: 56px 64px;
  color: #eaf3fb;
  background:
    radial-gradient(circle at 20% 20%, rgb(64 158 255 / 32%), transparent 46%),
    linear-gradient(155deg, #0b2740 0%, #123c5c 55%, #0f5148 100%);
}

.brand__mark {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: rgb(255 255 255 / 12%);
  border: 1px solid rgb(255 255 255 / 22%);
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 2px;
}

.brand__title {
  font-size: 34px;
  font-weight: 600;
  letter-spacing: 1px;
}

.brand__slogan {
  max-width: 24em;
  font-size: 14px;
  line-height: 1.9;
  color: rgb(234 243 251 / 74%);
}

.brand__points {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 4px 0 0;
  padding: 0;
  list-style: none;
  font-size: 13px;
  color: rgb(234 243 251 / 82%);
}

.brand__footer {
  margin-top: auto;
  font-size: 12px;
  color: rgb(234 243 251 / 45%);
  letter-spacing: 1px;
}

.register__panel {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  background: #f7f9fc;
}

.panel {
  width: 100%;
  max-width: 460px;
  padding: 34px 32px 26px;
  background: #fff;
  border: 1px solid #e8eef5;
  border-radius: 14px;
  box-shadow: 0 12px 40px rgb(16 42 67 / 8%);
}

.panel__head h2 {
  font-size: 22px;
  font-weight: 600;
  color: #1f2d3d;
}

.panel__head p {
  margin: 6px 0 20px;
  font-size: 13px;
  color: #909399;
}

.panel__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 14px;
}

.panel__submit {
  width: 100%;
  height: 42px;
  margin-top: 6px;
  font-size: 15px;
  letter-spacing: 4px;
}

.panel__footer {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px dashed #e4e7ed;
  font-size: 13px;
  color: #909399;
}

.panel__link {
  border: none;
  background: transparent;
  font-size: 13px;
  color: #1f6feb;
  cursor: pointer;
}

.register__copyright {
  position: absolute;
  bottom: 20px;
  font-size: 12px;
  color: #b1b3b8;
}

@media (max-width: 900px) {
  .register {
    grid-template-columns: 1fr;
  }

  .register__brand {
    display: none;
  }
}
</style>
