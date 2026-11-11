import http from './http'

/**
 * 打卡日历。
 *
 * 打卡不是「点一下就记」，而是「当天任务全部完成」才成立，所以这里没有新建接口，
 * 只有「查日历」和「试着补记今天」两个动作。补记是幂等的，多点几次也只会记一天。
 */
export interface CalendarDay {
  date: string
  /** 已打卡 */
  checked: boolean
  /** 当天有任务；false 表示这天本来就不用打卡，断了不算孩子的错 */
  has_task: boolean
}

export interface CalendarSnapshot {
  month: string
  /** 1=周一 … 7=周日，排格子用 */
  first_weekday: number
  days: CalendarDay[]
  streak: number
  longest: number
  total: number
  checked_today: boolean
  today_all_done: boolean
}

export interface SettleResult {
  /** 本次是否新记了一条 */
  created: boolean
  checked_today: boolean
  streak: number
}

export function getCalendar(month?: string): Promise<CalendarSnapshot> {
  return http.get<unknown, CalendarSnapshot>('/checkins', {
    params: month ? { month } : {},
  })
}

/** 任务全部完成时调一次，不必等 23:55 的定时结算。重复调用安全。 */
export function settleCheckin(): Promise<SettleResult> {
  return http.post<unknown, SettleResult>('/checkins/settle')
}
