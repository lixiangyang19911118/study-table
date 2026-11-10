import http from './http'

/**
 * 错题本接口。
 *
 * 一条规矩：这里**没有「复习一次」的方法**，因为后端也没有这个接口。
 * 错题的复习节奏只能由「家长审核错题重做任务」推进（见 api/tasks.ts 的 approveTask），
 * 否则孩子在错题本里连点几次「我会了」就能把复习计划刷穿。
 */
export type MistakeCategory = 'learning' | 'due' | 'mastered'
export type MistakeCause = '计算错' | '看错题' | '概念不清' | '不会做'

export const CAUSES: MistakeCause[] = ['计算错', '看错题', '概念不清', '不会做']

export interface MistakeLog {
  id: number
  action: 'add' | 'redo' | 'master' | 'reopen'
  is_correct: boolean | null
  answer: string | null
  created_at: string
}

export interface Mistake {
  id: number
  subject: string
  point: string
  stem: string
  answer_own: string | null
  answer_right: string | null
  cause: string | null
  source: 'manual' | 'calc'
  stage: number
  due_date: string | null
  mastered: boolean
  file_url: string | null
  review_count: number
  created_at: string
}

export interface MistakeDetail extends Mistake {
  logs: MistakeLog[]
}

export interface MistakeCounts {
  learning: number
  due: number
  mastered: number
}

export interface MistakeInput {
  subject?: string
  point?: string
  stem?: string
  answer_own?: string | null
  answer_right?: string | null
  cause?: MistakeCause | null
  file_id?: number | null
}

export function listMistakes(category: MistakeCategory, subject?: string) {
  return http.get<unknown, Mistake[]>('/mistakes', { params: { category, subject } })
}

export function getMistake(id: number) {
  return http.get<unknown, MistakeDetail>(`/mistakes/${id}`)
}

export function mistakeCounts() {
  return http.get<unknown, MistakeCounts>('/mistakes/counts')
}

export function createMistake(body: MistakeInput) {
  return http.post<unknown, MistakeDetail>('/mistakes', body)
}

export function patchMistake(id: number, body: MistakeInput) {
  return http.patch<unknown, MistakeDetail>(`/mistakes/${id}`, body)
}

export function deleteMistake(id: number) {
  return http.delete<unknown, void>(`/mistakes/${id}`)
}

/** 手动标记掌握：孩子当场讲明白了，或这题本身出错了，不必走完 4 轮。 */
export function masterMistake(id: number) {
  return http.post<unknown, MistakeDetail>(`/mistakes/${id}/master`)
}

export function reopenMistake(id: number) {
  return http.post<unknown, MistakeDetail>(`/mistakes/${id}/reopen`)
}

/** 错题照片。biz_type 用 mistake，与作业照片区分开。 */
export async function uploadMistakePhoto(file: File): Promise<{ file_id: number; url: string }> {
  const fd = new FormData()
  fd.append('biz_type', 'mistake')
  fd.append('file', file)
  const res = await http.post<unknown, { id: number; url: string }>('/files', fd)
  return { file_id: res.id, url: res.url }
}
