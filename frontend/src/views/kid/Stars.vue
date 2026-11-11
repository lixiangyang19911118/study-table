<script setup lang="ts">
/**
 * 孩子端 · 我的星星。
 *
 * 兑换是「申请」而不是「直接扣」：点完只是提交给爸爸妈妈，
 * 星星要等他们同意才真的减少。所以这里从不显示「余额变少了」，
 * 只显示「已提交，等确认」。
 */
import { computed, onMounted, ref } from 'vue'

import { getStars, type LedgerEntry, type StarsSnapshot } from '../../api/stars'
import {
  cancelRedemption,
  listRedemptions,
  listRewards,
  redeem,
  REDEMPTION_TEXT,
  type Redemption,
  type Reward,
} from '../../api/rewards'

const stars = ref<StarsSnapshot | null>(null)
const rewards = ref<Reward[]>([])
const mine = ref<Redemption[]>([])

const loading = ref(true)
const err = ref('')
const ok = ref('')

const expandedId = ref<number | null>(null)
const note = ref('')
const busy = ref(false)

const pending = computed(() => mine.value.filter((r) => r.status === 'pending'))
const history = computed(() => mine.value.filter((r) => r.status !== 'pending'))

/** 流水只显示前 12 条，够看出「星星怎么来的」，不必一次铺满整屏 */
const recent = computed<LedgerEntry[]>(() => stars.value?.ledger.slice(0, 12) ?? [])

async function load() {
  err.value = ''
  try {
    const [s, rw, rd] = await Promise.all([getStars(), listRewards('on'), listRedemptions()])
    stars.value = s
    rewards.value = rw
    mine.value = rd
  } catch (e) {
    err.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function ask(r: Reward) {
  expandedId.value = expandedId.value === r.id ? null : r.id
  note.value = ''
  ok.value = ''
  err.value = ''
}

async function submit(r: Reward) {
  busy.value = true
  err.value = ''
  ok.value = ''
  try {
    await redeem(r.id, note.value)
    expandedId.value = null
    note.value = ''
    ok.value = `「${r.name}」已经告诉爸爸妈妈了，等他们点头就行`
    await load()
  } catch (e) {
    err.value = e instanceof Error ? e.message : '提交失败'
  } finally {
    busy.value = false
  }
}

async function withdraw(r: Redemption) {
  busy.value = true
  err.value = ''
  ok.value = ''
  try {
    await cancelRedemption(r.id)
    ok.value = `已经不想换「${r.reward_name}」了`
    await load()
  } catch (e) {
    err.value = e instanceof Error ? e.message : '撤回失败'
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-if="loading" class="hint">正在数星星…</div>
  <p v-else-if="err && !stars" class="bad">{{ err }}</p>

  <template v-else-if="stars">
    <section class="head">
      <div>
        <h1>我的星星</h1>
        <p class="sub">攒够了就能换想要的东西</p>
      </div>
      <div class="balance">
        <strong>{{ stars.balance }}</strong>
        <span>颗</span>
      </div>
    </section>

    <p v-if="stars.pending" class="reserved">
      还有 {{ stars.pending }} 颗在等着确认，所以现在能换的是
      <b>{{ stars.available }}</b> 颗
    </p>

    <p v-if="ok" class="ok">{{ ok }}</p>
    <p v-if="err" class="bad">{{ err }}</p>

    <section v-if="pending.length" class="group">
      <h2>等爸爸妈妈确认<span class="count">{{ pending.length }}</span></h2>
      <div class="rows">
        <div v-for="r in pending" :key="r.id" class="row">
          <span class="name">{{ r.reward_name }}</span>
          <span class="cost">{{ r.cost }} 颗</span>
          <span class="wait">{{ REDEMPTION_TEXT[r.status] }}</span>
          <button class="mini" :disabled="busy" @click="withdraw(r)">算了</button>
        </div>
      </div>
    </section>

    <section class="group">
      <h2>能换什么</h2>
      <p v-if="!rewards.length" class="quiet">爸爸妈妈还没放奖励上来，去跟他们说说想要什么吧。</p>
      <div v-else class="rewards">
        <article
          v-for="r in rewards" :key="r.id" class="reward"
          :class="{ short: !r.affordable, opened: expandedId === r.id }"
        >
          <div class="main">
            <span class="rname">{{ r.name }}</span>
            <span class="rcost">{{ r.cost }} 颗</span>
          </div>

          <template v-if="expandedId === r.id">
            <label class="why">
              <span>想跟爸爸妈妈说一句（可以不写）</span>
              <input v-model="note" maxlength="60" placeholder="例如：这周作业都是自己检查的" />
            </label>
            <div class="ops">
              <button class="primary" :disabled="busy" @click="submit(r)">
                {{ busy ? '提交中…' : '就换这个' }}
              </button>
              <button class="ghost" @click="expandedId = null">再想想</button>
            </div>
          </template>

          <template v-else>
            <button v-if="r.affordable" class="primary" @click="ask(r)">兑换</button>
            <span v-else class="lack">还差 {{ r.cost - stars.available }} 颗</span>
          </template>
        </article>
      </div>
    </section>

    <section v-if="history.length" class="group">
      <h2>换过的</h2>
      <div class="rows">
        <div v-for="r in history" :key="r.id" class="row done">
          <span class="name">{{ r.reward_name }}</span>
          <span class="cost">{{ r.cost }} 颗</span>
          <span class="wait" :class="r.status">{{ REDEMPTION_TEXT[r.status] }}</span>
          <span v-if="r.note" class="parent-note">「{{ r.note }}」</span>
        </div>
      </div>
    </section>

    <section class="group">
      <h2>星星是这么来的</h2>
      <p v-if="!recent.length" class="quiet">还没有星星，先去完成今天的任务吧。</p>
      <ul v-else class="ledger">
        <li v-for="e in recent" :key="e.id">
          <span class="delta" :class="{ minus: e.delta < 0 }">
            {{ e.delta > 0 ? '+' + e.delta : e.delta }}
          </span>
          <span class="reason">{{ e.reason }}</span>
        </li>
      </ul>
    </section>

    <RouterLink class="link" to="/kid/today">← 回到今天的任务</RouterLink>
  </template>
</template>

<style scoped>
.head { display: flex; align-items: flex-start; gap: 16px; margin-bottom: 18px; }
.head h1 { font-size: 21px; font-weight: 500; margin-bottom: 4px; }
.sub { font-size: 13px; color: var(--muted); }
.balance { margin-left: auto; display: flex; align-items: baseline; gap: 4px; }
.balance strong { font-size: 34px; font-weight: 500; color: var(--star); line-height: 1; }
.balance span { font-size: 13px; color: var(--hint); }

.reserved {
  font-size: 12.5px; color: var(--warn); background: #fdf6e7;
  border: 1px solid #f0e0bb; border-radius: var(--r-sm);
  padding: 8px 12px; margin-bottom: 16px;
}
.reserved b { color: #8a6206; font-weight: 500; }

.group { margin-bottom: 26px; }
.group h2 { font-size: 13.5px; font-weight: 500; color: var(--ink-2); margin-bottom: 10px; }
.count {
  display: inline-block; margin-left: 7px; font-size: 11px; color: var(--bad);
  background: #fdf0f0; border-radius: 9px; padding: 0 6px;
}

.rewards { display: flex; flex-direction: column; gap: 8px; }
.reward {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 12px 16px;
}
.reward.short { background: #fbfbfc; }
.reward.opened { border-color: var(--kid); background: var(--kid-soft); }
.main { display: flex; align-items: baseline; gap: 10px; flex: 1; min-width: 160px; }
.rname { font-size: 14px; color: var(--ink); }
.rcost { font-size: 12.5px; color: var(--star); font-variant-numeric: tabular-nums; }
.reward.short .rname { color: var(--muted); }
.reward.short .rcost { color: var(--hint); }
.lack { font-size: 11.5px; color: var(--hint); }

.why { display: flex; flex-direction: column; gap: 5px; width: 100%; }
.why span { font-size: 11.5px; color: var(--hint); }
.why input {
  border: 1px solid var(--line); border-radius: var(--r-sm);
  padding: 7px 10px; font-size: 13px; font-family: inherit;
  background: var(--page); color: var(--ink); outline: none;
}
.why input:focus { border-color: var(--kid); background: var(--card); }

.rows { display: flex; flex-direction: column; gap: 6px; }
.row {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-sm); padding: 9px 14px;
}
.row.done { background: #fbfbfc; }
.name { font-size: 13.5px; flex: 1; min-width: 120px; }
.row.done .name { color: var(--ink-2); }
.cost { font-size: 12px; color: var(--hint); font-variant-numeric: tabular-nums; }
.wait { font-size: 11.5px; color: var(--warn); }
.wait.approved { color: var(--ok); }
.wait.rejected { color: var(--bad); }
.wait.cancelled { color: var(--hint); }
.parent-note { font-size: 11.5px; color: var(--muted); width: 100%; }

.ledger { list-style: none; margin: 0; padding: 0; }
.ledger li {
  display: flex; align-items: center; gap: 10px;
  padding: 7px 2px; border-bottom: 1px solid #f2f4f6;
}
.ledger li:last-child { border-bottom: none; }
.delta {
  font-size: 13px; color: var(--star); font-variant-numeric: tabular-nums;
  min-width: 34px; font-weight: 500;
}
.delta.minus { color: var(--bad); }
.reason { font-size: 12.5px; color: var(--muted); }

.primary {
  background: var(--kid); color: #fff; border: none; border-radius: var(--r-sm);
  padding: 7px 16px; font-size: 13px; font-family: inherit; cursor: pointer;
}
.primary:disabled { background: var(--page); color: var(--hint); cursor: default; }
.ghost {
  background: var(--card); color: var(--muted); border: 1px solid var(--line);
  border-radius: var(--r-sm); padding: 7px 14px; font-size: 13px;
  font-family: inherit; cursor: pointer;
}
.mini {
  background: var(--card); color: var(--hint); border: 1px solid var(--line);
  border-radius: 6px; padding: 2px 8px; font-size: 11.5px;
  font-family: inherit; cursor: pointer;
}
.ops { display: flex; align-items: center; gap: 8px; width: 100%; }

.ok { font-size: 12.5px; color: var(--ok); margin-bottom: 12px; }
.bad { font-size: 12.5px; color: var(--bad); margin-bottom: 12px; }
.hint { font-size: 13px; color: var(--hint); padding: 20px 0; }
.quiet {
  font-size: 12.5px; color: var(--hint); background: var(--card);
  border: 1px dashed var(--line); border-radius: var(--r-md); padding: 18px;
}
.link { font-size: 12.5px; display: inline-block; margin-top: 4px; }

@media (max-width: 640px) {
  .balance strong { font-size: 28px; }
  .main { min-width: 100%; }
}
</style>
