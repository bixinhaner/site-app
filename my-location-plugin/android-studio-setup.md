# Android Studio 编译设置指南

## 方法一：直接在 Android Studio 中操作（推荐）

### 1. 创建新项目
1. 打开 Android Studio
2. 选择 "Start a new Android Studio project"
3. 选择 "Empty Activity"
4. 项目配置：
   - **Name**: LocationPluginBuilder
   - **Package name**: com.example.builder
   - **Save location**: 任意目录
   - **Minimum SDK**: API 21
   - 点击 Finish

### 2. 添加 Library 模块
1. 右键点击项目根目录
2. 选择 `New` → `Module...`
3. 选择 `Android Library`
4. 模块配置：
   - **Application/Library name**: location-plugin
   - **Module name**: location-plugin  
   - **Package name**: com.example.location
   - **Minimum SDK**: API 21
   - 点击 Finish

### 3. 配置模块文件

#### 3.1 复制 build.gradle 内容
将我们提供的 `android/build.gradle` 内容复制到：
`location-plugin/build.gradle`

#### 3.2 复制 AndroidManifest.xml
将我们的 `android/AndroidManifest.xml` 复制到：
`location-plugin/src/main/AndroidManifest.xml`

#### 3.3 复制 Java 源码
1. 在 `location-plugin/src/main/java/` 下创建目录结构：
   `com/example/location/`
2. 将我们的 `LocationPlugin.java` 复制到：
   `location-plugin/src/main/java/com/example/location/LocationPlugin.java`

### 4. 添加 UniApp 依赖库

由于 UniApp 的依赖库不在公共仓库中，需要手动下载：

#### 4.1 下载 UniApp SDK
1. 访问 HBuilderX 官网下载 UniApp SDK
2. 或从现有的 UniApp 项目中获取相关 jar 包

#### 4.2 创建 libs 目录
在 `location-plugin/libs/` 目录下放置以下文件：
- `uniapp-debug.jar` 或 `uniapp-release.jar`
- `fastjson-x.x.x.jar`

#### 4.3 修改 build.gradle 依赖
```gradle
dependencies {
    // 使用本地 jar 文件
    implementation fileTree(dir: 'libs', include: ['*.jar'])
    implementation files('libs/uniapp-debug.jar')
    implementation files('libs/fastjson-1.2.83.jar')
    
    // 其他依赖保持不变
    implementation 'androidx.appcompat:appcompat:1.6.1'
    implementation 'com.google.android.material:material:1.10.0'
}
```

### 5. 编译生成 AAR
1. 在 Android Studio 中点击 `Build` → `Make Project`
2. 或在终端运行：`./gradlew :location-plugin:build`
3. 生成的 AAR 文件位置：
   `location-plugin/build/outputs/aar/location-plugin-debug.aar`
   `location-plugin/build/outputs/aar/location-plugin-release.aar`

## 方法二：使用我们提供的文件结构

### 1. 创建完整的 Android Studio 项目

创建以下项目结构：
```
LocationPluginBuilder/
├── settings.gradle                 # 项目设置
├── build.gradle                   # 根级构建文件
├── gradle.properties             # Gradle 属性
├── local.properties              # 本地 SDK 路径
└── location-plugin/              # Library 模块
    ├── build.gradle              # 模块构建文件
    ├── proguard-rules.pro        # 混淆规则
    ├── consumer-rules.pro        # 消费者混淆规则
    └── src/main/
        ├── AndroidManifest.xml   # 模块清单文件
        └── java/com/example/location/
            └── LocationPlugin.java
```

### 2. 项目级配置文件

#### settings.gradle
```gradle
pluginManagement {
    repositories {
        gradlePluginPortal()
        google()
        mavenCentral()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "LocationPluginBuilder"
include ':location-plugin'
```

#### 根级 build.gradle
```gradle
plugins {
    id 'com.android.application' version '8.1.2' apply false
    id 'com.android.library' version '8.1.2' apply false
}
```

#### gradle.properties
```properties
# Project-wide Gradle settings.
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
org.gradle.parallel=true
android.useAndroidX=true
android.enableJetifier=true
```

#### local.properties
```properties
# 需要设置为您本机的 Android SDK 路径
sdk.dir=/Users/YourName/Library/Android/sdk
```

## 编译命令

### 使用 Gradle 命令行编译：
```bash
# 进入项目目录
cd LocationPluginBuilder

# 编译 debug 版本
./gradlew :location-plugin:assembleDebug

# 编译 release 版本  
./gradlew :location-plugin:assembleRelease

# 清理并重新编译
./gradlew clean :location-plugin:build
```

### 输出文件位置：
- Debug AAR: `location-plugin/build/outputs/aar/location-plugin-debug.aar`
- Release AAR: `location-plugin/build/outputs/aar/location-plugin-release.aar`

## 常见问题解决

### 1. UniApp 依赖找不到
- 确保正确下载了 UniApp SDK
- 检查 libs 目录中的 jar 文件
- 验证 build.gradle 中的依赖路径

### 2. 编译失败
- 检查 Android SDK 版本
- 确认 compileSdk 和 targetSdk 版本匹配
- 检查包名是否正确

### 3. 权限相关错误
- 确保 AndroidManifest.xml 中包含所有必需权限
- 检查权限声明格式是否正确

## 下一步集成
编译成功后，将生成的 AAR 文件复制到 UniApp 项目的插件目录中使用。