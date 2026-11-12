<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ChatLineRound, Calendar, OfficeBuilding, Lock, User } from '@element-plus/icons-vue'
import { login } from '@/api/auth'
import { getRememberedUsername, setAuth, setRememberedUsername } from '@/utils/auth'

const router = useRouter()
const route = useRoute()

const DEMO = {
  student: { username: 'student', password: '123456', name: '张同学' },
  admin: { username: 'admin', password: '123456', name: '王老师' }
}

const role = ref('student')
const loading = ref(false)
const remember = ref(true)
const formRef = ref()
const form = reactive({ username: '', password: '' })

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度 3–20 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 32, message: '密码长度 6–32 个字符', trigger: 'blur' }
  ]
}

onMounted(() => {
  form.username = getRememberedUsername()
})

function switchRole(next) {
  if (role.value === next) return
  role.value = next
  formRef.value?.clearValidate()
}

function fillDemo() {
  const demo = DEMO[role.value]
  form.username = demo.username
  form.password = demo.password
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const data = await login({ username: form.username, password: form.password })
    setAuth({ token: data.accessToken, user: data.user })
    setRememberedUsername(remember.value ? form.username : '')

    if (data.user.role !== role.value) {
      const actual = data.user.role === 'admin' ? '管理员' : '学生'
      ElMessage.info(`该账号是${actual}，已进入对应入口`)
    }

    ElMessage.success(`欢迎回来，${data.user.name}`)
    const fallback = data.user.role === 'admin' ? '/admin/reviews' : '/chat'
    router.replace(route.query.redirect || fallback)
  } catch (error) {
    ElMessage.error(error.message || '登录失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login">
    <section class="login__brand">
      <div class="brand__mark">格物</div>
      <h1 class="brand__title">实验室智能预约</h1>
      <p class="brand__slogan">用对话完成实验室预约：查空档、校验规则、发起审批、自动改期。</p>

      <ul class="brand__points">
        <li>
          <el-icon><ChatLineRound /></el-icon>
          <span>一句话描述需求，自动生成预约方案</span>
        </li>
        <li>
          <el-icon><OfficeBuilding /></el-icon>
          <span>四间实验室的设备、容量与使用规则一目了然</span>
        </li>
        <li>
          <el-icon><Calendar /></el-icon>
          <span>预约进度全程可查，审核结果及时通知</span>
        </li>
      </ul>

      <p class="brand__footer">Gewu Lab · 校园实验室预约平台</p>
    </section>

    <section class="login__panel">
      <div class="panel">
        <header class="panel__head">
          <h2>登录</h2>
          <p>请选择身份后登录系统</p>
        </header>

        <div class="role-switch">
          <button
            type="button"
            class="role-switch__item"
            :class="{ 'is-active': role === 'student' }"
            @click="switchRole('student')"
          >
            学生
          </button>
          <button
            type="button"
            class="role-switch__item"
            :class="{ 'is-active': role === 'admin' }"
            @click="switchRole('admin')"
          >
            管理员
          </button>
        </div>

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
              placeholder="请输入用户名"
              :prefix-icon="User"
              autocomplete="username"
              @keyup.enter="submit"
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              show-password
              placeholder="请输入密码"
              :prefix-icon="Lock"
              autocomplete="current-password"
              @keyup.enter="submit"
            />
          </el-form-item>

          <div class="panel__row">
            <el-checkbox v-model="remember">记住用户名</el-checkbox>
            <el-tooltip content="找回密码功能暂未开放" placement="top">
              <span class="panel__link">忘记密码？</span>
            </el-tooltip>
          </div>

          <el-button
            type="primary"
            class="panel__submit"
            :loading="loading"
            native-type="submit"
          >
            登 录
          </el-button>
        </el-form>

        <p class="panel__register">
          还没有账号？
          <button type="button" class="panel__link" @click="router.push('/register')">立即注册</button>
        </p>

        <p class="panel__demo">
          演示账号
          <button type="button" class="panel__link" @click="fillDemo">
            {{ DEMO[role].username }} / {{ DEMO[role].password }}
          </button>
          <span class="panel__demo-tip">（学生与管理员账号均可登录，密码 123456）</span>
        </p>
      </div>

      <p class="login__copyright">© 2026 格物 · Gewu Lab</p>
    </section>
  </div>
</template>

<style scoped>
.login {
  display: grid;
  grid-template-columns: minmax(360px, 46%) 1fr;
  min-height: 100vh;
}

/* 左侧品牌区 */
.login__brand {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 18px;
  padding: 56px 64px;
  color: #eaf3fb;
  background:
    radial-gradient(circle at 18% 18%, rgb(64 158 255 / 35%), transparent 46%),
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
  max-width: 26em;
  font-size: 14px;
  line-height: 1.9;
  color: rgb(234 243 251 / 72%);
}

.brand__points {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 8px;
  padding: 0;
  list-style: none;
}

.brand__points li {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: rgb(234 243 251 / 88%);
}

.brand__points .el-icon {
  flex: none;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: rgb(255 255 255 / 10%);
}

.brand__footer {
  margin-top: auto;
  font-size: 12px;
  color: rgb(234 243 251 / 45%);
  letter-spacing: 1px;
}

.panel__register {
  margin-top: 16px;
  font-size: 13px;
  color: #909399;
}

/* 右侧表单区 */
.login__panel {
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
  max-width: 380px;
  padding: 36px 32px 28px;
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
  margin: 6px 0 22px;
  font-size: 13px;
  color: #909399;
}

.role-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  margin-bottom: 22px;
  padding: 4px;
  border-radius: 9px;
  background: #f2f5f9;
}

.role-switch__item {
  padding: 8px 0;
  border: none;
  border-radius: 7px;
  background: transparent;
  font-size: 14px;
  color: #606266;
  cursor: pointer;
  transition:
    background 0.2s,
    color 0.2s,
    box-shadow 0.2s;
}

.role-switch__item.is-active {
  background: #fff;
  color: #1f6feb;
  font-weight: 600;
  box-shadow: 0 2px 6px rgb(16 42 67 / 10%);
}

.panel__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 2px 0 18px;
}

.panel__link {
  border: none;
  background: transparent;
  font-size: 13px;
  color: #1f6feb;
  cursor: pointer;
}

.panel__submit {
  width: 100%;
  height: 42px;
  font-size: 15px;
  letter-spacing: 4px;
}

.panel__demo {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px dashed #e4e7ed;
  font-size: 12px;
  color: #909399;
}

.panel__demo-tip {
  display: block;
  margin-top: 6px;
  color: #b1b3b8;
}

.login__copyright {
  position: absolute;
  bottom: 20px;
  font-size: 12px;
  color: #b1b3b8;
}

@media (max-width: 900px) {
  .login {
    grid-template-columns: 1fr;
  }

  .login__brand {
    display: none;
  }
}
</style>
