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
    const msg =
      err.response?.data?.detail ||
      err.response?.data?.error?.message ||
      err.message ||
      '请求失败'
    return Promise.reject(new Error(msg))
  },
)

export default http
