<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="shell">
    <header class="bar">
      <div class="brand">
        <span class="dot"></span>
        <strong>学习工作台</strong>
        <span class="ver">M0 骨架</span>
      </div>
      <nav class="nav">
        <RouterLink to="/">首页</RouterLink>
        <RouterLink to="/kid/today">孩子端</RouterLink>
        <RouterLink to="/parent/dashboard">家长端</RouterLink>
      </nav>
    </header>

    <main class="main">
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
.nav { display: flex; gap: 4px; margin-left: auto; }
.nav a {
  font-size: 13px; color: var(--ink-2);
  padding: 6px 12px; border-radius: var(--r-sm);
}
.nav a:hover { background: var(--page); }
.nav a.router-link-active { color: var(--kid); background: var(--kid-soft); }

.main { flex: 1; padding: 32px 28px 64px; max-width: 960px; width: 100%; margin: 0 auto; }
</style>
