<template>
  <view class="location-test-page" :key="languageStore.currentLocale">
    <view class="header">
      <text class="title">{{ $t('test.locationPlugin.title') }}</text>
      <text class="subtitle">{{ $t('test.locationPlugin.subtitle') }}</text>
    </view>
    
    <view class="test-section">
      <view class="status-card" :class="pluginStatus.class">
        <text class="status-text">{{ pluginStatus.text }}</text>
        <text class="status-desc">{{ pluginStatus.desc }}</text>
      </view>
      
      <view class="button-group">
        <button @click="testPluginLoad" class="test-btn primary">{{ $t('test.locationPlugin.btnDetectLoad') }}</button>
        <button @click="checkAvailableMethods" class="test-btn info" :disabled="!pluginLoaded">{{ $t('test.locationPlugin.btnCheckMethods') }}</button>
        <button @click="runCompleteTest" class="test-btn warning" :disabled="!pluginLoaded">{{ $t('test.locationPlugin.btnRunAll') }}</button>
        <button @click="testPluginBasic" class="test-btn" :disabled="!pluginLoaded">{{ $t('test.locationPlugin.btnBasic') }}</button>
        <button @click="testPermissions" class="test-btn" :disabled="!pluginLoaded">{{ $t('test.locationPlugin.btnPermissions') }}</button>
        <button @click="testLocationSync" class="test-btn" :disabled="!pluginLoaded">{{ $t('test.locationPlugin.btnLocationSync') }}</button>
        <button @click="testLocationAsync" class="test-btn success" :disabled="!pluginLoaded">{{ $t('test.locationPlugin.btnLocationAsync') }}</button>
        <button @click="testLocationWithAddress" class="test-btn success" :disabled="!pluginLoaded">{{ $t('test.locationPlugin.btnLocationWithAddress') }}</button>
      </view>
    </view>
    
    <view class="result-section" v-if="testResults.length > 0">
      <text class="section-title">{{ $t('test.locationPlugin.sectionResults') }}</text>
      <scroll-view class="results-list" scroll-y>
        <view v-for="(result, index) in testResults" :key="index" class="result-item">
          <view class="result-header">
            <text class="result-time">{{ result.time }}</text>
            <text class="result-status" :class="result.success ? 'success' : 'error'">
              {{ result.success ? $t('test.locationPlugin.resultSuccess') : $t('test.locationPlugin.resultFailed') }}
            </text>
          </view>
          <text class="result-message">{{ result.message }}</text>
          <view v-if="result.data" class="result-data">
            <text class="data-text">{{ JSON.stringify(result.data, null, 2) }}</text>
          </view>
        </view>
      </scroll-view>
      
      <button @click="clearResults" class="clear-btn">{{ $t('test.locationPlugin.clearResults') }}</button>
    </view>
    
    <view class="integration-info">
      <text class="info-title">{{ $t('test.locationPlugin.integrationTitle') }}</text>
      <view class="info-item">
        <text class="info-label">{{ $t('test.locationPlugin.pluginDir') }}:</text>
        <text class="info-value">nativeplugins/my-location-plugin ✅</text>
      </view>
      <view class="info-item">
        <text class="info-label">{{ $t('test.locationPlugin.manifestConfigured') }}:</text>
        <text class="info-value">已配置 nativePlugins ✅</text>
      </view>
      <view class="info-item">
        <text class="info-label">{{ $t('test.locationPlugin.aarFile') }}:</text>
        <text class="info-value">location-plugin-debug.aar ✅</text>
      </view>
      <view class="info-item">
        <text class="info-label">{{ $t('test.locationPlugin.permissionConfig') }}:</text>
        <text class="info-value">AndroidManifest.xml ✅</text>
      </view>
    </view>
  </view>
</template>

<script>
import { useLanguageStore } from '@/stores/language'
export default {
  name: 'TestLocationPlugin',
  data() {
    return {
      languageStore: useLanguageStore(),
      pluginLoaded: false,
      locationPlugin: null,
      pluginStatus: {
        text: '',
        desc: '',
        class: 'status-pending'
      },
      testResults: []
    }
  },
  
  onLoad() {
    uni.setNavigationBarTitle({ title: this.$t('test.locationPlugin.title') })
    this.pluginStatus = {
      text: this.$t('test.locationPlugin.statusNotChecked'),
      desc: this.$t('test.locationPlugin.statusPendingDesc'),
      class: 'status-pending'
    }
    this.addResult(false, '页面加载', '🚀 增强版定位插件测试页面已加载');
    this.addResult(false, '说明', '📋 请依次点击按钮进行测试，或使用"完整诊断测试"一键检测所有功能');
  },
  
  methods: {
    // 测试插件加载
    testPluginLoad() {
      this.addResult(false, '插件加载检测', '正在尝试加载 my-location-plugin...');
      
      try {
        // 尝试加载插件
        const plugin = uni.requireNativePlugin('my-location-plugin');
        
        if (plugin) {
          this.locationPlugin = plugin;
          this.pluginLoaded = true;
          this.pluginStatus = {
            text: this.$t('test.locationPlugin.statusLoadSuccess'),
            desc: this.$t('test.locationPlugin.statusLoadSuccessDesc'),
            class: 'status-success'
          };
          
          this.addResult(true, '插件加载', '成功加载 my-location-plugin', { 
            plugin: '已加载',
            type: typeof plugin 
          });
          
          uni.showToast({
            title: this.$t('test.locationPlugin.statusLoadSuccess'),
            icon: 'success'
          });
          
        } else {
          throw new Error('插件返回 null 或 undefined');
        }
        
      } catch (error) {
        this.pluginStatus = {
          text: this.$t('test.locationPlugin.statusLoadFailed'),
          desc: error.message,
          class: 'status-error'
        };
        
        this.addResult(false, '插件加载', `加载失败: ${error.message}`);
        
        uni.showModal({
          title: this.$t('test.locationPlugin.statusLoadFailed'),
          content: this.$t('test.locationPlugin.modalLoadFailedContent', { error: error.message }),
          showCancel: false
        });
      }
    },
    
    // 运行完整诊断测试
    runCompleteTest() {
      this.addResult(false, '完整诊断', '开始运行完整的插件诊断测试...', '🔍');
      
      setTimeout(() => this.testPluginBasic(), 100);
      setTimeout(() => this.testPermissions(), 500);
      setTimeout(() => this.testLocationSync(), 1000);
      setTimeout(() => this.testLocationAsync(), 1500);
      setTimeout(() => this.testLocationWithAddress(), 2000);
    },
    
    // 测试插件基本功能
    testPluginBasic() {
      if (!this.locationPlugin) {
        this.addResult(false, '插件基本测试', '插件未加载');
        return;
      }
      
      this.addResult(false, '插件基本测试', '正在调用 test() 方法...');
      
      try {
        const rawResult = this.locationPlugin.test();
        
        console.log('=== 插件基本测试结果 ===');
        console.log('原始结果:', rawResult);
        console.log('结果类型:', typeof rawResult);
        
        // 如果返回的是字符串，尝试解析为JSON
        let result = rawResult;
        if (typeof rawResult === 'string') {
          try {
            result = JSON.parse(rawResult);
            console.log('解析后的JSON:', result);
          } catch (parseError) {
            console.error('JSON解析失败:', parseError);
            result = { success: false, error: 'JSON解析失败', raw: rawResult };
          }
        }
        
        console.log('最终结果:', JSON.stringify(result, null, 2));
        console.log('是否为对象:', typeof result === 'object');
        console.log('=== 插件基本测试结束 ===');
        
        if (result) {
          this.addResult(true, '插件基本测试', '✅ test() 方法调用成功', result);
          
          // 如果有 deviceInfo，单独显示
          if (result.deviceInfo) {
            this.addResult(true, '设备信息', '📱 设备状态详情', result.deviceInfo);
          }
          
          // 如果有版本信息，单独显示
          if (result.version) {
            this.addResult(true, '插件版本', `📦 版本: ${result.version}`, {
              version: result.version,
              sdk: result.sdk,
              features: result.features
            });
          }
          
        } else {
          this.addResult(false, '插件基本测试', '❌ test() 方法返回空结果', { 
            result: result, 
            type: typeof result 
          });
        }
        
      } catch (error) {
        console.error('插件基本测试错误:', error);
        this.addResult(false, '插件基本测试', `❌ test() 方法调用失败: ${error.message}`, {
          error: error.message,
          stack: error.stack
        });
      }
    },
    
    // 测试权限状态
    testPermissions() {
      if (!this.locationPlugin) {
        this.addResult(false, '权限检查', '插件未加载');
        return;
      }
      
      this.addResult(false, '权限检查', '正在调用 checkPermission() 方法...');
      
      try {
        const rawResult = this.locationPlugin.checkPermission();
        
        console.log('=== 权限检查结果 ===');
        console.log('原始结果:', rawResult);
        console.log('结果类型:', typeof rawResult);
        
        // 如果返回的是字符串，尝试解析为JSON
        let result = rawResult;
        if (typeof rawResult === 'string') {
          try {
            result = JSON.parse(rawResult);
            console.log('解析后的JSON:', result);
          } catch (parseError) {
            console.error('JSON解析失败:', parseError);
            result = { success: false, error: 'JSON解析失败', raw: rawResult };
          }
        }
        
        console.log('最终结果:', JSON.stringify(result, null, 2));
        console.log('=== 权限检查结束 ===');
        
        if (result) {
          const success = result.success !== false;
          const hasPermission = result.hasPermission === true;
          const locationEnabled = result.locationEnabled === true;
          
          this.addResult(success, '权限检查', 
            success ? '✅ checkPermission() 方法调用成功' : '❌ checkPermission() 方法调用失败', 
            result
          );
          
          // 详细权限分析
          if (result.hasPermission !== undefined) {
            this.addResult(hasPermission, '定位权限', 
              hasPermission ? '✅ 应用已获得定位权限' : '❌ 应用缺少定位权限', 
              {
                hasPermission: result.hasPermission,
                fineLocation: result.fineLocation,
                coarseLocation: result.coarseLocation
              }
            );
          }
          
          if (result.locationEnabled !== undefined) {
            this.addResult(locationEnabled, '位置服务', 
              locationEnabled ? '✅ 设备位置服务已开启' : '❌ 设备位置服务未开启', 
              {
                locationEnabled: result.locationEnabled,
                gpsEnabled: result.gpsEnabled,
                networkEnabled: result.networkEnabled
              }
            );
          }
          
        } else {
          this.addResult(false, '权限检查', '❌ checkPermission() 方法返回空结果', {
            result: result,
            type: typeof result
          });
        }
        
      } catch (error) {
        console.error('权限检查错误:', error);
        this.addResult(false, '权限检查', `❌ checkPermission() 方法调用失败: ${error.message}`, {
          error: error.message,
          stack: error.stack
        });
      }
    },
    
    // 测试同步定位
    testLocationSync() {
      if (!this.locationPlugin) {
        this.addResult(false, '同步定位', '插件未加载');
        return;
      }
      
      this.addResult(false, '同步定位', '正在调用 getLocationSync() 方法...');
      
      try {
        const rawResult = this.locationPlugin.getLocationSync();
        
        console.log('=== 同步定位结果 ===');
        console.log('原始结果:', rawResult);
        console.log('结果类型:', typeof rawResult);
        
        // 如果返回的是字符串，尝试解析为JSON
        let result = rawResult;
        if (typeof rawResult === 'string') {
          try {
            result = JSON.parse(rawResult);
            console.log('解析后的JSON:', result);
          } catch (parseError) {
            console.error('JSON解析失败:', parseError);
            result = { success: false, error: 'JSON解析失败', raw: rawResult };
          }
        }
        
        console.log('最终结果:', JSON.stringify(result, null, 2));
        if (result) {
          console.log('success字段:', result.success);
          console.log('code字段:', result.code);
          console.log('data字段:', result.data);
          console.log('message字段:', result.message);
        }
        console.log('=== 同步定位结束 ===');
        
        if (result) {
          const success = result.success === true;
          const hasData = result.data && typeof result.data === 'object';
          
          this.addResult(success, '同步定位', 
            success ? '✅ getLocationSync() 调用成功' : `⚠️ getLocationSync() 返回: ${result.message || result.error}`, 
            result
          );
          
          // 如果有位置数据，单独显示
          if (hasData && result.data.latitude && result.data.longitude) {
            this.addResult(true, '位置数据', 
              `📍 坐标: ${result.data.latitude}, ${result.data.longitude}`, 
              {
                latitude: result.data.latitude,
                longitude: result.data.longitude,
                accuracy: result.data.accuracy,
                provider: result.data.provider,
                time: new Date(result.data.time).toLocaleString()
              }
            );
          }
          
        } else {
          this.addResult(false, '同步定位', '❌ getLocationSync() 返回空结果', {
            result: result,
            type: typeof result
          });
        }
        
      } catch (error) {
        console.error('同步定位错误:', error);
        this.addResult(false, '同步定位', `❌ getLocationSync() 调用失败: ${error.message}`, {
          error: error.message,
          stack: error.stack
        });
      }
    },
    
    // 测试异步定位
    testLocationAsync() {
      if (!this.locationPlugin) {
        this.addResult(false, '异步定位', '插件未加载');
        return;
      }
      
      this.addResult(false, '异步定位', '正在调用 getLocation() 方法...');
      
      try {
        // 设置超时处理
        const timeout = setTimeout(() => {
          this.addResult(false, '异步定位超时', '⏰ getLocation() 方法30秒内未返回结果', {
            timeout: '30秒',
            suggestion: '可能是定位权限、GPS信号或网络问题'
          });
        }, 30000);
        
        this.locationPlugin.getLocation((rawResult) => {
          clearTimeout(timeout);
          
          console.log('=== 异步定位结果 ===');
          console.log('原始结果:', rawResult);
          console.log('结果类型:', typeof rawResult);
          
          // 如果返回的是字符串，尝试解析为JSON
          let result = rawResult;
          if (typeof rawResult === 'string') {
            try {
              result = JSON.parse(rawResult);
              console.log('解析后的JSON:', result);
            } catch (parseError) {
              console.error('JSON解析失败:', parseError);
              result = { success: false, error: 'JSON解析失败', raw: rawResult };
            }
          }
          
          console.log('最终结果:', JSON.stringify(result, null, 2));
          if (result) {
            console.log('success字段:', result.success);
            console.log('code字段:', result.code);
            console.log('data字段:', result.data);
            console.log('message字段:', result.message);
          }
          console.log('=== 异步定位结束 ===');
          
          if (result) {
            const success = result.success === true;
            const hasData = result.data && typeof result.data === 'object';
            
            this.addResult(success, '异步定位', 
              success ? '✅ getLocation() 调用成功' : `⚠️ getLocation() 返回: ${result.message || result.error}`, 
              result
            );
            
            // 如果有位置数据，单独显示
            if (hasData && result.data.latitude && result.data.longitude) {
              this.addResult(true, '实时位置数据', 
                `📍 实时坐标: ${result.data.latitude}, ${result.data.longitude}`, 
                {
                  latitude: result.data.latitude,
                  longitude: result.data.longitude,
                  accuracy: result.data.accuracy,
                  provider: result.data.provider,
                  time: new Date(result.data.time).toLocaleString()
                }
              );
              
              uni.showToast({
                title: this.$t('test.locationPlugin.toastRealtimeLocationSuccess'),
                icon: 'success'
              });
            }
            
          } else {
            this.addResult(false, '异步定位', '❌ getLocation() 回调返回空结果', {
              result: result,
              type: typeof result
            });
          }
        });
        
      } catch (error) {
        console.error('异步定位错误:', error);
        this.addResult(false, '异步定位', `❌ getLocation() 调用失败: ${error.message}`, {
          error: error.message,
          stack: error.stack
        });
      }
    },
    
    // 测试位置+地址解析
    testLocationWithAddress() {
      if (!this.locationPlugin) {
        this.addResult(false, '位置+地址', '插件未加载');
        return;
      }
      
      this.addResult(false, '位置+地址', '正在调用 getLocationWithAddress() 方法...');
      
      try {
        // 设置超时处理
        const timeout = setTimeout(() => {
          this.addResult(false, '地址解析超时', '⏰ getLocationWithAddress() 方法30秒内未返回结果', {
            timeout: '30秒',
            suggestion: '可能是定位权限、GPS信号、网络或Geocoder服务问题'
          });
        }, 30000);
        
        this.locationPlugin.getLocationWithAddress((rawResult) => {
          clearTimeout(timeout);
          
          console.log('=== 位置+地址解析结果 ===');
          console.log('原始结果:', rawResult);
          console.log('结果类型:', typeof rawResult);
          
          // 如果返回的是字符串，尝试解析为JSON
          let result = rawResult;
          if (typeof rawResult === 'string') {
            try {
              result = JSON.parse(rawResult);
              console.log('解析后的JSON:', result);
            } catch (parseError) {
              console.error('JSON解析失败:', parseError);
              result = { success: false, error: 'JSON解析失败', raw: rawResult };
            }
          }
          
          console.log('最终结果:', JSON.stringify(result, null, 2));
          if (result) {
            console.log('success字段:', result.success);
            console.log('code字段:', result.code);
            console.log('data字段:', result.data);
            console.log('address字段:', result.address);
            console.log('message字段:', result.message);
          }
          console.log('=== 位置+地址解析结束 ===');
          
          if (result) {
            const success = result.success === true;
            const hasData = result.data && typeof result.data === 'object';
            const hasAddress = result.address && typeof result.address === 'object';
            
            this.addResult(success, '位置+地址', 
              success ? '✅ getLocationWithAddress() 调用成功' : `⚠️ getLocationWithAddress() 返回: ${result.message || result.error}`, 
              result
            );
            
            // 如果有位置数据，单独显示
            if (hasData && result.data.latitude && result.data.longitude) {
              this.addResult(true, '位置数据', 
                `📍 坐标: ${result.data.latitude}, ${result.data.longitude}`, 
                result.data
              );
            }
            
            // 如果有地址数据，单独显示
            if (hasAddress) {
              const address = result.address;
              const fullAddress = address.formattedAddress || address.country + address.province + address.city;
              
              this.addResult(true, '地址解析', 
                `🏠 地址: ${fullAddress}`, 
                address
              );
              
              uni.showToast({
                title: this.$t('test.locationPlugin.toastAddressResolvedSuccess'),
                icon: 'success'
              });
            }
            
          } else {
            this.addResult(false, '位置+地址', '❌ getLocationWithAddress() 回调返回空结果', {
              result: result,
              type: typeof result
            });
          }
        });
        
      } catch (error) {
        console.error('位置+地址解析错误:', error);
        this.addResult(false, '位置+地址', `❌ getLocationWithAddress() 调用失败: ${error.message}`, {
          error: error.message,
          stack: error.stack
        });
      }
    },
    
    // 添加测试结果
    addResult(success, type, message, data = null) {
      const result = {
        time: new Date().toLocaleTimeString(),
        success,
        type,
        message,
        data
      };
      
      this.testResults.unshift(result);
      
      // 限制结果数量
      if (this.testResults.length > 20) {
        this.testResults.splice(20);
      }
    },
    
    // 检查插件可用方法
    checkAvailableMethods() {
      if (!this.locationPlugin) {
        this.addResult(false, '方法检查', '插件未加载');
        return;
      }
      
      this.addResult(false, '方法检查', '正在检查插件的可用方法...', 'info');
      
      try {
        // 获取插件对象的所有属性和方法
        const methods = [];
        const properties = [];
        
        for (const key in this.locationPlugin) {
          try {
            const value = this.locationPlugin[key];
            if (typeof value === 'function') {
              methods.push(key);
            } else {
              properties.push({
                name: key,
                type: typeof value,
                value: value
              });
            }
          } catch (e) {
            // 忽略无法访问的属性
          }
        }
        
        // 检查原型链上的方法
        let prototype = Object.getPrototypeOf(this.locationPlugin);
        const prototypeMethods = [];
        
        while (prototype && prototype !== Object.prototype) {
          const propNames = Object.getOwnPropertyNames(prototype);
          for (const propName of propNames) {
            if (propName !== 'constructor' && typeof prototype[propName] === 'function') {
              if (!prototypeMethods.includes(propName)) {
                prototypeMethods.push(propName);
              }
            }
          }
          prototype = Object.getPrototypeOf(prototype);
        }
        
        const pluginInfo = {
          type: typeof this.locationPlugin,
          constructor: this.locationPlugin.constructor?.name || 'Unknown',
          methods: methods,
          prototypeMethods: prototypeMethods,
          properties: properties,
          toString: this.locationPlugin.toString()
        };
        
        this.addResult(true, '方法检查', '插件信息获取成功', pluginInfo);
        
        // 详细日志
        if (methods.length > 0) {
          this.addResult(true, '可用方法', `发现 ${methods.length} 个直接方法: ${methods.join(', ')}`, 'success');
        } else {
          this.addResult(false, '可用方法', '未发现直接可用方法', 'warning');
        }
        
        if (prototypeMethods.length > 0) {
          this.addResult(true, '原型方法', `发现 ${prototypeMethods.length} 个原型方法: ${prototypeMethods.join(', ')}`, 'info');
        }
        
        if (properties.length > 0) {
          this.addResult(true, '属性信息', `发现 ${properties.length} 个属性`, 'info');
          properties.forEach(prop => {
            this.addResult(false, '属性', `${prop.name}: ${prop.type} = ${prop.value}`, 'info');
          });
        }
        
      } catch (error) {
        this.addResult(false, '方法检查', `检查失败: ${error.message}`, 'error');
      }
    },
    
    // 清空结果
    clearResults() {
      this.testResults = [];
    }
  }
}
</script>

<style>
.location-test-page {
  padding: 20rpx;
  background-color: #f5f5f5;
  min-height: 100vh;
}

.header {
  text-align: center;
  margin-bottom: 40rpx;
  padding: 40rpx 20rpx;
  background-color: #fff;
  border-radius: 16rpx;
}

.title {
  font-size: 36rpx;
  font-weight: bold;
  color: #333;
  display: block;
  margin-bottom: 10rpx;
}

.subtitle {
  font-size: 26rpx;
  color: #666;
  display: block;
}

.test-section {
  margin-bottom: 40rpx;
}

.status-card {
  padding: 30rpx;
  margin-bottom: 30rpx;
  border-radius: 16rpx;
  text-align: center;
}

.status-pending {
  background-color: #fff;
  border: 2rpx solid #ddd;
}

.status-success {
  background-color: #f0f9ff;
  border: 2rpx solid #4cd964;
}

.status-error {
  background-color: #fef2f2;
  border: 2rpx solid #ff3b30;
}

.status-text {
  font-size: 32rpx;
  font-weight: bold;
  display: block;
  margin-bottom: 10rpx;
}

.status-success .status-text {
  color: #4cd964;
}

.status-error .status-text {
  color: #ff3b30;
}

.status-desc {
  font-size: 26rpx;
  color: #666;
  display: block;
}

.button-group {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.test-btn {
  height: 80rpx;
  border-radius: 12rpx;
  font-size: 28rpx;
  background-color: #f5f5f5;
  color: #666;
}

.test-btn.primary {
  background-color: #007aff;
  color: white;
}

.test-btn.success {
  background-color: #4cd964;
  color: white;
}

.test-btn.info {
  background-color: #17a2b8;
  color: white;
}

.test-btn.warning {
  background-color: #ff9500;
  color: white;
  font-weight: bold;
}

.result-section {
  background-color: #fff;
  border-radius: 16rpx;
  padding: 30rpx;
  margin-bottom: 40rpx;
}

.section-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
  display: block;
  margin-bottom: 20rpx;
}

.results-list {
  max-height: 600rpx;
  margin-bottom: 20rpx;
}

.result-item {
  padding: 20rpx;
  margin-bottom: 20rpx;
  background-color: #f8f8f8;
  border-radius: 12rpx;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10rpx;
}

.result-time {
  font-size: 24rpx;
  color: #999;
}

.result-status {
  font-size: 24rpx;
  font-weight: bold;
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
}

.result-status.success {
  background-color: #4cd964;
  color: white;
}

.result-status.error {
  background-color: #ff3b30;
  color: white;
}

.result-message {
  font-size: 26rpx;
  color: #333;
  margin-bottom: 10rpx;
  display: block;
}

.result-data {
  background-color: #f0f0f0;
  padding: 20rpx;
  border-radius: 8rpx;
}

.data-text {
  font-size: 22rpx;
  font-family: monospace;
  color: #666;
  word-break: break-all;
}

.clear-btn {
  background-color: #ff3b30;
  color: white;
  border-radius: 12rpx;
  height: 60rpx;
  font-size: 26rpx;
}

.integration-info {
  background-color: #fff;
  border-radius: 16rpx;
  padding: 30rpx;
}

.info-title {
  font-size: 30rpx;
  font-weight: bold;
  color: #333;
  display: block;
  margin-bottom: 20rpx;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15rpx 0;
  border-bottom: 1rpx solid #f0f0f0;
}

.info-item:last-child {
  border-bottom: none;
}

.info-label {
  font-size: 26rpx;
  color: #666;
}

.info-value {
  font-size: 26rpx;
  color: #4cd964;
  font-weight: bold;
}
</style>
