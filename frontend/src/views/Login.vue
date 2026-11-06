<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useSession } from '../stores/session'

const session = useSession()
const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const error = ref('')

// 开发期把演示账号显示出来，省得每次查 README。生产构建时这段会被 tree-shake 掉。
const isDev = import.meta.env.DEV

async function submit() {
  if (!username.value.trim() || !password.value) {
    error.value = '登录名和口令都要填'
    return
  }
  error.value = ''
  try {
    await session.signIn(username.value.trim(), password.value)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
    router.replace(redirect || '/kid/today')
  } catch (e) {
    error.value = e instanceof Error ? e.message : '登录失败'
  }
}

onMounted(() => {
  // 已登录就直接进工作台，避免后退回到登录页还能看到表单
  if (session.isLoggedIn) router.replace('/kid/today')
})
</script>

<template>
  <div class="wrap">
    <form class="card" @submit.prevent="submit">
      <div class="brand">
        <span class="dot"></span>
        <span>学习工作台</span>
      </div>
      <h1>家长登录</h1>
      <p class="sub">一个账号管理孩子的任务、错题与星星。</p>

      <label class="field">
        <span>登录名</span>
        <input
          v-model="username"
          type="text"
          autocomplete="username"
          placeholder="parent"
          :disabled="session.busy"
        />
      </label>

      <label class="field">
        <span>口令</span>
        <input
          v-model="password"
          type="password"
          autocomplete="current-password"
          placeholder="••••••"
          :disabled="session.busy"
        />
      </label>

      <p v-if="error" class="err">{{ error }}</p>

      <button type="submit" :disabled="session.busy">
        {{ session.busy ? '登录中…' : '登录' }}
      </button>

      <p v-if="isDev" class="hint">
        演示账号：<code>parent</code> / <code>study123</code>
      </p>
    </form>
  </div>
</template>

<style scoped>
.wrap {
  min-height: 78vh;
  display: flex; align-items: center; justify-content: center;
}
.card {
  width: 100%; max-width: 360px;
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-lg); padding: 28px 26px 22px;
}
.brand {
  display: flex; align-items: center; gap: 8px;
  font-size: 12.5px; color: var(--muted); margin-bottom: 18px;
}
.dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--kid); box-shadow: 0 0 0 3px var(--kid-soft);
}
h1 { font-size: 19px; font-weight: 500; }
.sub { font-size: 12.5px; color: var(--muted); margin-top: 4px; margin-bottom: 20px; }

.field { display: block; margin-bottom: 14px; }
.field span {
  display: block; font-size: 12px; color: var(--muted); margin-bottom: 5px;
}
.field input {
  width: 100%; font: inherit; font-size: 13.5px;
  padding: 9px 11px;
  background: var(--page); color: var(--ink);
  border: 1px solid var(--line); border-radius: var(--r-sm);
  outline: none;
}
.field input:focus { border-color: var(--kid); background: var(--card); }

button {
  width: 100%; font: inherit; font-size: 13.5px;
  margin-top: 6px; padding: 10px;
  background: var(--kid); color: #fff;
  border: none; border-radius: var(--r-sm);
  cursor: pointer;
}
button:disabled { opacity: 0.6; cursor: default; }

.err {
  font-size: 12.5px; color: var(--bad);
  background: #fdf2f2; border: 1px solid #f3c9c9;
  border-radius: var(--r-sm); padding: 8px 10px; margin-bottom: 12px;
}
.hint {
  margin-top: 16px; padding-top: 14px;
  border-top: 1px solid var(--line);
  font-size: 11.5px; color: var(--hint);
}
</style>
