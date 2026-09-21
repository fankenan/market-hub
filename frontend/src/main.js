import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Dashboard from './views/Dashboard.vue'
import Detail from './views/Detail.vue'
import Portfolio from './views/Portfolio.vue'
import IpoNew from './views/IpoNew.vue'
import Login from './views/Login.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: Login, meta: { public: true } },
    { path: '/', component: Dashboard },
    { path: '/portfolio', component: Portfolio },
    { path: '/ipo', component: IpoNew },
    { path: '/stock/:symbol', component: Detail },
    // 兜底：未知路径回首页（避免空白页）
    { path: '/:pathMatch(.*)*', redirect: '/' }
  ]
})

// 登录守卫：未登录且目标页非公开 → 去登录页。
// 已登录访问 /login → 去首页。都在登录页时直接放行，绝不重定向，
// 否则会与 api.js 的 401 处理形成无限循环。
router.beforeEach((to) => {
  const token = localStorage.getItem('mh_token')

  if (to.meta.public) {
    // 已登录还去登录页，直接进首页
    if (token && to.path === '/login') return { path: '/', replace: true }
    return true
  }

  if (!token) {
    return { path: '/login', replace: true }
  }

  return true
})

const app = createApp(App)
app.use(ElementPlus)
app.use(router)
app.mount('#app')
