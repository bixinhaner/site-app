<template>
  <div class="login-page">
    <div class="login-locale-switcher">
      <LocaleSwitcher />
    </div>
    <div class="login-container">
      <div class="login-card">
        <!-- 登录头部 -->
        <div class="login-header">
          <div class="logo-section">
            <div class="logo-icon">
              <svg class="logo-svg" viewBox="0 0 64 64" aria-hidden="true">
                <g
                  fill="none"
                  stroke="currentColor"
                  stroke-width="3.2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <!-- 信号波纹 -->
                  <path d="M20 18 C10 26 10 38 20 46" />
                  <path d="M24 22 C17 27 17 37 24 42" />
                  <path d="M44 18 C54 26 54 38 44 46" />
                  <path d="M40 22 C47 27 47 37 40 42" />

                  <!-- 天线塔 -->
                  <circle cx="32" cy="14" r="3" />
                  <path d="M32 17 L32 24" />
                  <path d="M32 18 L24 54" />
                  <path d="M32 18 L40 54" />
                  <path d="M22 54 L42 54" />
                  <path d="M28 30 L36 30" />
                  <path d="M27 40 L37 40" />
                  <path d="M26 48 L38 48" />
                </g>
              </svg>
            </div>
            <h1 class="system-title">{{ t('app.systemName') }}</h1>
          </div>
          <p class="login-subtitle">{{ t('app.systemSubtitle') }}</p>
        </div>

        <!-- 登录表单 -->
        <el-form
          ref="loginFormRef"
          :model="loginForm"
          :rules="loginRules"
          class="login-form"
          size="large"
        >
          <el-form-item prop="username">
            <el-input
              v-model="loginForm.username"
              :placeholder="t('login.username')"
              :prefix-icon="User"
              clearable
              autocomplete="username"
              :disabled="loading"
            />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              :placeholder="t('login.password')"
              :prefix-icon="Lock"
              show-password
              @keyup.enter="handleLogin"
              autocomplete="current-password"
              :disabled="loading"
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              :loading="loading"
              :disabled="loading"
              @click="handleLogin"
              class="login-button"
            >
              {{ loading ? t('login.submitting') : t('login.submit') }}
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 页面底部 -->
      <div class="login-footer">
        <p>&copy; {{ currentYear }} Baicells Technologies Co., Ltd. All Rights Reserved.</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '../stores/user'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import LocaleSwitcher from '../components/common/LocaleSwitcher.vue'
import { resolveDefaultAuthenticatedRoute } from '../router/access'

const router = useRouter()
const userStore = useUserStore()
const { t } = useI18n()

const loginFormRef = ref()
const loading = ref(false)
const currentYear = new Date().getFullYear()

const loginForm = reactive({
  username: '',
  password: ''
})

const loginRules = computed(() => ({
  username: [
    { required: true, message: t('login.usernameRequired'), trigger: 'blur' },
    { min: 2, max: 50, message: t('login.usernameLength'), trigger: 'blur' }
  ],
  password: [
    { required: true, message: t('login.passwordRequired'), trigger: 'blur' },
    { min: 6, message: t('login.passwordLength'), trigger: 'blur' }
  ]
}))

// 处理登录
const handleLogin = async () => {
  if (!loginFormRef.value) return
  
  try {
    const isValid = await loginFormRef.value.validate()
    if (!isValid) return
    
    loading.value = true
    const credentials = {
      username: String(loginForm.username || '').trim(),
      password: loginForm.password,
    }
    const result = await userStore.login(credentials)
    
    if (result.success) {
      ElMessage.success(t('login.success'))
      const nextRoute = resolveDefaultAuthenticatedRoute(router.options.routes, userStore)
      router.push(nextRoute || { path: '/dashboard' })
    } else {
      ElMessage.error(result.error || t('login.failed'))
    }
  } catch (error) {
    console.error('登录错误:', error)
    ElMessage.error(t('login.failedRetry'))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.login-page {
  min-height: 100vh;
  background:
    radial-gradient(1100px 600px at 10% 10%, rgba(249, 115, 22, 0.12), transparent 55%),
    radial-gradient(900px 520px at 90% 20%, rgba(59, 130, 246, 0.10), transparent 58%),
    var(--bg-color);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  position: relative;
  
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-image: radial-gradient(rgba(17, 24, 39, 0.06) 1px, transparent 1px);
    background-size: 24px 24px;
    opacity: 0.35;
    pointer-events: none;
  }
}

.login-locale-switcher {
  position: absolute;
  top: 20px;
  right: 20px;
  z-index: 2;
}

.login-container {
  position: relative;
  z-index: 1;
  max-width: 420px;
  width: 100%;
}

.login-card {
  background: #ffffff;
  border-radius: 16px;
  padding: 40px 40px 32px;
  box-shadow: var(--shadow-lg);
  border: 1px solid var(--border-color);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
  
  .logo-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
    
    .logo-icon {
      width: 64px;
      height: 64px;
      background: #fff7ed;
      border-radius: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--primary-color);
      border: 1px solid rgba(249, 115, 22, 0.25);
      box-shadow: 0 8px 20px rgba(17, 24, 39, 0.06);
    }

    .logo-svg {
      width: 40px;
      height: 40px;
      display: block;
    }
    
    .system-title {
      color: var(--text-primary);
      font-size: 24px;
      font-weight: 700;
      margin: 0;
      letter-spacing: -0.5px;
    }
  }
  
  .login-subtitle {
    color: var(--text-secondary);
    font-size: 14px;
    margin: 8px 0 0 0;
  }
}

.login-form {
  .el-form-item {
    margin-bottom: 18px;
    
    :deep(.el-input__inner) {
      height: 48px;
      border-radius: 8px;
      border: 1px solid var(--border-color);
      transition: all 0.3s ease;
      
      &:focus {
        border-color: var(--primary-color);
        box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.1);
      }
    }
    
    :deep(.el-input__prefix) {
      color: var(--text-light);
    }
  }
  
  .login-button {
    width: 100%;
    height: 48px;
    font-size: 16px;
    font-weight: 600;
    border-radius: 8px;
    background: var(--primary-color);
    border: none;
    transition: all 0.3s ease;
    
    &:hover {
      background: var(--primary-dark);
      box-shadow: 0 8px 18px rgba(249, 115, 22, 0.25);
    }
  }
}

.login-footer {
  text-align: center;
  margin-top: 32px;
  
  p {
    color: var(--text-secondary);
    font-size: 12px;
    margin: 0;
  }
}

// 响应式设计
@media (max-width: 768px) {
  .login-page {
    padding: 16px;
  }

  .login-locale-switcher {
    top: 12px;
    right: 12px;
  }
  
  .login-card {
    padding: 28px 20px 22px;
  }
  
  .login-header {
    margin-bottom: 24px;
    
    .logo-section {
      .logo-icon {
        width: 56px;
        height: 56px;
      }
      
      .system-title {
        font-size: 22px;
      }
    }
    
    .login-subtitle {
      font-size: 14px;
    }
  }
}

// 加载动画
.login-card {
  animation: slideIn 0.6s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
