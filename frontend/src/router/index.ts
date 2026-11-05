import { createRouter, createWebHistory } from 'vue-router'

// 孩子端与家长端分成两组，各自懒加载：切到家长端不加载孩子端的包
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('../views/Home.vue') },
    {
      path: '/kid',
      children: [
        { path: '', redirect: '/kid/today' },
        { path: 'today', name: 'kid-today', component: () => import('../views/kid/Today.vue') },
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
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

export default router
