# GPS地址水印功能说明

## 概述

增强的GPS地址水印功能可以在拍照时自动获取当前位置的GPS坐标，并通过地理编码服务获取详细的地址信息（省市区街道等），然后将这些信息自动添加到照片水印中，提供更丰富的位置信息记录。

## 主要特性

### 🌍 多地理编码服务支持
- **高德地图**：国内最准确的地理编码服务
- **腾讯地图**：微信生态集成，服务稳定
- **百度地图**：老牌地图服务，覆盖全面
- **OpenStreetMap**：免费开源服务，作为兜底方案

### 📍 丰富的地址信息
- GPS坐标（经纬度）
- 定位精度
- 详细地址（省市区街道门牌号）
- POI信息（附近地标）
- 行政区域信息

### ⚡ 智能缓存机制
- 24小时地址缓存，减少API调用
- 自动清理过期缓存
- 离线地址显示支持

### 🛡️ 安全可靠
- 多重降级方案
- 错误处理机制
- 水印防篡改

## 安装配置

### 1. 文件结构
```
uniapp-site-manager/
├── utils/
│   ├── watermark.js          # 原水印工具（已增强）
│   └── geocoding.js          # 新增：地理编码服务
├── config/
│   └── geocoding.js          # 新增：地理编码配置
├── examples/
│   └── watermark-usage.js    # 新增：使用示例
└── pages/test/
    └── watermark-test.vue    # 新增：测试页面
```

### 2. 基础使用（无需API密钥）
```javascript
import { watermarkTool } from '../utils/watermark.js'

// 直接使用增强水印功能（使用OpenStreetMap免费服务）
const watermarkedPath = await watermarkTool.addWatermarkWithGPS(imagePath, {
  inspector: '检查员姓名',
  checkItem: '检查项目',
  siteName: '站点名称'
})
```

### 3. 高级配置（使用商用API）
```javascript
// 配置API密钥获得更准确的地址信息
watermarkTool.setGeocodingApiKey('amap', 'your-amap-api-key')
watermarkTool.setGeocodingApiKey('tencent', 'your-tencent-api-key')
watermarkTool.setGeocodingApiKey('baidu', 'your-baidu-api-key')
```

## API密钥申请指南

### 高德地图（推荐）
1. 访问：https://lbs.amap.com/
2. 注册开发者账号
3. 创建应用，选择"Web服务API"
4. 获取API Key
5. **免费额度**：个人开发者每日100万次调用

### 腾讯地图
1. 访问：https://lbs.qq.com/
2. 创建应用
3. 申请WebService API密钥
4. **免费额度**：每日10万次调用

### 百度地图
1. 访问：https://lbsyun.baidu.com/
2. 创建应用
3. 申请服务端API
4. **免费额度**：个人开发者每日30万次调用

## 使用方法

### 方法1：自动获取GPS+地址水印
```javascript
import { watermarkTool } from '../utils/watermark.js'

// 最简单的用法
const watermarkedPath = await watermarkTool.addWatermarkWithGPS(imagePath, {
  inspector: '张三',
  checkItem: '天线检查',
  siteName: '基站001'
})
```

### 方法2：自定义配置
```javascript
const watermarkedPath = await watermarkTool.addWatermarkWithGPS(imagePath, {
  inspector: '张三',
  checkItem: '天线检查', 
  siteName: '基站001'
}, {
  showAddressDetails: true,  // 显示详细地址信息
  showPOI: true,            // 显示附近POI信息
  fallbackToBasic: true,    // GPS失败时使用基本模式
  geocoding: {
    skipCache: false        // 是否跳过缓存
  }
})
```

### 方法3：批量处理
```javascript
const results = await watermarkTool.addWatermarkBatch(imagePaths, {
  inspector: '张三',
  checkItem: '批量检查',
  siteName: '基站002'
}, {
  showAddressDetails: true,
  useGPS: true
})
```

### 方法4：手动获取GPS信息
```javascript
import { getEnhancedGPSInfo } from '../utils/geocoding.js'

const gpsInfo = await getEnhancedGPSInfo({
  watermarkOptions: {
    showDetails: true,
    showPOI: false
  }
})

console.log('GPS信息:', gpsInfo.address)
console.log('详细信息:', gpsInfo.addressInfo)
```

## 水印显示效果

增强后的水印将显示以下信息：

```
📍 39.904200, 116.407400
📊 精度: 5.2m
🏠 北京市东城区东长安街1号
🛣️ 东长安街1号
🕐 2024-01-15 14:30:25
👤 张三
📋 天线安装检查
🏗️ 基站001
```

## 在Vue组件中使用

```vue
<template>
  <button @click="takePhotoWithWatermark">拍照+水印</button>
</template>

<script>
import { watermarkTool } from '../utils/watermark.js'

export default {
  methods: {
    async takePhotoWithWatermark() {
      try {
        const cameraResult = await uni.chooseImage({
          count: 1,
          sizeType: ['original'],
          sourceType: ['camera']
        })
        
        const watermarkedPath = await watermarkTool.addWatermarkWithGPS(
          cameraResult.tempFilePaths[0],
          {
            inspector: this.$store.state.user.name,
            checkItem: this.currentCheckItem,
            siteName: this.currentSite.name
          }
        )
        
        // 处理带水印的照片
        this.handleWatermarkedPhoto(watermarkedPath)
        
      } catch (error) {
        uni.showToast({
          title: '水印添加失败: ' + error.message,
          icon: 'none'
        })
      }
    }
  }
}
</script>
```

## 配置管理

### 在应用启动时配置
```javascript
// main.js 或 App.vue
import { watermarkTool } from './utils/watermark.js'
import { autoConfigureGeocodingServices } from './config/geocoding.js'

// 自动配置所有可用的地理编码服务
autoConfigureGeocodingServices(watermarkTool)
```

### 环境变量配置
```javascript
// config/geocoding.js
export const geocodingConfig = {
  amap: {
    apiKey: process.env.AMAP_API_KEY || '',
    enabled: false
  },
  tencent: {
    apiKey: process.env.TENCENT_API_KEY || '',
    enabled: false
  },
  // ...
}
```

## 错误处理

### 常见问题及解决方案

1. **GPS获取失败**
   - 检查是否授权位置权限
   - 确保在户外环境或信号良好的地方
   - 系统会自动降级到基本水印模式

2. **地址获取失败**
   - 检查网络连接
   - 验证API密钥是否正确
   - 系统会显示GPS坐标作为兜底

3. **API调用超限**
   - 使用缓存减少重复调用
   - 配置多个地图服务作为备选
   - OpenStreetMap作为免费兜底方案

### 调试模式
```javascript
// 启用详细日志
console.log('GPS信息:', gpsInfo)
console.log('地址信息:', addressInfo)
console.log('水印数据:', watermarkData)
```

## 性能优化

### 缓存策略
- 相同坐标24小时内复用地址信息
- 自动清理过期缓存数据
- 缓存数量限制防止内存占用过大

### 网络优化
- 并发调用多个地理编码服务
- 超时设置避免长时间等待
- 失败快速降级到下一个服务

### 内存管理
- 及时释放canvas资源
- 限制同时处理的照片数量
- 清理临时文件

## 测试与验证

### 使用测试页面
访问测试页面进行功能验证：
```
/pages/test/watermark-test.vue
```

### 功能测试项目
- [ ] GPS坐标获取
- [ ] 地址信息获取
- [ ] 水印添加和显示
- [ ] 多张照片批量处理
- [ ] 网络异常处理
- [ ] 权限拒绝处理

### API密钥验证
```javascript
import { testApiKeys } from '../config/geocoding.js'

const results = await testApiKeys()
console.log('API测试结果:', results)
```

## 注意事项

### 隐私和安全
- GPS信息属于敏感数据，确保合规使用
- API密钥不要提交到代码仓库
- 生产环境使用HTTPS保护数据传输

### 成本控制
- 合理设置缓存策略减少API调用
- 监控API使用量，避免超出免费额度
- 配置多个服务商分散风险

### 兼容性
- 确保在不同设备上测试GPS功能
- 考虑iOS和Android的差异
- 处理不同网络环境下的表现

## 技术支持

如果遇到问题，请：
1. 查看控制台日志定位问题
2. 使用测试页面验证功能
3. 检查API密钥配置是否正确
4. 确认网络和GPS权限状态

---

通过这个增强的GPS地址水印功能，您的应用将能够提供更加详细和实用的位置信息记录，极大提升现场作业的数据质量和可信度。