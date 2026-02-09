<template>
	<view class="page" :key="languageStore.currentLocale">
		<CustomNavbar :title="$t('stock.returnNew')" :showBack="true" variant="brand" />

		<scroll-view class="content" scroll-y>
			<view class="hero u-card">
				<text class="hero-title">{{ $t('stock.returnNew') }}</text>
				<text class="hero-sub">{{ $t('stock.selectStockOutHint') }}</text>
			</view>

			<!-- 1) 选择出库单 -->
			<view class="section u-card">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.selectStockOut') }}</text>
					<text v-if="selectedOut" class="hint mono">{{ selectedOut.document_number }}</text>
				</view>
				<view class="u-card-content">
					<view class="search">
						<uni-icons type="search" size="18" color="#6b7280" />
						<input
							class="search-input"
							v-model="keyword"
							:placeholder="$t('stock.materialRequestSearchPlaceholder')"
							confirm-type="search"
							@confirm="reloadOuts"
						/>
						<uni-icons v-if="keyword" type="clear" size="18" color="#9ca3af" @click="clearKeyword" />
					</view>

					<view class="out-list">
						<template v-if="outsLoading && outs.length === 0">
							<SkeletonCard mode="list" />
							<SkeletonCard mode="list" />
						</template>
						<EmptyState
							v-else-if="!outsLoading && outs.length === 0"
							icon="📤"
							:title="$t('messages.noData')"
							:description="$t('messages.noData')"
							:compact="true"
						/>
						<template v-else>
							<view
								v-for="o in outs"
								:key="o.id"
								class="out-card u-pressable-subtle"
								:class="{ active: selectedOut && selectedOut.id === o.id }"
								@click="selectOut(o)"
							>
								<view class="out-head">
									<text class="out-no mono">{{ o.document_number }}</text>
									<view class="u-tag" :class="selectedOut && selectedOut.id === o.id ? 'tag-ok' : 'tag-muted'">
										{{ selectedOut && selectedOut.id === o.id ? $t('common.selected') : $t('common.select') }}
									</view>
								</view>
								<view class="out-meta">
									<text class="meta-item">{{ o.warehouse_name || '-' }}</text>
									<text class="dot">·</text>
									<text class="meta-item">{{ timeAgo(o.operation_time) }}</text>
								</view>
							</view>
						</template>
					</view>

					<button class="u-btn u-btn-secondary u-btn-sm u-pressable" :disabled="outsLoading || !hasMoreOuts" @click="loadMoreOuts">
						{{ $t('stock.loadMore') }}
					</button>
				</view>
			</view>

			<!-- 2) 选择退入仓库 -->
			<view class="section u-card">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.selectReturnWarehouse') }}</text>
					<text class="hint">{{ $t('common.optional') }}</text>
				</view>
				<view class="u-card-content">
					<picker @change="onWarehouseChange" :value="warehouseIndex" :range="warehouseOptions">
						<view class="picker-input" :class="{ placeholder: !selectedWarehouse }">
							<text>{{ selectedWarehouse ? selectedWarehouse.warehouse_name : $t('common.pleaseSelect') }}</text>
							<text class="picker-arrow">▼</text>
						</view>
					</picker>
				</view>
			</view>

			<!-- 3) 选择退库明细 -->
			<view v-if="selectedOut" class="section u-card">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.materialRequestItems') }}</text>
					<view class="header-actions">
						<button class="u-btn u-btn-secondary u-btn-xs u-pressable" @click="selectAllReturnable">
							{{ $t('stock.returnSelectAll') }}
						</button>
						<button class="u-btn u-btn-ghost u-btn-xs u-pressable" @click="clearSelection">
							{{ $t('stock.returnClearSelection') }}
						</button>
					</view>
				</view>
				<view class="u-card-content">
					<view class="block">
						<view class="block-head">
							<text class="block-title">{{ $t('stock.mainDevice') }}</text>
							<text class="block-sub">{{ $t('stock.returnMainSnListHint') }}</text>
						</view>
						<view v-if="mainSnItems.length" class="main-sn-list">
							<view class="main-sn-head">
								<text class="main-sn-title">{{ $t('stock.returnMainSnListTitle', { count: mainSnItems.length }) }}</text>
								<text
									v-if="mainSnCanToggle"
									class="main-sn-toggle u-pressable"
									@click="toggleMainSnExpanded"
								>
									{{ mainSnExpanded ? $t('stock.returnMainSnCollapse') : $t('stock.returnMainSnExpand') }}
								</text>
							</view>
							<view v-for="row in visibleMainSnItems" :key="row.key" class="main-sn-row">
								<text class="mono main-sn-value">{{ row.sn || '-' }}</text>
								<text class="main-sn-status" :class="`status-${row.status}`">{{ mainSnStatusText(row.status) }}</text>
							</view>
							<text v-if="mainSnHiddenCount > 0 && !mainSnExpanded" class="main-sn-more">
								{{ $t('stock.returnMainSnMoreCount', { count: mainSnHiddenCount }) }}
							</text>
						</view>
						<view v-else class="main-sn-empty">{{ $t('stock.returnMainSnListEmpty') }}</view>
						<button class="u-btn u-btn-primary u-btn-sm u-pressable" @click="scanAddMain">
							<uni-icons type="scan" size="18" color="#fff" />
							<text>{{ $t('stock.scanAddMainDevice') }}</text>
						</button>
						<view v-if="selectedMainSns.length" class="picked-list">
							<view v-for="sn in selectedMainSns" :key="sn" class="picked-row">
								<text class="mono">{{ sn }}</text>
								<text class="remove u-pressable" @click="removeMain(sn)">×</text>
							</view>
						</view>
					</view>

					<view class="block">
						<view class="block-head">
							<text class="block-title">{{ $t('stock.auxMaterial') }}</text>
							<text class="block-sub">{{ $t('stock.returnMaxLabel') }} = {{ $t('stock.qtyRemaining') }}</text>
						</view>
						<view class="aux-list">
							<view v-for="it in auxItems" :key="it.item_id" class="aux-row">
								<view class="aux-left">
									<text class="aux-name">{{ it.equipment_name }}</text>
									<text class="aux-meta">{{ $t('stock.returnMaxLabel') }} {{ it.max_returnable || 0 }} {{ it.unit }}</text>
								</view>
								<view class="stepper">
									<view class="step u-pressable" @click="decAux(it)">−</view>
									<text class="num mono">{{ auxQtyMap[it.equipment_id] || 0 }}</text>
									<view class="step u-pressable" @click="incAux(it)">＋</view>
								</view>
							</view>
						</view>
					</view>
				</view>
			</view>

			<!-- 4) 线下单据（可选） -->
			<view class="section u-card">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.offlineDocTitle') }}</text>
					<text class="hint">{{ $t('common.optional') }}</text>
				</view>
				<view class="u-card-content">
					<OfflineDocumentSection v-model="offlineDocumentId" :disabled="submitting" :showHeader="false" />
				</view>
			</view>

			<view class="footer">
				<button class="u-btn u-btn-primary u-pressable" :disabled="submitting" @click="submit">
					{{ submitting ? $t('stock.processing') : $t('stock.submitReturnRequest') }}
				</button>
			</view>

			<view class="spacer" />
		</scroll-view>

		<!-- 检查绑定提示（复用旧退库的规则） -->
		<view v-if="bindModalVisible" class="bind-modal-mask" @click="closeBindModal">
			<view class="bind-modal" @click.stop>
				<view class="bind-modal-header">
					<text class="bind-modal-title">
						{{ bindModalAction === 'need_unbind' ? $t('stock.oneClickUnbind') : $t('common.hint') }}
					</text>
					<text class="bind-modal-close u-pressable" @click="closeBindModal">×</text>
				</view>

				<view class="bind-modal-body">
					<text class="bind-modal-desc">{{ bindModalMessage }}</text>

					<scroll-view v-if="bindModalBindings.length" class="bind-list" scroll-y>
						<view v-for="(b, idx) in bindModalBindings" :key="idx" class="bind-item">
							<view class="bind-item-row">
								<text class="bind-sn mono">{{ b.sn || '-' }}</text>
								<text class="bind-title">{{ bindingTitle(b) }}</text>
							</view>
							<text v-if="bindingSiteName(b)" class="bind-sub">{{ bindingSiteName(b) }}</text>
							<text v-if="bindingReasonText(b)" class="bind-reason">{{ bindingReasonText(b) }}</text>
						</view>
					</scroll-view>
				</view>

				<view class="bind-modal-footer">
					<button class="u-btn u-btn-secondary u-pressable" :disabled="unbindSubmitting" @click="closeBindModal">
						{{ $t('common.close') }}
					</button>
					<button
						v-if="bindModalAction === 'need_unbind'"
						class="u-btn u-btn-primary u-pressable"
						:disabled="unbindSubmitting"
						@click="confirmUnbindAndRetry"
					>
						{{ unbindSubmitting ? $t('stock.processing') : $t('stock.oneClickUnbind') }}
					</button>
				</view>
			</view>
		</view>
	</view>
</template>

<script setup>
	import { computed, getCurrentInstance, onMounted, ref } from 'vue'
	import { onLoad } from '@dcloudio/uni-app'
	import { API_ENDPOINTS, buildApiUrl, createRequestConfig, getAuthHeaders } from '@/config/api.js'
	import { parseBarcode } from '@/utils/barcode-parser.js'
	import { useUserStore } from '@/stores/user'
	import { useLanguageStore } from '@/stores/language'

	const userStore = useUserStore()
	const languageStore = useLanguageStore()
	const { appContext } = getCurrentInstance()
	const { $t } = appContext.config.globalProperties

	const warehouses = ref([])
	const warehouseIndex = ref(0)

	const outsLoading = ref(false)
	const outs = ref([])
	const outsTotal = ref(0)
	const outsPage = ref(1)
	const outsPageSize = ref(10)
	const keyword = ref('')

	const selectedOut = ref(null)
	const selectedMainSns = ref([])
	const auxQtyMap = ref({})
	const offlineDocumentId = ref(null)
	const MAIN_SN_COLLAPSE_THRESHOLD = 8
	const mainSnExpanded = ref(true)

	// 从“我的设备→设备详情→退库”带入
	const preselectOutId = ref('')
	const preselectSn = ref('')
	const preselectApplied = ref(false)

	// 检查绑定弹窗（后端 400 detail.action）
	const bindModalVisible = ref(false)
	const bindModalAction = ref('')
	const bindModalMessage = ref('')
	const bindModalBindings = ref([])
	const unbindSubmitting = ref(false)

	const submitting = ref(false)

	const warehouseOptions = computed(() => (warehouses.value || []).map(w => w.warehouse_name))
	const selectedWarehouse = computed(() => warehouses.value?.[warehouseIndex.value] || null)

	const hasMoreOuts = computed(() => outs.value.length < outsTotal.value)

	const auxItems = computed(() => {
		const items = selectedOut.value?.items || []
		return items.filter(it => it && !it.is_main_device)
	})

	const mainSnItems = computed(() => {
		const items = selectedOut.value?.items || []
		return items
			.filter(it => it && it.is_main_device)
			.map((it, idx) => {
				const rawSn = String(it?.serial_number || '').trim()
				const maxReturnable = Number(it?.max_returnable || 0)
				let status = 'returnable'
				if (!rawSn) status = 'missing_sn'
				else if (maxReturnable <= 0) status = 'already_requested'
				return {
					key: String(it?.item_id || rawSn || `main_${idx}`),
					sn: rawSn,
					status,
				}
			})
	})

	const mainSnCanToggle = computed(() => mainSnItems.value.length > MAIN_SN_COLLAPSE_THRESHOLD)
	const visibleMainSnItems = computed(() => {
		if (mainSnExpanded.value) return mainSnItems.value
		if (!mainSnCanToggle.value) return mainSnItems.value
		return mainSnItems.value.slice(0, MAIN_SN_COLLAPSE_THRESHOLD)
	})
	const mainSnHiddenCount = computed(() => {
		if (!mainSnCanToggle.value || mainSnExpanded.value) return 0
		return Math.max(mainSnItems.value.length - MAIN_SN_COLLAPSE_THRESHOLD, 0)
	})

	const mainSnStatusText = (status) => {
		if (status === 'already_requested') return $t('stock.returnMainSnStatusAlreadyRequested')
		if (status === 'missing_sn') return $t('stock.returnMainSnStatusMissing')
		return $t('stock.returnMainSnStatusReturnable')
	}

	const setMainSnDefaultExpanded = (out) => {
		const totalMainSn = (out?.items || []).filter(it => it?.is_main_device).length
		mainSnExpanded.value = totalMainSn <= MAIN_SN_COLLAPSE_THRESHOLD
	}

	const toggleMainSnExpanded = () => {
		if (!mainSnCanToggle.value) return
		mainSnExpanded.value = !mainSnExpanded.value
	}

	const timeAgo = (iso) => {
		if (!iso) return '-'
		const d = new Date(iso)
		if (Number.isNaN(d.getTime())) return String(iso)
		const diff = Date.now() - d.getTime()
		const m = Math.floor(diff / 60000)
		if (m < 1) return '刚刚'
		if (m < 60) return `${m} 分钟前`
		const h = Math.floor(m / 60)
		if (h < 24) return `${h} 小时前`
		const dd = Math.floor(h / 24)
		return `${dd} 天前`
	}

	const loadWarehouses = async () => {
		try {
			const res = await uni.request({
				url: buildApiUrl('/api/stock/warehouses'),
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token),
				})
			})
			if (res.statusCode === 200) {
				warehouses.value = Array.isArray(res.data?.warehouses) ? res.data.warehouses : []
				return
			}
		} catch (e) {
			console.error('加载仓库失败:', e)
		}
	}

	const loadOuts = async (reset = true) => {
		if (!userStore.token) return
		if (reset) {
			outsPage.value = 1
			outs.value = []
			outsTotal.value = 0
		}
		outsLoading.value = true
		try {
			const params = []
			params.push(`page=${outsPage.value}`)
			params.push(`page_size=${outsPageSize.value}`)
			if (keyword.value?.trim()) params.push(`keyword=${encodeURIComponent(keyword.value.trim())}`)
			const url = `${buildApiUrl(API_ENDPOINTS.STOCK.MY_STOCK_OUTS)}?${params.join('&')}`

			const res = await uni.request({
				url,
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token),
				})
			})

			if (res.statusCode === 200) {
				const list = Array.isArray(res.data?.records) ? res.data.records : []
				outsTotal.value = Number(res.data?.total || 0)
				outs.value = reset ? list : outs.value.concat(list)
				return
			}

			if (res.statusCode === 401) userStore.logout()
			else uni.showToast({ title: String(res.data?.detail || res.data?.message || '加载失败'), icon: 'none' })
		} catch (e) {
			console.error('加载出库记录失败:', e)
			uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
		} finally {
			outsLoading.value = false
		}
	}

	const reloadOuts = async () => {
		await loadOuts(true)
	}

	const clearKeyword = async () => {
		keyword.value = ''
		await loadOuts(true)
	}

	const loadMoreOuts = async () => {
		if (!hasMoreOuts.value || outsLoading.value) return
		outsPage.value += 1
		await loadOuts(false)
	}

	const selectOut = (o) => {
		selectedOut.value = o
		selectedMainSns.value = []
		setMainSnDefaultExpanded(o)
		const map = {}
		for (const it of (o?.items || [])) {
			if (it?.is_main_device) continue
			map[it.equipment_id] = 0
		}
		auxQtyMap.value = map

		// 默认退回到原出库仓库（若存在）
		const idx = (warehouses.value || []).findIndex(w => w.id === o?.warehouse_id)
		if (idx >= 0) warehouseIndex.value = idx
	}

	const onWarehouseChange = (e) => {
		warehouseIndex.value = Number(e.detail.value || 0)
	}

	const bindingTitle = (binding) => {
		const fallback = $t('stock.unknownWorkOrderOrSite')
		if (!binding) return fallback
		return binding.work_order_title || binding.site_name || fallback
	}

	const bindingSiteName = (binding) => {
		if (!binding) return ''
		if (binding.work_order_title && binding.site_name) return binding.site_name
		return ''
	}

	const bindingReasonText = (binding) => {
		if (!binding) return ''
		const code = String(binding.reason_code || '').trim()
		const map = {
			other_inspector: $t('stock.unbindReasonOtherInspector'),
			inspection_locked: $t('stock.unbindReasonInspectionLocked'),
			status_not_supported: $t('stock.unbindReasonStatusNotSupported'),
		}
		return map[code] || binding.reason || ''
	}

	const openBindModalFromDetail = (detail) => {
		const action = String(detail?.action || '').trim()
		if (action !== 'need_unbind' && action !== 'unbind_blocked') return false
		bindModalAction.value = action
		bindModalMessage.value = String(detail?.message || detail?.detail || $t('messages.operationFailed') || '').trim()
		bindModalBindings.value = Array.isArray(detail?.need_unbind)
			? detail.need_unbind
			: Array.isArray(detail?.blocked_bindings)
				? detail.blocked_bindings
				: []
		bindModalVisible.value = true
		return true
	}

	const closeBindModal = (force = false) => {
		if (unbindSubmitting.value && !force) return
		bindModalVisible.value = false
		bindModalAction.value = ''
		bindModalMessage.value = ''
		bindModalBindings.value = []
	}

	const validateMainSnInSelectedOut = (sn) => {
		const value = String(sn || '').trim()
		if (!value || !selectedOut.value) return { ok: false, reason: 'not_in_out' }

		const mainItem = (selectedOut.value.items || []).find(it => it?.is_main_device && String(it?.serial_number || '').trim() === value)
		if (!mainItem) return { ok: false, reason: 'not_in_out' }

		const maxReturnable = Number(mainItem?.max_returnable || 0)
		if (maxReturnable <= 0) return { ok: false, reason: 'already_return_requested' }

		return { ok: true, value }
	}

	const showMainSnPickErrorToast = (sn, reason) => {
		const value = String(sn || '').trim()
		if (!value) return

		if (reason === 'already_return_requested') {
			uni.showToast({ title: $t('stock.returnSnAlreadyReturnRequested', { sn: value }), icon: 'none' })
			return
		}
		uni.showToast({ title: $t('stock.returnSnNotInStockOut', { sn: value }), icon: 'none' })
	}

	const scanAddMain = async () => {
		if (!selectedOut.value) {
			uni.showToast({ title: $t('stock.selectStockOut'), icon: 'none' })
			return
		}
		try {
			const res = await uni.scanCode({ scanType: ['qrCode', 'barCode'] })
			const raw = (res?.result || '').trim()
			const parsed = parseBarcode(raw)
			const sn = (parsed?.success ? parsed.sn : raw) || ''
			const value = String(sn).trim()
			if (!value) {
				uni.showToast({ title: $t('stock.scanResultEmpty'), icon: 'none' })
				return
			}
			const exist = selectedMainSns.value.includes(value)
			if (exist) return

			const check = validateMainSnInSelectedOut(value)
			if (!check.ok) {
				showMainSnPickErrorToast(value, check.reason)
				return
			}
			selectedMainSns.value = selectedMainSns.value.concat([value])
		} catch (e) {
			// 用户取消扫码无需提示
		}
	}

	const removeMain = (sn) => {
		selectedMainSns.value = selectedMainSns.value.filter(s => s !== sn)
	}

	const decAux = (it) => {
		const eid = it?.equipment_id
		const cur = Number(auxQtyMap.value?.[eid] || 0)
		auxQtyMap.value = { ...(auxQtyMap.value || {}), [eid]: Math.max(0, cur - 1) }
	}
	const incAux = (it) => {
		const eid = it?.equipment_id
		const cur = Number(auxQtyMap.value?.[eid] || 0)
		const max = Number(it?.max_returnable || 0)
		auxQtyMap.value = { ...(auxQtyMap.value || {}), [eid]: Math.min(max, cur + 1) }
	}

	const selectAllReturnable = () => {
		const map = { ...(auxQtyMap.value || {}) }
		for (const it of auxItems.value) {
			map[it.equipment_id] = Math.max(0, Number(it.max_returnable || 0))
		}
		auxQtyMap.value = map
	}

	const clearSelection = () => {
		selectedMainSns.value = []
		const map = { ...(auxQtyMap.value || {}) }
		Object.keys(map).forEach(k => { map[k] = 0 })
		auxQtyMap.value = map
	}

	const buildSubmitPayload = () => {
		if (!selectedOut.value?.id) {
			uni.showToast({ title: $t('stock.selectStockOut'), icon: 'none' })
			return null
		}
		if (!selectedWarehouse.value) {
			uni.showToast({ title: $t('stock.selectReturnWarehouse'), icon: 'none' })
			return null
		}

		const auxItemsPayload = []
		Object.keys(auxQtyMap.value || {}).forEach((k) => {
			const qty = Number(auxQtyMap.value[k] || 0)
			const eid = Number(k)
			if (!Number.isFinite(eid) || qty <= 0) return
			auxItemsPayload.push({ equipment_id: eid, quantity: qty })
		})

		if (selectedMainSns.value.length === 0 && auxItemsPayload.length === 0) {
			uni.showToast({ title: $t('stock.returnSelectAtLeastOne'), icon: 'none' })
			return null
		}

		return {
			out_transaction_id: selectedOut.value.id,
			return_warehouse_id: selectedWarehouse.value.id,
			main_sns: selectedMainSns.value,
			aux_items: auxItemsPayload,
			offline_document_id: offlineDocumentId.value || undefined,
		}
	}

	const buildSubmitConfirmAuxRows = (payload) => {
		const itemMap = new Map((auxItems.value || []).map(it => [Number(it?.equipment_id), it]))
		const rows = []
		for (const row of (payload?.aux_items || [])) {
			const eid = Number(row?.equipment_id)
			const qty = Number(row?.quantity || 0)
			if (!Number.isFinite(eid) || qty <= 0) continue
			const matched = itemMap.get(eid)
			rows.push({
				equipment_id: eid,
				quantity: qty,
				equipment_name: String(matched?.equipment_name || eid),
				unit: String(matched?.unit || ''),
			})
		}
		return rows
	}

	const buildSubmitConfirmContent = (payload) => {
		const mainList = Array.isArray(payload?.main_sns) ? payload.main_sns : []
		const auxRows = buildSubmitConfirmAuxRows(payload)

		const mainLines = mainList.length
			? mainList.map((sn, idx) => `${idx + 1}. ${sn}`).join('\n')
			: $t('stock.returnSubmitConfirmNone')

		const auxLines = auxRows.length
			? auxRows.map((row, idx) => `${idx + 1}. ${row.equipment_name} x ${row.quantity}${row.unit ? ` ${row.unit}` : ''}`).join('\n')
			: $t('stock.returnSubmitConfirmNone')

		return [
			`${$t('stock.returnSubmitConfirmOutNo')}: ${selectedOut.value?.document_number || '-'}`,
			`${$t('stock.returnSubmitConfirmWarehouse')}: ${selectedWarehouse.value?.warehouse_name || '-'}`,
			`${$t('stock.returnSubmitConfirmMainTitle', { count: mainList.length })}:`,
			mainLines,
			`${$t('stock.returnSubmitConfirmAuxTitle', { count: auxRows.length })}:`,
			auxLines,
		].join('\n')
	}

	const confirmSubmitPayload = async (payload) => await new Promise((resolve) => {
		uni.showModal({
			title: $t('stock.returnSubmitConfirmTitle'),
			content: buildSubmitConfirmContent(payload),
			confirmText: $t('common.confirm'),
			cancelText: $t('common.cancel'),
			success: (r) => resolve(!!r.confirm),
			fail: () => resolve(false),
		})
	})

	const goAfterCreateSuccess = () => {
		// 避免 create -> redirectTo(list) 造成 list 页面被重复压栈（返回按钮需点多次）
		try {
			const pages = typeof getCurrentPages === 'function' ? getCurrentPages() : []
			const prev = pages?.[pages.length - 2]
			const rawRoute = String(prev?.route || prev?.__route__ || prev?.$page?.route || prev?.$page?.fullPath || '').trim()
			const route = rawRoute.replace(/^\//, '').split('?')[0]
			if (route === 'pages/stock/returns/list') {
				uni.navigateBack({ delta: 1 })
				return
			}
		} catch (e) {
			// 忽略：兜底跳转到列表页
		}
		uni.redirectTo({ url: '/pages/stock/returns/list' })
	}

	const doSubmit = async (preparedPayload = null) => {
		const payload = preparedPayload || buildSubmitPayload()
		if (!payload) return

		try {
			submitting.value = true
			const res = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.STOCK.CREATE_RETURN),
				...createRequestConfig({
					method: 'POST',
					headers: getAuthHeaders(userStore.token),
					data: payload,
				})
			})

			if (res.statusCode === 200) {
				uni.showToast({ title: $t('stock.createReturnSuccess'), icon: 'success' })
				setTimeout(goAfterCreateSuccess, 500)
				return
			}

			if (res.statusCode === 401) {
				userStore.logout()
				return
			}

			// 后端返回检查绑定阻断/需解绑：展示弹窗并支持一键解绑重试
			if (res.statusCode === 400 && res.data?.detail && typeof res.data.detail === 'object') {
				const handled = openBindModalFromDetail(res.data.detail)
				if (handled) return
			}

			uni.showToast({ title: String(res.data?.detail || res.data?.message || $t('messages.operationFailed')), icon: 'none' })
		} catch (e) {
			console.error('提交退库失败:', e)
			uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
		} finally {
			submitting.value = false
		}
	}

	const submit = async () => {
		if (submitting.value) return
		const payload = buildSubmitPayload()
		if (!payload) return
		const confirmed = await confirmSubmitPayload(payload)
		if (!confirmed) return
		await doSubmit(payload)
	}

	const fetchOutDetail = async (outId) => {
		const id = String(outId || '').trim()
		if (!id || !userStore.token) return null
		try {
			const res = await uni.request({
				url: buildApiUrl(`/api/stock/my-stock-outs/${id}`),
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token),
				})
			})
			if (res.statusCode === 200) return res.data || null
			if (res.statusCode === 401) userStore.logout()
			return null
		} catch (e) {
			console.error('加载出库单详情失败:', e)
			return null
		}
	}

	const ensureSelectedOutById = async (outId) => {
		const id = String(outId || '').trim()
		if (!id) return false
		if (String(selectedOut.value?.id || '') === id) return true
		const found = (outs.value || []).find(o => String(o?.id || '') === id)
		if (found) {
			selectOut(found)
			return true
		}
		const detail = await fetchOutDetail(id)
		if (!detail?.id) {
			uni.showToast({ title: $t('stock.stockOutNotFoundOrNoPermission') || '出库单不存在或无权限', icon: 'none' })
			return false
		}
		outs.value = [detail].concat((outs.value || []).filter(o => String(o?.id || '') !== String(detail.id)))
		selectOut(detail)
		return true
	}

	const tryPreselectSn = (sn) => {
		const value = String(sn || '').trim()
		if (!value || !selectedOut.value) return { ok: false, reason: 'not_in_out' }
		const exist = selectedMainSns.value.includes(value)
		if (exist) return { ok: true }

		const check = validateMainSnInSelectedOut(value)
		if (!check.ok) return check
		selectedMainSns.value = selectedMainSns.value.concat([value])
		return { ok: true }
	}

	const applyPreselectFromQuery = async () => {
		if (preselectApplied.value) return
		const outId = String(preselectOutId.value || '').trim()
		const sn = String(preselectSn.value || '').trim()
		if (!outId) return

		preselectApplied.value = true
		const ok = await ensureSelectedOutById(outId)
		if (!ok) return
		if (!sn) return

		const picked = tryPreselectSn(sn)
		if (!picked.ok) showMainSnPickErrorToast(sn, picked.reason)
	}

	const confirmUnbindAndRetry = async () => {
		if (unbindSubmitting.value) return
		const sns = Array.from(new Set((bindModalBindings.value || []).map(b => String(b?.sn || '').trim()).filter(Boolean)))
		if (sns.length === 0) {
			closeBindModal()
			return
		}

		uni.showModal({
			title: $t('stock.oneClickUnbind'),
			content: $t('stock.unbindWillClearAndDelete'),
			confirmText: $t('common.confirm'),
			cancelText: $t('common.cancel'),
			success: async (r) => {
				if (!r.confirm) return
				unbindSubmitting.value = true
				try {
					for (const sn of sns) {
						const ret = await uni.request({
							url: buildApiUrl(API_ENDPOINTS.STOCK.SCAN_RETURN_UNBIND),
							...createRequestConfig({
								method: 'POST',
								headers: getAuthHeaders(userStore.token),
								data: { sn },
							})
						})
						if (ret.statusCode === 401) {
							userStore.logout()
							return
						}
						if (ret.statusCode !== 200) {
							const msg = ret.data?.detail || ret.data?.message || $t('messages.operationFailed')
							uni.showToast({ title: String(msg), icon: 'none' })
							return
						}
					}

					uni.showToast({ title: $t('messages.operationSuccess'), icon: 'success' })
					closeBindModal(true)
					await doSubmit()
				} catch (e) {
					console.error('解绑失败:', e)
					uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
				} finally {
					unbindSubmitting.value = false
				}
			}
		})
	}

	onMounted(async () => {
		await loadWarehouses()
		await loadOuts(true)
		await applyPreselectFromQuery()
	})

	onLoad((query) => {
		preselectOutId.value = String(query?.out_transaction_id || '').trim()
		preselectSn.value = String(query?.sn || '').trim()
	})
</script>

<style scoped lang="scss">
	.page { background: var(--bg-page); min-height: 100vh; }
	.content { background: var(--bg-page); }

	.hero {
		margin: 14px 16px 0;
		border-radius: var(--radius-lg);
		padding: 14px;
		background:
			radial-gradient(920px 260px at 10% 0%, rgba(var(--color-primary-rgb), 0.14), transparent 62%),
			radial-gradient(920px 260px at 90% 10%, rgba(var(--color-brand-blue-rgb), 0.08), transparent 62%),
			linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(255, 255, 255, 0.90));
		border: 1px solid rgba(229, 231, 235, 0.9);
		box-shadow: var(--shadow-card);
	}
	.hero-title { font-size: 16px; font-weight: 900; color: var(--text-primary); }
	.hero-sub { margin-top: 8px; font-size: 12px; color: var(--text-secondary); line-height: 1.5; }

	.section { margin: 14px 16px 0; border-radius: var(--radius-lg); overflow: hidden; }

	.search {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 10px 12px;
		border-radius: 14px;
		border: 1px solid var(--border-color);
		background: rgba(255, 255, 255, 0.92);
	}
	.search-input { flex: 1; font-size: 13px; color: var(--text-primary); }

	.out-list { margin-top: 12px; display: grid; gap: 10px; }
	.out-card {
		padding: 12px;
		border-radius: 16px;
		background: rgba(255, 255, 255, 0.94);
		border: 1px solid rgba(229, 231, 235, 0.95);
	}
	.out-card.active { border-color: rgba(var(--color-primary-rgb), 0.55); background: rgba(var(--color-primary-rgb), 0.06); }
	.out-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
	.out-no { font-size: 14px; font-weight: 900; color: var(--text-primary); }
	.out-meta { margin-top: 6px; display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--text-secondary); }
	.dot { color: #d1d5db; }

	.picker-input {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 10px;
		padding: 12px;
		border-radius: 14px;
		border: 1px solid var(--border-color);
		background: rgba(255, 255, 255, 0.92);
	}
	.picker-input.placeholder { color: #9ca3af; }
	.picker-arrow { font-size: 11px; color: #9ca3af; }

	.block { margin-top: 14px; padding: 12px; border-radius: 16px; background: rgba(243, 244, 246, 0.7); border: 1px solid rgba(229, 231, 235, 0.9); }
	.block-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
	.block-title { font-size: 13px; font-weight: 900; color: var(--text-primary); }
	.block-sub { font-size: 11px; color: var(--text-secondary); }

	.picked-list { margin-top: 10px; display: grid; gap: 8px; }
	.picked-row { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; border-radius: 14px; background: rgba(255, 255, 255, 0.9); border: 1px solid rgba(229, 231, 235, 0.9); }
	.remove { font-size: 18px; font-weight: 900; color: #ef4444; }
	.main-sn-list { margin-bottom: 10px; padding: 10px; border-radius: 14px; background: rgba(255, 255, 255, 0.9); border: 1px solid rgba(229, 231, 235, 0.9); display: grid; gap: 8px; }
	.main-sn-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
	.main-sn-title { font-size: 12px; color: var(--text-secondary); }
	.main-sn-toggle { font-size: 12px; font-weight: 700; color: var(--color-primary); }
	.main-sn-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 8px 10px; border-radius: 12px; background: rgba(243, 244, 246, 0.72); border: 1px solid rgba(229, 231, 235, 0.9); }
	.main-sn-value { font-size: 12px; color: var(--text-primary); flex: 1; min-width: 0; word-break: break-all; }
	.main-sn-status { font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 999px; white-space: nowrap; }
	.status-returnable { color: #15803d; background: rgba(34, 197, 94, 0.12); border: 1px solid rgba(34, 197, 94, 0.22); }
	.status-already_requested { color: #475569; background: rgba(148, 163, 184, 0.10); border: 1px solid rgba(148, 163, 184, 0.18); }
	.status-missing_sn { color: #b45309; background: rgba(245, 158, 11, 0.14); border: 1px solid rgba(245, 158, 11, 0.22); }
	.main-sn-more { font-size: 11px; color: var(--text-secondary); text-align: center; }
	.main-sn-empty { margin-bottom: 10px; font-size: 12px; color: var(--text-secondary); }

	.aux-list { display: grid; gap: 10px; }
	.aux-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
	.aux-left { flex: 1; min-width: 0; }
	.aux-name { display: block; font-size: 13px; font-weight: 800; color: var(--text-primary); }
	.aux-meta { display: block; margin-top: 4px; font-size: 11px; color: var(--text-secondary); }

	.stepper { display: flex; align-items: center; gap: 10px; }
	.step { width: 34px; height: 34px; border-radius: 12px; background: #f3f4f6; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 900; color: #111827; }
	.num { width: 42px; text-align: center; font-size: 14px; font-weight: 900; color: var(--text-primary); }

	.footer { margin: 16px; }
	.spacer { height: 24px; }
	.mono { font-family: monospace; }

	.bind-modal-mask {
		position: fixed;
		left: 0;
		top: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.45);
		display: flex;
		align-items: flex-end;
		justify-content: center;
		z-index: 999;
	}
	.bind-modal {
		width: 100%;
		max-height: 78vh;
		background: #fff;
		border-top-left-radius: 18px;
		border-top-right-radius: 18px;
		overflow: hidden;
		box-shadow: 0 -12px 30px rgba(17, 24, 39, 0.16);
	}
	.bind-modal-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 14px 16px;
		border-bottom: 1px solid rgba(229, 231, 235, 0.9);
	}
	.bind-modal-title { font-size: 14px; font-weight: 900; color: var(--text-primary); }
	.bind-modal-close { font-size: 22px; color: #6b7280; padding: 2px 6px; }
	.bind-modal-body { padding: 12px 16px 6px; }
	.bind-modal-desc { font-size: 12px; color: var(--text-secondary); line-height: 1.5; }

	.bind-list { margin-top: 12px; max-height: 40vh; }
	.bind-item { padding: 10px 12px; border-radius: 14px; background: rgba(243, 244, 246, 0.7); border: 1px solid rgba(229, 231, 235, 0.95); margin-bottom: 10px; }
	.bind-item-row { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
	.bind-sn { font-size: 12px; font-weight: 900; color: var(--text-primary); }
	.bind-title { flex: 1; min-width: 0; text-align: right; font-size: 12px; color: var(--text-primary); }
	.bind-sub { margin-top: 6px; font-size: 11px; color: var(--text-secondary); }
	.bind-reason { margin-top: 6px; font-size: 11px; color: #ef4444; }

	.bind-modal-footer { padding: 12px 16px 16px; display: flex; gap: 10px; }
	.bind-modal-footer .u-btn { flex: 1; }
</style>
