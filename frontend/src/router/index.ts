import { createRouter, createWebHistory } from 'vue-router'

import { useSession } from '../stores/session'

// 孩子端与家长端分成两组，各自懒加载：切到家长端不加载孩子端的包
const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/Home.vue'),
      meta: { public: true },   // 自检页不需要登录，方便排故障
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/Login.vue'),
      meta: { public: true },
    },
    {
      path: '/kid',
      children: [
        { path: '', redirect: '/kid/today' },
        { path: 'today', name: 'kid-today', component: () => import('../views/kid/Today.vue') },
        // 作业页单独一条路由：拍照、计时、提交都在那，列表页只管导航
        {
          path: 'task/:id',
          name: 'kid-task',
          component: () => import('../views/kid/Task.vue'),
        },
        // 口算一题一屏。带 id 是任务模式（交卷结算发星），不带是独立练习（只记成绩）
        {
          path: 'calc/:id?',
          name: 'kid-calc',
          component: () => import('../views/kid/Calc.vue'),
        },
        {
          path: 'stars',
          name: 'kid-stars',
          component: () => import('../views/kid/Stars.vue'),
        },
      ],
    },
    {
      path: '/parent',
      children: [
        { path: '', redirect: '/parent/dashboard' },
        {
          path: 'dashboard',
          name: 'parent-dashboard',
          component: () => import('../views/parent/Dashboard.vue'),
        },
        {
          path: 'tasks',
          name: 'parent-tasks',
          component: () => import('../views/parent/Tasks.vue'),
        },
        {
          path: 'review',
          name: 'parent-review',
          component: () => import('../views/parent/Review.vue'),
        },
        {
          path: 'mistakes',
          name: 'parent-mistakes',
          component: () => import('../views/parent/Mistakes.vue'),
        },
        {
          path: 'rewards',
          name: 'parent-rewards',
          component: () => import('../views/parent/Rewards.vue'),
        },
        {
          path: 'report',
          name: 'parent-report',
          component: () => import('../views/parent/Report.vue'),
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

/**
 * 全局守卫。要点是「先问后端再判断」：
 * 刷新页面时 store 是空的，必须先 /auth/me 确认，否则已登录用户会被踢到登录页。
 * loaded 标记保证每次页面加载只问一次。
 */
router.beforeEach(async (to) => {
  const session = useSession()

  if (!session.loaded) {
    await session.refresh()
  }

  if (to.meta.public) {
    // 已登录还去登录页，直接送进工作台（自检页仍然放行）
    if (to.name === 'login' && session.isLoggedIn) {
      return { path: '/kid/today' }
    }
    return true
  }

  if (!session.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
