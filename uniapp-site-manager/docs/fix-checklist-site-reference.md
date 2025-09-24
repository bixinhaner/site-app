# 修复检查列表页面站点引用问题

## 问题描述

在 `pages/inspection/checklist.vue` 页面中，增强水印功能使用了未定义的 `currentSite.value` 变量，导致以下错误：

```
ReferenceError: currentSite is not defined
```

## 问题原因

不同页面的站点信息存储方式不同：

- `camera.vue`: 使用 `currentSite.value?.site_name`
- `workorder/detail.vue`: 使用 `order.value?.site_name` 
- `checklist.vue`: 使用 `inspectionData.value?.site_name`

但在增强水印功能中，错误地在 checklist.vue 中使用了 `currentSite.value`。

## 解决方案

已修复 `pages/inspection/checklist.vue` 第753行：

**修复前：**
```javascript
siteName: currentSite.value?.site_name || '未知站点'
```

**修复后：**
```javascript
siteName: inspectionData.value?.site_name || '未知站点'
```

## 验证方法

1. 打开检查列表页面
2. 选择任一检查项进行拍照
3. 观察控制台日志，应该看到：
   ```
   使用增强GPS地址水印功能
   增强水印添加完成: [path]
   ```
   而不是：
   ```
   增强水印失败，使用原方案: ReferenceError: currentSite is not defined
   ```

## 影响范围

- ✅ 修复后，所有页面的增强水印功能都能正常工作
- ✅ 水印将正确显示详细地址信息
- ✅ 不影响现有的兜底功能

## 测试建议

建议在以下页面测试水印功能：

1. **检查列表页面** (`/pages/inspection/checklist.vue`)
   - 选择检查项拍照
   - 确认显示详细地址

2. **拍照页面** (`/pages/inspection/camera.vue`) 
   - 直接拍照功能
   - 确认站点信息正确显示

3. **工单详情页面** (`/pages/workorder/detail.vue`)
   - 工单检查项拍照
   - 确认工单站点信息正确

现在所有页面的GPS地址水印功能都应该正常工作了！🎉