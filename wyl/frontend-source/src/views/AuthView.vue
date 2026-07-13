<template>
  <section class="auth-page">
    <div class="auth-shell">
      <!-- Left: form -->
      <div class="auth-form-side">
        <div class="form-inner" :class="{ 'animate-in': showContent }">
          <div class="auth-brand anim-item anim-1">
            <span class="auth-mark">R</span>
            <span class="auth-mark-text">RenTA</span>
          </div>

          <div class="auth-head anim-item anim-2">
            <span class="page-issue">Welcome</span>
            <h1 class="auth-title">{{ isLogin ? '欢迎回来' : '建立账户。' }}</h1>
            <p class="auth-sub">{{ isLogin ? '进入RenTA，探索无限可能' : '几分钟内开始 — 仅需用户名与密码。' }}</p>
          </div>

          <div class="auth-tabs anim-item anim-3">
            <button :class="{ active: isLogin }" @click="isLogin = true">登录</button>
            <button :class="{ active: !isLogin }" @click="isLogin = false">注册</button>
          </div>

          <form v-if="isLogin" class="auth-form anim-item anim-4" @submit.prevent="handleLogin">
            <div class="form-group">
              <label for="login-username">用户名</label>
              <input id="login-username" v-model="loginForm.username" placeholder="your handle" required />
            </div>
            <div class="form-group">
              <label for="login-pwd">密码</label>
              <input id="login-pwd" v-model="loginForm.password" type="password" placeholder="••••••••" required />
            </div>
            <button type="submit" class="btn btn-primary btn-block" :disabled="loading">
              <span v-if="loading" class="spinner-sm"></span>
              {{ loading ? '登录中…' : '登录' }}
            </button>
          </form>

          <form v-else class="auth-form anim-item anim-4" @submit.prevent="handleRegister">
            <div class="form-group">
              <label for="reg-username">用户名</label>
              <input id="reg-username" v-model="registerForm.username" placeholder="至少 3 个字符" required />
            </div>
            <div class="form-group">
              <label for="reg-pwd">密码</label>
              <input id="reg-pwd" v-model="registerForm.password" type="password" placeholder="••••••••" required />
            </div>
            <div class="form-group">
              <label for="reg-pwd2">确认密码</label>
              <input id="reg-pwd2" v-model="registerForm.confirmPassword" type="password" placeholder="再次输入" required />
            </div>
            <button type="submit" class="btn btn-primary btn-block" :disabled="loading">
              <span v-if="loading" class="spinner-sm"></span>
              {{ loading ? '创建中…' : '创建账户' }}
            </button>
          </form>

          <div class="auth-foot anim-item anim-5">
            <router-link to="/">← 返回首页</router-link>
          </div>
        </div>
      </div>

      <!-- Right: editorial plate -->
      <aside class="auth-plate">
        <div class="plate-grain" aria-hidden="true"></div>

        <div class="plate-top">

        </div>

        <div class="plate-mid">
          <h2 class="plate-headline">
            Rent  <em>   </em>  A  <em>gents</em>
          </h2>
          <p class="plate-lead">
            一个安静的工坊。允许注册、验证与发现，让每一个人的 agent 都能在它自己的小角落里生长。
          </p>
        </div>

        <div class="plate-quote">
          <span class="quote-mark">"</span>
          <p>智能体互联网应当像旷野，<br> </p>
          <p>而不是一亩私人花园。</p>
          <span class="quote-by">— Internet of Agents</span>
        </div>

        <div class="plate-foot">
          <div class="foot-stat"><span class="k">2026</span><span class="v">Year</span></div>
          <div class="foot-stat"><span class="k">1.0</span><span class="v">Version</span></div>
         <div class="foot-stat"><span class="k">24 h</span><span class="v">Service</span></div>        </div>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
const showContent = ref(false)
onMounted(() => { nextTick(() => { showContent.value = true }) })
import api from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const toast = useToastStore()

const isLogin = ref(true)
const loading = ref(false)
const loginForm = ref({ username: '', password: '' })
const registerForm = ref({ username: '', password: '', confirmPassword: '' })

const handleLogin = async () => {
 if (!loginForm.value.username || !loginForm.value.password) {
 toast.error('请填写完整信息'); return
 }
 loading.value = true
 try {
  // 真后端:POST /api/auth/login 是 OAuth2PasswordRequestForm,需要 form-urlencoded
  // 返回 { access_token, refresh_token, token_type, is_admin, user_id, username }
  const form = new URLSearchParams()
  form.append('username', loginForm.value.username)
  form.append('password', loginForm.value.password)
  const tokenRes = await api.post('/auth/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  })
 if (tokenRes?.access_token) {
 localStorage.setItem('access_token', tokenRes.access_token)
 } else {
 throw new Error('登录响应缺少 access_token: ' + JSON.stringify(tokenRes))
 }
 if (tokenRes?.refresh_token) localStorage.setItem('refresh_token', tokenRes.refresh_token)

  // 拉取当前用户信息
  let userInfo = null
  try {
  userInfo = await api.get('/account/me')
  } catch (e) {
  console.warn('[auth/login] /account/me 失败,降级用 token 信息', e)
  }

  // 规范化:后端用 id,store 用 user_id
  const userId = userInfo?.id || userInfo?.user_id || tokenRes?.user_id
  const username = userInfo?.username || tokenRes?.username || loginForm.value.username
  const roles = Array.isArray(userInfo?.roles) ? userInfo.roles : []

  // 管理员判定:优先 token 自带的 is_admin(注册/登录接口直接返回),fallback 到 roles 数组
  const isAdmin = tokenRes?.is_admin === true
  || roles.some(r => /admin/i.test(r))
  // 已知字段都给上
  auth.login({
  ...userInfo,
  user_id: userId,
  username,
  is_admin: isAdmin,
  roles,
  email: userInfo?.email || '',
  phone: userInfo?.phone || '',
  name: userInfo?.name || username,
  avatar: userInfo?.avatar || '',
  created_at: userInfo?.created_at || userInfo?.create_time || userInfo?.date_joined || '',
  is_active: userInfo?.is_active ?? userInfo?.active ?? true
  })
 toast.success('登录成功')
 const redirect = route.query.redirect || '/'
 await router.push(redirect)
 } catch (err) {
 console.error('[auth/login] error:', err)
 toast.error(err.message || '登录失败')
 } finally {
 loading.value = false
 }
}

const handleRegister = async () => {
  if (!registerForm.value.username || !registerForm.value.password) { toast.error('请填写完整信息'); return }
  if (registerForm.value.username.length < 3) { toast.error('用户名至少 3 个字符'); return }
  if (registerForm.value.password !== registerForm.value.confirmPassword) { toast.error('两次密码不一致'); return }
  loading.value = true
  try {
    const res = await api.post('/auth/register', {
 username: registerForm.value.username,
 password: registerForm.value.password
 })
 // 注册响应同样支持 success_response包裹 或扁平返回
 const regPayload = (res && res.data && typeof res.data === 'object' && 'access_token' in res.data)
 ? res.data
 : res
 if (regPayload?.access_token) {
      toast.success('注册成功,请登录')
      isLogin.value = true
      loginForm.value.username = registerForm.value.username
      registerForm.value = { username: '', password: '', confirmPassword: '' }
    }
  } catch (err) {
    toast.error(err.message || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* Entry */
.anim-item { opacity: 0; transform: translateY(16px); }
.animate-in .anim-item { animation: fadeInUp 0.5s var(--ease-out) forwards; }
.animate-in .anim-1 { animation-delay: 0ms; }
.animate-in .anim-2 { animation-delay: 80ms; }
.animate-in .anim-3 { animation-delay: 160ms; }
.animate-in .anim-4 { animation-delay: 240ms; }
.animate-in .anim-5 { animation-delay: 320ms; }
@keyframes fadeInUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }

/* === Page === */
.auth-page {
  min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  padding: 32px 24px;
  background: var(--bg-page);
}

/* === Shell === */
.auth-shell {
  display: grid;
  grid-template-columns: 1.1fr 1fr;
  width: 100%;
  max-width: 1080px;
  background: var(--bg-card);
  border: 1px solid var(--border-card);
  border-radius: var(--r-4);
  overflow: hidden;
  box-shadow: var(--shadow-lg);
  min-height: 640px;
}

/* === Form side === */
.auth-form-side {
  display: flex; align-items: center; justify-content: center;
  padding: 56px 48px;
}
.form-inner { width: 100%; max-width: 360px; }

.auth-brand { display: flex; align-items: center; gap: 10px; margin-bottom: 36px; }
.auth-mark {
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  background: var(--sky-grad-deep); color: var(--ink-inverse); box-shadow: 0 2px 8px rgba(46, 122, 184, 0.22);
  font-family: var(--font-editorial);
  font-size: 18px; font-style: italic; font-weight: 400;
  border-radius: 50%;
}
.auth-mark-text {
  font-family: var(--font-display);
  font-size: 15px; font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--ink);
}

.auth-head { margin-bottom: 28px; }
.auth-title {
  font-family: var(--font-display);
  font-size: 32px; font-weight: 600;
  line-height: 1.1; letter-spacing: -0.02em;
  color: var(--ink);
  margin: 12px 0 8px;
}
.auth-sub {
  font-size: 14px; line-height: 1.6;
  color: var(--ink-3);
  margin: 0;
}

.auth-tabs {
  display: flex;
  margin-bottom: 24px;
  background: var(--bg-card-soft);
  border: 1px solid var(--border-card);
  border-radius: var(--r-2);
  padding: 3px;
}
.auth-tabs button {
  flex: 1; padding: 9px 12px;
  background: none; border: none;
  font-size: 13px; font-weight: 500;
  color: var(--ink-3);
  cursor: pointer;
  border-radius: var(--r-1);
  transition: all var(--t-fast);
}
.auth-tabs button:hover:not(.active) { color: var(--ink); }
.auth-tabs button.active {
  background: var(--sky-grad-deep);
  color: var(--ink-inverse);
  box-shadow: var(--shadow-sm);
}

.auth-form { margin-bottom: 20px; }
.btn-block { width: 100%; min-height: 44px; font-size: 14px; }

.auth-foot {
  padding-top: 20px;
  border-top: 1px solid var(--border-divider);
  text-align: center;
}
.auth-foot a {
  font-size: 13px;
  color: var(--ink-3);
  text-decoration: none;
  transition: color var(--t-fast);
}
.auth-foot a:hover { color: var(--ink); }

/* === Plate (right) === */
.auth-plate {
  position: relative;
  background: var(--sky-grad-deep);
  color: var(--ink-inverse);
  padding: 48px 40px;
  display: flex; flex-direction: column; gap: 32px;
  overflow: hidden;
}
.plate-grain {
  position: absolute; inset: 0;
  background:
    radial-gradient(ellipse 400px 300px at 80% 20%, rgba(255,255,255,0.05) 0%, transparent 70%),
    radial-gradient(ellipse 500px 400px at 20% 80%, rgba(30, 58, 76, 0.3) 0%, transparent 70%);
  pointer-events: none;
}

.plate-top {
  position: relative; z-index: 1;
  display: flex; justify-content: space-between; align-items: center;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}
.plate-top .page-issue { color: rgba(255,255,255,0.6); border-color: rgba(255,255,255,0.2); }
.plate-issue {
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.18em; text-transform: uppercase;
  color: rgba(255,255,255,0.5);
}

.plate-mid { position: relative; z-index: 1; }
.plate-headline {
  font-family: var(--font-display);
  font-size: clamp(32px, 3.6vw, 44px);
  font-weight: 600;
  line-height: 1.05;
  letter-spacing: -0.025em;
  margin: 0 0 16px;
}
.plate-headline em {
  font-family: var(--font-editorial);
  font-style: italic; font-weight: 400;
  color: rgba(255,255,255,0.7);
}
.plate-lead {
  font-size: 14px; line-height: 1.7;
  color: rgba(255,255,255,0.65);
  margin: 0;
  max-width: 36ch;
}

.plate-quote {
  position: relative; z-index: 1;
  padding: 24px 0;
  border-top: 1px solid rgba(255,255,255,0.1);
  border-bottom: 1px solid rgba(255,255,255,0.1);
}
.quote-mark {
  font-family: var(--font-editorial);
  font-size: 64px; font-style: italic;
  line-height: 0.6;
  color: rgba(255,255,255,0.2);
  position: absolute; top: 16px; left: 0;
}
.plate-quote p {
  font-family: var(--font-editorial);
  font-size: 22px; font-style: italic; line-height: 1.3;
  color: var(--ink-inverse);
  margin: 0 0 12px;
  padding-left: 24px;
}
.quote-by {
  display: block;
  font-family: var(--font-mono);
  font-size: 10px; letter-spacing: 0.18em; text-transform: uppercase;
  color: rgba(255,255,255,0.4);
  padding-left: 24px;
}

.plate-foot {
  position: relative; z-index: 1;
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-top: auto;
}
.foot-stat { display: flex; flex-direction: column; gap: 2px; }
.foot-stat .k {
  font-family: var(--font-editorial);
  font-size: 24px; font-style: italic; font-weight: 400;
  color: var(--ink-inverse);
  font-variant-numeric: tabular-nums;
}
.foot-stat .v {
  font-family: var(--font-mono);
  font-size: 9px; letter-spacing: 0.18em; text-transform: uppercase;
  color: rgba(255,255,255,0.5);
}

/* === Responsive === */
@media (max-width: 900px) {
  .auth-shell { grid-template-columns: 1fr; max-width: 480px; }
  .auth-form-side { padding: 40px 28px; }
  .auth-plate { padding: 40px 32px; gap: 24px; }
  .plate-quote p { font-size: 18px; }
}
</style>
