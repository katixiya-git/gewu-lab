import { createRouter, createWebHistory } from 'vue-router'
import StudentLayout from '@/layouts/StudentLayout.vue'
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

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · 格物` : '格物 · 实验室智能预约'
})

export default router
