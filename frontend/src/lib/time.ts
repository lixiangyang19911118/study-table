import { onMounted, onUnmounted, ref } from 'vue'

/**
 * 时间显示的几个小工具。
 *
 * 为什么单独放一个文件：孩子端和家长端都要显示「用了多久」「几点交的」
 * 「这是哪天的任务」，三处各写一遍迟早不一致（特别是「昨天」的判定）。
 */

/** 秒 → 03:21 / 1:03:21。计时器用，不进位到「分钟」。 */
export function fmtClock(sec: number): string {
  const s = Math.max(0, Math.floor(sec))
  const pad = (n: number) => String(n).padStart(2, '0')
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h}:${pad(m)}:${pad(s % 60)}` : `${m}:${pad(s % 60)}`
}

/** 秒 → 「18 分钟」。审核页看用时用这个，比 00:18 直观。 */
export function fmtMinutes(sec: number): string {
  const m = Math.round(sec / 60)
  return m < 1 ? '不到 1 分钟' : `${m} 分钟`
}

/** '2026-11-06' → 今天 / 昨天 / 11 月 4 日。补做区靠它说明「这是哪天的」。 */
export function dayLabel(iso: string): string {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const d = new Date(`${iso}T00:00:00`)
  const diff = Math.round((today.getTime() - d.getTime()) / 86400000)
  if (diff === 0) return '今天'
  if (diff === 1) return '昨天'
  if (diff === 2) return '前天'
  return `${d.getMonth() + 1} 月 ${d.getDate()} 日`
}

/** ISO 时间串 → 09:30。 */
export function timeOf(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

/** 每秒跳一次的「现在」。组件卸载时自动清掉，否则切页面后定时器还在跑。 */
export function useNow(interval = 1000) {
  const now = ref(Date.now())
  let timer = 0
  onMounted(() => {
    timer = window.setInterval(() => {
      now.value = Date.now()
    }, interval)
  })
  onUnmounted(() => {
    if (timer) window.clearInterval(timer)
  })
  return now
}

/**
 * 任务已用时长。只有 doing 才需要把「开始到现在」加上去——
 * submitted 及以上状态的 spent_sec 已经在提交时结算过了，
 * 再加一遍会把时间越滚越大。
 */
export function elapsedSec(
  task: { status: string; spent_sec: number; started_at: string | null },
  nowMs: number,
): number {
  if (task.status !== 'doing' || !task.started_at) return task.spent_sec
  const started = Date.parse(task.started_at)
  if (Number.isNaN(started)) return task.spent_sec
  return task.spent_sec + Math.max(0, Math.floor((nowMs - started) / 1000))
}
