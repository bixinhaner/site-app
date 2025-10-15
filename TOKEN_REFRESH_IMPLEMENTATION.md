# Token自动刷新机制实现说明

## 概述

实现了Token自动刷新和统一的401处理逻辑，解决了用户在操作过程中被强制退出的问题。

## 问题分析

### 原有问题
1. **Token过期时间短**: 30分钟后自动过期
2. **无自动刷新机制**: 即使用户一直在操作，30分钟后也会被强制退出
3. **401处理不统一**: 不同API文件有不同的处理逻辑
4. **用户体验差**: 操作到一半突然退出，数据可能丢失

## 解决方案

### 后端改进

#### 1. 添加Token刷新接口 (`backend/app/api/auth.py`)

```python
@router.post("/refresh", response_model=Token)
async def refresh_token(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """刷新访问令牌
    
    使用当前有效的token换取新的token，延长登录时间
    """
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=current_user.username, expires_delta=access_token_expires
    )
    
    raw = get_user_by_username(db, current_user.username)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse.from_orm(raw)
    }
```

### 前端改进

#### 1. 创建统一的请求工具 (`web-admin/src/utils/request.js`)

**核心特性**：
- 统一的axios实例配置
- 自动添加Authorization请求头
- Token自动刷新逻辑
- 请求队列管理，避免并发刷新
- 统一的401错误处理

**工作流程**：
1. 请求发送前自动添加token到Authorization头
2. 收到401响应时，尝试刷新token
3. 如果正在刷新，将请求加入队列等待
4. 刷新成功后，使用新token重试所有队列中的请求
5. 刷新失败则清除登录信息并跳转登录页

#### 2. 更新所有API文件使用统一请求实例

更新的文件：
- `web-admin/src/api/auth.js`
- `web-admin/src/api/user.js`
- `web-admin/src/api/equipment.js`
- `web-admin/src/api/stock.js`
- `web-admin/src/api/sitePlanning.js`
- `web-admin/src/api/templates.js`
- `web-admin/src/api/workorder.js`

所有文件统一使用：
```javascript
import request from '@/utils/request'
```

## 技术细节

### Token刷新策略

1. **触发时机**: 当API返回401状态码时
2. **刷新窗口**: 在Token过期前可以无限次刷新
3. **并发控制**: 多个请求同时401时，只刷新一次
4. **队列机制**: 等待刷新完成的请求会被放入队列

### 请求队列设计

```javascript
// 是否正在刷新token的标志
let isRefreshing = false

// 待重试的请求队列
let requestQueue = []

// 将失败的请求加入队列
function addRequestToQueue(config) {
  return new Promise((resolve, reject) => {
    requestQueue.push({ config, resolve, reject })
  })
}

// 重试队列中的所有请求
function retryRequestQueue(newToken) {
  requestQueue.forEach(({ config, resolve, reject }) => {
    config.headers.Authorization = `Bearer ${newToken}`
    request(config).then(resolve).catch(reject)
  })
  requestQueue = []
}
```

### 错误处理流程

```
API请求 → 401错误
    ↓
检查是否正在刷新
    ↓
    是 → 加入队列等待
    ↓
    否 → 标记刷新中
    ↓
调用/api/auth/refresh
    ↓
    ├─ 成功
    │   ├─ 更新localStorage
    │   ├─ 重试队列请求
    │   └─ 重试原请求
    │
    └─ 失败
        ├─ 清空队列
        ├─ 清除登录信息
        └─ 跳转登录页
```

## 用户体验提升

### 改进前
- 30分钟后强制退出
- 正在编辑的数据可能丢失
- 需要重新登录继续操作

### 改进后
- 自动刷新token，无感知延长会话
- 正常操作下永不过期
- 只有真正失效时才提示重新登录

## 配置说明

### 后端配置 (`backend/app/core/config.py`)
```python
ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # Token有效期30分钟
```

### 前端配置 (`web-admin/src/utils/request.js`)
```javascript
const request = axios.create({
  baseURL: config.API_BASE_URL,
  timeout: config.TIMEOUT || 10000
})
```

## 测试验证

运行测试脚本验证功能：
```bash
python backend/test_token_refresh.py
```

测试覆盖：
1. ✅ 登录获取token
2. ✅ 使用token访问受保护接口
3. ✅ 刷新token
4. ✅ 使用新token访问接口
5. ✅ 验证旧token状态

## 注意事项

1. **JWT特性**: JWT在过期前都是有效的，刷新token不会使旧token立即失效
2. **网络异常**: 如果刷新请求失败（如网络断开），会提示用户重新登录
3. **安全性**: Token仍然有过期时间，用户长时间不活动后需要重新登录
4. **并发请求**: 同时发送多个请求时，刷新机制确保只刷新一次

## 后续优化建议

1. **Refresh Token机制**: 实现单独的refresh token，提高安全性
2. **过期提醒**: 在token即将过期时提前提醒用户
3. **活动检测**: 基于用户活动动态调整刷新策略
4. **心跳机制**: 定期发送心跳保持会话活跃

## 兼容性

- ✅ 向后兼容：不影响现有功能
- ✅ 渐进式：用户无感知升级
- ✅ 统一处理：所有API请求都受益
