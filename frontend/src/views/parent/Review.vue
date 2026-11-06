<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import {
  approveTask, getTask, listTasks, rejectTask, type TaskDetail,
} from '../../api/tasks'
import { fmtMinutes, timeOf } from '../../lib/time'
import { useSession } from '../../stores/session'

const session = useSession()

const items = ref<TaskDetail[]>([])
const loading = ref(true)
const err = ref('')
const msg = ref('')

const busyId = ref<number | null>(null)
const rejectingId = ref<number | null>(null)
const comment = ref('')

async function load() {
  loading.value = true
  err.value = ''
  try {
    // 列表接口不带照片和审核流水，逐条取详情。待审的一般就一两件，
    // 不值得为此在列表接口里加一个「带不带详情」的参数。
    const briefs = await listTasks('review')
    items.value = await Promise.all(briefs.map((b) => getTask(b.id)))
  } catch (e) {
    err.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function rejectCount(t: TaskDetail) {
  return t.reviews.filter((r) => r.action === 'reject').length
}

async function approve(t: TaskDetail) {
  const ok = window.confirm(
    `通过「${t.title}」？通过后孩子立刻拿到 ${t.stars} 颗星，这一步不能撤回。`,
  )
  if (!ok) return

  busyId.value = t.id
  err.value = ''
  msg.value = ''
  try {
    await approveTask(t.id)
    msg.value = `已通过，发出去 ${t.stars} 颗星`
    await load()
  } catch (e) {
    err.value = e instanceof Error ? e.message : '操作失败'
  } finally {
    busyId.value = null
  }
}

function openReject(t: TaskDetail) {
  rejectingId.value = t.id
  comment.value = ''
  err.value = ''
}

async function submitReject(t: TaskDetail) {
  const text = comment.value.trim()
  if (!text) {
    err.value = '写一句原因，孩子才知道要改什么'
    return
  }
  busyId.value = t.id
  err.value = ''
  msg.value = ''
  try {
    await rejectTask(t.id, text)
    msg.value = '已退回，孩子端会看到原因'
    rejectingId.value = null
    await load()
  } catch (e) {
    err.value = e instanceof Error ? e.message : '操作失败'
  } finally {
    busyId.value = null
  }
}

onMounted(load)
</script>

<template>
  <section class="head">
    <h1>审核作业</h1>
    <p>
      通过就发星，退回要写原因。
      <RouterLink to="/parent/tasks">去布置</RouterLink>
    </p>
  </section>

  <div v-if="!session.child" class="empty">
    <strong>还没有孩子档案</strong>
    <p>先去家长端总览建一个。</p>
  </div>

  <div v-else-if="loading" class="quiet">正在加载…</div>

  <div v-else-if="!items.length" class="quiet">
    没有待审核的作业。孩子交了会出现在这里。
  </div>

  <template v-else>
    <p v-if="msg" class="ok">{{ msg }}</p>
    <p v-if="err" class="bad">{{ err }}</p>

    <article v-for="t in items" :key="t.id" class="card">
      <header class="card-head">
        <div class="line">
          <span class="subject">{{ t.subject }}</span>
          <h2>{{ t.title }}</h2>
        </div>
        <div class="meta">
          {{ timeOf(t.submitted_at) }} 提交 · 用了 {{ fmtMinutes(t.spent_sec) }}
          <template v-if="rejectCount(t)"> · 之前退回过 {{ rejectCount(t) }} 次</template>
        </div>
      </header>

      <div v-if="t.shots.length" class="shots">
        <a v-for="s in t.shots" :key="s.id" :href="s.url" target="_blank" rel="noopener">
          <img :src="s.url" alt="作业照片" />
        </a>
      </div>
      <p v-else class="no-shot">这次没拍照，只有下面这句话。</p>

      <p v-if="t.submit_note" class="quote">{{ t.submit_note }}</p>

      <div v-if="rejectingId === t.id" class="reject-box">
        <label>
          <span>哪里要改</span>
          <input
            v-model="comment" type="text" maxlength="255"
            placeholder="例如：第 3 题漏了单位"
            @keyup.enter="submitReject(t)"
          />
        </label>
        <div class="ops">
          <button class="warn" :disabled="busyId === t.id" @click="submitReject(t)">
            {{ busyId === t.id ? '退回中…' : '确认退回' }}
          </button>
          <button class="ghost" @click="rejectingId = null">算了</button>
        </div>
      </div>

      <div v-else class="ops">
        <button class="primary" :disabled="busyId === t.id" @click="approve(t)">
          {{ busyId === t.id ? '处理中…' : `通过，给 ${t.stars} 颗星` }}
        </button>
        <button class="ghost" @click="openReject(t)">退回重做</button>
      </div>
    </article>
  </template>
</template>

<style scoped>
.head { margin-bottom: 22px; }
h1 { font-size: 21px; font-weight: 500; margin-bottom: 6px; }
.head p { font-size: 13px; color: var(--muted); }

.card {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 16px 18px;
  margin-bottom: 14px;
}
.card-head { margin-bottom: 14px; }
.line { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.subject {
  font-size: 11px; color: var(--muted);
  background: var(--page); border-radius: 4px; padding: 1px 6px;
}
.card-head h2 { font-size: 15px; font-weight: 500; }
.meta { font-size: 11.5px; color: var(--hint); margin-top: 3px; }

.shots {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 10px; margin-bottom: 12px;
}
.shots a {
  display: block; aspect-ratio: 3 / 4;
  background: var(--page); border: 1px solid var(--line);
  border-radius: var(--r-sm); overflow: hidden;
}
.shots img { width: 100%; height: 100%; object-fit: cover; display: block; }
.no-shot { font-size: 12px; color: var(--hint); margin-bottom: 10px; }

.quote {
  font-size: 13px; color: var(--ink-2);
  background: var(--page); border-radius: var(--r-sm);
  padding: 10px 13px; margin-bottom: 14px; white-space: pre-wrap;
}

.reject-box {
  border-top: 1px solid #f0f2f4; padding-top: 13px;
}
.reject-box label { display: flex; flex-direction: column; gap: 5px; }
.reject-box span { font-size: 11.5px; color: var(--hint); }
.reject-box input {
  font: inherit; font-size: 13px;
  padding: 7px 10px;
  background: var(--page); color: var(--ink);
  border: 1px solid var(--line); border-radius: var(--r-sm);
  outline: none;
}
.reject-box input:focus { border-color: var(--bad); background: var(--card); }

.ops { display: flex; align-items: center; gap: 10px; margin-top: 13px; flex-wrap: wrap; }
.reject-box .ops { margin-top: 11px; }
button { font: inherit; cursor: pointer; }
.primary {
  font-size: 13px; padding: 7px 18px;
  background: var(--kid); color: #fff;
  border: none; border-radius: var(--r-sm);
}
.primary:disabled { background: var(--page); color: var(--hint); cursor: default; }
.ghost {
  font-size: 12.5px; padding: 6px 14px;
  background: transparent; color: var(--muted);
  border: 1px solid var(--line); border-radius: var(--r-sm);
}
.warn {
  font-size: 13px; padding: 7px 18px;
  background: var(--bad); color: #fff;
  border: none; border-radius: var(--r-sm);
}
.ok { font-size: 12.5px; color: var(--ok); margin-bottom: 12px; }
.bad { font-size: 12.5px; color: var(--bad); margin-bottom: 12px; }
.quiet {
  font-size: 12.5px; color: var(--hint);
  background: var(--card); border: 1px dashed var(--line);
  border-radius: var(--r-md); padding: 18px;
}
.empty {
  background: var(--card); border: 1px dashed var(--line);
  border-radius: var(--r-md); padding: 18px;
}
.empty strong { font-size: 13.5px; font-weight: 500; }
.empty p { font-size: 12.5px; color: var(--muted); margin-top: 6px; }
</style>
