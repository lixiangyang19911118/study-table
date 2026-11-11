import http from './http'

/**
 * 星星余额与流水。
 *
 * 余额不是字段，是后端 SUM(star_ledger.delta) 算出来的，
 * 所以前端永远不要自己累加流水列表——列表是分页的，加出来会错。
 */
export interface LedgerEntry {
  id: number
  delta: number
  reason: string
  ref_type: string | null
  created_at: string
}

export interface StarsSnapshot {
  balance: number
  /** 余额 - 待确认兑换占用的星星。能拿去兑换的只有这个数。 */
  available: number
  /** 待家长确认的兑换一共占了多少颗 */
  pending: number
  ledger: LedgerEntry[]
}

export function getStars(limit = 30): Promise<StarsSnapshot> {
  return http.get<unknown, StarsSnapshot>('/stars', { params: { limit } })
}

export function adjustStars(delta: number, reason?: string): Promise<StarsSnapshot> {
  return http.post<unknown, StarsSnapshot>('/stars/adjust', {
    delta,
    reason: reason?.trim() || null,
  })
}
