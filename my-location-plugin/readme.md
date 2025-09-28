# UniApp 自定义原生定位插件

一个功能完善的 UniApp 原生定位插件，支持高精度GPS定位、地址逆解析和持续定位功能。

## 功能特性

- ✅ 高精度GPS定位
- ✅ 网络定位支持  
- ✅ 地址逆解析（经纬度转地址）
- ✅ 持续定位监听
- ✅ 智能提供者选择（GPS优先，网络备用）
- ✅ 权限检查和状态监控
- ✅ 位置缓存机制
- ✅ 详细错误处理和日志记录

## 安装配置

### 1. 本地插件集成

1. 将 `my-location-plugin` 文件夹复制到你的 UniApp 项目的 `nativeplugins` 目录
2. 在 `manifest.json` 中配置插件：

```json
{
  "app-plus": {
    "nativePlugins": {
      "my-location-plugin": {
        "android": {
          "appkey": "可选的应用密钥"
        }
      }
    }
  }
}
```

### 2. 权限配置

插件会自动申请以下权限：
- `ACCESS_FINE_LOCATION`: 精确定位权限
- `ACCESS_COARSE_LOCATION`: 粗略定位权限  
- `ACCESS_BACKGROUND_LOCATION`: 后台定位权限（Android 10+）
- `INTERNET`: 网络权限（用于地址解析）

## API 接口

### 引入插件

```javascript
const locationPlugin = uni.requireNativePlugin('my-location-plugin');
```

### 1. 获取当前位置（异步）

```javascript
// 异步获取位置
locationPlugin.getLocation((result) => {
  if (result.success) {
    console.log('位置信息:', result.data);
    // result.data 包含:
    // - latitude: 纬度
    // - longitude: 经度  
    // - accuracy: 精度(米)
    // - altitude: 海拔
    // - speed: 速度
    // - bearing: 方向角
    // - time: 时间戳
    // - provider: 位置提供者
  } else {
    console.error('定位失败:', result.error);
  }
});
```

### 2. 获取当前位置（同步）

```javascript
// 同步获取缓存位置
const result = locationPlugin.getLocationSync();
if (result.success) {
  console.log('缓存位置:', result.data);
} else {
  console.log('无缓存位置:', result.error);
}
```

### 3. 地址逆解析

```javascript
// 经纬度转地址
locationPlugin.reverseGeocode({
  latitude: 39.9042,
  longitude: 116.4074
}, (result) => {
  if (result.success) {
    console.log('地址信息:', result.data);
    // result.data 包含:
    // - country: 国家
    // - province: 省份
    // - city: 城市
    // - district: 区县
    // - street: 街道
    // - streetNumber: 门牌号
    // - postalCode: 邮编
    // - formattedAddress: 格式化地址
  }
});
```

### 4. 持续定位

```javascript
// 开始持续定位
locationPlugin.startLocationUpdates({
  interval: 5000,    // 更新间隔(毫秒)
  distance: 10       // 最小移动距离(米)
}, (result) => {
  if (result.success) {
    console.log('持续定位更新:', result.data);
    // 持续接收位置更新...
  }
});

// 停止持续定位
locationPlugin.stopLocationUpdates();
```

## 使用示例

### 完整定位示例

```javascript
<template>
  <view class="location-demo">
    <button @click="getCurrentLocation">获取当前位置</button>
    <button @click="startContinuousLocation">开始持续定位</button>
    <button @click="stopContinuousLocation">停止持续定位</button>
    <button @click="getAddress">获取地址</button>
    
    <view v-if="locationData">
      <text>纬度: {{ locationData.latitude }}</text>
      <text>经度: {{ locationData.longitude }}</text>
      <text>精度: {{ locationData.accuracy }}米</text>
      <text>地址: {{ addressData.formattedAddress }}</text>
    </view>
  </view>
</template>

<script>
export default {
  data() {
    return {
      locationPlugin: null,
      locationData: null,
      addressData: null
    }
  },
  
  onLoad() {
    this.locationPlugin = uni.requireNativePlugin('my-location-plugin');
  },
  
  methods: {
    // 获取当前位置
    getCurrentLocation() {
      this.locationPlugin.getLocation((result) => {
        if (result.success) {
          this.locationData = result.data;
          uni.showToast({
            title: '定位成功',
            icon: 'success'
          });
        } else {
          uni.showToast({
            title: '定位失败: ' + result.error,
            icon: 'none'
          });
        }
      });
    },
    
    // 开始持续定位
    startContinuousLocation() {
      this.locationPlugin.startLocationUpdates({
        interval: 3000,
        distance: 5
      }, (result) => {
        if (result.success) {
          this.locationData = result.data;
          console.log('位置更新:', result.data);
        }
      });
    },
    
    // 停止持续定位
    stopContinuousLocation() {
      this.locationPlugin.stopLocationUpdates();
      uni.showToast({
        title: '已停止定位',
        icon: 'success'
      });
    },
    
    // 获取地址信息
    getAddress() {
      if (!this.locationData) {
        uni.showToast({
          title: '请先获取位置',
          icon: 'none'
        });
        return;
      }
      
      this.locationPlugin.reverseGeocode({
        latitude: this.locationData.latitude,
        longitude: this.locationData.longitude
      }, (result) => {
        if (result.success) {
          this.addressData = result.data;
          uni.showToast({
            title: '地址解析成功',
            icon: 'success'
          });
        } else {
          uni.showToast({
            title: '地址解析失败',
            icon: 'none'
          });
        }
      });
    }
  }
}
</script>
```

## 错误码说明

| 错误码 | 说明 |
|--------|------|
| 0 | 成功 |
| -1 | 无定位权限 |
| -2 | 位置服务未开启/无缓存位置 |
| -3 | 定位服务被禁用/定位异常 |
| -4 | 安全异常 |
| -5 | 定位失败/参数错误 |

## 注意事项

### Android 权限处理

1. **运行时权限**: Android 6.0+ 需要动态申请定位权限
2. **后台定位**: Android 10+ 需要额外申请后台定位权限
3. **精确定位**: Android 12+ 区分精确和模糊定位权限

### 最佳实践

1. **权限引导**: 在使用前向用户说明定位用途，提高权限授予率
2. **错误处理**: 处理各种定位失败情况，提供友好提示
3. **性能优化**: 不需要时及时停止定位，避免耗电
4. **隐私保护**: 遵循最小化原则，仅在必要时使用定位

### 兼容性

- **最低SDK版本**: Android API 21 (Android 5.0)
- **目标SDK版本**: 兼容最新Android版本
- **UniApp版本**: HBuilderX 3.0+

## 编译和调试

插件开发完成后，需要在 Android Studio 中编译生成 AAR 文件，然后集成到 UniApp 项目中。

### 调试模式

插件内置详细日志，可以通过 HBuilderX 控制台查看：

```javascript
// 查看插件日志
console.log('LocationPlugin 相关日志');
```

### 常见问题

1. **定位失败**: 检查权限是否授予，GPS是否开启
2. **地址解析失败**: 检查网络连接，Geocoder服务可用性
3. **持续定位不工作**: 检查是否正确停止之前的监听

## 更新日志

### v1.0.0
- 初始版本发布
- 支持基础定位功能
- 支持地址逆解析
- 支持持续定位

## 技术支持

如有问题，请提交 Issue 或联系开发者。

## 开源协议

MIT License