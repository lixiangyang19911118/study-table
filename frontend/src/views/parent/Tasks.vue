<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import {
  createTask, deleteTask, listTasks, patchTask,
  SUBJECTS, type Subject, type TaskBrief,
} from '../../api/tasks'
import { fmtClock, timeOf } from '../../lib/time'
import { useSession } from '../../stores/session'

const session = useSession()

const open = ref<TaskBrief[]>([])
const done = ref<TaskBrief[]>([])
const loading = ref(true)
const busy = ref(false)
const err = ref('')
const msg = ref('')

const editingId = ref<number | null>(null)

const blank = () => ({
  subject: '语文' as Subject,
  title: '',
  // calc 会让孩子进「一题一屏」的口算页，交卷当场判分，不走拍照提交
  kind: 'normal' as 'normal' | 'calc',
  minutes_est: 20,
  stars: 1,
  note: '',
})
const form = ref(blank())

const editing = computed(() => {
  const id = editingId.value
  return id === null ? null : open.value.find((t) => t.id === id) ?? null
})

const STATUS_TEXT: Record<string, string> = {
  todo: '待做',
  doing: '进行中',
  rejected: '已退回',
}

async function load() {
  loading.value = true
  err.value = ''
  try {
    const [a, b] = await Promise.all([listTasks('today'), listTasks('done')])
    open.value = a
    done.value = b
  } catch (e) {
    err.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!form.value.title.trim()) {
    err.value = '先写个标题，孩子才知道要做什么'
    return
  }
  busy.value = true
  err.value = ''
  msg.value = ''
  const body = {
    subject: form.value.subject,
    title: form.value.title.trim(),
    kind: form.value.kind,
    minutes_est: form.value.minutes_est,
    stars: form.value.stars,
    note: form.value.note.trim() || null,
  }
  try {
    if (editingId.value !== null) {
      await patchTask(editingId.value, body)
      msg.value = '改好了'
    } else {
      await createTask(body)
      msg.value = '布置好了，孩子端就能看到'
    }
    form.value = blank()
    editingId.value = null
    await load()
  } catch (e) {
    err.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    busy.value = false
  }
}

function edit(t: TaskBrief) {
  editingId.value = t.id
  form.value = {
    subject: t.subject as Subject,
    title: t.title,
    kind: t.kind === 'calc' ? 'calc' : 'normal',
    minutes_est: t.minutes_est,
    stars: t.stars,
    note: t.note ?? '',
  }
  msg.value = ''
  err.value = ''
}

function cancel() {
  editingId.value = null
  form.value = blank()
  err.value = ''
}

async function remove(t: TaskBrief) {
  if (!window.confirm(`删掉「${t.title}」？删掉之后孩子端就看不到了。`)) return
  err.value = ''
  msg.value = ''
  try {
    await deleteTask(t.id)
    if (editingId.value === t.id) cancel()
    msg.value = '已删除'
    await load()
  } catch (e) {
    err.value = e instanceof Error ? e.message : '删除失败'
  }
}

onMounted(load)
</script>

<template>
  <section class="head">
    <h1>布置作业</h1>
    <p>
      布置下去孩子端立刻能看到。
      <RouterLink to="/parent/review">去审核</RouterLink>
    </p>
  </section>

  <div v-if="!session.child" class="empty">
    <strong>还没有孩子档案</strong>
    <p>先去家长端总览建一个，任务得挂在 <code>child_id</code> 上。</p>
    <RouterLink class="link" to="/parent/dashboard">去建档案</RouterLink>
  </div>

  <div v-else class="panel">
    <div class="panel-head">
      <h2>{{ editing ? `修改「${editing.title}」` : '新任务' }}</h2>
      <span v-if="editing" class="badge">只有还没开始的才能改</span>
    </div>

    <div class="form">
      <label class="narrow">
        <span>科目</span>
        <select v-model="form.subject">
          <option v-for="s in SUBJECTS" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <label class="grow">
        <span>做什么</span>
        <input v-model="form.title" type="text" maxlength="128" placeholder="例如：口算 20 题" />
      </label>
      <label class="narrow">
        <span>预计分钟</span>
        <input v-model.number="form.minutes_est" type="number" min="5" max="180" />
      </label>
      <label class="narrow">
        <span>完成给几颗星</span>
        <input v-model.number="form.stars" type="number" min="1" max="10" />
      </label>
    </div>

    <div class="kind-row">
      <button
        class="kind" :class="{ on: form.kind === 'normal' }"
        :disabled="!!editing" @click="form.kind = 'normal'"
      >
        普通作业<span>拍照提交，家长审核</span>
      </button>
      <button
        class="kind" :class="{ on: form.kind === 'calc' }"
        :disabled="!!editing" @click="form.kind = 'calc'"
      >
        口算练习<span>电脑出题，交卷当场判分发星</span>
      </button>
    </div>

    <label class="field">
      <span>想对孩子说的话（可不填，会显示在任务页）</span>
      <textarea v-model="form.note" rows="2" maxlength="500" placeholder="例如：写完自己检查一遍"></textarea>
    </label>

    <div class="actions">
      <button class="primary" :disabled="busy" @click="submit">
        {{ busy ? '保存中…' : editing ? '保存修改' : '布置下去' }}
      </button>
      <button v-if="editing" class="ghost" @click="cancel">取消</button>
      <span v-if="msg" class="ok">{{ msg }}</span>
      <span v-if="err" class="bad">{{ err }}</span>
    </div>
  </div>

  <section v-if="session.child" class="group">
    <h2>今天还没交的 <span v-if="open.length" class="count">{{ open.length }}</span></h2>

    <div v-if="loading" class="quiet">加载中…</div>
    <div v-else-if="!open.length" class="quiet">今天没有待交的任务。</div>

    <div v-else class="rows">
      <div v-for="t in open" :key="t.id" class="row" :class="t.status">
        <span class="bar"></span>
        <div class="body">
          <div class="line">
            <span class="subject">{{ t.subject }}</span>
            <span class="title">{{ t.title }}</span>
            <span v-if="t.kind === 'calc'" class="chip">口算</span>
            <span class="chip">{{ STATUS_TEXT[t.status] }}</span>
            <span v-if="t.status === 'doing'" class="chip timer">
              已用 {{ fmtClock(t.spent_sec) }}
            </span>
          </div>
          <div class="meta">
            预计 {{ t.minutes_est }} 分钟 · {{ t.stars }} 颗星
            <template v-if="t.shot_count"> · 已有 {{ t.shot_count }} 张照片</template>
          </div>
        </div>
        <div class="ops">
          <button v-if="t.status === 'todo'" class="mini" @click="edit(t)">编辑</button>
          <button class="mini danger" @click="remove(t)">删除</button>
        </div>
      </div>
    </div>
  </section>

  <section v-if="session.child && done.length" class="group">
    <h2>今天已完成 <span class="count">{{ done.length }}</span></h2>
    <div class="rows">
      <div v-for="t in done" :key="t.id" class="row done">
        <span class="tick">✓</span>
        <div class="body">
          <div class="line">
            <span class="subject">{{ t.subject }}</span>
            <span class="title">{{ t.title }}</span>
          </div>
          <div class="meta">
            {{ timeOf(t.reviewed_at) }} 通过 · 用时 {{ fmtClock(t.spent_sec) }}
          </div>
        </div>
        <span class="gain">+{{ t.stars }}</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.head { margin-bottom: 22px; }
h1 { font-size: 21px; font-weight: 500; margin-bottom: 6px; }
.head p { font-size: 13px; color: var(--muted); }

.panel {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 16px 18px 15px;
  margin-bottom: 24px;
}
.panel-head { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.panel-head h2 { font-size: 14px; font-weight: 500; }
.badge {
  font-size: 10.5px; color: var(--hint);
  border: 1px solid var(--line); border-radius: 5px; padding: 1px 7px;
}

.form {
  display: grid; gap: 12px 14px;
  grid-template-columns: 110px minmax(0, 1fr) 100px 100px;
}
.form label { display: flex; flex-direction: column; gap: 5px; }
.form span { font-size: 11.5px; color: var(--hint); }
.form input, .form select, .field textarea {
  font: inherit; font-size: 13px;
  padding: 7px 10px;
  background: var(--page); color: var(--ink);
  border: 1px solid var(--line); border-radius: var(--r-sm);
  outline: none;
}
.form input:focus, .form select:focus, .field textarea:focus {
  border-color: var(--kid); background: var(--card);
}

.field { display: flex; flex-direction: column; gap: 5px; margin-top: 12px; }
.field span { font-size: 11.5px; color: var(--hint); }
.field textarea { resize: vertical; line-height: 1.6; }

.actions { display: flex; align-items: center; gap: 12px; margin-top: 15px; flex-wrap: wrap; }
button { font: inherit; cursor: pointer; }
.primary {
  font-size: 13px; padding: 7px 20px;
  background: var(--kid); color: #fff;
  border: none; border-radius: var(--r-sm);
}
.primary:disabled { background: var(--page); color: var(--hint); cursor: default; }
.ghost {
  font-size: 12.5px; padding: 6px 14px;
  background: transparent; color: var(--muted);
  border: 1px solid var(--line); border-radius: var(--r-sm);
}
.ok { font-size: 12px; color: var(--ok); }
.bad { font-size: 12px; color: var(--bad); }

.group { margin-bottom: 24px; }
.group h2 {
  font-size: 13px; font-weight: 500; color: var(--muted);
  margin-bottom: 10px; display: flex; align-items: center; gap: 7px;
}
.count {
  font-size: 11px; color: var(--hint);
  background: var(--card); border: 1px solid var(--line);
  border-radius: 20px; padding: 0 7px; line-height: 17px;
}
.rows { display: flex; flex-direction: column; gap: 8px; }
.row {
  display: flex; align-items: center; gap: 13px;
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 12px 15px;
}
.bar { width: 3px; height: 28px; border-radius: 2px; background: var(--kid); flex: 0 0 auto; }
.row.doing .bar { background: var(--star); }
.row.rejected .bar { background: var(--bad); }
.body { min-width: 0; flex: 1; }
.line { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.subject {
  font-size: 11px; color: var(--muted);
  background: var(--page); border-radius: 4px; padding: 1px 6px;
}
.title { font-size: 13.5px; }
.meta { font-size: 11.5px; color: var(--hint); margin-top: 2px; }
.chip { font-size: 11px; color: var(--muted); }
.chip.timer { color: var(--star); }
.row.rejected .chip { color: var(--bad); }

.ops { display: flex; gap: 6px; flex: 0 0 auto; }
.mini {
  font-size: 11.5px; padding: 4px 10px;
  background: transparent; color: var(--muted);
  border: 1px solid var(--line); border-radius: var(--r-sm);
}
.mini:hover { color: var(--ink); }
.mini.danger:hover { color: var(--bad); border-color: #f0d4d4; }

.row.done .title { color: var(--ink-2); }
.tick {
  flex: 0 0 auto; width: 20px; height: 20px; line-height: 20px; text-align: center;
  font-size: 12px; color: var(--ok); background: #eaf5ee; border-radius: 50%;
}
.gain { margin-left: auto; flex: 0 0 auto; font-size: 13px; color: var(--star); }

.quiet {
  font-size: 12.5px; color: var(--hint);
  background: var(--card); border: 1px dashed var(--line);
  border-radius: var(--r-md); padding: 15px 18px;
}
.empty {
  background: var(--card); border: 1px dashed var(--line);
  border-radius: var(--r-md); padding: 18px;
}
.empty strong { font-size: 13.5px; font-weight: 500; }
.empty p { font-size: 12.5px; color: var(--muted); margin-top: 6px; }
.link { font-size: 12.5px; display: inline-block; margin-top: 10px; }

.kind-row { display: flex; gap: 10px; margin: 14px 0; flex-wrap: wrap; }
.kind {
  flex: 1 1 200px; text-align: left; cursor: pointer;
  font: inherit; font-size: 13px;
  padding: 10px 14px;
  background: var(--page); color: var(--ink-2);
  border: 1px solid var(--line); border-radius: var(--r-sm);
  display: flex; flex-direction: column; gap: 3px;
}
.kind span { font-size: 11px; color: var(--hint); }
.kind.on { background: var(--kid-soft); color: var(--kid); border-color: #c7d8ef; }
.kind.on span { color: var(--kid); }
.kind:disabled { cursor: default; opacity: 0.6; }

@media (max-width: 720px) {
  .form { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
  .form .grow { grid-column: 1 / -1; }
}
</style>
