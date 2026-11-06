import axios from 'axios'

/**
 * 统一请求层。页面里不出现裸 axios。
 * withCredentials 现在没用到，但 M1 接 JWT 后必须靠它带上 Cookie ——
 * <img> 和 PDF iframe 带不了 Authorization 头，只能走 Cookie，见技术方案 v1.1 缺口 1。
 */
const http = axios.create({
  baseURL: '/api/v1',
  timeout: 20000,
  withCredentials: true,
})

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    // Cookie 有过期时间（7 天），过期后所有接口都 401。
    // 不处理的话页面只会显示「请求失败」，用户不知道要重新登录。
    // 用整页跳转而不是 router.push：顺便把 store 里的残留状态一起清掉。
    // 登录页自身除外，否则密码输错会被当成会话过期。
    if (err.response?.status === 401 && location.pathname !== '/login') {
      const back = encodeURIComponent(location.pathname + location.search)
      location.assign(`/login?redirect=${back}`)
    }

    const msg =
      err.response?.data?.detail ||
      err.response?.data?.error?.message ||
      err.message ||
      '请求失败'
    return Promise.reject(new Error(msg))
  },
)

export default http
