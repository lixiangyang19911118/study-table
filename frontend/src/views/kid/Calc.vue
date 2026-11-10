<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import {
  createRound, roundToMistakes, submitRound,
  type CalcResult, type Round,
} from '../../api/calc'
import { fmtClock } from '../../lib/time'

const route = useRoute()
const router = useRouter()

/**
 * 两种进入方式：
 * - /kid/calc/12   口算任务，交卷后自动结算并发星
 * - /kid/calc      独立练习，只记成绩不发星（发星会被反复练刷通胀）
 */
const taskId = computed(() => {
  const raw = route.params.id
  const n = Number(raw)
  return Number.isFinite(n) && n > 0 ? n : null
})

const phase = ref<'loading' | 'doing' | 'result'>('loading')
const round = ref<Round | null>(null)
const idx = ref(0)
const draft = ref('')
const answers = ref<(string | null)[]>([])
const result = ref<CalcResult | null>(null)
const err = ref('')
const busy = ref(false)
const savedToMistakes = ref(false)
const inputEl = ref<HTMLInputElement | null>(null)

const current = computed(() => round.value?.questions[idx.value] ?? null)
const isLast = computed(() => !!round.value && idx.value === round.value.total - 1)

async function start() {
  phase.value = 'loading'
  err.value = ''
  result.value = null
  idx.value = 0
  draft.value = ''
  savedToMistakes.value = false
  try {
    const r = await createRound({
      count: 20,
      range_max: 20,
      task_id: taskId.value,
    })
    round.value = r
    answers.value = new Array(r.total).fill(null)
    phase.value = 'doing'
    await focusInput()
  } catch (e) {
    err.value = e instanceof Error ? e.message : '出题失败'
  }
}

async function focusInput() {
  await nextTick()
  inputEl.value?.focus()
}

function commit() {
  if (!round.value) return
  // 空着也算一次作答（后端按错处理）。允许跳过，但不给「回头改」的机会——
  // 口算练的是即时反应，能改就会一直改。
  answers.value[idx.value] = draft.value.trim() || null
  draft.value = ''

  if (isLast.value) {
    void finish()
    return
  }
  idx.value += 1
  void focusInput()
}

async function finish() {
  if (!round.value || busy.value) return
  busy.value = true
  err.value = ''
  try {
    result.value = await submitRound(round.value.id, answers.value)
    phase.value = 'result'
  } catch (e) {
    err.value = e instanceof Error ? e.message : '交卷失败'
  } finally {
    busy.value = false
  }
}

async function addToMistakes() {
  if (!round.value) return
  busy.value = true
  err.value = ''
  try {
    await roundToMistakes(round.value.id)
    savedToMistakes.value = true
  } catch (e) {
    err.value = e instanceof Error ? e.message : '加入错题本失败'
  } finally {
    busy.value = false
  }
}

function percent(x: number) {
  return `${Math.round(x * 100)}%`
}

function quit() {
  router.push('/kid/today')
}

onMounted(start)
</script>

<template>
  <div class="back">
    <RouterLink to="/kid/today">← 回到今天</RouterLink>
  </div>

  <div v-if="phase === 'loading'" class="quiet">{{ err || '正在出题…' }}</div>

  <!-- 作答：一题一屏 -->
  <template v-else-if="phase === 'doing' && round && current">
    <header class="head">
      <div class="progress">
        <div class="bar">
          <span :style="{ width: `${((idx + 1) / round.total) * 100}%` }"></span>
        </div>
        <span class="count">第 {{ idx + 1 }} / {{ round.total }} 题</span>
      </div>
    </header>

    <section class="quiz">
      <p class="stem">{{ current.stem }}</p>
      <input
        ref="inputEl"
        v-model="draft"
        class="answer"
        type="text"
        inputmode="numeric"
        autocomplete="off"
        placeholder="填答案"
        @keyup.enter="commit"
      />
      <div class="ops">
        <button class="primary" :disabled="busy" @click="commit">
          {{ isLast ? (busy ? '判分中…' : '交卷') : '下一题' }}
        </button>
        <span class="hint">回车也行 · 不会可以留空跳过</span>
      </div>
      <p v-if="err" class="bad">{{ err }}</p>
    </section>

    <p class="foot-hint">
      做完自动判分，不用等爸爸妈妈批。
      <button class="linklike" @click="quit">先不做了</button>
    </p>
  </template>

  <!-- 结果 -->
  <template v-else-if="phase === 'result' && result">
    <section class="score">
      <div class="big">
        <strong>{{ result.right_count }}</strong>
        <span>/ {{ result.total }}</span>
      </div>
      <p class="sub">
        正确率 {{ percent(result.accuracy) }} · 用时 {{ fmtClock(result.seconds) }}
      </p>
      <p v-if="result.stars_earned > 0" class="stars">
        拿到 <strong>{{ result.stars_earned }}</strong> 颗星
      </p>
      <p v-else-if="result.task" class="stars zero">
        这一轮没有星星，错的题看一眼再来
      </p>
    </section>

    <section v-if="result.wrong.length" class="wrong">
      <div class="wrong-head">
        <h2>错了 {{ result.wrong.length }} 道</h2>
        <button
          class="ghost"
          :disabled="busy || savedToMistakes"
          @click="addToMistakes"
        >
          {{ savedToMistakes ? '已加入错题本' : '全部加入错题本' }}
        </button>
      </div>

      <ul>
        <li v-for="w in result.wrong" :key="w.index">
          <span class="q">{{ w.stem }}</span>
          <span class="yours">你写 {{ w.your_answer || '空' }}</span>
          <span class="right">正确 {{ w.right_answer }}</span>
        </li>
      </ul>
      <p class="hint">
        加进错题本之后，会按 1 / 2 / 4 / 7 天提醒你复习。不想加也行，这只是这一次的练习记录。
      </p>
    </section>

    <section v-else class="all-right">
      <strong>全对，一道都没错</strong>
      <p>要不要再来一轮？</p>
    </section>

    <div class="ops end">
      <button class="primary" @click="start">再来一轮</button>
      <button class="ghost" @click="quit">回到今天</button>
    </div>

    <p v-if="err" class="bad">{{ err }}</p>
  </template>
</template>

<style scoped>
.back { margin-bottom: 14px; }
.back a { font-size: 12.5px; color: var(--muted); }

.head { margin-bottom: 22px; }
.progress { display: flex; align-items: center; gap: 12px; }
.bar { flex: 1; height: 4px; background: var(--line); border-radius: 2px; overflow: hidden; }
.bar span { display: block; height: 100%; background: var(--kid); transition: width 0.18s; }
.count { font-size: 11.5px; color: var(--hint); font-variant-numeric: tabular-nums; }

.quiz {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 26px 22px;
}
.stem {
  font-size: 26px; font-weight: 500; text-align: center;
  color: var(--ink); margin-bottom: 22px;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.5px;
}
.answer {
  display: block; width: 100%; max-width: 220px; margin: 0 auto;
  font: inherit; font-size: 24px; text-align: center;
  padding: 10px 12px;
  background: var(--page); color: var(--ink);
  border: 1px solid var(--line); border-radius: var(--r-sm);
  outline: none;
  font-variant-numeric: tabular-nums;
}
.answer:focus { border-color: var(--kid); background: var(--card); }

.ops { display: flex; align-items: center; justify-content: center; gap: 14px; margin-top: 20px; flex-wrap: wrap; }
.ops.end { justify-content: flex-start; margin-top: 20px; }
button { font: inherit; cursor: pointer; }
.primary {
  font-size: 13.5px; padding: 9px 30px;
  background: var(--kid); color: #fff; border: none; border-radius: var(--r-sm);
}
.primary:disabled { background: var(--page); color: var(--hint); cursor: default; }
.ghost {
  font-size: 12.5px; padding: 7px 16px;
  background: transparent; color: var(--muted);
  border: 1px solid var(--line); border-radius: var(--r-sm);
}
.hint { font-size: 11.5px; color: var(--hint); }
.foot-hint { font-size: 12px; color: var(--hint); text-align: center; margin-top: 18px; }
.linklike {
  font: inherit; font-size: 12px; cursor: pointer;
  background: none; border: none; padding: 0;
  color: var(--kid); text-decoration: underline;
}

.score {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 22px; margin-bottom: 16px;
}
.big { display: flex; align-items: baseline; gap: 6px; }
.big strong { font-size: 40px; font-weight: 500; color: var(--star); font-variant-numeric: tabular-nums; }
.big span { font-size: 16px; color: var(--hint); }
.sub { font-size: 12.5px; color: var(--muted); margin-top: 2px; }
.stars { font-size: 13.5px; color: var(--ink-2); margin-top: 12px; }
.stars strong { color: var(--star); font-weight: 500; }
.stars.zero { color: var(--muted); }

.wrong, .all-right {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 16px 18px; margin-bottom: 16px;
}
.wrong-head { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.wrong-head h2 { font-size: 14px; font-weight: 500; }
.wrong-head button { margin-left: auto; }
.wrong ul { list-style: none; margin: 0 0 10px; padding: 0; }
.wrong li {
  display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;
  padding: 7px 0; border-bottom: 1px solid #f0f2f4;
  font-size: 12.5px;
}
.wrong li:last-child { border-bottom: none; }
.q { color: var(--ink); font-variant-numeric: tabular-nums; }
.yours { color: var(--bad); font-size: 11.5px; }
.right { color: var(--ok); font-size: 11.5px; }

.all-right strong { font-size: 14px; font-weight: 500; color: var(--ok); }
.all-right p { font-size: 12.5px; color: var(--muted); margin-top: 4px; }

.quiet, .bad { font-size: 12.5px; }
.quiet { color: var(--hint); background: var(--card); border: 1px dashed var(--line); border-radius: var(--r-md); padding: 18px; }
.bad { color: var(--bad); margin-top: 10px; }
</style>
