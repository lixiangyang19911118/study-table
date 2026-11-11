<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { createChild, patchChild, type Child } from '../../api/auth'
import { mistakeCounts } from '../../api/mistakes'
import { listRedemptions } from '../../api/rewards'
import { listTasks } from '../../api/tasks'
import { useSession } from '../../stores/session'

const session = useSession()

// 几个数只是给家长一个「今天要不要管」的判断，取不到不影响下面的档案编辑
const reviewCount = ref(0)
const openCount = ref(0)
const doneCount = ref(0)
const dueMistakes = ref(0)
const pendingRedeem = ref(0)

async function loadOverview() {
  if (!session.child) return
  try {
    const [review, open, done, counts, redeem] = await Promise.all([
      listTasks('review'),
      listTasks('today'),
      listTasks('done'),
      mistakeCounts(),
      listRedemptions('pending'),
    ])
    reviewCount.value = review.length
    openCount.value = open.length
    doneCount.value = done.length
    dueMistakes.value = counts.due
    pendingRedeem.value = redeem.length
  } catch {
    // 总览是锦上添花，出错就不显示数字，别把整页搞崩
  }
}

const EDITIONS = ['人教版', '苏教版', '北师大版', '外研版']
const GRADES = [1, 2, 3, 4, 5, 6]

const form = ref({ name: '', grade: 3, edition: '人教版' })
const newName = ref('')
const saving = ref(false)
const msg = ref('')
const err = ref('')

// 加载完成或切换孩子时把表单对齐到服务端数据
watch(
  () => session.child,
  (c) => {
    if (c) form.value = { name: c.name, grade: c.grade, edition: c.edition }
    void loadOverview()
  },
  { immediate: true },
)

const dirty = computed(() => {
  const c = session.child
  if (!c) return false
  return (
    form.value.name !== c.name ||
    form.value.grade !== c.grade ||
    form.value.edition !== c.edition
  )
})

async function save() {
  const c = session.child
  if (!c) return
  saving.value = true
  msg.value = ''
  err.value = ''
  try {
    const next = await patchChild(c.id, {
      name: form.value.name.trim(),
      grade: form.value.grade,
      edition: form.value.edition,
    })
    session.replaceChild(next)
    msg.value = '已保存'
  } catch (e) {
    err.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    saving.value = false
  }
}

async function addChild() {
  if (!newName.value.trim()) return
  saving.value = true
  err.value = ''
  try {
    const created: Child = await createChild({
      name: newName.value.trim(),
      grade: 3,
      edition: '人教版',
    })
    session.children.push(created)
    newName.value = ''
    msg.value = '已新建，可在上方编辑'
  } catch (e) {
    err.value = e instanceof Error ? e.message : '新建失败'
  } finally {
    saving.value = false
  }
}

const planned = [
  { name: '粘贴导入老师作业', note: '识别段落头与科目，生成待确认清单', m: 'M2 后续' },
  { name: '任务拖拽调序', note: '按预估时长控制每天总量', m: 'M2 后续' },
  { name: '教材资源管理', note: 'PDF 存磁盘，按年级科目分类', m: 'M4' },
  { name: '周报与星星余额', note: '实时聚合，不读快照', m: 'M4' },
  { name: '拍照识别录入错题', note: 'OCR 结果要能人工核对', m: 'M5' },
]
</script>

<template>
  <section class="head">
    <h1>家长端 · 总览</h1>
    <p>今天要管的就这几件事。点进去能直接处理。</p>
  </section>

  <div v-if="session.child" class="overview">
    <RouterLink v-if="pendingRedeem > 0" class="ov" to="/parent/rewards">
      <span class="num hot">{{ pendingRedeem }}</span>
      <span class="lbl">兑换等你点头</span>
    </RouterLink>
    <RouterLink class="ov" to="/parent/review">
      <span class="num" :class="{ hot: reviewCount > 0 }">{{ reviewCount }}</span>
      <span class="lbl">待你审核</span>
    </RouterLink>
    <RouterLink class="ov" to="/parent/tasks">
      <span class="num">{{ openCount }}</span>
      <span class="lbl">今天还没交</span>
    </RouterLink>
    <RouterLink class="ov" to="/parent/tasks">
      <span class="num">{{ doneCount }}</span>
      <span class="lbl">今天已完成</span>
    </RouterLink>
    <RouterLink class="ov" to="/parent/mistakes">
      <span class="num" :class="{ hot: dueMistakes > 0 }">{{ dueMistakes }}</span>
      <span class="lbl">错题待复习</span>
    </RouterLink>
    <RouterLink class="ov new" to="/parent/tasks">
      <span class="plus">＋</span>
      <span class="lbl">布置任务</span>
    </RouterLink>
  </div>

  <!-- 有档案：可编辑 -->
  <div v-if="session.child" class="panel">
    <div class="panel-head">
      <h2>孩子档案</h2>
      <span class="badge">child #{{ session.child.id }}</span>
    </div>

    <div class="form">
      <label>
        <span>昵称</span>
        <input v-model="form.name" type="text" maxlength="32" />
      </label>
      <label>
        <span>年级</span>
        <select v-model.number="form.grade">
          <option v-for="g in GRADES" :key="g" :value="g">{{ g }} 年级</option>
        </select>
      </label>
      <label>
        <span>教材版本</span>
        <select v-model="form.edition">
          <option v-for="e in EDITIONS" :key="e" :value="e">{{ e }}</option>
        </select>
      </label>
    </div>

    <div class="actions">
      <button :disabled="saving || !dirty" @click="save">
        {{ saving ? '保存中…' : dirty ? '保存修改' : '没有改动' }}
      </button>
      <span v-if="msg" class="ok">{{ msg }}</span>
      <span v-if="err" class="bad">{{ err }}</span>
    </div>
  </div>

  <!-- 没档案：引导新建 -->
  <div v-else class="panel">
    <div class="panel-head"><h2>还没有孩子档案</h2></div>
    <p class="tip">
      所有任务、错题、教材都挂在 <code>child_id</code> 上，先建一个才能写入数据。
    </p>
    <div class="form">
      <label class="wide">
        <span>昵称</span>
        <input v-model="newName" type="text" maxlength="32" placeholder="例如：小明" />
      </label>
    </div>
    <div class="actions">
      <button :disabled="saving || !newName.trim()" @click="addChild">新建档案</button>
      <span v-if="err" class="bad">{{ err }}</span>
    </div>
  </div>

  <div class="card">
    <div v-for="item in planned" :key="item.name" class="item">
      <div class="left">
        <span class="name">{{ item.name }}</span>
        <span class="note">{{ item.note }}</span>
      </div>
      <span class="tag">{{ item.m }}</span>
    </div>
  </div>
</template>

<style scoped>
.head { margin-bottom: 22px; }
h1 { font-size: 21px; font-weight: 500; margin-bottom: 6px; }
.head p { font-size: 13px; color: var(--muted); }

.overview {
  display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px; margin-bottom: 22px;
}
.ov {
  display: flex; flex-direction: column; gap: 1px;
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 12px 16px;
  color: var(--ink); transition: border-color 0.15s;
}
.ov:hover { border-color: #c9d6ea; }
.num { font-size: 20px; font-weight: 500; line-height: 1.35; }
.num.hot { color: var(--star); }
.lbl { font-size: 11.5px; color: var(--hint); }
.ov.new {
  justify-content: center; align-items: flex-start;
  background: var(--kid-soft); border-color: #d8e2f3;
}
.plus { font-size: 14px; color: var(--kid); line-height: 1.5; }
.ov.new .lbl { color: var(--kid); }

.panel {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 16px 18px 14px;
  margin-bottom: 22px;
}
.panel-head { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.panel-head h2 { font-size: 14px; font-weight: 500; }
.badge {
  font-size: 11px; color: var(--hint);
  border: 1px solid var(--line); border-radius: 5px;
  padding: 1px 7px; font-family: "SF Mono", Menlo, monospace;
}
.tip { font-size: 12.5px; color: var(--muted); margin-bottom: 14px; }

.form {
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px 16px;
}
.form .wide { grid-column: 1 / -1; max-width: 320px; }
.form label { display: flex; flex-direction: column; gap: 5px; }
.form span { font-size: 11.5px; color: var(--hint); }
.form input, .form select {
  font: inherit; font-size: 13px;
  padding: 7px 10px;
  background: var(--page); color: var(--ink);
  border: 1px solid var(--line); border-radius: var(--r-sm);
  outline: none;
}
.form input:focus, .form select:focus { border-color: var(--kid); background: var(--card); }

.actions { display: flex; align-items: center; gap: 12px; margin-top: 14px; }
.actions button {
  font: inherit; font-size: 12.5px; cursor: pointer;
  padding: 6px 16px;
  background: var(--kid); color: #fff;
  border: none; border-radius: var(--r-sm);
}
.actions button:disabled {
  background: var(--page); color: var(--hint);
  border: 1px solid var(--line); cursor: default;
}
.ok { font-size: 12px; color: var(--ok); }
.bad { font-size: 12px; color: var(--bad); }

.card {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); overflow: hidden;
}
.item {
  display: flex; align-items: center; gap: 12px;
  padding: 13px 18px; border-bottom: 1px solid #f0f2f4;
}
.item:last-child { border-bottom: none; }
.left { display: flex; flex-direction: column; }
.name { font-size: 13.5px; }
.note { font-size: 11.5px; color: var(--hint); margin-top: 1px; }
.tag {
  margin-left: auto; flex: 0 0 auto;
  font-size: 11px; color: var(--muted);
  background: var(--page); border: 1px solid var(--line);
  border-radius: 5px; padding: 2px 7px;
}

@media (max-width: 720px) {
  .form { grid-template-columns: minmax(0, 1fr); }
  .overview { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
