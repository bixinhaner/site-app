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

			<view class="footer">
				<button class="u-btn u-btn-primary u-pressable" :disabled="submitting" @click="submit">
					{{ submitting ? $t('stock.processing') : $t('stock.submitReturnRequest') }}
				</button>
			</view>

			<view class="spacer" />
		</scroll-view>
	</view>
</template>

<script setup>
	import { computed, getCurrentInstance, onMounted, ref, watch } from 'vue'
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

	const submit = async () => {
		if (!selectedOut.value?.id) {
			uni.showToast({ title: $t('stock.selectStockOut'), icon: 'none' })
			return
		}
		if (!selectedWarehouse.value) {
			uni.showToast({ title: $t('stock.selectReturnWarehouse'), icon: 'none' })
			return
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
			return
		}

		try {
			submitting.value = true
			const res = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.STOCK.CREATE_RETURN),
				...createRequestConfig({
					method: 'POST',
					headers: getAuthHeaders(userStore.token),
					data: {
						out_transaction_id: selectedOut.value.id,
						return_warehouse_id: selectedWarehouse.value.id,
						main_sns: selectedMainSns.value,
						aux_items: auxItemsPayload,
					}
				})
			})

			if (res.statusCode === 200) {
				uni.showToast({ title: $t('stock.createReturnSuccess'), icon: 'success' })
				setTimeout(() => {
					uni.redirectTo({ url: '/pages/stock/returns/list' })
				}, 500)
				return
			}

			if (res.statusCode === 401) {
				userStore.logout()
				return
			}
			uni.showToast({ title: String(res.data?.detail || res.data?.message || $t('messages.operationFailed')), icon: 'none' })
		} catch (e) {
			console.error('提交退库失败:', e)
			uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
		} finally {
			submitting.value = false
		}
	}

	watch(() => selectedOut.value?.id, () => {
		selectedMainSns.value = []
	})

	onMounted(async () => {
		await loadWarehouses()
		await loadOuts(true)
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
</style>

