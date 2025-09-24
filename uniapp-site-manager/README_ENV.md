# 环境配置说明

## 环境切换原理

本项目使用**自定义条件编译**来区分开发和生产环境：

- **开发环境**：默认配置（本地开发、HBuilderX运行）
- **生产环境**：需要在云打包时设置 `APP_PROD` 条件编译标识

## 重要说明 ⚠️

**HBuilderX 开发模式的限制**：
- HBuilderX 本地开发模式**不支持** manifest.json 的 `buildFeatures` 配置
- 只有在**云打包**时，条件编译才会生效
- 这是 HBuilderX 的设计限制，不是配置错误

## 如何使用

### 1. 开发环境（默认）
不需要任何配置，直接运行或本地打包：
```bash
npm run dev
# 或者在 HBuilderX 中直接运行
```

**输出日志**：
```
[ENV] 环境: DEVELOPMENT
[ENV] API地址: http://192.168.2.100:8000
```

### 2. 生产环境（仅云打包生效）

**在云打包前**，修改 `manifest.json` 中的 `buildFeatures`：

```json
{
  "app-plus": {
    "distribute": {
      "android": {
        "buildFeatures": ["APP_PROD"]
      },
      "ios": {
        "buildFeatures": ["APP_PROD"]  
      }
    }
  }
}
```

**云打包后的输出日志**：
```
[ENV] 环境: PRODUCTION
[ENV] API地址: http://113.45.25.135/api
```

## 配置文件结构

```
uniapp-site-manager/
├── config/
│   └── env.js              # 主要环境配置文件（条件编译）
├── env/
│   ├── .env.development    # 开发环境参考配置
│   └── .env.production     # 生产环境参考配置  
└── README_ENV.md           # 本说明文件
```

## 修改配置

要修改环境配置，请编辑 `config/env.js` 文件：

```javascript
// 开发环境配置
// #ifndef APP_PROD
config = {
  API_BASE_URL: 'http://192.168.2.100:8000',  // 修改这里
  APP_NAME: '站点管理系统',
  APP_VERSION: '1.0.0',
  DEBUG: true
}
// #endif

// 生产环境配置  
// #ifdef APP_PROD
config = {
  API_BASE_URL: 'https://your-production-server.com/api',  // 修改这里
  APP_NAME: '站点管理系统',
  APP_VERSION: '1.0.0', 
  DEBUG: false
}
// #endif
```

## 验证配置

打包完成后，在应用启动时查看控制台日志，确认环境配置是否正确。

## 故障排除

1. **云打包后仍然是开发环境**：
   - 检查 manifest.json 中是否正确配置了 `APP_PROD` 条件编译
   - 确认云打包配置中是否添加了自定义条件编译标识

2. **本地测试生产环境**：
   - 暂时在代码中强制设置：在 `config/env.js` 最顶部添加 `// #define APP_PROD`
   - **注意**：测试完成后务必删除此行

3. **API连接失败**：
   - 确认生产服务器地址是否正确
   - 检查网络连接和服务器状态