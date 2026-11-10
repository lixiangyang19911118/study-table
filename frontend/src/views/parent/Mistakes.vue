<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import {
  CAUSES, createMistake, deleteMistake, getMistake, listMistakes,
  masterMistake, mistakeCounts, reopenMistake, uploadMistakePhoto,
  type Mistake, type MistakeCategory, type MistakeCause, type MistakeCounts, type MistakeDetail,
} from '../../api/mistakes'
import { SUBJECTS, type Subject } from '../../api/tasks'
import { dueLabel, timeOf } from '../../lib/time'
import { useSession } from '../../stores/session'

const session = useSession()

const tab = ref<MistakeCategory>('learning')
const items = ref<Mistake[]>([])
const counts = ref<MistakeCounts>({ learning: 0, due: 0, mastered: 0 })
const loading = ref(true)
const err = ref('')
const msg = ref('')

const showForm = ref(false)
const saving = ref(false)
const photoUrl = ref('')
const photoId = ref<number | null>(null)
const uploading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const blank = () => ({
  subject: '数学' as Subject,
  point: '',
  stem: '',
  answer_own: '',
  answer_right: '',
  cause: '' as MistakeCause | '',
})
const form = ref(blank())

const detailId = ref<number | null>(null)
const detail = ref<MistakeDetail | null>(null)
const busyId = ref<number | null>(null)

const TABS: { key: MistakeCategory; label: string; hint: string }[] = [
  { key: 'learning', label: '学习中', hint: '还没掌握的' },
  { key: 'due', label: '今天该复习', hint: '到期或逾期的' },
  { key: 'mastered', label: '已掌握', hint: '连对 4 次或手动标记' },
]

const emptyText = computed(() => {
  if (tab.value === 'due') return '今天没有到期要复习的错题。'
  if (tab.value === 'mastered') return '还没有掌握的错题。连对 4 次会自动进来。'
  return '错题本还是空的。孩子做错的题记一条进来，之后按 1 / 2 / 4 / 7 天自动提醒复习。'
})

async function load() {
  loading.value = true
  err.value = ''
  try {
    const [list, c] = await Promise.all([listMistakes(tab.value), mistakeCounts()])
    items.value = list
    counts.value = c
    if (detailId.value !== null && !list.some((m) => m.id === detailId.value)) {
      detailId.value = null
      detail.value = null
    }
  } catch (e) {
    err.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function switchTab(next: MistakeCategory) {
  tab.value = next
  detailId.value = null
  detail.value = null
  void load()
}

async function onPickPhoto(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploading.value = true
  err.value = ''
  try {
    const res = await uploadMistakePhoto(file)
    photoId.value = res.file_id
    photoUrl.value = res.url
  } catch (e2) {
    err.value = e2 instanceof Error ? e2.message : '照片上传失败'
  } finally {
    uploading.value = false
    input.value = ''
  }
}

function clearPhoto() {
  photoId.value = null
  photoUrl.value = ''
}

async function submit() {
  if (!form.value.stem.trim() && photoId.value === null) {
    err.value = '题干和照片至少要有一个，不然这道题以后没法复习'
    return
  }
  saving.value = true
  err.value = ''
  msg.value = ''
  try {
    await createMistake({
      subject: form.value.subject,
      point: form.value.point.trim(),
      stem: form.value.stem.trim(),
      answer_own: form.value.answer_own.trim() || null,
      answer_right: form.value.answer_right.trim() || null,
      cause: form.value.cause || null,
      file_id: photoId.value,
    })
    msg.value = '记下了，明天开始复习'
    form.value = blank()
    clearPhoto()
    showForm.value = false
    await load()
  } catch (e) {
    err.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    saving.value = false
  }
}

async function toggleDetail(m: Mistake) {
  if (detailId.value === m.id) {
    detailId.value = null
    detail.value = null
    return
  }
  err.value = ''
  try {
    detail.value = await getMistake(m.id)
    detailId.value = m.id
  } catch (e) {
    err.value = e instanceof Error ? e.message : '加载失败'
  }
}

async function toggleMaster(m: Mistake) {
  busyId.value = m.id
  err.value = ''
  msg.value = ''
  try {
    if (m.mastered) {
      await reopenMistake(m.id)
      msg.value = '已重新放进复习队列，明天第一次复习'
    } else {
      await masterMistake(m.id)
      msg.value = '已标记掌握，不再自动生成复习任务'
    }
    await load()
  } catch (e) {
    err.value = e instanceof Error ? e.message : '操作失败'
  } finally {
    busyId.value = null
  }
}

async function remove(m: Mistake) {
  if (!window.confirm(`删掉「${m.point || m.stem.slice(0, 12)}」这道错题？`)) return
  err.value = ''
  msg.value = ''
  try {
    await deleteMistake(m.id)
    msg.value = '已删除'
    await load()
  } catch (e) {
    err.value = e instanceof Error ? e.message : '删除失败'
  }
}

function stemText(m: Mistake) {
  return m.stem || '（只有照片）'
}

const ACTION_TEXT: Record<string, string> = {
  add: '录入',
  redo: '复习',
  master: '标记掌握',
  reopen: '重新打开',
}

onMounted(load)
</script>

<template>
  <section class="head">
    <h1>错题本</h1>
    <p>
      按 1 / 2 / 4 / 7 天自动安排复习，连对 4 次算掌握。
      <RouterLink to="/parent/review">待审核</RouterLink>
      ·
      <RouterLink to="/parent/tasks">布置作业</RouterLink>
    </p>
  </section>

  <div v-if="!session.child" class="empty">
    <strong>还没有孩子档案</strong>
    <p>先去总览建一个，错题要挂在孩子身上。</p>
    <RouterLink class="link" to="/parent/dashboard">去建档案</RouterLink>
  </div>

  <template v-else>
    <div class="tabs">
      <button
        v-for="t in TABS" :key="t.key"
        class="tab" :class="{ on: tab === t.key }"
        @click="switchTab(t.key)"
      >
        <span class="tab-label">{{ t.label }}</span>
        <span class="tab-num">{{ counts[t.key] }}</span>
      </button>
      <button class="add-btn" @click="showForm = !showForm">
        {{ showForm ? '收起' : '＋ 记一道错题' }}
      </button>
    </div>

    <!-- 录入 -->
    <div v-if="showForm" class="panel">
      <div class="form-grid">
        <label>
          <span>科目</span>
          <select v-model="form.subject">
            <option v-for="s in SUBJECTS" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <label>
          <span>知识点</span>
          <input v-model="form.point" type="text" maxlength="128" placeholder="两位数进位加法" />
        </label>
        <label>
          <span>错因</span>
          <select v-model="form.cause">
            <option value="">先不填</option>
            <option v-for="c in CAUSES" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
      </div>

      <label class="full">
        <span>题干</span>
        <textarea
          v-model="form.stem" rows="2" maxlength="2000"
          placeholder="37 + 25 = ?　　也可以只拍照片，这里留空"
        ></textarea>
      </label>

      <div class="form-grid">
        <label>
          <span>孩子当时的答案</span>
          <input v-model="form.answer_own" type="text" maxlength="500" placeholder="52" />
        </label>
        <label>
          <span>正确答案</span>
          <input v-model="form.answer_right" type="text" maxlength="500" placeholder="62" />
        </label>
      </div>

      <div class="photo-row">
        <label class="photo-add" :class="{ busy: uploading }">
          <input ref="fileInput" type="file" accept="image/*" hidden @change="onPickPhoto" />
          <span>{{ uploading ? '上传中…' : photoUrl ? '换一张' : '＋ 拍错题' }}</span>
        </label>
        <figure v-if="photoUrl" class="thumb">
          <img :src="photoUrl" alt="错题照片" />
          <button class="del" @click="clearPhoto">去掉</button>
        </figure>
      </div>

      <div class="ops">
        <button class="primary" :disabled="saving || uploading" @click="submit">
          {{ saving ? '保存中…' : '记下来' }}
        </button>
        <span class="hint">记下之后，明天开始第一次复习</span>
      </div>
    </div>

    <p v-if="msg" class="ok">{{ msg }}</p>
    <p v-if="err" class="bad">{{ err }}</p>

    <div v-if="loading" class="quiet">正在加载…</div>
    <div v-else-if="!items.length" class="quiet">{{ emptyText }}</div>

    <template v-else>
      <article v-for="m in items" :key="m.id" class="card">
        <div class="line">
          <span class="chip">{{ m.subject }}</span>
          <span v-if="m.point" class="point">{{ m.point }}</span>
          <span v-if="m.source === 'calc'" class="tag">口算</span>
          <span class="spacer"></span>
          <span v-if="m.due_date" class="due" :class="{ overdue: dueLabel(m.due_date).startsWith('逾期') }">
            {{ dueLabel(m.due_date) }}复习
          </span>
          <span v-else class="due done">已掌握</span>
        </div>

        <p class="stem" :class="{ faint: !m.stem }">{{ stemText(m) }}</p>

        <div class="answer-row">
          <span v-if="m.answer_own" class="ans bad-ans">孩子写：{{ m.answer_own }}</span>
          <span v-if="m.answer_right" class="ans ok-ans">正确：{{ m.answer_right }}</span>
          <span v-if="m.cause" class="cause">{{ m.cause }}</span>
        </div>

        <div class="foot">
          <div class="stage" :title="`已复习 ${m.review_count} 次`">
            <span v-for="i in 4" :key="i" class="dot" :class="{ on: m.stage >= i }"></span>
            <span class="stage-text">{{ m.review_count ? `复习 ${m.review_count} 次` : '还没复习' }}</span>
          </div>
          <div class="ops small">
            <button class="ghost" @click="toggleDetail(m)">
              {{ detailId === m.id ? '收起' : '看记录' }}
            </button>
            <button class="ghost" :disabled="busyId === m.id" @click="toggleMaster(m)">
              {{ m.mastered ? '重新打开' : '标记掌握' }}
            </button>
            <button class="ghost danger" @click="remove(m)">删除</button>
          </div>
        </div>

        <div v-if="detailId === m.id && detail" class="logs">
          <a v-if="m.file_url" :href="m.file_url" target="_blank" rel="noopener" class="photo-link">
            <img :src="m.file_url" alt="错题照片" />
          </a>
          <ul>
            <li v-for="log in detail.logs" :key="log.id">
              <span class="when">{{ timeOf(log.created_at) }}</span>
              <span class="what">{{ ACTION_TEXT[log.action] ?? log.action }}</span>
              <span v-if="log.is_correct === true" class="res ok">做对了</span>
              <span v-else-if="log.is_correct === false" class="res bad">还是错</span>
              <span v-if="log.answer" class="wrote">写了 {{ log.answer }}</span>
            </li>
          </ul>
          <p v-if="detail.logs.length <= 1" class="hint">
            明天会生成一条「错题重做」任务，交上来审核时顺手判对错，这里就有记录了。
          </p>
        </div>
      </article>
    </template>
  </template>
</template>

<style scoped>
.head { margin-bottom: 18px; }
h1 { font-size: 21px; font-weight: 500; margin-bottom: 6px; }
.head p { font-size: 13px; color: var(--muted); }
.head a { color: var(--kid); }

.tabs { display: flex; align-items: center; gap: 6px; margin-bottom: 16px; flex-wrap: wrap; }
.tab {
  font: inherit; cursor: pointer;
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 12px;
  background: var(--card); color: var(--muted);
  border: 1px solid var(--line); border-radius: var(--r-sm);
}
.tab.on { background: var(--kid-soft); color: var(--kid); border-color: #c7d8ef; }
.tab-label { font-size: 12.5px; }
.tab-num { font-size: 11.5px; color: var(--hint); font-variant-numeric: tabular-nums; }
.tab.on .tab-num { color: var(--kid); }
.add-btn {
  font: inherit; cursor: pointer; margin-left: auto;
  font-size: 12.5px; padding: 6px 14px;
  background: var(--kid); color: #fff;
  border: none; border-radius: var(--r-sm);
}

.panel {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 16px 18px; margin-bottom: 16px;
}
.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 12px; }
.panel label, .full { display: flex; flex-direction: column; gap: 5px; }
.panel label span { font-size: 11.5px; color: var(--hint); }
.panel input, .panel select, .panel textarea {
  font: inherit; font-size: 13px;
  padding: 7px 10px;
  background: var(--page); color: var(--ink);
  border: 1px solid var(--line); border-radius: var(--r-sm);
  outline: none;
}
.panel input:focus, .panel select:focus, .panel textarea:focus {
  border-color: var(--kid); background: var(--card);
}
.panel textarea { resize: vertical; line-height: 1.6; }
.full { margin-bottom: 12px; }

.photo-row { display: flex; align-items: center; gap: 10px; margin: 4px 0 14px; }
.photo-add {
  width: 84px; height: 84px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; color: var(--kid);
  background: var(--kid-soft); border: 1px dashed #c7d8ef; border-radius: var(--r-sm);
}
.photo-add.busy { color: var(--hint); background: var(--page); border-color: var(--line); }
.thumb { position: relative; margin: 0; width: 84px; height: 84px; }
.thumb img { width: 100%; height: 100%; object-fit: cover; border-radius: var(--r-sm); border: 1px solid var(--line); }
.thumb .del {
  position: absolute; right: 3px; bottom: 3px;
  font: inherit; font-size: 10.5px; cursor: pointer;
  color: #fff; background: rgba(28, 32, 38, 0.62);
  border: none; border-radius: 4px; padding: 1px 5px;
}

.ops { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.ops.small { margin-left: auto; gap: 6px; }
button { font: inherit; cursor: pointer; }
.primary {
  font-size: 13px; padding: 7px 18px;
  background: var(--kid); color: #fff; border: none; border-radius: var(--r-sm);
}
.primary:disabled { background: var(--page); color: var(--hint); cursor: default; }
.ghost {
  font-size: 12px; padding: 5px 11px;
  background: transparent; color: var(--muted);
  border: 1px solid var(--line); border-radius: var(--r-sm);
}
.ghost:hover { color: var(--ink); }
.ghost.danger:hover { color: var(--bad); border-color: #f0d4d4; }
.hint { font-size: 11.5px; color: var(--hint); }

.card {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 14px 16px; margin-bottom: 10px;
}
.line { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.chip {
  font-size: 11px; color: var(--muted);
  background: var(--page); border-radius: 4px; padding: 1px 6px;
}
.point { font-size: 13px; color: var(--ink-2); }
.tag {
  font-size: 10.5px; color: var(--kid);
  background: var(--kid-soft); border-radius: 4px; padding: 1px 5px;
}
.spacer { flex: 1; }
.due { font-size: 11.5px; color: var(--warn); }
.due.overdue { color: var(--bad); }
.due.done { color: var(--ok); }

.stem { font-size: 13.5px; color: var(--ink); margin: 8px 0; line-height: 1.6; }
.stem.faint { color: var(--hint); font-style: italic; }

.answer-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
.ans { font-size: 12px; }
.bad-ans { color: var(--bad); }
.ok-ans { color: var(--ok); }
.cause { font-size: 11.5px; color: var(--muted); background: var(--page); border-radius: 4px; padding: 1px 6px; }

.foot { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.stage { display: flex; align-items: center; gap: 4px; }
.dot { width: 7px; height: 7px; border-radius: 50%; background: var(--line); }
.dot.on { background: var(--kid); }
.stage-text { font-size: 11px; color: var(--hint); margin-left: 5px; }

.logs { border-top: 1px solid #f0f2f4; margin-top: 12px; padding-top: 12px; }
.photo-link { display: block; width: 110px; margin-bottom: 10px; }
.photo-link img { width: 100%; border-radius: var(--r-sm); border: 1px solid var(--line); }
.logs ul { list-style: none; margin: 0; padding: 0; }
.logs li {
  display: flex; align-items: center; gap: 9px;
  font-size: 12px; color: var(--ink-2);
  padding: 4px 0;
}
.when { color: var(--hint); font-variant-numeric: tabular-nums; }
.what { color: var(--muted); }
.res { font-size: 11.5px; }
.res.ok { color: var(--ok); }
.res.bad { color: var(--bad); }
.wrote { color: var(--hint); }

.ok { font-size: 12.5px; color: var(--ok); margin-bottom: 10px; }
.bad { font-size: 12.5px; color: var(--bad); margin-bottom: 10px; }
.quiet {
  font-size: 12.5px; color: var(--hint); line-height: 1.7;
  background: var(--card); border: 1px dashed var(--line);
  border-radius: var(--r-md); padding: 18px;
}
.empty {
  background: var(--card); border: 1px dashed var(--line);
  border-radius: var(--r-md); padding: 18px;
}
.empty strong { font-size: 13.5px; font-weight: 500; }
.empty p { font-size: 12.5px; color: var(--muted); margin-top: 6px; }
.link { font-size: 12.5px; display: inline-block; margin-top: 10px; }
</style>
