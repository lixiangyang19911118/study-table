<script setup lang="ts">
/**
 * 家长端 · 奖励与兑换。
 *
 * 三块放在一页，因为它们互相牵制：
 * 待确认列表决定「现在要不要点头」，奖励清单决定「孩子能换什么」，
 * 补发星星决定「余额够不够」。分三页反而要来回跳。
 */
import { computed, onMounted, ref } from 'vue'

import { adjustStars, getStars, type StarsSnapshot } from '../../api/stars'
import {
  approveRedemption,
  createReward,
  deleteReward,
  listRedemptions,
  listRewards,
  patchReward,
  rejectRedemption,
  REDEMPTION_TEXT,
  type Redemption,
  type Reward,
} from '../../api/rewards'

const stars = ref<StarsSnapshot | null>(null)
const rewards = ref<Reward[]>([])
const all = ref<Redemption[]>([])

const loading = ref(true)
const err = ref('')
const ok = ref('')
const busy = ref(0)

// 新增奖励
const newName = ref('')
const newCost = ref(10)

// 补发
const adjDelta = ref(5)
const adjReason = ref('')

// 拒绝
const rejectingId = ref<number | null>(null)
const rejectNote = ref('')

const pending = computed(() => all.value.filter((r) => r.status === 'pending'))
const history = computed(() => all.value.filter((r) => r.status !== 'pending').slice(0, 8))

async function load() {
  err.value = ''
  try {
    const [s, rw, rd] = await Promise.all([getStars(), listRewards(), listRedemptions()])
    stars.value = s
    rewards.value = rw
    all.value = rd
  } catch (e) {
    err.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function run(fn: () => Promise<unknown>, tip: string, id = 0) {
  busy.value = id || -1
  err.value = ''
  ok.value = ''
  try {
    await fn()
    ok.value = tip
    await load()
  } catch (e) {
    err.value = e instanceof Error ? e.message : '操作失败'
  } finally {
    busy.value = 0
  }
}

const add = () =>
  run(async () => {
    await createReward(newName.value, newCost.value)
    newName.value = ''
    newCost.value = 10
  }, '奖励已加上，孩子那边马上能看到')

const toggle = (r: Reward) =>
  run(
    () => patchReward(r.id, { status: r.status === 'on' ? 'off' : 'on' }),
    r.status === 'on' ? `「${r.name}」已下架` : `「${r.name}」已重新上架`,
  )

const remove = (r: Reward) => {
  if (!window.confirm(`删除「${r.name}」？已发生的兑换记录会保留，但孩子以后换不到了。`)) return
  return run(() => deleteReward(r.id), `已删除「${r.name}」`)
}

const approve = (r: Redemption) =>
  run(
    () => approveRedemption(r.id, undefined),
    `已同意「${r.reward_name}」，扣掉 ${r.cost} 颗星`,
    r.id,
  )

function openReject(r: Redemption) {
  rejectingId.value = r.id
  rejectNote.value = ''
  err.value = ''
}

async function reject(r: Redemption) {
  if (!rejectNote.value.trim()) {
    err.value = '写一句原因，孩子才知道为什么不行'
    return
  }
  await run(
    () => rejectRedemption(r.id, rejectNote.value),
    `已拒绝「${r.reward_name}」`,
    r.id,
  )
  rejectingId.value = null
  rejectNote.value = ''
}

const adjust = () =>
  run(async () => {
    await adjustStars(adjDelta.value, adjReason.value)
    adjReason.value = ''
  }, `已${adjDelta.value > 0 ? '补发' : '扣除'} ${Math.abs(adjDelta.value)} 颗星`)
</script>

<template>
  <div v-if="loading" class="hint">加载中…</div>

  <template v-else>
    <section class="head">
      <div>
        <h1>奖励与星星</h1>
        <p class="sub">孩子提兑换，你点头才扣星</p>
      </div>
      <div v-if="stars" class="balance">
        <strong>{{ stars.balance }}</strong>
        <span>颗 · 可用 {{ stars.available }}</span>
      </div>
    </section>

    <p v-if="ok" class="ok">{{ ok }}</p>
    <p v-if="err" class="bad">{{ err }}</p>

    <!-- 待确认 -->
    <section class="group">
      <h2>
        等确认
        <span v-if="pending.length" class="count">{{ pending.length }}</span>
      </h2>
      <p v-if="!pending.length" class="quiet">没有待确认的兑换。</p>
      <div v-else class="rows">
        <article v-for="r in pending" :key="r.id" class="row">
          <div class="line">
            <span class="name">{{ r.reward_name }}</span>
            <span class="cost">{{ r.cost }} 颗</span>
            <span class="when">{{ new Date(r.created_at).toLocaleDateString('zh-CN') }}</span>
          </div>
          <p v-if="r.note" class="quote">「{{ r.note }}」</p>

          <div v-if="rejectingId === r.id" class="reject">
            <label>
              <span>为什么不换（会显示给孩子）</span>
              <input
                v-model="rejectNote" maxlength="60"
                placeholder="例如：这周已经看过两次了，下周再说"
                @keyup.enter="reject(r)"
              />
            </label>
            <div class="ops">
              <button class="danger" :disabled="busy === r.id" @click="reject(r)">确认拒绝</button>
              <button class="ghost" @click="rejectingId = null">取消</button>
            </div>
          </div>
          <div v-else class="ops">
            <button class="primary" :disabled="busy === r.id" @click="approve(r)">
              {{ busy === r.id ? '处理中…' : `同意，扣 ${r.cost} 颗` }}
            </button>
            <button class="ghost" @click="openReject(r)">不同意</button>
          </div>
        </article>
      </div>
    </section>

    <!-- 奖励清单 -->
    <section class="panel">
      <div class="panel-head"><h2>奖励清单</h2></div>
      <p class="tip">孩子只能看到「上架中」的奖励。价格改高了不影响已经提交的申请——那批按当时的价结算。</p>

      <div class="new">
        <label class="wide">
          <span>奖励内容</span>
          <input v-model="newName" maxlength="64" placeholder="例如：看动画片 20 分钟" />
        </label>
        <label class="narrow">
          <span>要几颗星</span>
          <input v-model.number="newCost" type="number" min="1" max="999" />
        </label>
        <button class="primary" :disabled="busy === -1 || !newName.trim()" @click="add">
          加上
        </button>
      </div>

      <p v-if="!rewards.length" class="quiet">还没有奖励，先加一个吧。</p>
      <div v-else class="rows">
        <div v-for="r in rewards" :key="r.id" class="row flat" :class="{ off: r.status === 'off' }">
          <span class="name">{{ r.name }}</span>
          <span class="cost">{{ r.cost }} 颗</span>
          <span class="chip" :class="r.status">{{ r.status === 'on' ? '上架中' : '已下架' }}</span>
          <div class="ops right">
            <button class="mini" @click="toggle(r)">{{ r.status === 'on' ? '下架' : '上架' }}</button>
            <button class="mini bad" @click="remove(r)">删除</button>
          </div>
        </div>
      </div>
    </section>

    <!-- 补发 -->
    <section class="panel">
      <div class="panel-head"><h2>手动加减星星</h2></div>
      <p class="tip">不挂在任务上的奖励或扣罚走这里，会留一条流水，孩子的「星星从哪来」里看得到。</p>
      <div class="new">
        <label class="narrow">
          <span>颗数（负数表示扣）</span>
          <input v-model.number="adjDelta" type="number" min="-1000" max="1000" />
        </label>
        <label class="wide">
          <span>事由</span>
          <input v-model="adjReason" maxlength="30" placeholder="例如：主动帮妈妈洗碗" />
        </label>
        <button class="primary" :disabled="busy === -1 || !adjDelta" @click="adjust">
          {{ adjDelta > 0 ? '补发' : '扣除' }}
        </button>
      </div>
    </section>

    <!-- 历史 -->
    <section v-if="history.length" class="group">
      <h2>最近的兑换</h2>
      <div class="rows">
        <div v-for="r in history" :key="r.id" class="row flat">
          <span class="name">{{ r.reward_name }}</span>
          <span class="cost">{{ r.cost }} 颗</span>
          <span class="chip" :class="r.status">{{ REDEMPTION_TEXT[r.status] }}</span>
          <span v-if="r.note" class="note">「{{ r.note }}」</span>
        </div>
      </div>
    </section>
  </template>
</template>

<style scoped>
.head { display: flex; align-items: flex-start; gap: 16px; margin-bottom: 18px; }
.head h1 { font-size: 20px; font-weight: 500; margin-bottom: 4px; }
.sub { font-size: 13px; color: var(--muted); }
.balance { margin-left: auto; display: flex; align-items: baseline; gap: 6px; }
.balance strong { font-size: 26px; font-weight: 500; color: var(--star); line-height: 1; }
.balance span { font-size: 11.5px; color: var(--hint); }

.group { margin-bottom: 26px; }
.group h2 { font-size: 13.5px; font-weight: 500; color: var(--ink-2); margin-bottom: 10px; }
.count {
  display: inline-block; margin-left: 7px; font-size: 11px; color: var(--bad);
  background: #fdf0f0; border-radius: 9px; padding: 0 6px;
}

.panel {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 18px; margin-bottom: 22px;
}
.panel-head { margin-bottom: 6px; }
.panel-head h2 { font-size: 14px; font-weight: 500; }
.tip { font-size: 12px; color: var(--muted); margin-bottom: 14px; }

.rows { display: flex; flex-direction: column; gap: 8px; }
.row {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 12px 16px;
}
.row.flat { background: transparent; border: none; border-bottom: 1px solid #f2f4f6; border-radius: 0; padding: 9px 2px; }
.row.flat:last-child { border-bottom: none; }
.row.flat { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.row.off .name { color: var(--hint); text-decoration: line-through; }

.line { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.name { font-size: 13.5px; flex: 1; min-width: 120px; }
.cost { font-size: 12.5px; color: var(--star); font-variant-numeric: tabular-nums; }
.when { font-size: 11.5px; color: var(--hint); }
.quote {
  font-size: 12.5px; color: var(--ink-2); background: var(--page);
  border-radius: var(--r-sm); padding: 7px 10px; margin: 8px 0;
}
.note { font-size: 11.5px; color: var(--muted); }

.chip { font-size: 11px; color: var(--ok); }
.chip.off, .chip.cancelled { color: var(--hint); }
.chip.rejected { color: var(--bad); }
.chip.approved { color: var(--ok); }

.new {
  display: flex; align-items: flex-end; gap: 10px; flex-wrap: wrap;
  padding-bottom: 14px; margin-bottom: 6px; border-bottom: 1px solid #f2f4f6;
}
.new label { display: flex; flex-direction: column; gap: 5px; }
.new label span { font-size: 11.5px; color: var(--hint); }
.new .wide { flex: 1; min-width: 180px; }
.new .narrow { width: 120px; }
.new input {
  border: 1px solid var(--line); border-radius: var(--r-sm);
  padding: 7px 10px; font-size: 13px; font-family: inherit;
  background: var(--page); color: var(--ink); outline: none;
}
.new input:focus { border-color: var(--kid); background: var(--card); }

.reject { margin-top: 10px; }
.reject label { display: flex; flex-direction: column; gap: 5px; }
.reject label span { font-size: 11.5px; color: var(--hint); }
.reject input {
  border: 1px solid var(--line); border-radius: var(--r-sm);
  padding: 7px 10px; font-size: 13px; font-family: inherit;
  background: var(--page); color: var(--ink); outline: none;
}
.reject input:focus { border-color: var(--bad); background: var(--card); }

.ops { display: flex; align-items: center; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
.ops.right { margin-top: 0; margin-left: auto; }
.reject .ops { margin-top: 10px; }

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
.danger {
  background: var(--bad); color: #fff; border: none; border-radius: var(--r-sm);
  padding: 7px 16px; font-size: 13px; font-family: inherit; cursor: pointer;
}
.danger:disabled { background: var(--page); color: var(--hint); cursor: default; }
.mini {
  background: var(--card); color: var(--muted); border: 1px solid var(--line);
  border-radius: 6px; padding: 3px 9px; font-size: 11.5px;
  font-family: inherit; cursor: pointer;
}
.mini.bad { color: var(--bad); border-color: #f0d4d4; }

.ok { font-size: 12.5px; color: var(--ok); margin-bottom: 12px; }
.bad { font-size: 12.5px; color: var(--bad); margin-bottom: 12px; }
.hint { font-size: 13px; color: var(--hint); padding: 20px 0; }
.quiet {
  font-size: 12.5px; color: var(--hint); background: var(--card);
  border: 1px dashed var(--line); border-radius: var(--r-md); padding: 16px;
}

@media (max-width: 640px) {
  .head { flex-wrap: wrap; }
  .balance { margin-left: 0; }
}
</style>
