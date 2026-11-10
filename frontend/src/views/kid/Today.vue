<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { listTasks, type TaskBrief } from '../../api/tasks'
import { dayLabel, fmtClock, timeOf, useNow } from '../../lib/time'
import { useSession } from '../../stores/session'

const session = useSession()

const today = ref<TaskBrief[]>([])
const backlog = ref<TaskBrief[]>([])
const review = ref<TaskBrief[]>([])
const done = ref<TaskBrief[]>([])

const loading = ref(true)
const err = ref('')

// 进行中的任务要显示「已用 3:21」，每秒跳一次
const now = useNow()

const gradeText = computed(() => {
  const g = session.child?.grade
  return g ? `${['一', '二', '三', '四', '五', '六'][g - 1] ?? g} 年级` : '年级未设置'
})

const todayStars = computed(() => done.value.reduce((sum, t) => sum + t.stars, 0))

const openCount = computed(() => today.value.length)

/** 口算进「一题一屏」的做题页，其余进拍照提交的作业页。 */
function taskLink(t: TaskBrief) {
  return t.kind === 'calc' ? `/kid/calc/${t.id}` : `/kid/task/${t.id}`
}

const greeting = computed(() => {
  if (!session.child) return '孩子端 · 今日'
  if (openCount.value === 0 && backlog.value.length === 0) {
    return `${session.child.name}，今天的事都做完了`
  }
  if (openCount.value === 0) {
    return `${session.child.name}，今天的事做完了`
  }
  return `${session.child.name}，今天有 ${openCount.value} 件事`
})

const subline = computed(() => {
  if (!session.child) return '账号下还没有孩子档案'
  const bits = [`${gradeText.value} · ${session.child.edition}`]
  if (backlog.value.length) bits.push(`${backlog.value.length} 件要补做`)
  if (review.value.length) bits.push(`${review.value.length} 件等爸爸妈妈看`)
  return bits.join(' · ')
})

function actionLabel(t: TaskBrief) {
  if (t.status === 'doing') return '继续'
  if (t.status === 'rejected') return '重做'
  return '开始做'
}

function statusText(t: TaskBrief) {
  if (t.status === 'doing') return `进行中 ${fmtClock(elapsed(t))}`
  if (t.status === 'rejected') return '退回了'
  return ''
}

function elapsed(t: TaskBrief) {
  return t.status === 'doing' && t.started_at
    ? t.spent_sec + Math.max(0, Math.floor((now.value - Date.parse(t.started_at)) / 1000))
    : t.spent_sec
}

async function load() {
  loading.value = true
  err.value = ''
  try {
    const [a, b, c, d] = await Promise.all([
      listTasks('today'),
      listTasks('backlog'),
      listTasks('review'),
      listTasks('done'),
    ])
    today.value = a
    backlog.value = b
    review.value = c
    done.value = d
  } catch (e) {
    err.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="head">
    <div>
      <h1>{{ greeting }}</h1>
      <p class="sub">{{ subline }}</p>
      <RouterLink v-if="session.child" class="practice" to="/kid/calc">
        想多练几道口算？自己来一轮
      </RouterLink>
    </div>
    <div v-if="session.child" class="stars">
      <strong>{{ todayStars }}</strong>
      <span>颗星 · 今天</span>
    </div>
  </section>

  <!-- 所有业务表都挂 child_id，没档案什么都写不了 -->
  <div v-if="!session.child" class="empty">
    <strong>先去家长端建一个孩子档案</strong>
    <p>任务、错题、教材都挂在 <code>child_id</code> 上，没有档案就写不进数据。</p>
    <RouterLink class="link" to="/parent/dashboard">去家长端设置</RouterLink>
  </div>

  <div v-else-if="loading" class="hint">正在加载…</div>

  <div v-else-if="err" class="empty">
    <strong>没能读到今天的任务</strong>
    <p>{{ err }}</p>
    <button class="link" @click="load">重试</button>
  </div>

  <template v-else>
    <!-- 今天还没交的 -->
    <section class="group">
      <h2>今天要做 <span v-if="today.length" class="count">{{ today.length }}</span></h2>

      <div v-if="!today.length" class="quiet">
        今天的任务都交出去了。想多做点，可以让爸爸妈妈再布置。
      </div>

      <div v-else class="rows">
        <RouterLink
          v-for="t in today"
          :key="t.id"
          class="row"
          :class="t.status"
          :to="taskLink(t)"
        >
          <span class="bar"></span>
          <div class="body">
            <div class="line">
              <span class="subject">{{ t.subject }}</span>
              <span class="title">{{ t.title }}</span>
              <span v-if="statusText(t)" class="chip">{{ statusText(t) }}</span>
            </div>
            <div class="meta">
              预计 {{ t.minutes_est }} 分钟 · 完成得 {{ t.stars }} 颗星
            </div>
          </div>
          <span class="go">{{ actionLabel(t) }}</span>
        </RouterLink>
      </div>
    </section>

    <!-- 补做：更早的日子还没交的。逾期不是状态，是算出来的 -->
    <section v-if="backlog.length" class="group">
      <h2>要补做的 <span class="count">{{ backlog.length }}</span></h2>
      <div class="rows">
        <RouterLink
          v-for="t in backlog"
          :key="t.id"
          class="row backlog"
          :to="taskLink(t)"
        >
          <span class="bar"></span>
          <div class="body">
            <div class="line">
              <span class="day">{{ dayLabel(t.task_date) }}</span>
              <span class="subject">{{ t.subject }}</span>
              <span class="title">{{ t.title }}</span>
            </div>
            <div class="meta">还没交 · 完成得 {{ t.stars }} 颗星</div>
          </div>
          <span class="go">补上</span>
        </RouterLink>
      </div>
    </section>

    <!-- 交给家长了，球在对面 -->
    <section v-if="review.length" class="group">
      <h2>等爸爸妈妈看 <span class="count">{{ review.length }}</span></h2>
      <div class="rows">
        <RouterLink
          v-for="t in review"
          :key="t.id"
          class="row submitted"
          :to="taskLink(t)"
        >
          <span class="bar"></span>
          <div class="body">
            <div class="line">
              <span class="subject">{{ t.subject }}</span>
              <span class="title">{{ t.title }}</span>
            </div>
            <div class="meta">已提交 {{ timeOf(t.submitted_at) }}，等一会儿</div>
          </div>
          <span class="go">看看</span>
        </RouterLink>
      </div>
    </section>

    <!-- 今天已通过 -->
    <section v-if="done.length" class="group">
      <h2>已经完成 <span class="count">{{ done.length }}</span></h2>
      <div class="rows">
        <RouterLink
          v-for="t in done"
          :key="t.id"
          class="row done"
          :to="taskLink(t)"
        >
          <span class="tick">✓</span>
          <div class="body">
            <div class="line">
              <span class="subject">{{ t.subject }}</span>
              <span class="title">{{ t.title }}</span>
            </div>
            <div class="meta">用时 {{ fmtClock(t.spent_sec) }}</div>
          </div>
          <span class="gain">+{{ t.stars }}</span>
        </RouterLink>
      </div>
    </section>
  </template>
</template>

<style scoped>
.head {
  display: flex; align-items: flex-start; gap: 20px;
  margin-bottom: 26px;
}
.head h1 { font-size: 21px; font-weight: 500; margin-bottom: 5px; }
.sub { font-size: 13px; color: var(--muted); }
.practice {
  display: inline-block; margin-top: 7px;
  font-size: 12px; color: var(--kid);
}

.stars {
  margin-left: auto; flex: 0 0 auto;
  display: flex; align-items: baseline; gap: 5px;
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 8px 14px;
}
.stars strong { font-size: 20px; font-weight: 500; color: var(--star); }
.stars span { font-size: 11.5px; color: var(--hint); }

.group { margin-bottom: 26px; }
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
  display: flex; align-items: center; gap: 14px;
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 13px 16px;
  color: var(--ink); transition: border-color 0.15s;
}
.row:hover { border-color: #c9d6ea; }
.bar { width: 3px; height: 30px; border-radius: 2px; background: var(--kid); flex: 0 0 auto; }
.row.doing .bar { background: var(--star); }
.row.rejected .bar { background: var(--bad); }
.row.submitted .bar { background: #c9c9c9; }
.row.backlog .bar { background: var(--warn); }

.body { min-width: 0; flex: 1; }
.line { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.subject {
  font-size: 11px; color: var(--muted);
  background: var(--page); border-radius: 4px; padding: 1px 6px;
}
.day { font-size: 11px; color: var(--warn); }
.title { font-size: 14px; }
.meta { font-size: 11.5px; color: var(--hint); margin-top: 2px; }

.chip { font-size: 11px; color: var(--star); }
.row.rejected .chip { color: var(--bad); }

.go {
  flex: 0 0 auto; font-size: 12.5px; color: var(--kid);
  border: 1px solid #d8e2f3; background: var(--kid-soft);
  border-radius: var(--r-sm); padding: 5px 13px;
}
.row.doing .go { color: #8a6206; border-color: #f0e0bb; background: #fdf6e7; }
.row.rejected .go { color: var(--bad); border-color: #f0d4d4; background: #fdf0f0; }
.row.submitted .go { color: var(--muted); border-color: var(--line); background: var(--page); }

.row.done { padding: 11px 16px; }
.row.done .title { color: var(--ink-2); }
.tick {
  flex: 0 0 auto; width: 20px; height: 20px; line-height: 20px; text-align: center;
  font-size: 12px; color: var(--ok);
  background: #eaf5ee; border-radius: 50%;
}
.gain {
  margin-left: auto; flex: 0 0 auto;
  font-size: 13px; color: var(--star); font-weight: 500;
}

.quiet {
  font-size: 12.5px; color: var(--hint);
  background: var(--card); border: 1px dashed var(--line);
  border-radius: var(--r-md); padding: 16px 18px;
}
.hint { font-size: 13px; color: var(--hint); padding: 20px 0; }

.empty {
  background: var(--card); border: 1px dashed var(--line);
  border-radius: var(--r-md); padding: 18px;
}
.empty strong { font-size: 13.5px; font-weight: 500; }
.empty p { font-size: 12.5px; color: var(--muted); margin-top: 6px; }
.link {
  font-size: 12.5px; display: inline-block; margin-top: 10px;
  background: none; border: none; cursor: pointer; color: var(--kid); font-family: inherit;
}

@media (max-width: 720px) {
  .head { flex-direction: column; gap: 12px; }
  .stars { margin-left: 0; }
}
</style>
