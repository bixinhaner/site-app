<template>
  <view class="detail-container">
    <view class="custom-navbar">
      <view class="navbar-content">
        <text class="navbar-title">{{ $t('workorder.detail') }}</text>
      </view>
    </view>

    <view v-if="order" class="content">
      <view class="card">
        <view class="row"><text class="label">{{ $t('workorder.title') }}</text><text class="value">{{ order.title }}</text></view>
        <view class="row"><text class="label">{{ $t('site.name') }}</text><text class="value">{{ order.site_name || order.site_id }}</text></view>
        <view class="row"><text class="label">{{ $t('workorder.status') }}</text><text class="value status" :class="'status-'+order.status">{{ statusText(order.status) }}</text></view>
        <view class="row"><text class="label">{{ $t('workorder.assignedAt') }}</text><text class="value">{{ formatDateTime(order.assigned_at) }}</text></view>
      </view>

      <view class="card">
        <view class="section-title">{{ $t('inspection.checklist') }}</view>
        <view class="item" v-for="it in items" :key="it.id">
          <view class="item-header">
            <text class="name">{{ it.item_name }}</text>
            <view class="status-group">
              <text class="istatus" :class="'istatus-'+it.status">{{ itemStatusText(it.status) }}</text>
              <text v-if="it.review_status" class="review-status" :class="'review-'+it.review_status">
                {{ reviewStatusText(it.review_status) }}
              </text>
            </view>
          </view>
          <view class="meta">{{ it.category_name }}</view>
          <view v-if="it.review_comments" class="review-comments">
            <text class="comments-label">{{ $t('inspection.reviewComments') }}:</text>
            <text class="comments-text">{{ it.review_comments }}</text>
          </view>
          <view class="photos" v-if="itemPhotos(it).length">
            <scroll-view class="photo-scroll" scroll-x>
              <view class="p-item" v-for="p in itemPhotos(it)" :key="p.id" @click="previewPhoto(p)" @longpress="deletePhoto(p)">
                <image class="thumb" :src="p.file_path" mode="aspectFill" />
                <view class="delete-tip">{{ $t('common.longPressDelete') }}</view>
              </view>
            </scroll-view>
          </view>
          <view class="item-actions">
            <button class="mini" size="mini" @click.stop="chooseAndUpload(it)">{{ $t('common.uploadPhoto') }}</button>
            <button class="mini" size="mini" @click.stop="openEdit(it)">{{ $t('inspection.fillReport') }}</button>
          </view>
        </view>
      </view>

      <view class="bottom-actions" v-if="order.status === 'ACTIVE' || order.status === 'REJECTED' || order.status === 'SUBMITTED' || order.status === 'UNDER_REVIEW'">
        <button 
          class="action-btn" 
          @click="completeWorkOrder"
          v-if="order.status === 'ACTIVE'"
        >{{ $t('workorder.complete') }}</button>
        <button 
          class="action-btn rejected" 
          @click="openEdit(null)"
          v-if="order.status === 'REJECTED'"
        >{{ $t('workorder.modify') }}</button>
        <button 
          class="action-btn warning" 
          @click="handleRecall"
          v-if="(order.status === 'SUBMITTED' || order.status === 'UNDER_REVIEW') && canRecall"
        >撤回</button>
      </view>
    </view>

    <!-- 填报弹层 -->
    <view class="overlay" v-if="editVisible" @click="closeEdit">
      <view class="edit-panel" @click.stop>
        <view class="panel-title">{{ $t('inspection.fillInspectionItem') }}</view>
        <!-- 动态字段渲染 -->
        <view class="form-row" v-for="f in fieldDefs" :key="f.field_id || f.label">
          <text class="label">{{ f.label || f.field_id }}</text>
          <block v-if="f.type==='text' || f.type==='rich_text'">
            <textarea class="textarea" v-model="fieldValues[f.field_id || f.label]" :placeholder="$t('common.pleaseEnter') + ' ' + (f.label||'')" />
          </block>
          <block v-else-if="f.type==='number'">
            <input class="input" type="number" v-model.number="fieldValues[f.field_id || f.label]" :placeholder="$t('common.pleaseEnter') + ' ' + (f.label||'')" />
          </block>
          <block v-else-if="f.type==='boolean'">
            <switch :checked="fieldValues[f.field_id || f.label]===true" @change="e=> fieldValues[f.field_id || f.label] = e.detail.value" />
          </block>
          <block v-else-if="f.type==='select_single'">
            <picker :range="(f.options||[]).map(o=>o.label||o)" @change="e=> fieldValues[f.field_id || f.label] = (f.options||[])[e.detail.value].value || (f.options||[])[e.detail.value]">
              <view class="picker">
                {{ (f.options||[]).find(o => (o.value||o) === fieldValues[f.field_id || f.label])?.label || $t('common.pleaseSelect') }}
              </view>
            </picker>
          </block>
          <block v-else-if="f.type==='select_multi'">
            <checkbox-group @change="e=> fieldValues[f.field_id || f.label] = e.detail.value">
              <label class="chk" v-for="opt in (f.options||[])" :key="opt.value||opt">
                <checkbox :value="opt.value||opt" :checked="(fieldValues[f.field_id || f.label]||[]).includes(opt.value||opt)" /> {{ opt.label||opt }}
              </label>
            </checkbox-group>
          </block>
          <block v-else>
            <textarea class="textarea" v-model="fieldValues[f.field_id || f.label]" :placeholder="$t('common.pleaseEnter')" />
          </block>
        </view>
        <view class="form-row">
          <text class="label">{{ $t('common.status') }}</text>
          <view class="radio-row">
            <label class="radio"><radio value="completed" :checked="editStatus==='completed'" @click="setStatus('completed')" /> {{ $t('inspection.completed') }}</label>
            <label class="radio"><radio value="in_progress" :checked="editStatus==='in_progress'" @click="setStatus('in_progress')" /> {{ $t('inspection.inProgress') }}</label>
            <label class="radio"><radio value="failed" :checked="editStatus==='failed'" @click="setStatus('failed')" /> {{ $t('inspection.failed') }}</label>
          </view>
        </view>
        <view class="panel-actions">
          <button class="btn cancel" @click="closeEdit">{{ $t('common.cancel') }}</button>
          <button class="btn save" @click="saveEdit">{{ $t('common.save') }}</button>
        </view>
      </view>
    </view>
    
    <!-- 隐藏的canvas用于水印处理 -->
    <canvas 
      :canvas-id="'watermark-canvas-' + Date.now()" 
      style="position: fixed; top: -9999px; left: -9999px; width: 1px; height: 1px;"
    ></canvas>
  </view>
</template>

<script setup>
import { ref, getCurrentInstance, computed } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { useWorkOrderStore } from '@/stores/workorder'
import { useUserStore } from '@/stores/user'

const { $t } = getCurrentInstance().appContext.config.globalProperties
const store = useWorkOrderStore()
const userStore = useUserStore()
const order = ref(null)
const items = ref([])
const photos = ref([])
const orderId = ref(null)
const isPageVisible = ref(false)

// 编辑弹窗（动态字段）
const editVisible = ref(false)
const editItemObj = ref(null)
const editStatus = ref('completed')
const fieldDefs = ref([])
const fieldValues = ref({})

const load = async () => {
  const id = orderId.value
  if (!id) return
  
  try {
    console.log('🔄 工单详情页面加载中...', { orderId: id })
    
    // 并行加载所有数据
    const [orderRes, itemsRes, photosRes] = await Promise.all([
      store.getWorkOrder(id),
      store.getItems(id),
      store.getPhotos(id)
    ])
    
    if (orderRes.success) {
      order.value = orderRes.data
      console.log('✅ 工单详情加载成功')
    } else {
      console.error('❌ 工单详情加载失败', orderRes.error)
    }
    
    if (itemsRes.success) {
      items.value = itemsRes.data
      console.log('✅ 工单检查项加载成功', { count: itemsRes.data?.length })
    } else {
      console.error('❌ 工单检查项加载失败', itemsRes.error)
    }
    
    if (photosRes.success) {
      photos.value = photosRes.data
      console.log('✅ 工单照片加载成功', { count: photosRes.data?.length })
    } else {
      console.error('❌ 工单照片加载失败', photosRes.error)
    }
    
  } catch (error) {
    console.error('❌ 工单详情加载异常', error)
    uni.showToast({ title: $t('messages.loadFailed'), icon: 'none' })
  }
}

const completeWorkOrder = async () => {
  const id = orderId.value
  try {
    uni.showLoading({ title: $t('messages.completing') })
    const res = await store.completeWorkOrder(id)
    if (res.success) {
      order.value = res.data.work_order || res.data
      uni.showToast({ title: $t('messages.workOrderCompleted'), icon: 'success' })
    } else {
      uni.showToast({ title: res.error || $t('messages.operationFailed'), icon: 'error' })
    }
  } catch (e) {
    uni.showToast({ title: $t('messages.operationFailed'), icon: 'error' })
  } finally {
    uni.hideLoading()
  }
}

const statusText = (s) => ({
  PENDING: $t('workorder.pending'), 
  ACTIVE: $t('workorder.inProgress'), 
  SUBMITTED: $t('workorder.submitted'), 
  UNDER_REVIEW: $t('workorder.underReview'), 
  APPROVED: $t('workorder.approved'), 
  REJECTED: $t('workorder.rejected'), 
  COMPLETED: $t('workorder.completed')
})[s] || s
const itemStatusText = (s) => ({ pending: $t('inspection.pending'), in_progress: $t('inspection.inProgress'), completed: $t('inspection.completed'), failed: $t('inspection.failed') })[s] || s
const reviewStatusText = (s) => ({ pass: '✅ ' + $t('inspection.passed'), fail: '❌ ' + $t('inspection.failed'), warning: '⚠️ ' + $t('inspection.warning') })[s] || s
const formatDateTime = (val) => {
  if (!val) return '-'
  const locale = getCurrentInstance().appContext.config.globalProperties.$language?.currentLocale || 'zh'
  return new Date(val).toLocaleString(locale === 'zh' ? 'zh-CN' : 'en-US')
}

const itemPhotos = (it) => (photos.value || []).filter(p => p.item_id === it.id)

const previewPhoto = (p) => {
  const urls = itemPhotos({ id: p.item_id }).map(x => x.file_path)
  const current = urls.indexOf(p.file_path)
  uni.previewImage({ urls, current: current >= 0 ? current : 0 })
}

const canRecall = computed(() => {
  try { return !!order.value && order.value.assigned_to === userStore.userInfo?.id } catch { return false }
})

const handleRecall = async () => {
  try {
    await new Promise((resolve, reject) => {
      uni.showModal({ title: '确认撤回', content: '确认撤回本次提交？撤回后可继续编辑。', success: (res)=> res.confirm?resolve():reject('cancel') })
    })
  } catch { return }
  try {
    uni.showLoading({ title: '撤回中...' })
    const res = await store.recallWorkOrder(orderId.value)
    if (res.success) {
      uni.showToast({ title: '已撤回，可继续编辑', icon: 'success' })
      const inspectionId = res.data?.work_order?.inspection_id || order.value?.inspection_id
      if (inspectionId) {
        uni.navigateTo({ url: `/pages/inspection/detail?id=${inspectionId}&fromWorkOrder=${orderId.value}` })
      }
    } else {
      uni.showToast({ title: res.error || '撤回失败', icon: 'none' })
    }
  } catch (e) {
    uni.showToast({ title: '撤回失败', icon: 'none' })
  } finally {
    uni.hideLoading()
  }
}

const chooseAndUpload = async (it) => {
  try {
    // 检查该检查项是否已有照片，如果有则限制只能上传1张
    const existingPhotos = itemPhotos(it)
    if (existingPhotos.length >= 1) {
      uni.showModal({
        title: $t('common.hint'),
        content: $t('messages.onlyOnePhotoAllowed'),
        showCancel: false
      })
      return
    }
    
    // 显示选择方式
    const actionResult = await new Promise((resolve) => {
      uni.showActionSheet({
        itemList: [$t('common.takePhoto'), $t('common.selectFromAlbum')],
        success: (res) => {
          resolve(res.tapIndex)
        },
        fail: () => {
          resolve(-1) // 取消
        }
      })
    })
    
    if (actionResult === -1) return // 用户取消
    
    let tempFilePaths = []
    
    if (actionResult === 0) {
      // 拍照
      const cameraResult = await new Promise((resolve, reject) => {
        uni.chooseImage({ 
          count: 1, 
          sourceType: ['camera'],
          success: resolve, 
          fail: reject 
        })
      })
      tempFilePaths = cameraResult.tempFilePaths || []
    } else {
      // 从相册选择
      const albumResult = await new Promise((resolve, reject) => {
        uni.chooseImage({ 
          count: 3, 
          sourceType: ['album'],
          success: resolve, 
          fail: reject 
        })
      })
      tempFilePaths = albumResult.tempFilePaths || []
    }
    
    if (tempFilePaths.length === 0) return
    
    // 获取高精度GPS定位
    const gpsData = await getHighAccuracyGPS()
    
    // 处理每张照片
    for (const imagePath of tempFilePaths) {
      try {
        let finalImagePath = imagePath
        
        // 如果是拍照，添加水印
        if (actionResult === 0) {
          finalImagePath = await addWatermarkToImage(imagePath, it, gpsData)
        }
        
        // 上传照片
        await store.uploadPhoto(orderId.value, finalImagePath, {
          item_id: it.id,
          gps_latitude: gpsData?.latitude || 0,
          gps_longitude: gpsData?.longitude || 0,
          gps_accuracy: gpsData?.accuracy || undefined,
          has_watermark: actionResult === 0 // 拍照的有水印
        })
      } catch (photoError) {
        console.error('处理照片失败:', photoError)
        uni.showToast({ title: $t('messages.photoProcessFailed'), icon: 'error' })
      }
    }
    
    uni.showToast({ title: $t('messages.uploadCompleted'), icon: 'success' })
    
    // 刷新照片列表
    const c = await store.getPhotos(orderId.value)
    if (c.success) photos.value = c.data
    
  } catch (e) {
    console.error('上传失败:', e)
    uni.showToast({ title: $t('messages.uploadCancelled'), icon: 'none' })
  }
}

// 删除照片
const deletePhoto = async (photo) => {
  try {
    const confirmResult = await new Promise((resolve) => {
      uni.showModal({
        title: $t('messages.confirmDelete'),
        content: $t('messages.confirmDeletePhoto'),
        success: (res) => resolve(res.confirm),
        fail: () => resolve(false)
      })
    })
    
    if (!confirmResult) return
    
    // 调用后端删除接口
    await store.deletePhoto(photo.id)
    
    uni.showToast({ title: $t('messages.deleteSuccess'), icon: 'success' })
    
    // 刷新照片列表
    const c = await store.getPhotos(orderId.value)
    if (c.success) photos.value = c.data
    
  } catch (e) {
    console.error('删除失败:', e)
    uni.showToast({ title: $t('messages.deleteFailed'), icon: 'error' })
  }
}

// 使用原生插件获取高精度GPS定位
const getHighAccuracyGPS = async () => {
  try {
    console.log('开始通过原生插件获取GPS定位...')
    
    // 获取原生定位插件
    const locationPlugin = uni.requireNativePlugin('my-location-plugin')
    
    if (!locationPlugin) {
      throw new Error('原生定位插件未加载')
    }
    
    const gpsResult = await new Promise((resolve, reject) => {
      // 调用插件的异步定位方法
      locationPlugin.getLocationWithAddress((result) => {
        console.log('原生插件定位结果:', result)
        
        // 解析结果
        let parsedResult = result
        if (typeof result === 'string') {
          try {
            parsedResult = JSON.parse(result)
          } catch (parseError) {
            console.error('解析原生插件结果失败:', parseError)
            reject(new Error('解析原生插件结果失败'))
            return
          }
        }
        
        if (parsedResult && parsedResult.success && parsedResult.data) {
          const data = parsedResult.data
          const address = parsedResult.address
          
          // 转换为旧的格式，保持兼容性
          const compatibleResult = {
            latitude: data.latitude,
            longitude: data.longitude,
            accuracy: data.accuracy || 0,
            altitude: data.altitude || 0,
            address: address,
            provider: 'native-plugin'
          }
          
          resolve(compatibleResult)
        } else {
          reject(new Error(parsedResult?.message || '原生插件定位失败'))
        }
      })
    })
    
    console.log('原生插件GPS定位成功:', gpsResult)
    
    // 检查GPS精度
    if (gpsResult.accuracy > 20) {
      uni.showToast({
        title: $t('messages.lowGPSAccuracy', {accuracy: gpsResult.accuracy}),
        icon: 'none',
        duration: 2000
      })
    }
    
    return gpsResult
  } catch (error) {
    console.error('原生插件GPS定位失败:', error)
    uni.showToast({
      title: $t('messages.nativePluginLocationFailed'),
      icon: 'error'
    })
    return null
  }
}

// 为照片添加水印
const addWatermarkToImage = async (imagePath, checkItem, gpsData) => {
  try {
    console.log('开始添加GPS地址水印:', { imagePath, checkItem: checkItem.item_name })
    
    uni.showLoading({
      title: $t('messages.addingGPSWatermark'),
      mask: true
    })
    
    // 导入增强水印工具
    const { watermarkTool } = await import('@/utils/watermark.js')
    
    // 获取图片信息并设置canvas
    const imageInfo = await new Promise((resolve, reject) => {
      uni.getImageInfo({
        src: imagePath,
        success: resolve,
        fail: reject
      })
    })
    
    const canvasId = 'watermark-canvas-' + Date.now()
    
    console.log('设置WorkOrder页面Canvas:', {
      canvasId: canvasId,
      width: imageInfo.width,
      height: imageInfo.height
    })
    
    // 使用新的增强水印功能
    const watermarkedPath = await watermarkTool.addWatermarkWithGPS(imagePath, {
      inspector: userInfo.value?.username || '未知检查员',
      checkItem: checkItem.item_name || '检查项目',
      siteName: order.value?.site_name || '未知站点'
    }, {
      showAddressDetails: true,  // 显示详细地址信息
      showPOI: false,           // 不显示POI信息
      canvasId: canvasId        // 使用生成的canvasId
    })
    
    console.log('GPS地址水印添加完成:', watermarkedPath)
    return watermarkedPath
    
  } catch (error) {
    console.error('增强水印添加失败，尝试原方案:', error)
    
    try {
      // 获取图片信息
      const imageInfo = await new Promise((resolve, reject) => {
        uni.getImageInfo({
          src: imagePath,
          success: resolve,
          fail: reject
        })
      })
      
      console.log('图片信息:', imageInfo)
      
      // 创建canvas进行水印处理（兜底方案）
      const canvasId = 'watermark-canvas-' + Date.now()
      const watermarkedPath = await processImageWithWatermark(imagePath, imageInfo, checkItem, gpsData, canvasId)
      
      console.log('兜底水印添加完成:', watermarkedPath)
      return watermarkedPath
      
    } catch (fallbackError) {
      console.error('兜底水印方案也失败:', fallbackError)
      uni.showToast({
        title: $t('messages.watermarkFailedUsingOriginal'),
        icon: 'none'
      })
      return imagePath
    }
  } finally {
    uni.hideLoading()
  }
}

// 使用canvas处理图片水印
const processImageWithWatermark = async (imagePath, imageInfo, checkItem, gpsData, canvasId) => {
  return new Promise((resolve, reject) => {
    const ctx = uni.createCanvasContext(canvasId)
    
    // 绘制原始图片
    ctx.drawImage(imagePath, 0, 0, imageInfo.width, imageInfo.height)
    
    // 准备水印文本
    const watermarkLines = [
      gpsData ? `📍 ${gpsData.latitude.toFixed(6)}, ${gpsData.longitude.toFixed(6)}` : `📍 ${$t('messages.gpsNotObtained')}`,
      gpsData?.accuracy ? `📊 ${$t('messages.accuracy')}: ${gpsData.accuracy.toFixed(1)}m` : '',
      `🕐 ${new Date().toLocaleString(getCurrentInstance().appContext.config.globalProperties.$language?.currentLocale === 'zh' ? 'zh-CN' : 'en-US')}`,
      `👤 ${user.value?.username || $t('common.inspector')}`,
      `📋 ${checkItem.item_name}`,
      `🏗️ ${order.value?.site_name || order.value?.site_id || $t('common.workOrderSite')}`
    ].filter(Boolean)
    
    // 绘制水印
    drawWatermarkOnCanvas(ctx, watermarkLines, imageInfo)
    
    // 渲染并保存
    ctx.draw(true, () => {
      uni.canvasToTempFilePath({
        canvasId: canvasId,
        destWidth: imageInfo.width,
        destHeight: imageInfo.height,
        quality: 0.9,
        fileType: 'jpg',
        success: (res) => {
          resolve(res.tempFilePath)
        },
        fail: (error) => {
          reject(new Error('保存canvas失败: ' + error.errMsg))
        }
      })
    })
  })
}

// 在canvas上绘制水印
const drawWatermarkOnCanvas = (ctx, lines, imageInfo) => {
  const fontSize = 28
  const padding = 15
  const margin = 20
  const lineHeight = 35
  const backgroundColor = 'rgba(0, 0, 0, 0.7)'
  const textColor = '#FF6600'
  
  // 计算水印尺寸
  ctx.setFontSize(fontSize)
  let maxWidth = 0
  lines.forEach(line => {
    const width = ctx.measureText(line).width
    maxWidth = Math.max(maxWidth, width)
  })
  
  const watermarkWidth = maxWidth + padding * 2
  const watermarkHeight = lines.length * lineHeight + padding * 2
  
  // 计算水印位置（左下角）
  const x = margin
  const y = imageInfo.height - watermarkHeight - margin
  
  // 绘制背景
  ctx.setFillStyle(backgroundColor)
  ctx.fillRect(x, y, watermarkWidth, watermarkHeight)
  
  // 绘制文本
  ctx.setFillStyle(textColor)
  ctx.setFontSize(fontSize)
  ctx.setTextAlign('left')
  
  lines.forEach((line, index) => {
    const textX = x + padding
    const textY = y + padding + (index + 1) * lineHeight - 8
    ctx.fillText(line, textX, textY)
  })
}

const openEdit = async (it) => {
  editItemObj.value = it
  // 获取字段定义
  const schema = await store.getItemFieldSchema(orderId.value)
  if (schema.success) {
    const found = (schema.data || []).find(s => s.item_id === it.id)
    fieldDefs.value = found?.fields || [{ field_id:'note', label:'备注', type:'text', required:false }]
  } else {
    fieldDefs.value = [{ field_id:'note', label:'备注', type:'text', required:false }]
  }
  // 填充已有答案
  const dv = it.data_value || []
  const map = {}
  for (const f of fieldDefs.value) {
    const ex = dv.find(x => x.field_name === (f.field_id || f.label))
    map[f.field_id || f.label] = ex?.value ?? (f.type === 'select_multi' ? [] : (f.type==='boolean'? false : ''))
  }
  fieldValues.value = map
  editStatus.value = it.status || 'completed'
  editVisible.value = true
}

const closeEdit = () => { editVisible.value = false }
const setStatus = (s) => { editStatus.value = s }

const saveEdit = async () => {
  if (!editItemObj.value) return
  // 校验必填与约束
  for (const f of fieldDefs.value) {
    const key = f.field_id || f.label
    const val = fieldValues.value[key]
    if (f.required) {
      const empty = (f.type === 'select_multi') ? (!val || val.length === 0) : (val === undefined || val === null || val === '')
      if (empty) {
        uni.showToast({ title: `${f.label || key} 为必填`, icon: 'none' })
        return
      }
    }
    const c = f.constraints || {}
    if (f.type === 'number') {
      if (typeof val === 'number') {
        if (c.min !== undefined && val < c.min) { uni.showToast({ title: `${f.label||key} 不能小于 ${c.min}`, icon:'none' }); return }
        if (c.max !== undefined && val > c.max) { uni.showToast({ title: `${f.label||key} 不能大于 ${c.max}`, icon:'none' }); return }
      }
    }
    if (f.type === 'text' || f.type === 'rich_text') {
      const len = (val || '').length
      if (c.min_length !== undefined && len < c.min_length) { uni.showToast({ title: `${f.label||key} 最少 ${c.min_length} 字`, icon:'none' }); return }
      if (c.max_length !== undefined && len > c.max_length) { uni.showToast({ title: `${f.label||key} 最多 ${c.max_length} 字`, icon:'none' }); return }
      if (c.pattern) {
        try { const re = new RegExp(c.pattern); if (!re.test(val || '')) { uni.showToast({ title: `${f.label||key} 格式不符合`, icon:'none' }); return } } catch(e) {}
      }
    }
  }
  // 收集答案
  const answers = []
  for (const f of fieldDefs.value) {
    const key = f.field_id || f.label
    answers.push({ field_name: key, value: fieldValues.value[key] })
  }
  const payload = { data_value: answers, status: editStatus.value }
  const res = await store.updateItem(orderId.value, editItemObj.value.id, payload)
  if (res.success) {
    uni.showToast({ title: '已保存', icon: 'success' })
    editVisible.value = false
    const b = await store.getItems(orderId.value)
    if (b.success) items.value = b.data
  } else {
    uni.showToast({ title: res.error || '保存失败', icon: 'error' })
  }
}

// 页面初次加载
onLoad((options) => {
  console.log('📱 工单详情页面 onLoad', options)
  orderId.value = options?.id
  isPageVisible.value = true
  load()
})

// 每次页面显示时刷新数据
onShow(() => {
  console.log('👁️ 工单详情页面 onShow', { 
    orderId: orderId.value, 
    isPageVisible: isPageVisible.value 
  })
  
  // 避免重复刷新（onLoad后立即触发onShow）
  if (isPageVisible.value && orderId.value) {
    console.log('🔄 页面重新显示，自动刷新数据')
    load()
  }
  isPageVisible.value = true
})
</script>

<style lang="scss" scoped>
	.detail-container {
		min-height: 100vh;
		background-color: var(--bg-page);
	}
	
	// 自定义导航栏 - 统一风格
	.custom-navbar {
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
		padding: 44rpx 30rpx 20rpx;
		color: #fff;
	}
	
	.navbar-content {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: 88rpx;
	}
	
	.navbar-title {
		font-size: 36rpx;
		font-weight: bold;
	}
	
	// 内容区域
	.content {
		padding: 20rpx;
		padding-bottom: 140rpx;
	}
	
	// 卡片样式 - 统一APP卡片风格
	.card {
		background: var(--bg-elevated);
		border-radius: 24rpx;
		padding: 24rpx;
		margin-bottom: 20rpx;
		box-shadow: var(--shadow-card);
	}
	
	.row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin: 12rpx 0;
		font-size: 28rpx;
	}
	
	.label { color: var(--text-secondary); font-weight: 500; }
	
	.value {
		color: var(--text-primary);
		font-weight: 600;
		
		&.status {
			padding: 8rpx 16rpx;
			border-radius: 16rpx;
			font-size: 24rpx;
			
			&.status-PENDING {
				background: #f3f4f6;
				color: #6b7280;
			}
			
			&.status-ACTIVE {
				background: #dbeafe;
				color: #1d4ed8;
			}
			
			&.status-SUBMITTED {
				background: #fef3c7;
				color: #b45309;
			}
			
			&.status-UNDER_REVIEW {
				background: #e0e7ff;
				color: #6366f1;
			}
			
			&.status-APPROVED {
				background: #d1fae5;
				color: #059669;
			}
			
			&.status-REJECTED {
				background: #fee2e2;
				color: #dc2626;
			}
			
			&.status-COMPLETED {
				background: #d1fae5;
				color: #059669;
			}
		}
	}
	
	.section-title { font-weight: 600; color: var(--text-primary); margin-bottom: 16rpx; font-size: 32rpx; }
	
	// 检查项目样式
	.item {
		padding: 16rpx 0;
		border-bottom: 1rpx solid var(--border-soft);
		
		&:last-child {
			border-bottom: none;
		}
	}
	
	.item-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 8rpx;
	}
	
	.name { color: var(--text-primary); font-size: 28rpx; font-weight: 500; flex: 1; }
	
	.status-group {
		display: flex;
		gap: 8rpx;
		align-items: center;
	}
	
	.istatus {
		font-size: 24rpx;
		color: #6b7280;
		padding: 6rpx 12rpx;
		background: #f3f4f6;
		border-radius: 12rpx;
		
		&.istatus-completed {
			background: #d1fae5;
			color: #059669;
		}
		
		&.istatus-in_progress {
			background: #dbeafe;
			color: #1d4ed8;
		}
		
		&.istatus-failed {
			background: #fee2e2;
			color: #dc2626;
		}
	}
	
	.review-status {
		font-size: 22rpx;
		padding: 4rpx 8rpx;
		border-radius: 8rpx;
		font-weight: 500;
		
		&.review-pass {
			background: #dcfce7;
			color: #16a34a;
			border: 1rpx solid #22c55e;
		}
		
		&.review-fail {
			background: #fef2f2;
			color: #dc2626;
			border: 1rpx solid #ef4444;
		}
		
		&.review-warning {
			background: #fffbeb;
			color: #d97706;
			border: 1rpx solid #f59e0b;
		}
	}
	
	.review-comments {
		margin-top: 8rpx;
		padding: 12rpx;
		background: #f8fafc;
		border-radius: 8rpx;
		border-left: 4rpx solid #f97316;
		
		.comments-label {
			font-size: 24rpx;
			color: #f97316;
			font-weight: 500;
		}
		
		.comments-text {
			font-size: 24rpx;
			color: #374151;
			line-height: 1.5;
			margin-top: 4rpx;
			display: block;
		}
	}
	
	.meta { color: var(--text-secondary); font-size: 24rpx; margin-bottom: 12rpx; }
	
	// 照片展示区域
	.photos {
		margin-top: 16rpx;
	}
	
	.photo-scroll {
		white-space: nowrap;
	}
	
	.p-item {
		display: inline-block;
		position: relative;
		width: 144rpx;
		height: 144rpx;
		margin-right: 16rpx;
		border-radius: 16rpx;
		overflow: hidden;
		background: #f3f4f6;
		box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.1);
	}
	
	.delete-tip {
		position: absolute;
		bottom: 0;
		left: 0;
		right: 0;
		background: rgba(0, 0, 0, 0.6);
		color: white;
		font-size: 20rpx;
		text-align: center;
		padding: 4rpx 0;
	}
	
	.thumb {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}
	
	// 操作按钮
	.item-actions {
		display: flex;
		gap: 16rpx;
		margin-top: 16rpx;
	}
	
	.mini {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 88rpx; /* >=44px */
		padding: 0 24rpx;
		border: none;
		border-radius: 20rpx;
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
		color: #fff;
		font-size: 26rpx;
		font-weight: 600;
		box-shadow: 0 2rpx 8rpx rgba(249, 115, 22, 0.28);
		
		&:active { transform: translateY(1rpx); }
	}
	
	// 底部操作栏
	.bottom-actions {
		position: fixed;
		bottom: 0;
		left: 0;
		right: 0;
		background: var(--bg-elevated);
		padding: 24rpx 32rpx calc(32rpx + env(safe-area-inset-bottom));
		border-top: 1rpx solid var(--border-soft);
		display: flex;
		gap: 24rpx;
		z-index: 100;
		box-shadow: 0 -2rpx 16rpx rgba(0, 0, 0, 0.06);
	}
	
	.action-btn {
		flex: 1;
		padding: 28rpx;
		border-radius: 20rpx;
		font-size: 32rpx;
		border: none;
		color: #fff;
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
		font-weight: 600;
		box-shadow: 0 4rpx 12rpx rgba(249, 115, 22, 0.36);
		
		&:active {
			transform: translateY(2rpx);
			box-shadow: 0 2rpx 8rpx rgba(249, 115, 22, 0.36);
		}
	}
	
	// 编辑弹窗样式
	.overlay {
		position: fixed;
		left: 0;
		right: 0;
		top: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.4);
		display: flex;
		align-items: flex-end;
		z-index: 1000;
	}
	
	.edit-panel {
		width: 100%;
		background: var(--bg-elevated);
		border-top-left-radius: 32rpx;
		border-top-right-radius: 32rpx;
		padding: 32rpx;
		max-height: 80vh;
		overflow-y: auto;
	}
	
	.panel-title { font-weight: 600; color: var(--text-primary); margin-bottom: 24rpx; font-size: 32rpx; text-align: center; }
	
	.form-row {
		margin-bottom: 20rpx;
	}
	
	.form-row .label {
		color: #374151;
		margin-bottom: 8rpx;
		display: block;
		font-size: 28rpx;
		font-weight: 500;
	}
	
	.textarea, .input {
		width: 100%;
		min-height: 80rpx;
		background: #fafafa;
		border: 1rpx solid #e9ecef;
		border-radius: 16rpx;
		padding: 16rpx;
		font-size: 28rpx;
		color: var(--text-primary);
		
		&:focus {
			border-color: var(--color-primary);
			box-shadow: 0 0 0 6rpx rgba(249, 115, 22, 0.12);
			background: #fff;
		}
	}
	
	.textarea {
		min-height: 160rpx;
		resize: none;
	}
	
	.picker { background: #fafafa; border: 1rpx solid #e9ecef; border-radius: 16rpx; padding: 16rpx; font-size: 28rpx; color: var(--text-primary); }
	
	.radio-row {
		display: flex;
		gap: 24rpx;
	}
	
	.radio {
		display: flex;
		align-items: center;
		gap: 8rpx;
		font-size: 28rpx;
	}
	
	.chk {
		display: flex;
		align-items: center;
		gap: 8rpx;
		margin-bottom: 12rpx;
		font-size: 28rpx;
	}
	
	// 弹窗按钮
	.panel-actions {
		display: flex;
		gap: 16rpx;
		margin-top: 32rpx;
	}
	
	.btn {
		flex: 1;
		padding: 24rpx;
		border: none;
		border-radius: 16rpx;
		font-size: 28rpx;
		font-weight: 600;
		
		&.cancel { background: #f3f4f6; color: #6b7280; }
		&.save { background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light)); color: #fff; box-shadow: 0 2rpx 8rpx rgba(249, 115, 22, 0.28); }
		&.rejected { background: linear-gradient(135deg, #dc2626, #ef4444); color: #fff; box-shadow: 0 4rpx 12rpx rgba(220, 38, 38, 0.4); }
		&:active { transform: translateY(1rpx); }
	}
</style>
