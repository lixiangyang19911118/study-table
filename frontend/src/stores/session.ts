import { defineStore } from 'pinia'
import { ref } from 'vue'

export type Role = 'kid' | 'parent'

/**
 * 会话上下文。M0 只有角色与当前孩子 id 两个字段，
 * M1 接登录后这里补 token 刷新与账号信息。
 * 数据模型上 child 是一对多，所以从现在起就带 childId，不写死。
 */
export const useSession = defineStore('session', () => {
  const role = ref<Role>('kid')
  const childId = ref<number | null>(null)

  function switchRole(next: Role) {
    role.value = next
  }

  function setChild(id: number | null) {
    childId.value = id
  }

  return { role, childId, switchRole, setChild }
})
