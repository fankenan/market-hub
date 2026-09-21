import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1', timeout: 20000 })

api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem('mh_token')
  if (t) cfg.headers.Authorization = 'Bearer ' + t
  return cfg
})

// 401 处理：只在「已登录但 token 失效」时才清理并跳转，
// 且用路由跳转而非 location.href（避免整页刷新 + 无限重定向循环）
let _redirecting = false

api.interceptors.response.use(
  (r) => r.data,
  (e) => {
    const status = e.response && e.response.status
    if (status === 401) {
      localStorage.removeItem('mh_token')
      const path = window.location.pathname
      // 已经在登录页就不做任何跳转，直接让 Login.vue 显示错误
      if (path !== '/login' && !_redirecting) {
        _redirecting = true
        // 用 replace 而不是 href，避免在浏览器历史里堆栈
        window.location.replace('/login')
      }
    } else if (status === 500) {
      console.error('[api] 服务端错误:', e.config && e.config.url, e.response.data)
    }
    return Promise.reject(e)
  }
)

export default api
