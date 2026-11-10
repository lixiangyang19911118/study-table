import http from './http'
import type { TaskBrief } from './tasks'

/**
 * 口算接口。
 *
 * 注意 `Question` 里**没有 answer 字段**——不是漏了，后端故意不给。
 * 答案只留在服务端，判分也在服务端。前端唯一能做的是把题目显示出来、
 * 把孩子的作答原样提交。
 */
export type CalcType =
  | 'add' | 'sub'
  | 'fill_addend' | 'fill_minuend'
  | 'fill_sum' | 'fill_diff'
  | 'chain_add' | 'chain_sub'

export const TYPE_LABEL: Record<string, string> = {
  add: '加法',
  sub: '减法',
  fill_addend: '填加数',
  fill_minuend: '填被减数',
  fill_sum: '填和',
  fill_diff: '填差',
  chain_add: '连加',
  chain_sub: '连减',
}

export interface Question {
  index: number
  type: CalcType
  stem: string
}

export interface Round {
  id: number
  child_id: number
  task_id: number | null
  status: 'doing' | 'done'
  total: number
  range_max: number
  types: string[]
  questions: Question[]
}

export interface WrongItem {
  index: number
  type: string
  stem: string
  your_answer: string | null
  right_answer: string
}

export interface CalcResult {
  id: number
  total: number
  right_count: number
  seconds: number
  accuracy: number
  stars_earned: number
  task: TaskBrief | null
  wrong: WrongItem[]
}

export interface RoundBrief {
  id: number
  created_at: string
  total: number
  right_count: number
  seconds: number
  range_max: number
  accuracy: number
}

export interface GenerateInput {
  count?: number
  range_max?: 10 | 20 | 100
  types?: CalcType[]
  task_id?: number | null
}

/** 出一套题。返回里没有答案。 */
export function createRound(body: GenerateInput = {}) {
  return http.post<unknown, Round>('/calc/rounds', body)
}

export function submitRound(roundId: number, answers: (string | null)[]) {
  return http.post<unknown, CalcResult>(`/calc/rounds/${roundId}/submit`, { answers })
}

/** 把本轮错题加进错题本。不传 indexes 表示全部错题。 */
export function roundToMistakes(roundId: number, indexes?: number[]) {
  return http.post<unknown, { created: number; ids: number[] }>(
    `/calc/rounds/${roundId}/to-mistakes`,
    indexes ? { indexes } : {},
  )
}

export function listRounds(limit = 20) {
  return http.get<unknown, RoundBrief[]>('/calc/rounds', { params: { limit } })
}
