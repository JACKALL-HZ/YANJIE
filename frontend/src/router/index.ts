import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'landing',
      component: () => import('@/views/LandingView.vue'),
      meta: { title: '衍界 YanJie AI', hideBackground: true },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { title: '登录 · 衍界' },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/RegisterView.vue'),
      meta: { title: '注册 · 衍界' },
    },
    {
      path: '/library',
      name: 'library',
      component: () => import('@/views/LibraryView.vue'),
      meta: { title: '场景库 · 衍界', requiresAuth: true },
    },
    {
      path: '/breakdown',
      name: 'breakdown',
      component: () => import('@/views/BreakdownView.vue'),
      meta: { title: 'AI 拆解 · 衍界', requiresAuth: true },
    },
    {
      path: '/sim/:scenarioId?',
      name: 'sim',
      component: () => import('@/views/SimView.vue'),
      meta: { title: '推演 · 衍界', requiresAuth: true },
    },
    {
      path: '/compare',
      name: 'compare',
      component: () => import('@/views/CompareView.vue'),
      meta: { title: '分支对比 · 衍界', requiresAuth: true },
    },
    {
      path: '/profile',
      name: 'profile',
      component: () => import('@/views/ProfileView.vue'),
      meta: { title: '个人画像 · 衍界', requiresAuth: true },
    },
    {
      path: '/history',
      name: 'history',
      component: () => import('@/views/HistoryView.vue'),
      meta: { title: '推演历史 · 衍界', requiresAuth: true },
    },
    {
      path: '/diary',
      name: 'diary',
      component: () => import('@/views/DiaryView.vue'),
      meta: { title: '决策日记 · 衍界', requiresAuth: true },
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if ((to.name === 'login' || to.name === 'register') && auth.token) {
    return { path: (to.query.redirect as string) || '/' }
  }
  return true
})

router.afterEach((to) => {
  document.title = (to.meta.title as string) || '衍界 YanJie AI'
})

export default router
