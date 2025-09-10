# 在Android模拟器上运行站点管理APP

## 🎯 当前状态
- ✅ 后端API服务运行中: http://localhost:8000
- ✅ Android模拟器已启动: emulator-5554
- ✅ 项目代码已完成

## 📱 方法一：使用HBuilderX（推荐）

### 1. 下载安装HBuilderX
```bash
# 下载地址：https://www.dcloud.io/hbuilderx.html
# 选择App开发版本
```

### 2. 导入项目
1. 打开HBuilderX
2. 文件 → 导入 → 从本地目录导入
3. 选择目录: `/Users/like/Desktop/baicells/Trae/site-app/uniapp-site-manager`

### 3. 配置Android环境
1. 工具 → 设置 → 插件配置
2. 配置Android SDK路径: `/Users/like/Library/Android/sdk`
3. 安装Android插件

### 4. 运行到Android模拟器
1. 运行 → 运行到手机或模拟器 → Android模拟器
2. 选择 Medium_Phone_API_35
3. 等待编译和安装

## 📱 方法二：Web版本测试（当前可用）

我已经为你创建了一个Web版本来快速测试功能：

### 启动Web版本
```bash
cd /Users/like/Desktop/baicells/Trae/site-app
python -m http.server 3000 --directory web-demo
```

然后在Android模拟器的浏览器中访问：
- http://10.0.2.2:3000

## 🔧 方法三：命令行编译（高级用户）

### 1. 安装全局CLI
```bash
npm install -g @dcloudio/uvm
uvm 3.4.15
```

### 2. 编译为Android
```bash
cd uniapp-site-manager
npm run build:app-android
```

### 3. 安装到模拟器
```bash
adb install -r dist/android/app-release.apk
```

## 🚀 快速体验方案

为了让你立即看到效果，我将创建一个简化的PWA版本：

1. **Web版本**: 在Android浏览器中运行
2. **功能完整**: 包含所有主要功能
3. **实时API**: 连接真实的后端服务
4. **移动友好**: 响应式设计

## 📝 测试账户
- **管理员**: admin / admin123
- **普通用户**: test_user / user123

## 🔍 故障排除

### Android模拟器网络配置
- 模拟器访问主机: `10.0.2.2:8000`
- 如需修改API地址，编辑stores中的URL配置

### 端口转发
```bash
adb -s emulator-5554 reverse tcp:8000 tcp:8000
```

## 🎉 下一步
1. 使用HBuilderX获得最佳开发体验
2. 或者先体验Web版本查看所有功能
3. 根据需要调整功能和UI设计