<script setup lang="ts">
/**
 * 孩子端 · 打卡日历。
 *
 * 打卡不是按按钮，是「今天任务全部做完」自动记上的。所以这个页面不提供任何
 * 「打卡」按钮 —— 它只负责让孩子看见：我连着来了多少天、哪天空了。
 *
 * 进页面先试着结算一次（settle）。不这么做的话，孩子 20:00 做完最后一个任务，
 * 要等到 23:55 的定时任务才会盖上今天这一格，成就感的时机就全丢了。
 * settle 是幂等的，定时任务仍然是兜底。
 */
import { computed, onMounted, ref } from 'vue'

import {
  getCalendar,
  settleCheckin,
  type CalendarDay,
  type CalendarSnapshot,
} from '../../api/checkins'

const WEEK = ['一', '二', '三', '四', '五', '六', '日']

function iso(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

const now = new Date()
const TODAY = iso(now)
const CURRENT_MONTH = TODAY.slice(0, 7)

const data = ref<CalendarSnapshot | null>(null)
const month = ref(CURRENT_MONTH)
const loading = ref(true)
const err = ref('')
/** 本次进页面刚刚补记成功，放一次性提示 */
const justChecked = ref(false)

/** 1 号不是周一时，前面要空几格 */
const blanks = computed(() => (data.value ? data.value.first_weekday - 1 : 0))

/** 本月已打卡天数，和「累计」区分开 */
const monthChecked = computed(
  () => data.value?.days.filter((d) => d.checked).length ?? 0,
)

const todayCell = computed<CalendarDay | null>(
  () => data.value?.days.find((d) => d.date === TODAY) ?? null,
)

/** 今天的状态提示。孩子最容易困惑的是「为什么今天还没亮」。 */
const todayTip = computed(() => {
  if (!data.value) return ''
  if (data.value.checked_today) return '今天已经记上了，明天见 👋'
  if (data.value.today_all_done) return '任务都做完了，正在给你记上…'
  if (todayCell.value?.has_task) return '今天的任务还没做完，全部做完就会自动记上'
  return '今天没有布置任务，休息一下'
})

const canGoNext = computed(() => month.value < CURRENT_MONTH)

function shiftMonth(delta: number) {
  const [y, m] = month.value.split('-').map(Number)
  const d = new Date(y, m - 1 + delta, 1)
  if (iso(d).slice(0, 7) > CURRENT_MONTH) return
  month.value = iso(d).slice(0, 7)
  void load()
}

function cellClass(d: CalendarDay) {
  return {
    on: d.checked,
    off: !d.checked && d.has_task && d.date <= TODAY,
    idle: !d.has_task,
    today: d.date === TODAY,
    future: d.date > TODAY,
  }
}

async function load() {
  err.value = ''
  try {
    data.value = await getCalendar(month.value)
  } catch (e) {
    err.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    const r = await settleCheckin()
    justChecked.value = r.created
  } catch {
    // 结算失败不该挡住看日历，23:55 还有一次兜底
  }
  await load()
})
</script>

<template>
  <div v-if="loading" class="hint">正在翻开日历…</div>
  <p v-else-if="err && !data" class="bad">{{ err }}</p>

  <template v-else-if="data">
    <section class="hero">
      <div class="flame">
        <strong>{{ data.streak }}</strong>
        <span>天连续</span>
      </div>
      <div class="side">
        <h1>打卡日历</h1>
        <p class="sub">每天的任务全部做完，这一天就会自己亮起来</p>
        <p class="tip" :class="{ done: data.checked_today }">{{ todayTip }}</p>
      </div>
    </section>

    <p v-if="justChecked" class="ok">今天记上了，这是连续第 {{ data.streak }} 天 🎉</p>
    <p v-if="err" class="bad">{{ err }}</p>

    <section class="card">
      <header class="cal-head">
        <button class="arrow" title="上个月" @click="shiftMonth(-1)">‹</button>
        <span class="ym">
          {{ data.month.slice(0, 4) }} 年 {{ Number(data.month.slice(5, 7)) }} 月
        </span>
        <button
          class="arrow" title="下个月" :disabled="!canGoNext"
          @click="shiftMonth(1)"
        >
          ›
        </button>
      </header>

      <div class="grid week">
        <span v-for="w in WEEK" :key="w">{{ w }}</span>
      </div>

      <div class="grid days">
        <span v-for="n in blanks" :key="`b${n}`" class="blank"></span>
        <div
          v-for="d in data.days" :key="d.date"
          class="day" :class="cellClass(d)"
          :title="d.date"
        >
          {{ Number(d.date.slice(8, 10)) }}
        </div>
      </div>

      <footer class="legend">
        <span><i class="key on"></i>已打卡</span>
        <span><i class="key off"></i>有任务没做完</span>
        <span><i class="key idle"></i>没布置任务</span>
      </footer>
    </section>

    <section class="stats">
      <div class="stat">
        <strong>{{ monthChecked }}</strong>
        <span>本月打卡</span>
      </div>
      <div class="stat">
        <strong>{{ data.total }}</strong>
        <span>累计天数</span>
      </div>
      <div class="stat">
        <strong>{{ data.longest }}</strong>
        <span>最长连续</span>
      </div>
    </section>
  </template>
</template>

<style scoped>
.ok { font-size: 12.5px; color: var(--ok); margin-bottom: 12px; }
.bad { font-size: 12.5px; color: var(--bad); margin-bottom: 12px; }
.hint { font-size: 13px; color: var(--hint); padding: 20px 0; }

.hero {
  display: flex; align-items: center; gap: 20px;
  margin-bottom: 18px;
}
.flame {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  min-width: 92px; padding: 12px 16px;
  background: linear-gradient(160deg, #fdf3dd, #fbe9c4);
  border: 1px solid #f0dfb8; border-radius: var(--r-md);
}
.flame strong {
  font-size: 34px; font-weight: 500; line-height: 1.1;
  color: #b8801a; font-variant-numeric: tabular-nums;
}
.flame span { font-size: 11.5px; color: #9a7a3a; margin-top: 2px; }

.side h1 { font-size: 21px; font-weight: 500; margin-bottom: 3px; }
.sub { font-size: 12.5px; color: var(--muted); }
.tip {
  font-size: 12px; color: var(--hint); margin-top: 7px;
  transition: color 0.2s ease;
}
.tip.done { color: var(--ok); }

.card {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 16px 18px 14px;
  margin-bottom: 16px;
}
.cal-head {
  display: flex; align-items: center; justify-content: center; gap: 14px;
  margin-bottom: 12px;
}
.ym { font-size: 13.5px; color: var(--ink-2); font-variant-numeric: tabular-nums; }
.arrow {
  font: inherit; font-size: 16px; line-height: 1; cursor: pointer;
  width: 26px; height: 26px; border-radius: var(--r-sm);
  background: transparent; border: 1px solid var(--line); color: var(--muted);
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}
.arrow:hover:not(:disabled) { background: var(--kid-soft); color: var(--kid); border-color: #cfdef5; }
.arrow:disabled { opacity: 0.35; cursor: default; }

.grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }
.week { margin-bottom: 6px; }
.week span {
  text-align: center; font-size: 11px; color: var(--hint); padding-bottom: 2px;
}
.blank { aspect-ratio: 1; }

.day {
  aspect-ratio: 1; display: flex; align-items: center; justify-content: center;
  font-size: 12.5px; font-variant-numeric: tabular-nums;
  border-radius: var(--r-sm);
  border: 1px solid transparent;
  color: var(--hint);
  transition: background 0.18s ease, color 0.18s ease, transform 0.12s ease;
}
/* 已打卡：金色实心。孩子扫一眼就知道这个月亮了几格 */
.day.on {
  background: var(--star); color: #fff; font-weight: 500;
  box-shadow: 0 1px 3px rgba(224, 160, 32, 0.35);
}
/* 有任务但没做完：留个框，让人知道这天「该做而没做」 */
.day.off {
  background: #fbfbfc; border-color: var(--line); color: var(--ink-2);
}
/* 没布置任务：几乎透明，不给孩子「我漏了一天」的错觉 */
.day.idle { color: #cdd2d8; }
.day.future { opacity: 0.3; }
.day.on.future { opacity: 1; }
.day.today {
  box-shadow: 0 0 0 2px var(--kid);
}
.day.today.on { box-shadow: 0 0 0 2px var(--kid), 0 1px 3px rgba(224, 160, 32, 0.35); }

.legend {
  display: flex; gap: 16px; flex-wrap: wrap;
  margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--line);
}
.legend span { display: flex; align-items: center; gap: 5px; font-size: 11px; color: var(--hint); }
.key {
  width: 10px; height: 10px; border-radius: 3px; border: 1px solid transparent;
}
.key.on { background: var(--star); }
.key.off { background: #fbfbfc; border-color: var(--line); }
.key.idle { background: transparent; }

.stats { display: flex; gap: 10px; }
.stat {
  flex: 1; background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 13px 16px;
}
.stat strong {
  display: block; font-size: 22px; font-weight: 500; line-height: 1.25;
  color: var(--ink); font-variant-numeric: tabular-nums;
}
.stat span { font-size: 11.5px; color: var(--hint); }

@media (max-width: 640px) {
  .hero { flex-direction: column; align-items: stretch; gap: 12px; }
  .flame { flex-direction: row; gap: 6px; align-items: baseline; }
  .flame strong { font-size: 28px; }
  .day { font-size: 11.5px; }
  .stats { flex-wrap: wrap; }
  .stat { min-width: 30%; }
}
</style>
