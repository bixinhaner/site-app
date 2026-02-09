<template>
	<view class="page" :key="languageStore.currentLocale">
		<CustomNavbar :title="pageTitle" :showBack="true" variant="brand" />

		<scroll-view
			class="content"
			scroll-y
			refresher-enabled
			:refresher-triggered="refreshing"
			@refresherrefresh="handleRefresh"
			refresher-background="#f7f8fb"
		>
			<view class="hero u-card">
				<view class="hero-top">
					<view class="hero-left">
						<text class="hero-title">{{ isEdit ? $t('stock.materialRequestEditTitle') : $t('stock.materialRequestCreateTitle') }}</text>
						<text class="hero-sub">{{ $t('stock.materialRequestCreateSub') }}</text>
					</view>
					<view class="badge" v-if="isEdit && requestNo">
						<text class="badge-k">{{ $t('stock.materialRequestNo') }}</text>
						<text class="badge-v mono">{{ requestNo }}</text>
					</view>
				</view>

				<view class="form">
					<view class="u-form-item">
						<text class="u-form-label">{{ $t('stock.materialRequestWarehouse') }}</text>
						<picker @change="onWarehouseChange" :value="warehouseIndex" :range="warehouseOptions">
							<view class="picker-input" :class="{ placeholder: !selectedWarehouse }">
								<text>{{ selectedWarehouse ? selectedWarehouse.warehouse_name : $t('common.pleaseSelect') }}</text>
								<text class="picker-arrow">▼</text>
							</view>
						</picker>
					</view>

					<view class="u-form-item">
						<text class="u-form-label">{{ $t('stock.materialRequestNotes') }}</text>
						<textarea
							class="u-textarea notes-textarea"
							v-model="notes"
							:placeholder="$t('stock.materialRequestNotesPlaceholder')"
							maxlength="200"
						/>
						<text class="u-form-help">{{ $t('stock.materialRequestNotesHelp') }}</text>
					</view>
				</view>
			</view>

			<view class="section u-card">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.materialRequestQuickFill') }}</text>
					<text class="hint">{{ $t('stock.materialRequestQuickFillHint') }}</text>
				</view>
				<view class="u-card-content">
					<view class="quick-grid">
						<view class="field">
							<text class="label">{{ $t('stock.packageLabel') }}</text>
							<picker @change="onPackageChange" :value="packageIndex" :range="packageOptions">
								<view class="picker-input" :class="{ placeholder: !selectedPackage }">
									<text>{{ selectedPackage ? selectedPackage.package_name : $t('common.optional') }}</text>
									<text class="picker-arrow">▼</text>
								</view>
							</picker>
						</view>

						<view class="field">
							<text class="label">{{ $t('stock.materialRequestPackageCount') }}</text>
							<view class="stepper">
								<view class="step u-pressable" @click="decPackageCount">−</view>
								<text class="num mono">{{ packageCount }}</text>
								<view class="step u-pressable" @click="incPackageCount">＋</view>
							</view>
						</view>
					</view>

					<view class="preview" v-if="selectedPackage">
						<view class="u-chip">{{ $t('stock.materialRequestPackagePreviewMain') }} × {{ packageCount }}</view>
						<view class="u-chip">{{ $t('stock.materialRequestPackagePreviewAuxLines') }} {{ (selectedPackage.items || []).length }}</view>
					</view>

					<button class="u-btn u-btn-secondary u-btn-sm u-pressable" :disabled="!selectedPackage" @click="applyPackage">
						{{ $t('common.apply') }}
					</button>
				</view>
			</view>

			<view class="section u-card">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.materialRequestItems') }}</text>
					<view class="header-actions">
						<view class="mini-chip">{{ $t('stock.materialRequestItemsCount', { count: items.length }) }}</view>
						<button class="u-btn u-btn-primary u-btn-sm u-pressable" @click="openEquipmentPicker">
							{{ $t('common.add') }}
						</button>
					</view>
				</view>
				<view class="u-card-content">
					<view v-if="items.length === 0" class="empty-items">
						<text class="empty-text">{{ $t('stock.materialRequestItemsEmpty') }}</text>
						<button class="u-btn u-btn-secondary u-btn-sm u-pressable" @click="openEquipmentPicker">
							{{ $t('stock.materialRequestAddItem') }}
						</button>
					</view>

					<view v-else class="items">
						<view class="item" v-for="(it, idx) in items" :key="it.equipment_id">
							<view class="row">
								<view class="info">
									<view class="name-line">
										<text class="name">{{ it.equipment_name }}</text>
										<view class="u-tag" :class="it.equipment_category === 'main_device' ? 'u-tag-warning' : 'u-tag-info'">
											{{ it.equipment_category === 'main_device' ? $t('stock.mainDevice') : $t('stock.auxMaterial') }}
										</view>
									</view>
									<text class="code mono">{{ it.equipment_code }}</text>
								</view>
								<view class="actions">
									<view class="qty">
										<view class="qbtn u-pressable" @click="decQty(idx)">−</view>
										<input class="qinput mono" type="number" v-model="it.requested_qty" @blur="normalizeQty(idx)" />
										<view class="qbtn u-pressable" @click="incQty(idx)">＋</view>
									</view>
									<view class="remove u-pressable" @click="removeItem(idx)">
										<uni-icons type="trash" size="18" color="#ef4444" />
									</view>
								</view>
							</view>
						</view>
					</view>
				</view>
			</view>

			<view class="bottom-spacer" />
		</scroll-view>

		<view class="bottom-bar">
			<button class="u-btn u-btn-secondary u-pressable" :disabled="submitting" @click="saveDraft">
				{{ submitting ? $t('common.loading') : $t('common.save') }}
			</button>
			<button class="u-btn u-btn-primary u-pressable" :disabled="submitting" @click="submitRequest">
				{{ $t('common.submit') }}
			</button>
		</view>

		<!-- 物料选择弹窗 -->
		<view class="modal-mask" v-if="equipPickerVisible" @click="closeEquipmentPicker">
			<view class="modal" @click.stop>
				<view class="modal-head">
					<text class="modal-title">{{ $t('stock.materialRequestSelectEquipment') }}</text>
					<view class="modal-close u-pressable" @click="closeEquipmentPicker">
						<uni-icons type="closeempty" size="22" color="#6b7280" />
					</view>
				</view>

				<view class="modal-search">
					<uni-icons type="search" size="18" color="#6b7280" />
					<input
						class="modal-search-input"
						v-model="equipKeyword"
						:placeholder="$t('stock.materialRequestEquipSearchPlaceholder')"
						@input="noop"
					/>
					<uni-icons v-if="equipKeyword" type="clear" size="18" color="#9ca3af" @click="equipKeyword = ''" />
				</view>

				<view class="modal-tabs">
					<view class="tab u-pressable" :class="{ active: equipCategory === 'all' }" @click="equipCategory = 'all'">
						{{ $t('common.all') }}
					</view>
					<view class="tab u-pressable" :class="{ active: equipCategory === 'main_device' }" @click="equipCategory = 'main_device'">
						{{ $t('stock.mainDevice') }}
					</view>
					<view class="tab u-pressable" :class="{ active: equipCategory === 'auxiliary' }" @click="equipCategory = 'auxiliary'">
						{{ $t('stock.auxMaterial') }}
					</view>
				</view>

				<scroll-view class="modal-list" scroll-y>
					<view
						v-for="eq in filteredEquipments"
						:key="eq.id"
						class="eq-row u-pressable-subtle"
						@click="pickEquipment(eq)"
					>
						<view class="eq-left">
							<text class="eq-name">{{ eq.equipment_name }}</text>
							<text class="eq-code mono">{{ eq.equipment_code }}</text>
						</view>
						<view class="eq-right">
							<view class="u-tag" :class="eq.category === 'main_device' ? 'u-tag-warning' : 'u-tag-info'">
								{{ eq.category === 'main_device' ? $t('stock.mainDevice') : $t('stock.auxMaterial') }}
							</view>
							<text class="eq-arrow">›</text>
						</view>
					</view>
					<view v-if="filteredEquipments.length === 0" class="modal-empty">
						<text class="modal-empty-text">{{ $t('messages.noSearchResults') }}</text>
					</view>
				</scroll-view>
			</view>
		</view>
	</view>
</template>

<script setup>
	import { computed, getCurrentInstance, onMounted, reactive, ref } from 'vue'
	import { onLoad } from '@dcloudio/uni-app'
	import { useUserStore } from '@/stores/user'
	import { useLanguageStore } from '@/stores/language'
	import { buildApiUrl, API_ENDPOINTS, createRequestConfig, getAuthHeaders } from '@/config/api.js'
	import CustomNavbar from '@/components/CustomNavbar.vue'

	const userStore = useUserStore()
	const languageStore = useLanguageStore()
	const { $t } = getCurrentInstance().appContext.config.globalProperties

	const requestId = ref('')
	const requestNo = ref('')
	const isEdit = computed(() => !!requestId.value)
	const pageTitle = computed(() => isEdit.value ? $t('stock.materialRequestEditTitle') : $t('stock.materialRequestCreateTitle'))

	const refreshing = ref(false)
	const submitting = ref(false)

	const warehouses = ref([])
	const warehouseIndex = ref(0)
	const warehouseOptions = computed(() => (warehouses.value || []).map(w => w.warehouse_name))
	const selectedWarehouse = computed(() => warehouses.value?.[warehouseIndex.value] || null)

	const notes = ref('')

	const packages = ref([])
	const packageIndex = ref(0)
	const packageOptions = computed(() => (packages.value || []).map(p => p.package_name))
	const selectedPackage = computed(() => packages.value?.[packageIndex.value] || null)
	const packageCount = ref(1)

	const equipments = ref([])
	const items = ref([])

	// equipment picker
	const equipPickerVisible = ref(false)
	const equipKeyword = ref('')
	const equipCategory = ref('all') // all | main_device | auxiliary

	const filteredEquipments = computed(() => {
		const kw = String(equipKeyword.value || '').trim().toLowerCase()
		const cat = String(equipCategory.value || 'all')
		return (equipments.value || []).filter(eq => {
			if (cat !== 'all' && String(eq.category) !== cat) return false
			if (!kw) return true
			const hay = `${eq.equipment_name || ''} ${eq.equipment_code || ''}`.toLowerCase()
			return hay.includes(kw)
		})
	})

	const noop = () => {}

	const extractErrorMessage = (data, fallback = '') => {
		const detail = data?.detail
		if (!detail) return fallback || $t('messages.operationFailed')
		if (typeof detail === 'string') return detail
		return detail?.message || fallback || $t('messages.operationFailed')
	}

	const filterActivePackages = (source) => {
		const list = Array.isArray(source) ? source : []
		return list.filter((pkg) => {
			const status = String(pkg?.status || '').trim().toLowerCase()
			if (!status) return true
			return status === 'active'
		})
	}

	const ensureLoggedIn = () => {
		if (!userStore.isLoggedIn) {
			uni.reLaunch({ url: '/pages/login/login' })
			return false
		}
		if (userStore.isSurveyor) {
			uni.showToast({ title: $t('stock.surveyorNoPermission'), icon: 'none' })
			setTimeout(() => uni.navigateBack(), 600)
			return false
		}
		return true
	}

	const loadWarehouses = async () => {
		const res = await uni.request({
			url: buildApiUrl('/api/stock/warehouses'),
			method: 'GET',
			header: getAuthHeaders(userStore.token),
		})
		if (res.statusCode === 200) {
			warehouses.value = res.data?.warehouses || []
			return
		}
		if (res.statusCode === 401) userStore.logout()
	}

	const loadPackages = async () => {
		const res = await uni.request({
			url: buildApiUrl(`${API_ENDPOINTS.EQUIPMENT.PACKAGES}?status=active`),
			method: 'GET',
			header: getAuthHeaders(userStore.token),
		})
		if (res.statusCode === 200) {
			packages.value = filterActivePackages(res.data)
			if (packageIndex.value >= packages.value.length) packageIndex.value = 0
			return
		}
		if (res.statusCode === 401) userStore.logout()
	}

	const loadEquipments = async () => {
		let url = buildApiUrl(API_ENDPOINTS.EQUIPMENT.LIST)
		const params = ['limit=300']
		params.push('status=active')
		url += `?${params.join('&')}`

		const res = await uni.request({
			url,
			...createRequestConfig({
				method: 'GET',
				headers: getAuthHeaders(userStore.token),
			})
		})
		if (res.statusCode === 200) {
			equipments.value = Array.isArray(res.data) ? res.data : []
			return
		}
		if (res.statusCode === 401) userStore.logout()
	}

	const loadRequest = async (id) => {
		const res = await uni.request({
			url: buildApiUrl(API_ENDPOINTS.STOCK.MATERIAL_REQUEST_DETAIL(id)),
			method: 'GET',
			header: getAuthHeaders(userStore.token),
		})
		if (res.statusCode === 200 && res.data?.request) {
			const r = res.data.request
			requestId.value = r.id
			requestNo.value = r.request_no
			notes.value = r.notes || ''

			// 选中仓库
			const idx = (warehouses.value || []).findIndex(w => w.id === r.warehouse_id)
			warehouseIndex.value = idx >= 0 ? idx : 0

			// 仅允许编辑草稿
			if (String(r.status) !== 'draft') {
				uni.showToast({ title: $t('stock.materialRequestNotEditable'), icon: 'none' })
				setTimeout(() => {
					uni.redirectTo({ url: `/pages/stock/material-requests/detail?id=${r.id}` })
				}, 600)
				return
			}

			items.value = (r.items || []).map(it => ({
				equipment_id: it.equipment_id,
				equipment_name: it.equipment_name,
				equipment_code: it.equipment_code,
				equipment_category: it.equipment_category,
				unit: it.unit,
				requested_qty: Number(it.requested_qty || 0) || 1,
			}))
			return
		}
		if (res.statusCode === 401) {
			userStore.logout()
			return
		}
		uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
	}

	const handleRefresh = async () => {
		if (!ensureLoggedIn()) return
		refreshing.value = true
		try {
			await Promise.all([loadWarehouses(), loadPackages(), loadEquipments()])
			if (requestId.value) await loadRequest(requestId.value)
		} finally {
			refreshing.value = false
		}
	}

	const onWarehouseChange = (e) => {
		warehouseIndex.value = Number(e.detail.value || 0)
	}

	const onPackageChange = (e) => {
		packageIndex.value = Number(e.detail.value || 0)
	}

	const incPackageCount = () => {
		packageCount.value = Math.min(999, Number(packageCount.value || 1) + 1)
	}

	const decPackageCount = () => {
		packageCount.value = Math.max(1, Number(packageCount.value || 1) - 1)
	}

	const openEquipmentPicker = () => {
		equipPickerVisible.value = true
		equipKeyword.value = ''
		equipCategory.value = 'all'
	}

	const closeEquipmentPicker = () => {
		equipPickerVisible.value = false
	}

	const pickEquipment = (eq) => {
		const equipmentId = Number(eq?.id)
		if (!equipmentId) return

		const hitIdx = (items.value || []).findIndex(it => Number(it.equipment_id) === equipmentId)
		if (hitIdx >= 0) {
			items.value[hitIdx].requested_qty = Number(items.value[hitIdx].requested_qty || 0) + 1
		} else {
			items.value.push({
				equipment_id: equipmentId,
				equipment_name: eq.equipment_name,
				equipment_code: eq.equipment_code,
				equipment_category: eq.category,
				unit: eq.unit,
				requested_qty: 1,
			})
		}
		closeEquipmentPicker()
	}

	const normalizeQty = (idx) => {
		const it = items.value?.[idx]
		if (!it) return
		let n = Number(String(it.requested_qty || '').trim())
		if (!Number.isFinite(n) || n <= 0) n = 1
		if (n > 99999) n = 99999
		it.requested_qty = Math.floor(n)
	}

	const incQty = (idx) => {
		const it = items.value?.[idx]
		if (!it) return
		it.requested_qty = Math.min(99999, Number(it.requested_qty || 1) + 1)
	}

	const decQty = (idx) => {
		const it = items.value?.[idx]
		if (!it) return
		it.requested_qty = Math.max(1, Number(it.requested_qty || 1) - 1)
	}

	const removeItem = (idx) => {
		items.value.splice(idx, 1)
	}

	const applyPackage = () => {
		const pkg = selectedPackage.value
		if (!pkg) return
		const count = Math.max(1, Number(packageCount.value || 1))
		const pkgItems = Array.isArray(pkg.items) ? pkg.items : []

		for (const pi of pkgItems) {
			const equipmentId = Number(pi?.equipment_id)
			if (!equipmentId) continue
			const addQty = Math.max(0, Number(pi?.quantity || 0)) * count
			if (addQty <= 0) continue

			const hitIdx = (items.value || []).findIndex(it => Number(it.equipment_id) === equipmentId)
			if (hitIdx >= 0) {
				items.value[hitIdx].requested_qty = Number(items.value[hitIdx].requested_qty || 0) + addQty
				continue
			}
			items.value.push({
				equipment_id: equipmentId,
				equipment_name: pi.equipment_name,
				equipment_code: pi.equipment_code,
				equipment_category: pi.category,
				unit: pi.unit,
				requested_qty: addQty,
			})
		}

		uni.showToast({ title: $t('stock.materialRequestPackageApplied'), icon: 'success' })
	}

	const buildPayloadItems = () => {
		return (items.value || [])
			.map(it => ({
				equipment_id: Number(it.equipment_id),
				quantity: Number(it.requested_qty || 0),
			}))
			.filter(it => it.equipment_id && it.quantity > 0)
	}

	const validateForm = () => {
		if (!selectedWarehouse.value?.id) {
			uni.showToast({ title: $t('stock.materialRequestWarehouseRequired'), icon: 'none' })
			return false
		}
		const payloadItems = buildPayloadItems()
		if (payloadItems.length === 0) {
			uni.showToast({ title: $t('stock.materialRequestItemsRequired'), icon: 'none' })
			return false
		}
		return true
	}

	const saveDraft = async () => {
		if (!ensureLoggedIn()) return
		if (!validateForm()) return

		submitting.value = true
		try {
			const payload = {
				warehouse_id: Number(selectedWarehouse.value.id),
				notes: String(notes.value || '').trim(),
				items: buildPayloadItems(),
			}

			let res
			if (requestId.value) {
				res = await uni.request({
					url: buildApiUrl(API_ENDPOINTS.STOCK.MATERIAL_REQUEST_DETAIL(requestId.value)),
					method: 'PATCH',
					header: getAuthHeaders(userStore.token),
					data: payload,
				})
			} else {
				res = await uni.request({
					url: buildApiUrl(API_ENDPOINTS.STOCK.MATERIAL_REQUESTS),
					method: 'POST',
					header: getAuthHeaders(userStore.token),
					data: payload,
				})
			}

			if (res.statusCode === 200 && res.data?.request) {
				requestId.value = res.data.request.id
				requestNo.value = res.data.request.request_no
				uni.showToast({ title: $t('stock.materialRequestSaved'), icon: 'success' })
				return true
			}
			if (res.statusCode === 401) {
				userStore.logout()
				return false
			}
			uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
			return false
		} catch (e) {
			console.error('保存申请失败:', e)
			uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
			return false
		} finally {
			submitting.value = false
		}
	}

	const submitRequest = async () => {
		if (!ensureLoggedIn()) return
		if (!validateForm()) return

		uni.showModal({
			title: $t('common.confirm'),
			content: $t('stock.materialRequestSubmitConfirm'),
			success: async (modalRes) => {
				if (!modalRes.confirm) return

				const saved = await saveDraft()
				if (!saved || !requestId.value) return

				submitting.value = true
				try {
					const res = await uni.request({
						url: buildApiUrl(API_ENDPOINTS.STOCK.MATERIAL_REQUEST_SUBMIT(requestId.value)),
						method: 'POST',
						header: getAuthHeaders(userStore.token),
					})

					if (res.statusCode === 200 && res.data?.request) {
						uni.showToast({ title: $t('stock.materialRequestSubmitted'), icon: 'success' })
						setTimeout(() => {
							uni.redirectTo({ url: `/pages/stock/material-requests/detail?id=${requestId.value}` })
						}, 600)
						return
					}
					if (res.statusCode === 401) {
						userStore.logout()
						return
					}
					uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
				} catch (e) {
					console.error('提交申请失败:', e)
					uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
				} finally {
					submitting.value = false
				}
			}
		})
	}

	onLoad((query) => {
		const id = String(query?.id || '').trim()
		if (id) requestId.value = id
	})

	onMounted(async () => {
		if (!ensureLoggedIn()) return
		await Promise.all([loadWarehouses(), loadPackages(), loadEquipments()])
		if (requestId.value) await loadRequest(requestId.value)
	})
</script>

<style scoped lang="scss">
	.page {
		min-height: 100vh;
		background: var(--bg-page);
	}
	.content {
		height: calc(100vh - 88rpx - var(--status-bar-height, 0px));
	}

	.hero {
		margin: 16px;
		border-radius: var(--radius-lg);
		position: relative;
		background:
			radial-gradient(920px 260px at 10% 0%, rgba(var(--color-primary-rgb), 0.16), transparent 62%),
			radial-gradient(920px 260px at 90% 10%, rgba(var(--color-brand-blue-rgb), 0.10), transparent 62%),
			linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(255, 255, 255, 0.90));
		border: 1px solid rgba(229, 231, 235, 0.9);
		box-shadow: 0 10px 26px rgba(17, 24, 39, 0.08);
	}

	.hero-top {
		padding: 16px 16px 10px;
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 12px;
	}
	.hero-left { display: flex; flex-direction: column; gap: 6px; }
	.hero-title { font-size: 16px; font-weight: 800; color: #111827; }
	.hero-sub { font-size: 12px; color: var(--text-secondary); line-height: 1.5; }

	.badge {
		padding: 10px 12px;
		border-radius: 14px;
		border: 1px solid rgba(255, 255, 255, 0.75);
		background: rgba(255, 255, 255, 0.72);
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.badge-k { font-size: 11px; color: #6b7280; }
	.badge-v { font-size: 12px; color: #111827; font-weight: 800; }
	.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; }

	.form { padding: 0 16px 16px; }

	.picker-input {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 10px;
		padding: 10px 12px;
		min-height: 44px;
		box-sizing: border-box;
		border: 1px solid var(--border-color);
		border-radius: 10px;
		background: rgba(255, 255, 255, 0.72);
		color: #111827;
		font-size: 14px;
		line-height: 20px;
	}
	.picker-input.placeholder { color: #9ca3af; }
	.picker-arrow { color: #9ca3af; font-size: 10px; }

	.notes-textarea {
		height: 64px;
		min-height: 64px;
		font-size: 14px;
		line-height: 20px;
		padding: 12px 12px;
		box-sizing: border-box;
		resize: none;
	}

	.section { margin: 16px; border-radius: var(--radius-lg); overflow: hidden; }
	.hint { font-size: 12px; color: #9ca3af; }

	.quick-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
		margin-bottom: 12px;
	}
	.field { display: flex; flex-direction: column; gap: 8px; }
	.label { font-size: 12px; color: #6b7280; }

	.stepper {
		display: flex;
		align-items: center;
		justify-content: space-between;
		border: 1px solid var(--border-color);
		border-radius: 12px;
		background: rgba(255, 255, 255, 0.72);
		padding: 8px 10px;
	}
	.step { width: 36px; height: 36px; border-radius: 10px; background: #f3f4f6; color: #111827; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 700; }
	.num { font-size: 14px; font-weight: 800; color: #111827; }

	.preview { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; }

	.header-actions { display: flex; align-items: center; gap: 10px; }
	.mini-chip {
		font-size: 12px;
		color: #6b7280;
		background: #f3f4f6;
		padding: 6px 10px;
		border-radius: 999px;
		border: 1px solid rgba(229, 231, 235, 0.9);
	}

	.empty-items {
		padding: 14px 0 6px;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 12px;
	}
	.empty-text { color: #6b7280; font-size: 13px; }

	.items { display: flex; flex-direction: column; gap: 12px; }
	.item {
		border: 1px solid rgba(229, 231, 235, 0.9);
		background: #fff;
		border-radius: 14px;
		padding: 12px;
	}
	.row { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
	.info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
	.name-line { display: flex; align-items: center; gap: 10px; min-width: 0; }
	.name { font-size: 14px; font-weight: 700; color: #111827; max-width: 320rpx; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.code { font-size: 12px; color: #9ca3af; }

	.actions { display: flex; align-items: center; gap: 10px; }
	.qty {
		display: flex;
		align-items: center;
		border: 1px solid rgba(229, 231, 235, 0.9);
		border-radius: 12px;
		overflow: hidden;
		background: #f9fafb;
	}
	.qbtn {
		width: 38px;
		height: 38px;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 18px;
		font-weight: 700;
		color: #111827;
		background: #f3f4f6;
	}
	.qinput {
		width: 64px;
		height: 38px;
		text-align: center;
		font-size: 14px;
		font-weight: 800;
		color: #111827;
	}
	.remove { width: 38px; height: 38px; border-radius: 12px; display: flex; align-items: center; justify-content: center; background: rgba(239, 68, 68, 0.10); }

	.bottom-spacer { height: 92px; }
	.bottom-bar {
		position: fixed;
		left: 0;
		right: 0;
		bottom: 0;
		padding: 10px 16px 16px;
		background: rgba(247, 248, 251, 0.90);
		backdrop-filter: blur(10px);
		border-top: 1px solid rgba(229, 231, 235, 0.9);
		display: grid;
		grid-template-columns: 1fr 1.1fr;
		gap: 12px;
	}

	.modal-mask {
		position: fixed;
		left: 0;
		top: 0;
		right: 0;
		bottom: 0;
		background: rgba(17, 24, 39, 0.46);
		display: flex;
		align-items: flex-end;
		justify-content: center;
		z-index: 999;
	}
	.modal {
		width: 100%;
		max-height: 82vh;
		background: #fff;
		border-top-left-radius: 18px;
		border-top-right-radius: 18px;
		overflow: hidden;
		box-shadow: 0 -18px 50px rgba(0, 0, 0, 0.20);
	}
	.modal-head {
		padding: 14px 16px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		border-bottom: 1px solid rgba(229, 231, 235, 0.9);
	}
	.modal-title { font-size: 15px; font-weight: 800; color: #111827; }
	.modal-close { width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; border-radius: 12px; background: #f3f4f6; }

	.modal-search {
		margin: 12px 16px 10px;
		padding: 10px 12px;
		border: 1px solid rgba(229, 231, 235, 0.9);
		border-radius: 14px;
		background: #f9fafb;
		display: flex;
		align-items: center;
		gap: 10px;
	}
	.modal-search-input { flex: 1; font-size: 13px; color: #111827; }

	.modal-tabs {
		display: flex;
		gap: 10px;
		padding: 0 16px 12px;
	}
	.tab {
		padding: 8px 12px;
		border-radius: 999px;
		border: 1px solid rgba(229, 231, 235, 0.9);
		background: #fff;
		color: #6b7280;
		font-size: 12px;
	}
	.tab.active {
		color: #9a3412;
		border-color: rgba(var(--color-primary-rgb), 0.38);
		background: rgba(var(--color-primary-rgb), 0.10);
		font-weight: 700;
	}

	.modal-list { max-height: 56vh; padding: 0 8px 16px; }
	.eq-row {
		padding: 12px 10px;
		margin: 8px;
		border-radius: 14px;
		border: 1px solid rgba(229, 231, 235, 0.9);
		background: #fff;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}
	.eq-left { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
	.eq-name { font-size: 14px; font-weight: 700; color: #111827; }
	.eq-code { font-size: 12px; color: #9ca3af; }
	.eq-right { display: flex; align-items: center; gap: 10px; }
	.eq-arrow { color: #9ca3af; font-size: 18px; line-height: 1; }

	.modal-empty { padding: 18px; display: flex; justify-content: center; }
	.modal-empty-text { color: #9ca3af; font-size: 13px; }
</style>
