<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import { useSession } from './stores/session'

const session = useSession()
const route = useRoute()
const router = useRouter()

// 登录页不要顶栏：那里只有一张卡片，多一条导航反而分心
const bare = computed(() => route.name === 'login')

async function signOut() {
  await session.signOut()
  router.replace('/login')
}
</script>

<template>
  <div class="shell">
    <header v-if="!bare" class="bar">
      <div class="brand">
        <span class="dot"></span>
        <strong>学习工作台</strong>
        <span class="ver">M4</span>
      </div>
      <nav class="nav">
        <span class="seg">孩子</span>
        <RouterLink to="/kid/today">任务</RouterLink>
        <RouterLink to="/kid/stars">星星</RouterLink>
        <RouterLink to="/kid/calendar">打卡</RouterLink>
        <span class="seg">家长</span>
        <RouterLink to="/parent/dashboard">总览</RouterLink>
        <RouterLink to="/parent/tasks">布置</RouterLink>
        <RouterLink to="/parent/review">审核</RouterLink>
        <RouterLink to="/parent/mistakes">错题</RouterLink>
        <RouterLink to="/parent/rewards">奖励</RouterLink>
        <RouterLink to="/parent/report">周报</RouterLink>
      </nav>
      <div v-if="session.account" class="who">
        <span class="name">{{ session.account.nickname }}</span>
        <button class="out" @click="signOut">退出</button>
      </div>
    </header>

    <main class="main" :class="{ wide: bare }">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.shell { min-height: 100vh; display: flex; flex-direction: column; }

.bar {
  display: flex; align-items: center; gap: 24px;
  padding: 14px 28px;
  background: var(--card);
  border-bottom: 1px solid var(--line);
  position: sticky; top: 0; z-index: 10;
}
.brand { display: flex; align-items: center; gap: 8px; font-size: 14px; }
.brand strong { font-weight: 500; }
.dot {
  width: 9px; height: 9px; border-radius: 50%;
  background: var(--kid);
  box-shadow: 0 0 0 4px var(--kid-soft);
}
.ver {
  font-size: 11px; color: var(--hint);
  border: 1px solid var(--line); border-radius: 5px;
  padding: 1px 6px;
}
.nav { display: flex; align-items: center; gap: 2px; margin-left: auto; }
.nav a {
  font-size: 12.5px; color: var(--ink-2);
  padding: 6px 9px; border-radius: var(--r-sm);
}
.nav a:hover { background: var(--page); }
.nav a.router-link-active { color: var(--kid); background: var(--kid-soft); }
/* 导航分「孩子 / 家长」两组：两套界面共用一套登录态，靠分组让人一眼知道自己站在哪边 */
.seg {
  font-size: 10.5px; color: var(--hint); letter-spacing: 0.5px;
  padding: 0 3px 0 10px;
}
.seg:first-child { padding-left: 0; }

.who { display: flex; align-items: center; gap: 10px; }
.who .name { font-size: 12.5px; color: var(--muted); }
.out {
  font: inherit; font-size: 12px; cursor: pointer;
  background: transparent; color: var(--hint);
  border: 1px solid var(--line); border-radius: var(--r-sm);
  padding: 4px 10px;
}
.out:hover { color: var(--bad); border-color: #f3c9c9; }

.main { flex: 1; padding: 32px 28px 64px; max-width: 960px; width: 100%; margin: 0 auto; }
.main.wide { max-width: none; padding: 0 28px; }

@media (max-width: 720px) {
  .bar { gap: 12px; padding: 12px 16px; flex-wrap: wrap; }
  .nav { overflow-x: auto; }
  .main { padding: 22px 16px 48px; }
}
</style>
