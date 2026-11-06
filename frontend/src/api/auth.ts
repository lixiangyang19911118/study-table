import http from './http'

/** 登录态的形状。字段与后端 schemas/auth.py 一一对应，改一处要同步改另一处。 */
export interface Account {
  id: number
  username: string
  nickname: string
}

export interface Child {
  id: number
  name: string
  grade: number
  edition: string
}

export interface Me {
  account: Account
  children: Child[]
}

export function login(username: string, password: string) {
  return http.post<unknown, Me>('/auth/login', { username, password })
}

export function logout() {
  return http.post<unknown, { ok: boolean }>('/auth/logout')
}

export function fetchMe() {
  return http.get<unknown, Me>('/auth/me')
}

export function patchChild(
  id: number,
  patch: Partial<Pick<Child, 'name' | 'grade' | 'edition'>>,
) {
  return http.patch<unknown, Child>(`/children/${id}`, patch)
}

export function createChild(body: Pick<Child, 'name' | 'grade' | 'edition'>) {
  return http.post<unknown, Child>('/children', body)
}
