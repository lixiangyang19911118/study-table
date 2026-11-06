import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import {
  fetchMe,
  login as apiLogin,
  logout as apiLogout,
  type Account,
  type Child,
} from '../api/auth'

export type Role = 'kid' | 'parent'

/**
 * 会话上下文。
 *
 * - 登录态以 Cookie 为准，这里只是它的前端镜像；刷新页面后会重新拉 /auth/me。
 * - childId 是计算属性而不是独立字段：数据模型上 child 是一对多，
 *   但界面只用一个，避免出现「有 id 却没有对应孩子」的中间状态。
 * - loaded 表示「是否已经问过后端」，与 isLoggedIn 分开：
 *   否则刷新瞬间会把已登录用户误判成未登录，闪一下登录页。
 */
export const useSession = defineStore('session', () => {
  const account = ref<Account | null>(null)
  const children = ref<Child[]>([])
  const role = ref<Role>('kid')
  const loaded = ref(false)
  const busy = ref(false)

  const child = computed<Child | null>(() => children.value[0] ?? null)
  const childId = computed<number | null>(() => child.value?.id ?? null)
  const isLoggedIn = computed(() => account.value !== null)

  function apply(me: { account: Account; children: Child[] }) {
    account.value = me.account
    children.value = me.children
    loaded.value = true
  }

  function clear() {
    account.value = null
    children.value = []
    loaded.value = false
  }

  /** 向服务端确认一次登录态。401 不是错误，是「没登录」。 */
  async function refresh() {
    try {
      apply(await fetchMe())
    } catch {
      clear()
    }
    loaded.value = true
  }

  async function signIn(username: string, password: string) {
    busy.value = true
    try {
      apply(await apiLogin(username, password))
    } finally {
      busy.value = false
    }
  }

  async function signOut() {
    try {
      await apiLogout()
    } finally {
      clear()
    }
  }

  /** 档案改完后本地同步，省一次 /auth/me 往返。 */
  function replaceChild(next: Child) {
    children.value = children.value.map((c) => (c.id === next.id ? next : c))
  }

  function switchRole(next: Role) {
    role.value = next
  }

  return {
    account, children, role, loaded, busy,
    child, childId, isLoggedIn,
    refresh, signIn, signOut, replaceChild, switchRole,
  }
})
