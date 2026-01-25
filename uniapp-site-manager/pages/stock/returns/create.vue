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
							<text class="block-sub">{{ $t('stock.scanAddMainDevice') }}</text>
						</view>
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

			const inOut = (selectedOut.value.items || []).some(it => it?.is_main_device && it?.serial_number === value && Number(it?.max_returnable || 0) > 0)
			if (!inOut) {
				uni.showToast({ title: $t('stock.deviceNotInInventoryTitle'), icon: 'none' })
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

	const doSubmit = async () => {
		const payload = buildSubmitPayload()
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
				setTimeout(() => uni.redirectTo({ url: '/pages/stock/returns/list' }), 500)
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
		await doSubmit()
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
		if (!value || !selectedOut.value) return false
		const exist = selectedMainSns.value.includes(value)
		if (exist) return true
		const inOut = (selectedOut.value.items || []).some(it => it?.is_main_device && it?.serial_number === value && Number(it?.max_returnable || 0) > 0)
		if (!inOut) return false
		selectedMainSns.value = selectedMainSns.value.concat([value])
		return true
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
		if (!picked) {
			uni.showToast({ title: $t('stock.deviceNotInInventoryTitle'), icon: 'none' })
		}
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
