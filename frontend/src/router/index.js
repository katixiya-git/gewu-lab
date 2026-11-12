import { createRouter, createWebHistory } from 'vue-router'
import StudentLayout from '@/layouts/StudentLayout.vue'
import { fetchMe } from '@/api/auth'
import { clearAuth, getToken, getUser, setAuth } from '@/utils/auth'
import AdminLayout from '@/layouts/AdminLayout.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { title: '选择入口' }
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/RegisterView.vue'),
      meta: { title: '学生注册' }
    },
    {
      path: '/',
      component: StudentLayout,
      children: [
        { path: '', redirect: '/chat' },
        {
          path: 'chat',
          name: 'chat',
          component: () => import('@/views/student/ChatView.vue'),
          meta: { title: '对话预约' }
        },
        {
          path: 'labs',
          name: 'labs',
          component: () => import('@/views/student/LabsView.vue'),
          meta: { title: '实验室' }
        },
        {
          path: 'labs/:id',
          name: 'lab-detail',
          component: () => import('@/views/student/LabDetailView.vue'),
          meta: { title: '实验室详情' }
        },
        {
          path: 'bookings',
          name: 'bookings',
          component: () => import('@/views/student/MyBookingsView.vue'),
          meta: { title: '我的预约' }
        }
      ]
    },
    {
      path: '/admin',
      component: AdminLayout,
      children: [
        { path: '', redirect: '/admin/reviews' },
        {
          path: 'reviews',
          name: 'admin-reviews',
          component: () => import('@/views/admin/ReviewsView.vue'),
          meta: { title: '预约审核' }
        },
        {
          path: 'labs',
          name: 'admin-labs',
          component: () => import('@/views/admin/LabsManageView.vue'),
          meta: { title: '实验室管理' }
        },
        {
          path: 'devices',
          name: 'admin-devices',
          component: () => import('@/views/admin/DevicesManageView.vue'),
          meta: { title: '设备管理' }
        },
        {
          path: 'users',
          name: 'admin-users',
          component: () => import('@/views/admin/UsersManageView.vue'),
          meta: { title: '用户管理' }
        }
      ]
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue'),
      meta: { title: '页面不存在' }
    }
  ]
})

router.beforeEach(async (to) => {
  const token = getToken()

  // 已登录时访问登录/注册页，按角色回各自首页
  if (to.path === '/login' || to.path === '/register') {
    const user = getUser()
    if (!token) return true
    return user ? (user.role === 'admin' ? '/admin/reviews' : '/chat') : true
  }

  // 未登录一律回登录页，并记住原目标
  if (!token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // 有 token 但没有用户信息（刷新页面/换标签页）：先向后端确认 token 是否仍有效
  let user = getUser()
  if (!user) {
    try {
      user = await fetchMe()
      setAuth({ token, user })
    } catch {
      clearAuth()
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }

  // 角色与路由不匹配时纠正到各自首页
  const isAdminRoute = to.path.startsWith('/admin')
  if (user.role === 'admin' && !isAdminRoute) return '/admin/reviews'
  if (user.role !== 'admin' && isAdminRoute) return '/chat'
  return true
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · 格物` : '格物 · 实验室智能预约'
})

export default router
