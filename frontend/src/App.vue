<template>
  <!-- 登录页：不渲染顶栏，也不请求 /auth/me -->
  <router-view v-if="isLoginPage" />

  <div class="layout" v-else>
    <header class="topbar">
      <div class="brand"><span class="logo"></span>Market Hub 自选股</div>
      <nav>
        <router-link to="/" :class="{ on: $route.path === '/' }">自选</router-link>
        <router-link to="/portfolio" :class="{ on: $route.path === '/portfolio' }">持仓</router-link>
        <router-link to="/ipo" :class="{ on: $route.path === '/ipo' }">新上股票</router-link>
        <router-link
          v-if="$route.path.startsWith('/stock')"
          :to="$route.path"
          class="on">个股</router-link>
      </nav>
      <div class="right">
        <span class="who">{{ user }}</span>
        <a href="javascript:;" @click="logout">退出</a>
      </div>
    </header>
    <main><router-view /></main>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import api from './api'

const user = ref('')
const router = useRouter()
const route = useRoute()

// 登录页判定：既有路由 meta，也兼容路径判断
const isLoginPage = computed(() =>
  route.path === '/login' || route.meta.public === true
)

// 只在离开登录页、且已持 token 时拉取用户信息。
// 这样登录页不会发 /auth/me，彻底断掉 401 → 跳转 → 再请求的死循环。
watch(
  () => [isLoginPage.value, route.path],
  async () => {
    if (isLoginPage.value) { user.value = ''; return }
    if (!localStorage.getItem('mh_token')) return
    try {
      const r = await api.get('/auth/me')
      user.value = r.data.sub
    } catch (e) { /* 401 由拦截器处理 */ }
  },
  { immediate: true }
)

function logout() {
  localStorage.removeItem('mh_token')
  user.value = ''
  router.replace('/login')
}
</script>

<style>
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, 'Segoe UI', 'Microsoft YaHei', 'PingFang SC', sans-serif;
  background: #f3f5f9;
  color: #1a1a2e;
  font-size: 14px;
}
.topbar {
  display: flex; align-items: center; gap: 26px;
  height: 52px; padding: 0 22px; background: #fff;
  border-bottom: 1px solid #e8ecf2;
  position: sticky; top: 0; z-index: 100;
}
.brand { font-weight: 700; font-size: 15px; color: #0b1c33; display: flex; align-items: center; gap: 8px; }
.brand .logo {
  width: 22px; height: 22px; border-radius: 6px; display: inline-block;
  background: linear-gradient(135deg, #1485fe, #0b62e8);
  box-shadow: 0 2px 6px rgba(20,133,254,.35);
}
.topbar nav { display: flex; gap: 20px; font-size: 14px; }
.topbar nav a { color: #5a6472; text-decoration: none; padding: 15px 2px 13px; }
.topbar nav a.on { color: #1485fe; font-weight: 600; border-bottom: 2px solid #1485fe; }
.topbar .right { margin-left: auto; font-size: 12px; color: #8a94a6; display: flex; gap: 14px; align-items: center; }
.topbar .right a { color: #5a6472; text-decoration: none; }
main { padding: 14px 22px 40px; max-width: 1500px; margin: 0 auto; }

.up { color: #e64545; }
.down { color: #2fa36b; }
.flat { color: #8a94a6; }
.mono { font-variant-numeric: tabular-nums; }

/* 腾讯自选股风格通用卡片 */
.card {
  background: #fff; border: 1px solid #e8ecf2; border-radius: 10px;
  box-shadow: 0 1px 3px rgba(16,42,86,.04);
}
</style>
