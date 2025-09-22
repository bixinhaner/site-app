<template>
  <div class="login-page">
    <div class="login-container">
      <div class="login-card">
        <!-- 登录头部 -->
        <div class="login-header">
          <div class="logo-section">
            <div class="logo-icon">
              <el-icon size="40" color="#f97316"><Box /></el-icon>
            </div>
            <h1 class="system-title">站点信息管理系统</h1>
          </div>
          <p class="login-subtitle">通信基站设备管理平台</p>
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
              placeholder="用户名"
              :prefix-icon="User"
              clearable
            />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="密码"
              :prefix-icon="Lock"
              show-password
              @keyup.enter="handleLogin"
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              :loading="loading"
              @click="handleLogin"
              class="login-button"
            >
              {{ loading ? '登录中...' : '登录' }}
            </el-button>
          </el-form-item>
        </el-form>

        <!-- 测试账号提示 -->
        <div class="test-accounts">
          <el-divider content-position="center">
            <span class="divider-text">测试账号</span>
          </el-divider>
          <div class="account-tips">
            <div class="account-item" @click="quickLogin('admin', 'admin123')">
              <el-tag type="danger" size="small">管理员</el-tag>
              <span>admin / admin123</span>
            </div>
            <div class="account-item" @click="quickLogin('inspector', 'inspector123')">
              <el-tag type="info" size="small">检查员</el-tag>
              <span>inspector / inspector123</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 页面底部 -->
      <div class="login-footer">
        <p>&copy; 2024 Baicells Trae - 站点信息管理系统</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { ElMessage, ElLoading } from 'element-plus'
import { User, Lock, Box } from '@element-plus/icons-vue'

const router = useRouter()
const userStore = useUserStore()

const loginFormRef = ref()
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

const loginRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名长度在2到50个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6个字符', trigger: 'blur' }
  ]
}

// 处理登录
const handleLogin = async () => {
  if (!loginFormRef.value) return
  
  try {
    const isValid = await loginFormRef.value.validate()
    if (!isValid) return
    
    loading.value = true
    const result = await userStore.login(loginForm)
    
    if (result.success) {
      ElMessage.success('登录成功！')
      router.push('/dashboard')
    } else {
      ElMessage.error(result.error || '登录失败')
    }
  } catch (error) {
    console.error('登录错误:', error)
    ElMessage.error('登录失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

// 快速登录
const quickLogin = (username, password) => {
  loginForm.username = username
  loginForm.password = password
  handleLogin()
}
</script>

<style scoped lang="scss">
.login-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse"><path d="M 10 0 L 0 0 0 10" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="0.5"/></pattern></defs><rect width="100" height="100" fill="url(%23grid)"/></svg>');
    opacity: 0.3;
  }
}

.login-container {
  position: relative;
  z-index: 1;
  max-width: 450px;
  width: 100%;
}

.login-card {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 16px;
  padding: 40px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.login-header {
  text-align: center;
  margin-bottom: 40px;
  
  .logo-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    
    .logo-icon {
      width: 80px;
      height: 80px;
      background: linear-gradient(45deg, var(--primary-color), var(--primary-light));
      border-radius: 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 8px 24px rgba(249, 115, 22, 0.3);
    }
    
    .system-title {
      color: var(--text-primary);
      font-size: 28px;
      font-weight: 700;
      margin: 0;
      letter-spacing: -0.5px;
    }
  }
  
  .login-subtitle {
    color: var(--text-secondary);
    font-size: 16px;
    margin: 8px 0 0 0;
  }
}

.login-form {
  .el-form-item {
    margin-bottom: 24px;
    
    :deep(.el-input__inner) {
      height: 48px;
      border-radius: 8px;
      border: 2px solid #f1f5f9;
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
    background: linear-gradient(45deg, var(--primary-color), var(--primary-light));
    border: none;
    transition: all 0.3s ease;
    
    &:hover {
      background: linear-gradient(45deg, var(--primary-dark), var(--primary-color));
      transform: translateY(-2px);
      box-shadow: 0 8px 24px rgba(249, 115, 22, 0.4);
    }
  }
}

.test-accounts {
  margin-top: 32px;
  
  .divider-text {
    color: var(--text-light);
    font-size: 14px;
  }
  
  .account-tips {
    display: flex;
    flex-direction: column;
    gap: 8px;
    
    .account-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 16px;
      background: #f8fafc;
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.3s ease;
      border: 1px solid #e2e8f0;
      
      &:hover {
        background: #f1f5f9;
        border-color: var(--primary-color);
        transform: translateY(-1px);
      }
      
      span {
        color: var(--text-secondary);
        font-size: 14px;
      }
    }
  }
}

.login-footer {
  text-align: center;
  margin-top: 32px;
  
  p {
    color: rgba(255, 255, 255, 0.8);
    font-size: 14px;
    margin: 0;
  }
}

// 响应式设计
@media (max-width: 768px) {
  .login-page {
    padding: 16px;
  }
  
  .login-card {
    padding: 32px 24px;
  }
  
  .login-header {
    margin-bottom: 32px;
    
    .logo-section {
      .logo-icon {
        width: 64px;
        height: 64px;
      }
      
      .system-title {
        font-size: 24px;
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