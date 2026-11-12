<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import {
  attachShot, detachShot, getTask, restartTask, startTask,
  submitTask, uploadPhoto, withdrawTask, type TaskDetail,
} from '../../api/tasks'
import { dayLabel, elapsedSec, fmtClock, fmtMinutes, timeOf, useNow } from '../../lib/time'

const route = useRoute()
const id = Number(route.params.id)

const task = ref<TaskDetail | null>(null)
const loading = ref(true)
const loadErr = ref('')
const busy = ref(false)
const uploading = ref(false)
const actionErr = ref('')
const note = ref('')

const now = useNow()

const editable = computed(() => task.value?.status === 'doing')
const locked = computed(
  () => task.value?.status === 'submitted' || task.value?.status === 'done',
)

const dayText = computed(() => (task.value ? dayLabel(task.value.task_date) : ''))
const elapsedText = computed(() =>
  task.value ? fmtClock(elapsedSec(task.value, now.value)) : '0:00',
)

const rejectReason = computed(() => {
  const reviews = task.value?.reviews ?? []
  const last = [...reviews].reverse().find((r) => r.action === 'reject')
  return last?.comment ?? ''
})

const canSubmit = computed(
  () => (task.value?.shots.length ?? 0) > 0 || note.value.trim().length > 0,
)

async function load() {
  loading.value = true
  loadErr.value = ''
  try {
    task.value = await getTask(id)
    note.value = task.value.submit_note ?? ''
  } catch (e) {
    loadErr.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

/** 所有动作都返回最新详情，直接替换，省一次 GET。 */
async function run(fn: () => Promise<TaskDetail>) {
  busy.value = true
  actionErr.value = ''
  try {
    task.value = await fn()
  } catch (e) {
    actionErr.value = e instanceof Error ? e.message : '操作失败'
  } finally {
    busy.value = false
  }
}

const onStart = () => run(() => startTask(id))
const onRestart = () => run(() => restartTask(id))
const onWithdraw = () => run(() => withdrawTask(id))
const onSubmit = () => run(() => submitTask(id, note.value.trim() || undefined))

async function onPick(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  if (!files.length) return

  uploading.value = true
  actionErr.value = ''
  try {
    // 一张一张传：并发上传在同一条连接上并不更快，失败时还分不清是哪张
    for (const file of files) {
      const { file_id } = await uploadPhoto(file)
      task.value = await attachShot(id, file_id)
    }
  } catch (err) {
    actionErr.value = err instanceof Error ? err.message : '照片上传失败'
  } finally {
    uploading.value = false
    input.value = ''      // 不清空的话，选同一张图不会触发 change
  }
}

async function removeShot(shotId: number) {
  actionErr.value = ''
  try {
    task.value = await detachShot(id, shotId)
  } catch (e) {
    actionErr.value = e instanceof Error ? e.message : '删除失败'
  }
}

onMounted(load)
</script>

<template>
  <div class="back">
    <RouterLink to="/kid/today">← 回到今天</RouterLink>
  </div>

  <div v-if="loading" class="hint">正在加载…</div>

  <div v-else-if="!task" class="empty">
    <strong>打不开这个任务</strong>
    <p>{{ loadErr || '它可能已经被删掉了' }}</p>
    <RouterLink class="link" to="/kid/today">回到今天</RouterLink>
  </div>

  <template v-else>
    <header class="head">
      <div class="tags">
        <span class="subject">{{ task.subject }}</span>
        <span v-if="dayText !== '今天'" class="day">{{ dayText }}</span>
        <span class="state" :class="task.status">{{ task.status === 'doing' ? '进行中' : '' }}</span>
      </div>
      <h1>{{ task.title }}</h1>
      <p class="meta">
        预计 {{ task.minutes_est }} 分钟 · 完成得 {{ task.stars }} 颗星
      </p>
      <p v-if="task.note" class="from-parent">爸爸妈妈说：{{ task.note }}</p>
    </header>

    <div v-if="rejectReason" class="banner">
      <strong>被退回了</strong>
      <p>{{ rejectReason }}</p>
    </div>

    <!-- 待做 -->
    <div v-if="task.status === 'todo'" class="panel">
      <template v-if="task.kind === 'calc'">
        <p class="tip">口算题由电脑出，做完当场判分，不用拍照也不用等批。</p>
        <RouterLink class="primary link-btn" :to="`/kid/calc/${task.id}`">开始口算</RouterLink>
      </template>
      <template v-else-if="task.kind === 'dictation'">
        <p class="tip">
          点下面进听写页，电脑会一个一个念出来，你在本子上写。写完回来拍照交给爸爸妈妈。
        </p>
        <RouterLink class="primary link-btn" :to="`/kid/dictation/${task.id}`">
          开始听写（{{ task.words?.length ?? 0 }} 个词）
        </RouterLink>
      </template>
      <template v-else>
        <p class="tip">准备好了就开始。计时会记下你用了多久，中途随时可以交。</p>
        <button class="primary" :disabled="busy" @click="onStart">
          {{ busy ? '开始中…' : '开始做' }}
        </button>
      </template>
    </div>

    <!-- 已退回 -->
    <div v-if="task.status === 'rejected'" class="panel">
      <p class="tip">改好之后点下面重新开始，记得把刚才说的地方补上。</p>
      <button class="primary" :disabled="busy" @click="onRestart">
        {{ busy ? '…' : '重新做' }}
      </button>
    </div>

    <!-- 进行中 -->
    <div v-if="editable" class="panel">
      <!-- 口算不进拍照流程：题目在屏幕上，答案由后端判 -->
      <template v-if="task.kind === 'calc'">
        <p class="tip">这一条是口算，点下面进做题页。做完自动判分，不用提交照片。</p>
        <RouterLink class="primary link-btn" :to="`/kid/calc/${task.id}`">继续做口算</RouterLink>
      </template>

      <template v-else>
        <div v-if="task.kind === 'dictation'" class="dict-bar">
          <span>共 {{ task.words?.length ?? 0 }} 个词，没听清随时回去再听</span>
          <RouterLink class="ghost link-btn" :to="`/kid/dictation/${task.id}`">
            继续听写
          </RouterLink>
        </div>

        <div class="timer">
          <span class="label">已经用了</span>
          <strong>{{ elapsedText }}</strong>
        </div>

        <div class="shots">
          <figure v-for="s in task.shots" :key="s.id">
            <img :src="s.url" alt="作业照片" />
            <button class="del" @click="removeShot(s.id)">删掉</button>
          </figure>
          <label class="add" :class="{ uploading }">
            <input
              type="file" accept="image/*" capture="environment" multiple hidden
              @change="onPick"
            />
            <span>{{ uploading ? '上传中…' : '＋ 拍照' }}</span>
          </label>
        </div>

        <label class="field">
          <span>说一句（没拍照的话，这里写清楚也算交了）</span>
          <textarea
            v-model="note" rows="3" maxlength="500"
            placeholder="例如：第三题我重算了一遍，答案是 47"
          ></textarea>
        </label>

        <div class="actions">
          <button class="primary" :disabled="busy || uploading || !canSubmit" @click="onSubmit">
            {{ busy ? '提交中…' : '交给爸爸妈妈' }}
          </button>
          <span class="hint">照片和说明，有一样就行</span>
        </div>
      </template>
    </div>

    <!-- 已提交 / 已完成 -->
    <div v-if="locked" class="panel" :class="{ passed: task.status === 'done' }">
      <div class="result">
        <template v-if="task.status === 'done'">
          通过啦，拿到 <strong>{{ task.stars }}</strong> 颗星
        </template>
        <template v-else>已经交了，等爸爸妈妈看看</template>
      </div>
      <p class="meta">
        <template v-if="task.status === 'done'">用时 {{ fmtMinutes(task.spent_sec) }}</template>
        <template v-else>提交于 {{ timeOf(task.submitted_at) }}</template>
      </p>

      <div v-if="task.shots.length" class="shots">
        <figure v-for="s in task.shots" :key="s.id">
          <img :src="s.url" alt="作业照片" />
        </figure>
      </div>

      <p v-if="task.submit_note" class="quote">{{ task.submit_note }}</p>

      <div v-if="task.status === 'submitted'" class="actions">
        <button class="ghost" :disabled="busy" @click="onWithdraw">
          {{ busy ? '…' : '撤回提交' }}
        </button>
        <span class="hint">少拍了照片才需要撤回，重交要重新等审核</span>
      </div>
    </div>

    <p v-if="actionErr" class="bad">{{ actionErr }}</p>
  </template>
</template>

<style scoped>
.back { margin-bottom: 14px; }
.back a { font-size: 12.5px; color: var(--muted); }

.head { margin-bottom: 20px; }
.tags { display: flex; align-items: center; gap: 8px; margin-bottom: 7px; }
.subject {
  font-size: 11px; color: var(--muted);
  background: var(--card); border: 1px solid var(--line);
  border-radius: 4px; padding: 1px 7px;
}
.day { font-size: 11px; color: var(--warn); }
.state { font-size: 11px; color: var(--star); }
h1 { font-size: 20px; font-weight: 500; margin-bottom: 5px; }
.meta { font-size: 12.5px; color: var(--hint); }
.from-parent {
  font-size: 12.5px; color: var(--ink-2); margin-top: 9px;
  background: var(--card); border-left: 2px solid var(--line);
  padding: 7px 11px; border-radius: 0 var(--r-sm) var(--r-sm) 0;
}

.banner {
  background: #fdf0f0; border: 1px solid #f0d4d4;
  border-radius: var(--r-md); padding: 12px 15px; margin-bottom: 16px;
}
.banner strong { font-size: 12.5px; color: var(--bad); font-weight: 500; }
.banner p { font-size: 13px; color: var(--ink-2); margin-top: 4px; }

.panel {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 18px;
  margin-bottom: 16px;
}
.panel.passed { border-color: #d5e8dc; background: #fbfefc; }
.tip { font-size: 12.5px; color: var(--muted); margin-bottom: 14px; }

/* 听写任务的回头路：孩子写到一半想重听可以直接跳回去，不用退到列表 */
.dict-bar {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
  padding: 9px 13px; margin-bottom: 14px;
  background: var(--kid-soft); border-radius: var(--r-sm);
}
.dict-bar span { font-size: 12px; color: #3a5f96; flex: 1; min-width: 140px; }
.dict-bar .ghost { background: var(--card); }

.timer {
  display: flex; align-items: baseline; gap: 9px;
  padding-bottom: 14px; margin-bottom: 14px;
  border-bottom: 1px solid #f0f2f4;
}
.timer .label { font-size: 11.5px; color: var(--hint); }
.timer strong {
  font-size: 22px; font-weight: 500; color: var(--star);
  font-variant-numeric: tabular-nums;
}

.shots {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(104px, 1fr));
  gap: 10px; margin-bottom: 16px;
}
.shots figure {
  position: relative; margin: 0; aspect-ratio: 3 / 4;
  background: var(--page); border: 1px solid var(--line);
  border-radius: var(--r-sm); overflow: hidden;
}
.shots img { width: 100%; height: 100%; object-fit: cover; display: block; }
.del {
  position: absolute; right: 5px; bottom: 5px;
  font: inherit; font-size: 10.5px; cursor: pointer;
  color: #fff; background: rgba(28, 32, 38, 0.62);
  border: none; border-radius: 5px; padding: 2px 7px;
}
.add {
  aspect-ratio: 3 / 4; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  font-size: 12.5px; color: var(--kid);
  background: var(--kid-soft); border: 1px dashed #c7d8ef;
  border-radius: var(--r-sm);
}
.add.uploading { color: var(--hint); background: var(--page); border-color: var(--line); }

.field { display: flex; flex-direction: column; gap: 6px; }
.field span { font-size: 11.5px; color: var(--hint); }
.field textarea {
  font: inherit; font-size: 13px; line-height: 1.6;
  padding: 9px 11px; resize: vertical;
  background: var(--page); color: var(--ink);
  border: 1px solid var(--line); border-radius: var(--r-sm);
  outline: none;
}
.field textarea:focus { border-color: var(--kid); background: var(--card); }

.actions { display: flex; align-items: center; gap: 12px; margin-top: 16px; flex-wrap: wrap; }
button { font: inherit; cursor: pointer; }
.primary {
  font-size: 13px; padding: 8px 22px;
  background: var(--kid); color: #fff;
  border: none; border-radius: var(--r-sm);
}
.primary:disabled { background: var(--page); color: var(--hint); cursor: default; }
.link-btn { display: inline-block; text-decoration: none; }
.ghost {
  font-size: 12.5px; padding: 6px 14px;
  background: transparent; color: var(--muted);
  border: 1px solid var(--line); border-radius: var(--r-sm);
}
.ghost:hover { color: var(--ink); }
.hint { font-size: 11.5px; color: var(--hint); }

.result { font-size: 14px; margin-bottom: 5px; }
.result strong { color: var(--star); font-weight: 500; }
.quote {
  font-size: 13px; color: var(--ink-2);
  background: var(--page); border-radius: var(--r-sm);
  padding: 10px 13px; margin-top: 4px;
}
.bad { font-size: 12.5px; color: var(--bad); margin-top: 10px; }

.empty {
  background: var(--card); border: 1px dashed var(--line);
  border-radius: var(--r-md); padding: 18px;
}
.empty strong { font-size: 13.5px; font-weight: 500; }
.empty p { font-size: 12.5px; color: var(--muted); margin-top: 6px; }
.link { font-size: 12.5px; display: inline-block; margin-top: 10px; }
.hint:first-child { padding: 20px 0; }
</style>
