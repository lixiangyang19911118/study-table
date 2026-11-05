<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getHealth, type Health } from '../api/system'

const health = ref<Health | null>(null)
const error = ref('')
const loading = ref(true)

async function load() {
  loading.value = true
  error.value = ''
  try {
    health.value = await getHealth()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '请求失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="head">
    <h1>环境自检</h1>
    <p>
      这一页只做一件事：确认前端、后端、数据库、文件目录四者是否都通了。
      M0 结束时它应该是全绿。
    </p>
  </section>

  <p v-if="loading" class="hint">加载中…</p>

  <div v-else-if="error" class="err">
    <strong>连不上后端</strong>
    <p>{{ error }}</p>
    <p class="small">先确认后端在 8000 端口跑着：<code>bash scripts/dev.sh</code></p>
  </div>

  <template v-else-if="health">
    <div class="grid">
      <div class="card">
        <div class="row">
          <span class="dot" :class="health.db.ok ? 'ok' : 'bad'"></span>
          <span class="label">MySQL</span>
        </div>
        <p class="val">{{ health.db.ok ? '连接正常' : '未连接' }}</p>
        <p v-if="!health.db.ok" class="small">
          还没建库建账号，跑一次 <code>bash scripts/init_db.sh</code>，再
          <code>alembic upgrade head</code>。
        </p>
      </div>

      <div class="card">
        <div class="row">
          <span class="dot" :class="health.storage.writable ? 'ok' : 'bad'"></span>
          <span class="label">文件目录</span>
        </div>
        <p class="val">{{ health.storage.writable ? '可写' : '不可写' }}</p>
        <p class="small">{{ health.storage.root }}</p>
        <p class="small">已有 {{ health.storage.files }} 个文件</p>
      </div>

      <div class="card">
        <div class="row">
          <span class="dot" :class="health.scheduler ? 'ok' : 'warn'"></span>
          <span class="label">定时任务</span>
        </div>
        <p class="val">{{ health.scheduler ? '已启动' : '已关闭' }}</p>
        <p class="small">00:10 错题扫描 · 23:55 打卡结算</p>
      </div>
    </div>

    <div class="meta">
      <span>环境 {{ health.env }}</span>
      <span>·</span>
      <span>{{ health.app }}</span>
      <button class="reload" @click="load">重新检查</button>
    </div>
  </template>
</template>

<style scoped>
.head { margin-bottom: 24px; }
h1 { font-size: 21px; font-weight: 500; margin-bottom: 6px; }
.head p { font-size: 13px; color: var(--muted); max-width: 560px; }

.grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.card {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 16px 18px;
}
.row { display: flex; align-items: center; gap: 8px; }
.dot { width: 8px; height: 8px; border-radius: 50%; }
.dot.ok { background: var(--ok); }
.dot.bad { background: var(--bad); }
.dot.warn { background: var(--warn); }
.label { font-size: 12px; color: var(--muted); }
.val { font-size: 14px; margin-top: 8px; }
.small { font-size: 11.5px; color: var(--hint); line-height: 1.6; margin-top: 4px; word-break: break-all; }

.meta {
  display: flex; align-items: center; gap: 8px;
  margin-top: 18px; font-size: 12px; color: var(--hint);
}
.reload {
  margin-left: auto; font: inherit; font-size: 12px; cursor: pointer;
  background: var(--card); color: var(--ink-2);
  border: 1px solid var(--line); border-radius: var(--r-sm);
  padding: 5px 12px;
}
.reload:hover { border-color: var(--kid); color: var(--kid); }

.err {
  background: #fdf2f2; border: 1px solid #f3c9c9; color: var(--bad);
  border-radius: var(--r-md); padding: 14px 18px; font-size: 13px;
}
.err p { font-size: 12.5px; margin-top: 4px; }
.hint { font-size: 13px; color: var(--hint); }

@media (max-width: 720px) {
  .grid { grid-template-columns: minmax(0, 1fr); }
}
</style>
