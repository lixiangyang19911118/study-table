<script setup lang="ts">
/**
 * 家长端 · 本周回顾。
 *
 * 页面上有两组数字，口径不同，标题里写清楚了：
 * 「这周布置的」按布置日归周，「这周完成的」按完成日归周。
 * 周日补做上周的题会算进后者、不算进前者——所以完成率不会超过 100%。
 */
import { computed, onMounted, ref } from 'vue'

import { getWeekly, shiftWeek, type WeeklyReport } from '../../api/reports'

const report = ref<WeeklyReport | null>(null)
const week = ref('')
const loading = ref(true)
const err = ref('')

const maxDay = computed(() => {
  const m = Math.max(...(report.value?.daily.map((d) => d.done) ?? [0]))
  return Math.max(m, 1)
})

const maxSubject = computed(() => {
  const m = Math.max(...(report.value?.subjects.map((s) => s.done) ?? [0]))
  return Math.max(m, 1)
})

const ratePct = computed(() => {
  const r = report.value?.tasks.rate
  return r == null ? null : Math.round(r * 100)
})

const accPct = computed(() => {
  const a = report.value?.calc.accuracy
  return a == null ? null : Math.round(a * 100)
})

async function load(w?: string) {
  loading.value = true
  err.value = ''
  try {
    const r = await getWeekly(w)
    report.value = r
    week.value = r.week
  } catch (e) {
    err.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function move(delta: number) {
  if (!report.value) return
  void load(shiftWeek(report.value.week, delta))
}

onMounted(() => load())
</script>

<template>
  <section class="head">
    <div>
      <h1>每周回顾</h1>
      <p v-if="report" class="sub">{{ report.start }} ~ {{ report.end }}</p>
    </div>
    <div class="nav">
      <button class="mini" @click="move(-1)">上一周</button>
      <button class="mini" @click="load()">本周</button>
      <button class="mini" :disabled="report?.week === week && loading" @click="move(1)">
        下一周
      </button>
    </div>
  </section>

  <p v-if="err" class="bad">{{ err }}</p>
  <div v-if="loading" class="hint">正在汇总…</div>

  <template v-else-if="report">
    <section class="cards">
      <div class="card">
        <span class="num" :class="{ dim: ratePct === null }">
          {{ ratePct === null ? '—' : ratePct + '%' }}
        </span>
        <span class="lbl">这周布置的 · 完成率</span>
        <span class="foot">{{ report.tasks.completed }} / {{ report.tasks.planned }} 条</span>
      </div>
      <div class="card">
        <span class="num">{{ report.tasks.done_this_week }}</span>
        <span class="lbl">这周完成的 · 条数</span>
        <span class="foot">含补做往周的</span>
      </div>
      <div class="card">
        <span class="num star">{{ report.stars.earned }}</span>
        <span class="lbl">这周得了 · 颗星</span>
        <span class="foot">花了 {{ report.stars.spent }}，余额 {{ report.stars.balance }}</span>
      </div>
      <div class="card">
        <span class="num">{{ report.tasks.spent_min }}</span>
        <span class="lbl">这周用时 · 分钟</span>
        <span class="foot">口算另计 {{ report.calc.spent_min }} 分钟</span>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head"><h2>每天完成了多少</h2></div>
      <div class="bars">
        <div v-for="d in report.daily" :key="d.date" class="bar-col">
          <span class="bar-num">{{ d.done || '' }}</span>
          <div class="bar-track">
            <div
              class="bar-fill"
              :class="{ zero: !d.done }"
              :style="{ height: (d.done / maxDay) * 100 + '%' }"
            ></div>
          </div>
          <span class="bar-lbl">{{ d.weekday }}</span>
        </div>
      </div>
    </section>

    <div class="two">
      <section class="panel">
        <div class="panel-head"><h2>科目分布</h2></div>
        <p v-if="!report.subjects.length" class="quiet">这周还没有完成的任务。</p>
        <div v-else class="subjects">
          <div v-for="s in report.subjects" :key="s.subject" class="subj">
            <span class="sname">{{ s.subject }}</span>
            <div class="strack">
              <div class="sfill" :style="{ width: (s.done / maxSubject) * 100 + '%' }"></div>
            </div>
            <span class="snum">{{ s.done }}</span>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head"><h2>错题与口算</h2></div>
        <div class="pairs">
          <div class="pair">
            <span class="pnum">{{ report.mistakes.added }}</span>
            <span class="plbl">这周新增错题</span>
          </div>
          <div class="pair">
            <span class="pnum ok">{{ report.mistakes.mastered }}</span>
            <span class="plbl">这周掌握</span>
          </div>
          <div class="pair">
            <span class="pnum" :class="{ warn: report.mistakes.due > 0 }">
              {{ report.mistakes.due }}
            </span>
            <span class="plbl">当前待复习</span>
          </div>
          <div class="pair">
            <span class="pnum">{{ report.calc.rounds }}</span>
            <span class="plbl">口算轮次</span>
          </div>
          <div class="pair">
            <span class="pnum">{{ accPct === null ? '—' : accPct + '%' }}</span>
            <span class="plbl">口算正确率</span>
          </div>
          <div class="pair">
            <span class="pnum">{{ report.calc.questions }}</span>
            <span class="plbl">口算题数</span>
          </div>
        </div>
      </section>
    </div>

    <p class="legend">
      「这周布置的」按布置日算，「这周完成的」按完成日算。周日补做上周的题会算进完成数，
      但不会拉高完成率——所以百分比不会超过 100%。
    </p>

    <RouterLink class="link" to="/parent/rewards">去管理奖励与星星 →</RouterLink>
  </template>
</template>

<style scoped>
.head { display: flex; align-items: flex-start; gap: 16px; margin-bottom: 20px; }
.head h1 { font-size: 20px; font-weight: 500; margin-bottom: 4px; }
.sub { font-size: 12.5px; color: var(--muted); font-variant-numeric: tabular-nums; }
.nav { margin-left: auto; display: flex; gap: 6px; }

.cards { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 20px; }
.card {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 14px 16px;
  display: flex; flex-direction: column; gap: 2px;
}
.num { font-size: 24px; font-weight: 500; line-height: 1.25; font-variant-numeric: tabular-nums; }
.num.star { color: var(--star); }
.num.dim { color: var(--hint); }
.lbl { font-size: 12px; color: var(--ink-2); }
.foot { font-size: 11px; color: var(--hint); margin-top: 2px; }

.panel {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 18px; margin-bottom: 18px;
}
.panel-head { margin-bottom: 14px; }
.panel-head h2 { font-size: 13.5px; font-weight: 500; }

.bars { display: flex; align-items: flex-end; gap: 8px; height: 130px; }
.bar-col { flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; }
.bar-num { font-size: 11px; color: var(--muted); height: 16px; font-variant-numeric: tabular-nums; }
.bar-track { flex: 1; width: 100%; display: flex; align-items: flex-end; }
.bar-fill {
  width: 100%; min-height: 2px; background: var(--kid);
  border-radius: 3px 3px 0 0; transition: height 0.25s;
}
.bar-fill.zero { background: var(--line); }
.bar-lbl { font-size: 11px; color: var(--hint); margin-top: 6px; }

.two { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.two .panel { margin-bottom: 0; }

.subjects { display: flex; flex-direction: column; gap: 9px; }
.subj { display: flex; align-items: center; gap: 10px; }
.sname { font-size: 12.5px; color: var(--ink-2); width: 40px; flex: 0 0 auto; }
.strack { flex: 1; height: 6px; background: var(--page); border-radius: 3px; overflow: hidden; }
.sfill { height: 100%; background: var(--kid); border-radius: 3px; }
.snum { font-size: 11.5px; color: var(--hint); width: 22px; text-align: right; font-variant-numeric: tabular-nums; }

.pairs { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px 8px; }
.pair { display: flex; flex-direction: column; }
.pnum { font-size: 18px; font-weight: 500; font-variant-numeric: tabular-nums; }
.pnum.ok { color: var(--ok); }
.pnum.warn { color: var(--warn); }
.plbl { font-size: 11.5px; color: var(--hint); }

.legend { font-size: 11.5px; color: var(--hint); line-height: 1.7; margin: 16px 0 8px; }
.link { font-size: 12.5px; display: inline-block; }

.mini {
  background: var(--card); color: var(--muted); border: 1px solid var(--line);
  border-radius: 6px; padding: 4px 10px; font-size: 11.5px;
  font-family: inherit; cursor: pointer;
}
.mini:disabled { color: var(--hint); cursor: default; }

.bad { font-size: 12.5px; color: var(--bad); margin-bottom: 12px; }
.hint { font-size: 13px; color: var(--hint); padding: 20px 0; }
.quiet {
  font-size: 12.5px; color: var(--hint); background: var(--page);
  border: 1px dashed var(--line); border-radius: var(--r-md); padding: 16px;
}

@media (max-width: 860px) {
  .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .two { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 560px) {
  .head { flex-wrap: wrap; }
  .nav { margin-left: 0; }
}
</style>
