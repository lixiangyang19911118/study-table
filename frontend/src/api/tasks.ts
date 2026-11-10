import http from './http'

/**
 * 任务接口的封装。字段与后端 schemas/task.py 一一对应，改一处要同步改另一处。
 *
 * 注意时间字段：后端输出带 `+00:00` 的 ISO 串（库里是 UTC naive），
 * 直接交给 `new Date()` 能正确换算成本地时间。不要自己拼字符串。
 */
export type TaskStatus = 'todo' | 'doing' | 'submitted' | 'done' | 'rejected'
export type Bucket = 'today' | 'backlog' | 'review' | 'done' | 'all'

export const SUBJECTS = ['语文', '数学', '英语', '体育', '其他'] as const
export type Subject = (typeof SUBJECTS)[number]

export interface Shot {
  id: number
  file_id: number
  url: string
  width: number | null
  height: number | null
}

export interface ReviewLog {
  id: number
  action: 'approve' | 'reject'
  comment: string | null
  created_at: string
}

/** 错题重做任务关联的错题摘要。审核页要靠它显示原题和正确答案。 */
export interface MistakeRef {
  id: number
  subject: string
  point: string
  stem: string
  answer_own: string | null
  answer_right: string | null
  stage: number
  due_date: string | null
}

export interface TaskBrief {
  id: number
  subject: string
  title: string
  kind: string
  minutes_est: number
  stars: number
  status: TaskStatus
  source: string
  task_date: string
  spent_sec: number
  note: string | null
  submit_note: string | null
  started_at: string | null
  submitted_at: string | null
  reviewed_at: string | null
  shot_count: number
}

export interface TaskDetail extends TaskBrief {
  shots: Shot[]
  reviews: ReviewLog[]
  mistake: MistakeRef | null
}

export interface TaskInput {
  subject?: Subject
  title: string
  /** calc 任务会走口算页而不是拍照页 */
  kind?: 'normal' | 'calc'
  minutes_est?: number
  stars?: number
  task_date?: string
  note?: string | null
}

/**
 * bucket 决定取哪一堆，口径在服务端：
 * - today    今天还没交的（todo / doing / rejected）
 * - backlog  更早的日子还没交的，即「补做」
 * - review   待审核，不限日期——球在家长那边
 * - done     今天已完成的
 */
export function listTasks(bucket: Bucket, day?: string) {
  return http.get<unknown, TaskBrief[]>('/tasks', { params: { bucket, date: day } })
}

export function getTask(id: number) {
  return http.get<unknown, TaskDetail>(`/tasks/${id}`)
}

export function createTask(body: TaskInput) {
  return http.post<unknown, TaskDetail>('/tasks', body)
}

export function patchTask(id: number, body: Partial<TaskInput>) {
  return http.patch<unknown, TaskDetail>(`/tasks/${id}`, body)
}

export function deleteTask(id: number) {
  return http.delete<unknown, void>(`/tasks/${id}`)
}

export function startTask(id: number) {
  return http.post<unknown, TaskDetail>(`/tasks/${id}/start`)
}

/** 退回后重做。和 start 的区别是前置状态不同，且会重置计时。 */
export function restartTask(id: number) {
  return http.post<unknown, TaskDetail>(`/tasks/${id}/restart`)
}

/** 照片和说明二选一即可提交；只写说明时不要传空字符串。 */
export function submitTask(id: number, note?: string) {
  return http.post<unknown, TaskDetail>(`/tasks/${id}/submit`, note ? { note } : undefined)
}

export function withdrawTask(id: number) {
  return http.post<unknown, TaskDetail>(`/tasks/${id}/withdraw`)
}

/**
 * 审核通过。
 *
 * 如果这是「错题重做」任务，`redoCorrect` 决定这道错题下一轮什么时候再来：
 * true 往后排（+2/+4/+7 天），false 明天重来。
 * 不传就只完成任务、不动错题节奏——留给「先收星星，回头再判」的场景。
 */
export function approveTask(id: number, redoCorrect?: boolean | null) {
  const body = redoCorrect === undefined || redoCorrect === null
    ? undefined
    : { redo_correct: redoCorrect }
  return http.post<unknown, TaskDetail>(`/tasks/${id}/approve`, body)
}

export function rejectTask(id: number, comment: string) {
  return http.post<unknown, TaskDetail>(`/tasks/${id}/reject`, { comment })
}

/**
 * 两步上传：先 POST /files 拿 file_id，再挂到任务上。
 *
 * 拆成两步是因为拍照和提交是两个动作——孩子可能先拍三张再一起交，
 * 也可能是提交前删掉重拍。合成一个接口就没法删单张了。
 */
export async function uploadPhoto(file: File): Promise<{ file_id: number; url: string }> {
  const fd = new FormData()
  fd.append('biz_type', 'shot')
  fd.append('file', file)
  const res = await http.post<unknown, { id: number; url: string }>('/files', fd)
  return { file_id: res.id, url: res.url }
}

export function attachShot(taskId: number, fileId: number) {
  return http.post<unknown, TaskDetail>(`/tasks/${taskId}/shots`, { file_id: fileId })
}

export function detachShot(taskId: number, shotId: number) {
  return http.delete<unknown, TaskDetail>(`/tasks/${taskId}/shots/${shotId}`)
}
