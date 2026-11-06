<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { createChild, patchChild, type Child } from '../../api/auth'
import { useSession } from '../../stores/session'

const session = useSession()

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
  { name: '布置作业 · 粘贴导入', note: '识别段落头与科目，生成待确认清单', m: 'M2' },
  { name: '任务编辑 / 删除 / 调序', note: 'PRD 列为第一阻塞项', m: 'M2' },
  { name: '审核与退回', note: '通过时写星星流水，不是直接改余额', m: 'M2' },
  { name: '错题录入与重做记录', note: '含 OCR 结果核对页', m: 'M3' },
  { name: '教材资源管理', note: 'PDF 存磁盘，按年级科目分类', m: 'M4' },
  { name: '周报', note: '实时聚合，不读快照', m: 'M4' },
]
</script>

<template>
  <section class="head">
    <h1>家长端 · 总览</h1>
    <p>孩子档案已接通数据库，改动会直接落库；下面的清单是 M2 起的施工顺序。</p>
  </section>

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
}
</style>
