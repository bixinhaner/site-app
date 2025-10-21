# 导航栏样式规范

## 统一样式标准

所有自定义导航栏应遵循以下统一规范，确保应用界面的一致性和专业性。

### 1. 容器样式 (.custom-navbar)

```css
.custom-navbar {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  padding: 44rpx 30rpx 20rpx;
  color: #fff;
}
```

**说明:**
- **背景**: 使用渐变橙色主题 (primary color)
- **内边距**: 顶部 44rpx (状态栏高度), 左右 30rpx, 底部 20rpx
- **文字颜色**: 白色 (#fff)

### 2. 内容区域 (.navbar-content)

```css
.navbar-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 88rpx;
}
```

**说明:**
- **布局**: Flexbox 水平布局
- **高度**: 88rpx (≥44px，符合触控规范)
- **对齐**: 垂直居中，两端对齐

### 3. 标题样式 (.navbar-title)

```css
.navbar-title {
  font-size: 36rpx;
  font-weight: bold;
  color: white;
  text-align: center;
  flex: 1;
}
```

**说明:**
- **字体大小**: 36rpx (统一大小)
- **字体粗细**: bold (加粗)
- **颜色**: white (白色)
- **文本对齐**: 居中
- **弹性布局**: flex: 1 (占据剩余空间)

### 4. 返回按钮 (.back-button)

```css
.back-button {
  width: 88rpx;
  height: 88rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 44rpx;
  background: rgba(255, 255, 255, 0.2);
}
```

**说明:**
- **尺寸**: 88rpx × 88rpx (≥44px，符合触控规范)
- **形状**: 圆形 (border-radius: 44rpx)
- **背景**: 半透明白色 (20% 不透明度)

### 5. 图标样式 (.back-icon, .save-icon, .share-icon)

```css
.back-icon {
  font-size: 36rpx;
  color: white;
  font-weight: bold;
}
```

**说明:**
- **字体大小**: 36rpx (统一图标大小)
- **颜色**: white (白色)
- **字体粗细**: bold (加粗)

### 6. 右侧操作区域 (.navbar-actions / .navbar-right)

```css
.navbar-actions {
  width: 88rpx;
  display: flex;
  justify-content: flex-end;
}
```

**说明:**
- **宽度**: 88rpx (与返回按钮对称)
- **对齐**: 右对齐

## 已统一的页面清单

✅ **pages/home/home.vue** - 首页
✅ **pages/workorder/list.vue** - 工单列表
✅ **pages/workorder/detail.vue** - 工单详情
✅ **pages/inspection/detail.vue** - 检查详情
✅ **pages/inspection/checklist.vue** - 检查清单
✅ **pages/inspection/site-select.vue** - 站点选择
✅ **pages/inspection/review.vue** - 检查审核
✅ **pages/site/list.vue** - 站点列表
✅ **pages/site/detail.vue** - 站点详情

## 可复用组件

已创建统一的导航栏组件: `components/CustomNavbar.vue`

### 使用示例

```vue
<template>
  <view class="page-container">
    <CustomNavbar 
      title="页面标题" 
      :showBack="true"
      @back="handleBack"
    >
      <template #right>
        <view class="nav-button" @click="handleAction">
          <text class="nav-icon">💾</text>
        </view>
      </template>
    </CustomNavbar>
    
    <!-- 页面内容 -->
  </view>
</template>

<script setup>
import CustomNavbar from '@/components/CustomNavbar.vue'

const handleBack = () => {
  uni.navigateBack()
}

const handleAction = () => {
  // 自定义操作
}
</script>
```

## 注意事项

1. **单位统一**: 使用 `rpx` 而非 `px`，确保跨设备适配
2. **字体大小**: 标题统一 36rpx，图标统一 36rpx
3. **按钮尺寸**: 最小 88rpx × 88rpx (≥44px 触控标准)
4. **颜色一致**: 使用 CSS 变量 `var(--color-primary)` 保持主题一致
5. **padding统一**: 44rpx 30rpx 20rpx (顶部考虑状态栏高度)

## 设计令牌参考

```css
--color-primary: #f97316;        /* 主色调-橙色 */
--color-primary-light: #fb923c;  /* 主色调-浅橙色 */
--navbar-height: 88rpx;          /* 导航栏内容高度 */
--navbar-padding-top: 44rpx;     /* 导航栏顶部内边距 */
--navbar-padding-horizontal: 30rpx;  /* 导航栏水平内边距 */
--navbar-padding-bottom: 20rpx;  /* 导航栏底部内边距 */
--button-size: 88rpx;            /* 按钮标准尺寸 */
--icon-size: 36rpx;              /* 图标标准尺寸 */
--title-size: 36rpx;             /* 标题标准字体大小 */
```

## 无导航栏页面

以下页面采用完全自定义设计，不显示导航栏：
- **pages/profile/profile.vue** - 个人中心（Tab Bar 页面，使用全屏头部设计）

## 测试页面（保留原生导航栏）

以下测试页面保留原生导航栏配置，不影响主要业务流程：
- pages/test-location-plugin/test-location-plugin
- pages/test-location-builtin/test-location-builtin
- pages/stock/scan-pickup
- pages/test/logging-test

## 更新日期

最后更新: 2025-01-21
