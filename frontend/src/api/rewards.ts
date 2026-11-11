import http from './http'

/** 奖励清单与兑换。字段与后端 schemas/reward.py 对应。 */

export type RedemptionStatus = 'pending' | 'approved' | 'rejected' | 'cancelled'

export interface Reward {
  id: number
  name: string
  cost: number
  status: 'on' | 'off'
  /** 按当前可用余额够不够换。后端算好，前端别自己减。 */
  affordable: boolean
}

export interface Redemption {
  id: number
  reward_id: number | null
  /** 申请时的名称快照。奖励改名后这里仍是当时的名字。 */
  reward_name: string
  /** 申请时的价格快照。家长改价不影响已提交的申请。 */
  cost: number
  status: RedemptionStatus
  note: string | null
  decided_at: string | null
  created_at: string
}

export const REDEMPTION_TEXT: Record<RedemptionStatus, string> = {
  pending: '等爸爸妈妈确认',
  approved: '已兑换',
  rejected: '没有同意',
  cancelled: '已撤回',
}

export function listRewards(status?: 'on' | 'off'): Promise<Reward[]> {
  return http.get<unknown, Reward[]>('/rewards', { params: status ? { status } : {} })
}

export function createReward(name: string, cost: number): Promise<Reward> {
  return http.post<unknown, Reward>('/rewards', { name: name.trim(), cost })
}

export function patchReward(
  id: number,
  body: { name?: string; cost?: number; status?: 'on' | 'off' },
): Promise<Reward> {
  return http.patch<unknown, Reward>(`/rewards/${id}`, body)
}

export function deleteReward(id: number): Promise<void> {
  return http.delete<unknown, void>(`/rewards/${id}`)
}

export function listRedemptions(status?: RedemptionStatus): Promise<Redemption[]> {
  return http.get<unknown, Redemption[]>('/redemptions', {
    params: status ? { status } : {},
  })
}

/** 申请兑换。只落一条待确认记录，不动星星。 */
export function redeem(rewardId: number, note?: string): Promise<Redemption> {
  return http.post<unknown, Redemption>(`/rewards/${rewardId}/redeem`, {
    note: note?.trim() || null,
  })
}

export function approveRedemption(id: number, note?: string): Promise<Redemption> {
  return http.post<unknown, Redemption>(`/redemptions/${id}/approve`, {
    note: note?.trim() || null,
  })
}

/** 拒绝必须带原因，后端会校验；这里也拦一道，免得白跑一次请求。 */
export function rejectRedemption(id: number, note: string): Promise<Redemption> {
  return http.post<unknown, Redemption>(`/redemptions/${id}/reject`, { note: note.trim() })
}

export function cancelRedemption(id: number): Promise<Redemption> {
  return http.post<unknown, Redemption>(`/redemptions/${id}/cancel`)
}
