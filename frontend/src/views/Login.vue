<template>
  <div class="login-wrap">
    <div class="card">
      <h1>行情数据平台</h1>
      <p class="sub">请登录后使用</p>
      <el-form @submit.prevent="doLogin">
        <el-input v-model="username" placeholder="用户名" size="large" />
        <el-input v-model="password" type="password" placeholder="密码" size="large"
                  show-password @keyup.enter="doLogin" />
        <el-button type="primary" size="large" :loading="loading" @click="doLogin">
          登 录
        </el-button>
      </el-form>
      <p class="err" v-if="err">{{ err }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'

const username = ref('admin')
const password = ref('')
const loading = ref(false)
const err = ref('')
const router = useRouter()

async function doLogin() {
  if (!username.value || !password.value) { err.value = '请输入用户名和密码'; return }
  loading.value = true; err.value = ''
  try {
    // 注意：api 的响应拦截器已 return r.data，
    // 所以这里拿到的是 {code, data:{token,...}}
    const r = await api.post('/auth/login', {
      username: username.value,
      password: password.value,
    })
    const token = r?.data?.token || r?.token
    if (!token) { err.value = '登录响应异常，请重试'; return }
    localStorage.setItem('mh_token', token)
    // 用 replace 避免用户按返回键又回到登录页
    await router.replace('/')
  } catch (e) {
    err.value = e?.response?.data?.detail || e?.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  background: #f5f6f8;
}
.card {
  width: 340px; background: #fff; border: 1px solid #e6e8ec;
  border-radius: 12px; padding: 32px 28px;
}
h1 { font-size: 17px; margin: 0 0 6px; }
.sub { font-size: 12px; color: #8a94a6; margin: 0 0 22px; }
.el-input { margin-bottom: 14px; }
.el-button { width: 100%; margin-top: 6px; }
.err { color: #e64545; font-size: 12px; margin: 12px 0 0; text-align: center; }
</style>
