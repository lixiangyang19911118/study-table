<script setup lang="ts">
/**
 * 孩子端 · 听写。
 *
 * 这个页面的全部价值是「家长不用坐在旁边念」。所以它只做一件事：
 * 把词表里的词按节奏念出来，让孩子在本子上写。
 *
 * 三条刻意的设计：
 *
 * 1. **屏幕上不显示词。** 显示了就是抄，不是听写。所以中间只有一个大大的序号，
 *    词要等全部念完、孩子自查时才展开。
 * 2. **用 runId 打断，不用暂停标志位。** TTS 的 speak 是原子的，循环里插一个
 *    `if (paused) return` 拦不住已经排队的朗读。所以每次「暂停 / 再念一遍 / 下一个」
 *    都把 runId 加一，旧循环发现自己的号过期会立刻退出，不会和新的朗读叠在一起。
 * 3. **不负责提交。** 听完还是要回任务页拍照或写说明交给家长审核，
 *    状态机仍然只有那一套，这里只是个朗读工具。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { getTask, startTask, type TaskDetail } from '../../api/tasks'

const route = useRoute()
const id = Number(route.params.id)

const task = ref<TaskDetail | null>(null)
const loading = ref(true)
const loadErr = ref('')

const words = computed(() => task.value?.words ?? [])
const total = computed(() => words.value.length)

/** 当前要念第几个（0 起） */
const idx = ref(0)
const playing = ref(false)
/** 全部念完了 */
const finished = ref(false)
/** 展开词表让孩子自查 */
const reveal = ref(false)

/** 怎么念：默认正常语速、每个词两遍、每遍之间停 5 秒 */
const rate = ref(0.85)
const repeat = ref(2)
const gapSec = ref(5)

const supported = typeof window !== 'undefined' && 'speechSynthesis' in window
const synth = supported ? window.speechSynthesis : null
const voice = ref<SpeechSynthesisVoice | null>(null)

/** 念到某个词时给界面用的文案 */
const hintText = computed(() => {
  if (!total.value) return ''
  if (playing.value) return '正在念…在本子上写下来'
  if (finished.value) return '全部念完了，对照一下有没有写错'
  if (idx.value === 0) return '准备好了就点开始，第一个词马上来'
  return '停在这里了，点「继续」接着念'
})

const progress = computed(() =>
  total.value ? Math.round(((idx.value + (finished.value ? 1 : 0)) / total.value) * 100) : 0,
)

// ---------------------------------------------------------------- TTS

function loadVoices() {
  if (!synth) return
  const all = synth.getVoices()
  if (!all.length) return
  // 优先中文。getVoices 在部分浏览器是异步填充的，所以要监听 voiceschanged
  voice.value =
    all.find((v) => /^zh[-_]CN$/i.test(v.lang)) ??
    all.find((v) => /^zh/i.test(v.lang)) ??
    null
}

function speak(text: string): Promise<void> {
  return new Promise((resolve) => {
    if (!synth) return resolve()
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'zh-CN'
    u.rate = rate.value
    if (voice.value) u.voice = voice.value
    // onend 和 onerror 都要 resolve：某个词念失败不能把整轮卡死
    u.onend = () => resolve()
    u.onerror = () => resolve()
    synth.speak(u)
  })
}

function wait(ms: number): Promise<void> {
  return new Promise((r) => window.setTimeout(r, ms))
}

/** 每加一次，正在跑的循环就会在下一次检查时退出 */
let runId = 0

function stop() {
  runId += 1
  playing.value = false
  synth?.cancel()
}

async function run() {
  if (!total.value) return
  if (finished.value) {
    // 重头再来
    idx.value = 0
    finished.value = false
    reveal.value = false
  }
  const my = ++runId
  playing.value = true
  finished.value = false

  for (let i = idx.value; i < total.value; i++) {
    if (my !== runId) return
    idx.value = i
    const word = words.value[i]

    for (let r = 0; r < repeat.value; r++) {
      if (my !== runId) return
      await speak(word)
      if (my !== runId) return
      if (r < repeat.value - 1) await wait(gapSec.value * 1000)
    }
    if (i < total.value - 1) await wait(gapSec.value * 1000)
  }

  if (my !== runId) return
  playing.value = false
  finished.value = true
  reveal.value = true
}

/** 再念一遍：停掉主循环，单独把当前词念一次，停在原地 */
async function again() {
  stop()
  await speak(words.value[idx.value] ?? '')
}

/** 下一个：切换并念一次。不做成纯切换，否则孩子点完还得再点播放 */
async function next() {
  stop()
  if (idx.value >= total.value - 1) {
    finished.value = true
    reveal.value = true
    return
  }
  idx.value += 1
  await speak(words.value[idx.value])
}

// ---------------------------------------------------------------- 加载

async function load() {
  loading.value = true
  loadErr.value = ''
  try {
    task.value = await getTask(id)
    // 第一次进来等于「开始做」，顺手把计时起点记上
    if (task.value.status === 'todo') {
      task.value = await startTask(id)
    }
  } catch (e) {
    loadErr.value = e instanceof Error ? e.message : '打不开这个任务'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
  if (synth) {
    loadVoices()
    synth.addEventListener('voiceschanged', loadVoices)
  }
})

onUnmounted(() => {
  // 不清理的话，切走页面朗读还会继续，家长会以为是幽灵
  stop()
  synth?.removeEventListener('voiceschanged', loadVoices)
})
</script>

<template>
  <div class="back">
    <RouterLink :to="`/kid/task/${id}`">← 回到任务</RouterLink>
  </div>

  <div v-if="loading" class="hint">正在准备…</div>
  <p v-else-if="loadErr && !task" class="bad">{{ loadErr }}</p>

  <template v-else-if="task">
    <section class="head">
      <h1>{{ task.title }}</h1>
      <p class="sub">
        {{ task.subject }} · 点开始后电脑会一个一个念，你在本子上写
      </p>
    </section>

    <div v-if="!supported" class="empty">
      <strong>这个浏览器不会朗读</strong>
      <p>换 Chrome 或 Edge 打开，就能听到词语了。</p>
    </div>

    <div v-else-if="!total" class="empty">
      <strong>这个任务没有词表</strong>
      <p>让爸爸妈妈在布置的时候把要听写的词填进去。</p>
    </div>

    <template v-else>
      <section class="stage">
        <div class="counter" :class="{ pulsing: playing }">
          <strong>{{ idx + 1 }}</strong>
          <span>/ {{ total }}</span>
        </div>

        <div class="bar">
          <i :style="{ width: `${progress}%` }"></i>
        </div>

        <p class="tip">{{ hintText }}</p>
      </section>

      <section class="controls">
        <button class="primary big" @click="playing ? stop() : run()">
          {{ playing ? '暂停' : finished ? '从头再听' : '开始' }}
        </button>
        <button class="ghost" @click="again">再念一遍</button>
        <button class="ghost" @click="next" :disabled="idx >= total - 1">下一个 →</button>
      </section>

      <section class="knobs">
        <label>
          <span>语速</span>
          <select v-model.number="rate">
            <option :value="0.7">慢</option>
            <option :value="0.85">正常</option>
            <option :value="1">快</option>
          </select>
        </label>
        <label>
          <span>每个词念</span>
          <select v-model.number="repeat">
            <option :value="1">1 遍</option>
            <option :value="2">2 遍</option>
            <option :value="3">3 遍</option>
          </select>
        </label>
        <label>
          <span>每个词后等</span>
          <select v-model.number="gapSec">
            <option :value="3">3 秒</option>
            <option :value="5">5 秒</option>
            <option :value="8">8 秒</option>
          </select>
        </label>
      </section>

      <section v-if="reveal" class="checklist">
        <h2>对照一下，看看写错没有</h2>
        <ol>
          <li v-for="(w, i) in words" :key="i">{{ w }}</li>
        </ol>
      </section>

      <section class="footer">
        <RouterLink class="primary" :to="`/kid/task/${id}`">
          写完了，去交作业 →
        </RouterLink>
      </section>
    </template>
  </template>
</template>

<style scoped>
.bad { font-size: 12.5px; color: var(--bad); margin-bottom: 12px; }
.hint { font-size: 13px; color: var(--hint); padding: 20px 0; }

button { font: inherit; cursor: pointer; }
.primary {
  font-size: 13px; padding: 8px 22px;
  background: var(--kid); color: #fff;
  border: none; border-radius: var(--r-sm);
  text-align: center;
}
.primary:disabled { background: var(--page); color: var(--hint); cursor: default; }
.ghost {
  font-size: 12.5px; padding: 6px 14px;
  background: transparent; color: var(--muted);
  border: 1px solid var(--line); border-radius: var(--r-sm);
  transition: color 0.15s ease, border-color 0.15s ease;
}
.ghost:hover:not(:disabled) { color: var(--ink); }
.ghost:disabled { opacity: 0.45; cursor: default; }

.empty {
  background: var(--card); border: 1px dashed var(--line);
  border-radius: var(--r-md); padding: 18px;
}
.empty strong { font-size: 13.5px; font-weight: 500; }
.empty p { font-size: 12.5px; color: var(--muted); margin-top: 6px; }

.back { margin-bottom: 14px; }
.back a { font-size: 12.5px; color: var(--muted); }

.head { margin-bottom: 22px; }
.head h1 { font-size: 21px; font-weight: 500; margin-bottom: 4px; }
.sub { font-size: 12.5px; color: var(--muted); }

.stage {
  display: flex; flex-direction: column; align-items: center;
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-lg); padding: 34px 24px 22px;
  margin-bottom: 16px;
}

.counter {
  display: flex; align-items: baseline; gap: 6px;
  transition: transform 0.25s ease;
}
.counter strong {
  font-size: 64px; font-weight: 500; line-height: 1;
  color: var(--kid); font-variant-numeric: tabular-nums;
}
.counter span { font-size: 15px; color: var(--hint); }
/* 播放时轻微呼吸，让孩子知道电脑还在念 */
.counter.pulsing strong { animation: breathe 2s ease-in-out infinite; }
@keyframes breathe {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.62; transform: scale(0.97); }
}

.bar {
  width: 100%; max-width: 320px; height: 3px;
  background: var(--page); border-radius: 2px;
  margin: 26px 0 14px; overflow: hidden;
}
.bar i {
  display: block; height: 100%; background: var(--kid);
  border-radius: 2px; transition: width 0.3s ease;
}

.tip { font-size: 12.5px; color: var(--muted); text-align: center; }

.controls {
  display: flex; gap: 10px; align-items: center;
  margin-bottom: 20px; flex-wrap: wrap;
}
.big { padding: 10px 26px; font-size: 14px; }

.knobs {
  display: flex; gap: 18px; flex-wrap: wrap;
  padding: 12px 16px; margin-bottom: 20px;
  background: var(--page); border: 1px solid var(--line);
  border-radius: var(--r-sm);
}
.knobs label { display: flex; align-items: center; gap: 7px; }
.knobs span { font-size: 11.5px; color: var(--hint); }
.knobs select {
  font: inherit; font-size: 12px; padding: 3px 6px;
  border: 1px solid var(--line); border-radius: 6px;
  background: var(--card); color: var(--ink-2); outline: none;
}

.checklist {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r-md); padding: 16px 18px; margin-bottom: 20px;
}
.checklist h2 { font-size: 13px; font-weight: 500; color: var(--ink-2); margin-bottom: 12px; }
.checklist ol {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
  gap: 7px 14px; padding-left: 18px;
}
.checklist li { font-size: 13.5px; color: var(--ink); }
.checklist li::marker { color: var(--hint); font-size: 11px; }

.footer { padding-bottom: 20px; }
.footer a { display: inline-block; }

@media (max-width: 640px) {
  .counter strong { font-size: 52px; }
  .controls { gap: 8px; }
  .knobs { gap: 12px; }
}
</style>
