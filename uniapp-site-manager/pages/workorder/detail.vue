<template>
  <view class="detail-container">
    <view class="custom-navbar">
      <view class="navbar-content">
        <text class="navbar-title">工单详情</text>
      </view>
    </view>

    <view v-if="order" class="content">
      <view class="card">
        <view class="row"><text class="label">标题</text><text class="value">{{ order.title }}</text></view>
        <view class="row"><text class="label">站点</text><text class="value">{{ order.site_name || order.site_id }}</text></view>
        <view class="row"><text class="label">状态</text><text class="value status" :class="'status-'+order.status">{{ statusText(order.status) }}</text></view>
        <view class="row"><text class="label">分配时间</text><text class="value">{{ formatDateTime(order.assigned_at) }}</text></view>
      </view>

      <view class="card">
        <view class="section-title">检查项</view>
        <view class="item" v-for="it in items" :key="it.id">
          <view class="item-header">
            <text class="name">{{ it.item_name }}</text>
            <text class="istatus" :class="'istatus-'+it.status">{{ itemStatusText(it.status) }}</text>
          </view>
          <view class="meta">{{ it.category_name }}</view>
          <view class="photos" v-if="itemPhotos(it).length">
            <scroll-view class="photo-scroll" scroll-x>
              <view class="p-item" v-for="p in itemPhotos(it)" :key="p.id" @click="previewPhoto(p)">
                <image class="thumb" :src="p.file_path" mode="aspectFill" />
              </view>
            </scroll-view>
          </view>
          <view class="item-actions">
            <button class="mini" size="mini" @click.stop="chooseAndUpload(it)">上传照片</button>
            <button class="mini" size="mini" @click.stop="openEdit(it)">填报</button>
          </view>
        </view>
      </view>

      <view class="bottom-actions" v-if="order.status === 'ACTIVE' || order.status === 'REJECTED'">
        <button 
          class="action-btn" 
          @click="completeWorkOrder"
          v-if="order.status === 'ACTIVE'"
        >完成工单</button>
        <button 
          class="action-btn rejected" 
          @click="openEdit(null)"
          v-if="order.status === 'REJECTED'"
        >修改工单</button>
      </view>
    </view>

    <!-- 填报弹层 -->
    <view class="overlay" v-if="editVisible" @click="closeEdit">
      <view class="edit-panel" @click.stop>
        <view class="panel-title">填写检查项</view>
        <!-- 动态字段渲染 -->
        <view class="form-row" v-for="f in fieldDefs" :key="f.field_id || f.label">
          <text class="label">{{ f.label || f.field_id }}</text>
          <block v-if="f.type==='text' || f.type==='rich_text'">
            <textarea class="textarea" v-model="fieldValues[f.field_id || f.label]" :placeholder="'请输入' + (f.label||'')" />
          </block>
          <block v-else-if="f.type==='number'">
            <input class="input" type="number" v-model.number="fieldValues[f.field_id || f.label]" :placeholder="'请输入' + (f.label||'')" />
          </block>
          <block v-else-if="f.type==='boolean'">
            <switch :checked="fieldValues[f.field_id || f.label]===true" @change="e=> fieldValues[f.field_id || f.label] = e.detail.value" />
          </block>
          <block v-else-if="f.type==='select_single'">
            <picker :range="(f.options||[]).map(o=>o.label||o)" @change="e=> fieldValues[f.field_id || f.label] = (f.options||[])[e.detail.value].value || (f.options||[])[e.detail.value]">
              <view class="picker">
                {{ (f.options||[]).find(o => (o.value||o) === fieldValues[f.field_id || f.label])?.label || '请选择' }}
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
            <textarea class="textarea" v-model="fieldValues[f.field_id || f.label]" placeholder="请输入" />
          </block>
        </view>
        <view class="form-row">
          <text class="label">状态</text>
          <view class="radio-row">
            <label class="radio"><radio value="completed" :checked="editStatus==='completed'" @click="setStatus('completed')" /> 完成</label>
            <label class="radio"><radio value="in_progress" :checked="editStatus==='in_progress'" @click="setStatus('in_progress')" /> 进行中</label>
            <label class="radio"><radio value="failed" :checked="editStatus==='failed'" @click="setStatus('failed')" /> 失败</label>
          </view>
        </view>
        <view class="panel-actions">
          <button class="btn cancel" @click="closeEdit">取消</button>
          <button class="btn save" @click="saveEdit">保存</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { useWorkOrderStore } from '@/stores/workorder'

const store = useWorkOrderStore()
const order = ref(null)
const items = ref([])
const photos = ref([])
const orderId = ref(null)

// 编辑弹窗（动态字段）
const editVisible = ref(false)
const editItemObj = ref(null)
const editStatus = ref('completed')
const fieldDefs = ref([])
const fieldValues = ref({})

const load = async () => {
  const id = orderId.value
  if (!id) return
  const a = await store.getWorkOrder(id)
  if (a.success) order.value = a.data
  const b = await store.getItems(id)
  if (b.success) items.value = b.data
  const c = await store.getPhotos(id)
  if (c.success) photos.value = c.data
}

const completeWorkOrder = async () => {
  const id = orderId.value
  try {
    uni.showLoading({ title: '完成中...' })
    const res = await store.completeWorkOrder(id)
    if (res.success) {
      order.value = res.data.work_order || res.data
      uni.showToast({ title: '工单已完成', icon: 'success' })
    } else {
      uni.showToast({ title: res.error || '操作失败', icon: 'error' })
    }
  } catch (e) {
    uni.showToast({ title: '操作失败', icon: 'error' })
  } finally {
    uni.hideLoading()
  }
}

const statusText = (s) => ({
  PENDING: '待处理', ACTIVE: '执行中', SUBMITTED: '已提交', 
  UNDER_REVIEW: '审核中', APPROVED: '已通过', REJECTED: '已驳回', COMPLETED: '已完成'
})[s] || s
const itemStatusText = (s) => ({ pending: '待处理', in_progress: '进行中', completed: '已完成', failed: '失败' })[s] || s
const formatDateTime = (val) => (val ? new Date(val).toLocaleString('zh-CN') : '-')

const itemPhotos = (it) => (photos.value || []).filter(p => p.item_id === it.id)

const previewPhoto = (p) => {
  const urls = itemPhotos({ id: p.item_id }).map(x => x.file_path)
  const current = urls.indexOf(p.file_path)
  uni.previewImage({ urls, current: current >= 0 ? current : 0 })
}

const chooseAndUpload = async (it) => {
  try {
    const choose = await new Promise((resolve, reject) => {
      uni.chooseImage({ count: 3, success: resolve, fail: reject })
    })
    const paths = choose.tempFilePaths || []
    // 获取定位（可选）
    let loc = null
    try {
      loc = await new Promise((resolve, reject) => {
        uni.getLocation({ type: 'wgs84', success: resolve, fail: () => resolve(null) })
      })
    } catch (e) { /* ignore */ }
    for (const p of paths) {
      await store.uploadPhoto(orderId.value, p, {
        item_id: it.id,
        gps_latitude: loc?.latitude || 0,
        gps_longitude: loc?.longitude || 0,
        gps_accuracy: loc?.accuracy || undefined,
      })
    }
    uni.showToast({ title: '上传完成', icon: 'success' })
    const c = await store.getPhotos(orderId.value)
    if (c.success) photos.value = c.data
  } catch (e) {
    uni.showToast({ title: '上传取消', icon: 'none' })
  }
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

onLoad((options) => {
  orderId.value = options?.id
  load()
})
</script>

<style lang="scss" scoped>
	.detail-container {
		min-height: 100vh;
		background-color: #f5f5f5;
	}
	
	// 自定义导航栏 - 统一风格
	.custom-navbar {
		background: linear-gradient(135deg, #f97316, #fb923c);
		padding: 44rpx 32rpx 24rpx;
		color: white;
	}
	
	.navbar-title {
		font-size: 36rpx;
		font-weight: 600;
	}
	
	// 内容区域
	.content {
		padding: 20rpx;
		padding-bottom: 140rpx;
	}
	
	// 卡片样式 - 统一APP卡片风格
	.card {
		background: white;
		border-radius: 24rpx;
		padding: 24rpx;
		margin-bottom: 20rpx;
		box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.08);
	}
	
	.row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin: 12rpx 0;
		font-size: 28rpx;
	}
	
	.label {
		color: #6b7280;
		font-weight: 500;
	}
	
	.value {
		color: #111827;
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
	
	.section-title {
		font-weight: 600;
		color: #111827;
		margin-bottom: 16rpx;
		font-size: 32rpx;
	}
	
	// 检查项目样式
	.item {
		padding: 16rpx 0;
		border-bottom: 1rpx solid #f3f4f6;
		
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
	
	.name {
		color: #111827;
		font-size: 28rpx;
		font-weight: 500;
		flex: 1;
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
	
	.meta {
		color: #6b7280;
		font-size: 24rpx;
		margin-bottom: 12rpx;
	}
	
	// 照片展示区域
	.photos {
		margin-top: 16rpx;
	}
	
	.photo-scroll {
		white-space: nowrap;
	}
	
	.p-item {
		display: inline-block;
		width: 144rpx;
		height: 144rpx;
		margin-right: 16rpx;
		border-radius: 16rpx;
		overflow: hidden;
		background: #f3f4f6;
		box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.1);
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
		font-size: 24rpx;
		padding: 12rpx 20rpx;
		border: none;
		border-radius: 16rpx;
		background: linear-gradient(135deg, #f97316, #fb923c);
		color: white;
		font-weight: 500;
		box-shadow: 0 2rpx 8rpx rgba(249, 115, 22, 0.3);
		
		&:active {
			transform: translateY(1rpx);
		}
	}
	
	// 底部操作栏
	.bottom-actions {
		position: fixed;
		bottom: 0;
		left: 0;
		right: 0;
		background: white;
		padding: 24rpx 32rpx;
		border-top: 1rpx solid #f0f0f0;
		display: flex;
		gap: 24rpx;
		z-index: 100;
		box-shadow: 0 -2rpx 16rpx rgba(0, 0, 0, 0.1);
	}
	
	.action-btn {
		flex: 1;
		padding: 28rpx;
		border-radius: 20rpx;
		font-size: 32rpx;
		border: none;
		color: white;
		background: linear-gradient(135deg, #f97316, #fb923c);
		font-weight: 600;
		box-shadow: 0 4rpx 12rpx rgba(249, 115, 22, 0.4);
		
		&:active {
			transform: translateY(2rpx);
			box-shadow: 0 2rpx 8rpx rgba(249, 115, 22, 0.4);
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
		background: white;
		border-top-left-radius: 32rpx;
		border-top-right-radius: 32rpx;
		padding: 32rpx;
		max-height: 80vh;
		overflow-y: auto;
	}
	
	.panel-title {
		font-weight: 600;
		color: #111827;
		margin-bottom: 24rpx;
		font-size: 32rpx;
		text-align: center;
	}
	
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
		background: #f8f9fa;
		border: 1rpx solid #e9ecef;
		border-radius: 16rpx;
		padding: 16rpx;
		font-size: 28rpx;
		color: #111827;
		
		&:focus {
			border-color: #f97316;
			box-shadow: 0 0 0 6rpx rgba(249, 115, 22, 0.1);
		}
	}
	
	.textarea {
		min-height: 160rpx;
		resize: none;
	}
	
	.picker {
		background: #f8f9fa;
		border: 1rpx solid #e9ecef;
		border-radius: 16rpx;
		padding: 16rpx;
		font-size: 28rpx;
		color: #111827;
	}
	
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
		
		&.cancel {
			background: #f3f4f6;
			color: #6b7280;
		}
		
		&.save {
			background: linear-gradient(135deg, #f97316, #fb923c);
			color: white;
			box-shadow: 0 2rpx 8rpx rgba(249, 115, 22, 0.3);
		}
		
		&.rejected {
			background: linear-gradient(135deg, #dc2626, #ef4444);
			color: white;
			box-shadow: 0 4rpx 12rpx rgba(220, 38, 38, 0.4);
		}
		
		&:active {
			transform: translateY(1rpx);
		}
	}
</style>
