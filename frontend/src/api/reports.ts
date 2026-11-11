import http from './http'

/**
 * 周报。后端实时聚合，没有快照表。
 *
 * 两组数字口径不同，展示时别混：
 * - planned / completed / rate 按「布置日」归周 —— 这周布置的做完没有
 * - doneThisWeek / daily / subjects / spentMin 按「完成日」归周 —— 这周实际干了多少
 */
export interface ReportDay {
  date: string
  weekday: string
  done: number
  spent_min: number
}

export interface WeeklyReport {
  week: string
  start: string
  end: string
  tasks: {
    planned: number
    completed: number
    rate: number | null
    done_this_week: number
    spent_min: number
  }
  stars: { earned: number; spent: number; net: number; balance: number }
  daily: ReportDay[]
  subjects: { subject: string; done: number }[]
  mistakes: { added: number; mastered: number; due: number }
  calc: { rounds: number; questions: number; accuracy: number | null; spent_min: number }
}

export function getWeekly(week?: string): Promise<WeeklyReport> {
  return http.get<unknown, WeeklyReport>('/reports/weekly', {
    params: week ? { week } : {},
  })
}

/** 把 ISO 周号前后平移 n 周，用于「上一周 / 下一周」。
 *
 * ISO 8601 的锚点是「1 月 4 日必定落在第 1 周」，且该周包含 1 月 4 日所在的周四。
 * 所以先由年里推出第 1 周的周一，再按周偏移，最后用目标周的周四反推它属于哪一年
 * ——跨年那几周（12 月底可能是下一年的 W01）靠这一步才不会错。
 */
export function shiftWeek(week: string, delta: number): string {
  const [y, w] = week.split('-W').map(Number)
  const mondayOfWeek1 = (year: number) => {
    const jan4 = new Date(Date.UTC(year, 0, 4))
    return new Date(jan4.getTime() - ((jan4.getUTCDay() + 6) % 7) * 86400000)
  }
  const target = new Date(mondayOfWeek1(y).getTime() + (w - 1 + delta) * 7 * 86400000)
  const year = new Date(target.getTime() + 3 * 86400000).getUTCFullYear()
  const no = Math.round((target.getTime() - mondayOfWeek1(year).getTime()) / (7 * 86400000)) + 1
  return `${year}-W${String(no).padStart(2, '0')}`
}
