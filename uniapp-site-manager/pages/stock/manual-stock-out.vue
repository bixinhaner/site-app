<template>
	<view class="page" :key="languageStore.currentLocale">
		<CustomNavbar :title="$t('stock.manualStockOutTitle')" :showBack="true" variant="brand" />

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
					<view class="left">
						<text class="hero-title">{{ $t('stock.manualStockOutHeroTitle') }}</text>
						<text class="hero-sub">{{ $t('stock.manualStockOutHeroSub') }}</text>
					</view>
					<view class="right">
						<view class="pill">
							<text class="k">{{ $t('stock.manualStockOutSnCount') }}</text>
							<text class="v mono">{{ snList.length }}</text>
						</view>
						<view class="pill">
							<text class="k">{{ $t('stock.manualStockOutAuxTotal') }}</text>
							<text class="v mono">{{ auxTotal }}</text>
						</view>
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
						<text class="u-form-label">{{ $t('stock.manualStockOutIssuedTo') }}</text>
						<view class="picker-input u-pressable" :class="{ placeholder: !issuedToUser }" @click="openUserPicker">
							<text>{{ issuedToUser ? `${issuedToUser.full_name || issuedToUser.username}（${issuedToUser.username}）` : $t('common.pleaseSelect') }}</text>
							<text class="picker-arrow">▼</text>
						</view>
					</view>

					<view class="u-form-item">
						<text class="u-form-label">{{ $t('stock.materialRequestNotes') }}</text>
						<textarea class="u-textarea" v-model="notes" :placeholder="$t('stock.manualStockOutNotesPlaceholder')" maxlength="200" />
					</view>
				</view>
			</view>

			<view class="section u-card">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.manualStockOutMainDevices') }}</text>
					<view class="header-actions">
						<button class="u-btn u-btn-primary u-btn-sm u-pressable" :disabled="submitting" @click="scanByCamera">
							{{ $t('stock.issueDraftScan') }}
						</button>
						<button class="u-btn u-btn-secondary u-btn-sm u-pressable" :disabled="submitting || snList.length === 0" @click="clearSns">
							{{ $t('common.clear') }}
						</button>
					</view>
				</view>
				<view class="u-card-content">
					<view class="scanner">
						<view class="scanner-row">
							<input
								class="u-input scanner-input mono"
								v-model="snInput"
								:placeholder="$t('stock.issueDraftScanInputPlaceholder')"
								confirm-type="done"
								@confirm="addSnFromInput"
								:disabled="submitting"
							/>
							<button class="u-btn u-btn-secondary u-btn-sm u-pressable" :disabled="submitting || !snInput" @click="addSnFromInput">
								{{ $t('common.add') }}
							</button>
						</view>
						<text class="scanner-help">{{ $t('stock.manualStockOutSnHelp') }}</text>
					</view>

					<view class="sn-tags">
						<view v-if="snList.length === 0" class="empty">
							<text class="empty-text">{{ $t('stock.issueDraftNoSn') }}</text>
						</view>
						<view v-else class="tags">
							<view class="tag mono" v-for="sn in snList" :key="sn">
								<text class="tag-text">{{ sn }}</text>
								<view class="tag-close u-pressable" @click="removeSn(sn)">
									<uni-icons type="closeempty" size="16" color="#fff" />
								</view>
							</view>
						</view>
					</view>
				</view>
			</view>

			<view class="section u-card">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.manualStockOutAuxMaterials') }}</text>
					<view class="header-actions">
						<button class="u-btn u-btn-primary u-btn-sm u-pressable" :disabled="submitting" @click="openAuxPicker">
							{{ $t('common.add') }}
						</button>
						<button class="u-btn u-btn-secondary u-btn-sm u-pressable" :disabled="submitting || auxRows.length === 0" @click="clearAux">
							{{ $t('common.clear') }}
						</button>
					</view>
				</view>
				<view class="u-card-content">
					<view v-if="auxRows.length === 0" class="empty">
						<text class="empty-text">{{ $t('stock.manualStockOutAuxEmpty') }}</text>
					</view>
					<view v-else class="aux-list">
						<view class="aux" v-for="(a, idx) in auxRows" :key="a.equipment_id">
							<view class="aux-head">
								<view class="left">
									<text class="name">{{ a.equipment_name }}</text>
									<text class="code mono">{{ a.equipment_code }}</text>
								</view>
								<view class="right">
									<view class="u-tag u-tag-info">{{ displayUnit(a.unit) || '-' }}</view>
								</view>
							</view>

							<view class="aux-actions">
								<view class="qty">
									<view class="qbtn u-pressable" @click="decAux(idx)">−</view>
									<input class="qinput mono" type="number" v-model="a.quantity" @blur="normalizeAux(idx)" />
									<view class="qbtn u-pressable" @click="incAux(idx)">＋</view>
								</view>
								<view class="remove u-pressable" @click="removeAux(idx)">
									<uni-icons type="closeempty" size="18" color="#ef4444" />
								</view>
							</view>
						</view>
					</view>

					<view class="aux-total">
						<text class="k">{{ $t('stock.manualStockOutAuxTotal') }}</text>
						<text class="v mono">{{ auxTotal }}</text>
					</view>
				</view>
			</view>

			<view class="section u-card">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.offlineDocTitle') }}</text>
					<text class="hint">{{ $t('common.optional') }}</text>
				</view>
				<view class="u-card-content">
					<OfflineDocumentSection v-model="offlineDocumentId" :disabled="submitting" :showHeader="false" />
				</view>
			</view>

			<view class="bottom-spacer" />
		</scroll-view>

		<view class="bottom-bar">
			<button class="u-btn u-btn-secondary u-pressable" :disabled="submitting" @click="reset">
				{{ $t('common.reset') }}
			</button>
			<button class="u-btn u-btn-primary u-pressable" :disabled="submitting" @click="submit">
				{{ submitting ? $t('common.loading') : $t('stock.manualStockOutSubmit') }}
			</button>
		</view>

		<!-- 选择领取人 -->
		<view class="modal-mask" v-if="userPickerVisible" @click="closeUserPicker">
			<view class="modal" @click.stop>
				<view class="modal-head">
					<text class="modal-title">{{ $t('stock.manualStockOutIssuedTo') }}</text>
					<view class="modal-close u-pressable" @click="closeUserPicker">
						<uni-icons type="closeempty" size="22" color="#6b7280" />
					</view>
				</view>

				<view class="modal-search">
					<uni-icons type="search" size="18" color="#6b7280" />
					<input
						class="modal-search-input"
						v-model="userKeyword"
						:placeholder="$t('stock.manualStockOutUserSearchPlaceholder')"
						@input="onUserKeywordInput"
						confirm-type="search"
						@confirm="searchUsers"
					/>
					<uni-icons v-if="userKeyword" type="clear" size="18" color="#9ca3af" @click="userKeyword = ''" />
				</view>

				<scroll-view class="modal-list" scroll-y>
					<view class="pick-row u-pressable-subtle" v-for="u in userOptions" :key="u.id" @click="selectUser(u)">
						<view class="pick-left">
							<text class="pick-name">{{ u.full_name || u.username }}</text>
							<text class="pick-sub mono">{{ u.username }}</text>
						</view>
						<text class="pick-arrow">›</text>
					</view>
					<view v-if="userLoading" class="modal-empty">
						<text class="modal-empty-text">{{ $t('common.loading') }}</text>
					</view>
					<view v-else-if="userOptions.length === 0" class="modal-empty">
						<text class="modal-empty-text">{{ $t('messages.noSearchResults') }}</text>
					</view>
				</scroll-view>
			</view>
		</view>

		<!-- 辅料选择 -->
		<view class="modal-mask" v-if="auxPickerVisible" @click="closeAuxPicker">
			<view class="modal" @click.stop>
				<view class="modal-head">
					<text class="modal-title">{{ $t('stock.manualStockOutSelectAux') }}</text>
					<view class="modal-close u-pressable" @click="closeAuxPicker">
						<uni-icons type="closeempty" size="22" color="#6b7280" />
					</view>
				</view>

				<view class="modal-search">
					<uni-icons type="search" size="18" color="#6b7280" />
					<input class="modal-search-input" v-model="auxKeyword" :placeholder="$t('stock.materialRequestEquipSearchPlaceholder')" />
					<uni-icons v-if="auxKeyword" type="clear" size="18" color="#9ca3af" @click="auxKeyword = ''" />
				</view>

				<scroll-view class="modal-list" scroll-y>
					<view class="pick-row u-pressable-subtle" v-for="eq in filteredAuxEquipments" :key="eq.id" @click="selectAux(eq)">
						<view class="pick-left">
							<text class="pick-name">{{ eq.equipment_name }}</text>
							<text class="pick-sub mono">{{ eq.equipment_code }}</text>
						</view>
						<text class="pick-arrow">›</text>
					</view>
					<view v-if="filteredAuxEquipments.length === 0" class="modal-empty">
						<text class="modal-empty-text">{{ $t('messages.noSearchResults') }}</text>
					</view>
				</scroll-view>
			</view>
		</view>

		<!-- 库存不足 -->
		<view class="modal-mask" v-if="shortagesVisible" @click="shortagesVisible = false">
			<view class="modal" @click.stop>
				<view class="modal-head">
					<text class="modal-title">{{ $t('stock.insufficientStockTitle') }}</text>
					<view class="modal-close u-pressable" @click="shortagesVisible = false">
						<uni-icons type="closeempty" size="22" color="#6b7280" />
					</view>
				</view>
				<scroll-view class="modal-list" scroll-y>
					<view class="short-row" v-for="(s, idx) in shortages" :key="idx">
						<view class="short-left">
							<text class="pick-name">{{ s.equipment_name }}</text>
							<text class="pick-sub">{{ $t('stock.requiredLabel') }} {{ s.required }} / {{ $t('stock.availableLabel') }} {{ s.available }}</text>
						</view>
						<view class="u-tag u-tag-warning">{{ $t('stock.outOfStock') }}</view>
					</view>
				</scroll-view>
				<view class="modal-foot">
					<button class="u-btn u-btn-primary u-pressable" @click="shortagesVisible = false">{{ $t('common.ok') }}</button>
				</view>
			</view>
		</view>
	</view>
</template>

<script setup>
	import { computed, getCurrentInstance, onMounted, reactive, ref } from 'vue'
	import { onShow } from '@dcloudio/uni-app'
	import { useUserStore } from '@/stores/user'
	import { useLanguageStore } from '@/stores/language'
	import { buildApiUrl, API_ENDPOINTS, createRequestConfig, getAuthHeaders } from '@/config/api.js'
	import { parseBarcode } from '@/utils/barcode-parser.js'
	import { scanAndParseDeviceCode, ScanDeviceCodeError, isScanCanceled } from '@/utils/scan-code.js'
	import { getLocalizedStockUnit } from '@/utils/unit-i18n.js'
	import CustomNavbar from '@/components/CustomNavbar.vue'

	const userStore = useUserStore()
	const languageStore = useLanguageStore()
	const { $t } = getCurrentInstance().appContext.config.globalProperties
	const displayUnit = (unit) => getLocalizedStockUnit(unit, $t)

	const refreshing = ref(false)
	const submitting = ref(false)

	const flowSettings = reactive({
		allow_quick_stock_out: true,
	})

	const warehouses = ref([])
	const warehouseIndex = ref(0)
	const warehouseOptions = computed(() => (warehouses.value || []).map(w => w.warehouse_name))
	const selectedWarehouse = computed(() => warehouses.value?.[warehouseIndex.value] || null)

	const issuedToUser = ref(null)
	const notes = ref('')
	const offlineDocumentId = ref(null)

	const snInput = ref('')
	const snList = ref([])

	const auxRows = ref([]) // { equipment_id, equipment_name, equipment_code, unit, quantity }
	const equipments = ref([])

	// user picker
	const userPickerVisible = ref(false)
	const userKeyword = ref('')
	const userLoading = ref(false)
	const userOptions = ref([])
	let userSearchTimer = null

	// aux picker
	const auxPickerVisible = ref(false)
	const auxKeyword = ref('')

	// shortages
	const shortagesVisible = ref(false)
	const shortages = ref([])

	const auxTotal = computed(() => {
		return (auxRows.value || []).reduce((s, a) => s + Number(a.quantity || 0), 0)
	})

	const filteredAuxEquipments = computed(() => {
		const kw = String(auxKeyword.value || '').trim().toLowerCase()
		return (equipments.value || []).filter(eq => {
			if (String(eq.category) !== 'auxiliary') return false
			if (!kw) return true
			const hay = `${eq.equipment_name || ''} ${eq.equipment_code || ''}`.toLowerCase()
			return hay.includes(kw)
		})
	})

	const extractErrorMessage = (data, fallback = '') => {
		const detail = data?.detail
		if (!detail) return fallback || $t('messages.operationFailed')
		if (typeof detail === 'string') return detail
		return detail?.message || fallback || $t('messages.operationFailed')
	}

	const ensureAccess = async () => {
		if (!userStore.isLoggedIn) {
			uni.reLaunch({ url: '/pages/login/login' })
			return false
		}
		if (!userStore.isWarehouseOperator) {
			uni.showToast({ title: $t('stock.manualStockOutNoPermission'), icon: 'none' })
			setTimeout(() => uni.navigateBack(), 700)
			return false
		}
		if (userStore.isSurveyor) {
			uni.showToast({ title: $t('stock.surveyorNoPermission'), icon: 'none' })
			setTimeout(() => uni.navigateBack(), 700)
			return false
		}

		try {
			const flowRes = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.STOCK.FLOW_SETTINGS),
				method: 'GET',
				header: getAuthHeaders(userStore.token),
			})
			if (flowRes.statusCode === 200 && flowRes.data?.settings) {
				flowSettings.allow_quick_stock_out = flowRes.data.settings.allow_quick_stock_out !== false
			}
		} catch (e) {
			// ignore
		}

		if (!flowSettings.allow_quick_stock_out) {
			uni.showToast({ title: $t('stock.manualStockOutDisabled'), icon: 'none' })
			setTimeout(() => uni.navigateBack(), 700)
			return false
		}
		return true
	}

	const loadWarehouses = async () => {
		const response = await uni.request({
			url: buildApiUrl('/api/stock/warehouses'),
			method: 'GET',
			header: getAuthHeaders(userStore.token),
		})
		if (response.statusCode === 200) {
			warehouses.value = response.data?.warehouses || []
		} else if (response.statusCode === 401) {
			userStore.logout()
		}
	}

	const loadEquipments = async () => {
		let url = buildApiUrl(API_ENDPOINTS.EQUIPMENT.LIST)
		url += '?category=auxiliary&status=active&limit=500'
		const res = await uni.request({
			url,
			...createRequestConfig({
				method: 'GET',
				headers: getAuthHeaders(userStore.token),
			})
		})
		if (res.statusCode === 200) {
			equipments.value = Array.isArray(res.data) ? res.data : []
		} else if (res.statusCode === 401) {
			userStore.logout()
		}
	}

	const onWarehouseChange = (e) => {
		warehouseIndex.value = Number(e.detail.value || 0)
	}

	const scanByCamera = async () => {
		const scanned = await scanAndParseDeviceCode()
		if (!scanned.ok) {
			if (scanned.error === ScanDeviceCodeError.UNSUPPORTED_SCAN_TYPE) {
				uni.showToast({ title: $t('stock.unsupportedScanType', { type: scanned.scanType || 'UNKNOWN' }), icon: 'none' })
				return
			}
			if (scanned.error === ScanDeviceCodeError.EMPTY_RESULT) {
				uni.showToast({ title: $t('stock.scanResultEmpty'), icon: 'none' })
				return
			}
			if (scanned.error === ScanDeviceCodeError.INVALID_BARCODE) {
				uni.showToast({ title: scanned?.parsed?.error || $t('stock.invalidBarcode'), icon: 'none' })
				return
			}
			if (scanned.error === ScanDeviceCodeError.SCAN_FAILED && isScanCanceled(scanned)) return
			uni.showToast({ title: $t('stock.scanFailed'), icon: 'none' })
			return
		}
		addSn(scanned.sn, { alreadyNormalized: true })
	}

	const addSn = (raw, { alreadyNormalized = false } = {}) => {
		const value = String(raw || '').trim()
		const parsed = alreadyNormalized ? null : parseBarcode(value)
		const sn = alreadyNormalized
			? value
			: (parsed?.success && parsed?.sn) ? String(parsed.sn).trim() : value
		if (!sn) return
		if (snList.value.includes(sn)) return
		snList.value.push(sn)
	}

	const addSnFromInput = () => {
		const raw = String(snInput.value || '').trim()
		if (!raw) return
		snInput.value = ''
		addSn(raw)
	}

	const removeSn = (sn) => {
		snList.value = (snList.value || []).filter(x => x !== sn)
	}

	const clearSns = () => {
		snList.value = []
	}

	const openAuxPicker = () => {
		auxPickerVisible.value = true
		auxKeyword.value = ''
	}

	const closeAuxPicker = () => {
		auxPickerVisible.value = false
	}

	const selectAux = (eq) => {
		const equipmentId = Number(eq?.id)
		if (!equipmentId) return
		const hit = (auxRows.value || []).find(a => Number(a.equipment_id) === equipmentId)
		if (hit) {
			hit.quantity = Number(hit.quantity || 0) + 1
		} else {
			auxRows.value.push({
				equipment_id: equipmentId,
				equipment_name: eq.equipment_name,
				equipment_code: eq.equipment_code,
				unit: eq.unit,
				quantity: 1,
			})
		}
		closeAuxPicker()
	}

	const incAux = (idx) => {
		const a = auxRows.value?.[idx]
		if (!a) return
		a.quantity = Math.min(99999, Number(a.quantity || 1) + 1)
	}

	const decAux = (idx) => {
		const a = auxRows.value?.[idx]
		if (!a) return
		a.quantity = Math.max(1, Number(a.quantity || 1) - 1)
	}

	const normalizeAux = (idx) => {
		const a = auxRows.value?.[idx]
		if (!a) return
		let n = Number(String(a.quantity || '').trim())
		if (!Number.isFinite(n) || n <= 0) n = 1
		if (n > 99999) n = 99999
		a.quantity = Math.floor(n)
	}

	const removeAux = (idx) => {
		auxRows.value.splice(idx, 1)
	}

	const clearAux = () => {
		auxRows.value = []
	}

	const reset = () => {
		notes.value = ''
		snInput.value = ''
		snList.value = []
		auxRows.value = []
		issuedToUser.value = null
	}

	const openUserPicker = async () => {
		userPickerVisible.value = true
		userKeyword.value = ''
		userOptions.value = []
		await searchUsers()
	}

	const closeUserPicker = () => {
		userPickerVisible.value = false
	}

	const onUserKeywordInput = () => {
		if (userSearchTimer) clearTimeout(userSearchTimer)
		userSearchTimer = setTimeout(() => {
			searchUsers()
		}, 400)
	}

	const searchUsers = async () => {
		if (!userPickerVisible.value) return
		userLoading.value = true
		try {
			const kw = String(userKeyword.value || '').trim()
			const params = [`skip=0`, `limit=30`]
			if (kw) params.push(`keyword=${encodeURIComponent(kw)}`)
			const url = `${buildApiUrl('/api/users/search')}?${params.join('&')}`
			const res = await uni.request({
				url,
				method: 'GET',
				header: getAuthHeaders(userStore.token),
			})
			if (res.statusCode === 200) {
				userOptions.value = res.data?.users || []
				return
			}
			if (res.statusCode === 401) {
				userStore.logout()
				return
			}
			uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
		} catch (e) {
			console.error('搜索用户失败:', e)
		} finally {
			userLoading.value = false
		}
	}

	const selectUser = (u) => {
		issuedToUser.value = {
			id: u.id,
			username: u.username,
			full_name: u.full_name,
		}
		closeUserPicker()
	}

	const validate = () => {
		if (!selectedWarehouse.value?.id) {
			uni.showToast({ title: $t('stock.materialRequestWarehouseRequired'), icon: 'none' })
			return false
		}
		if (!issuedToUser.value?.id) {
			uni.showToast({ title: $t('stock.manualStockOutIssuedToRequired'), icon: 'none' })
			return false
		}
		if (snList.value.length === 0 && auxRows.value.length === 0) {
			uni.showToast({ title: $t('stock.manualStockOutItemsRequired'), icon: 'none' })
			return false
		}
		return true
	}

	const submit = async () => {
		if (!(await ensureAccess())) return
		if (!validate()) return

		uni.showModal({
			title: $t('common.confirm'),
			content: $t('stock.manualStockOutSubmitConfirm'),
			success: async (r) => {
				if (!r.confirm) return
				submitting.value = true
				shortages.value = []
				shortagesVisible.value = false

				try {
					const payload = {
						warehouse_id: Number(selectedWarehouse.value.id),
						issued_to: Number(issuedToUser.value.id),
						main_sns: snList.value.slice(),
						aux_items: (auxRows.value || []).map(a => ({
							equipment_id: Number(a.equipment_id),
							quantity: Number(a.quantity || 0),
						})),
						offline_document_id: offlineDocumentId.value || undefined,
						notes: String(notes.value || '').trim(),
					}

					const res = await uni.request({
						url: buildApiUrl(API_ENDPOINTS.STOCK.MANUAL_STOCK_OUT),
						method: 'POST',
						header: getAuthHeaders(userStore.token),
						data: payload,
					})

					if (res.statusCode === 200) {
						uni.showToast({ title: $t('stock.manualStockOutSuccess'), icon: 'success' })
						setTimeout(() => reset(), 450)
						return
					}

					if (res.statusCode === 401) {
						userStore.logout()
						return
					}

					const detail = res.data?.detail
					if (detail && typeof detail === 'object' && Array.isArray(detail.shortages)) {
						shortages.value = detail.shortages
						shortagesVisible.value = true
						return
					}

					uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
				} catch (e) {
					console.error('快速出库失败:', e)
					uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
				} finally {
					submitting.value = false
				}
			}
		})
	}

	const handleRefresh = async () => {
		if (!(await ensureAccess())) return
		refreshing.value = true
		try {
			await Promise.all([loadWarehouses(), loadEquipments()])
		} finally {
			refreshing.value = false
		}
	}

	onMounted(async () => {
		if (!(await ensureAccess())) return
		await Promise.all([loadWarehouses(), loadEquipments()])
		reset()
	})

	onShow(async () => {
		if (!(await ensureAccess())) return
	})
</script>

<style scoped lang="scss">
	.page { min-height: 100vh; background: var(--bg-page); }
	.content { height: calc(100vh - 88rpx - var(--status-bar-height, 0px)); }

	.hero {
		margin: 16px;
		border-radius: var(--radius-lg);
		overflow: hidden;
		position: relative;
		background:
			radial-gradient(920px 260px at 8% 0%, rgba(var(--color-primary-rgb), 0.16), transparent 62%),
			radial-gradient(920px 260px at 90% 10%, rgba(var(--color-brand-blue-rgb), 0.10), transparent 62%),
			linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(255, 255, 255, 0.90));
		border: 1px solid rgba(229, 231, 235, 0.9);
		box-shadow: 0 10px 26px rgba(17, 24, 39, 0.08);
	}

	.hero-top { padding: 16px 16px 10px; display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
	.hero-title { font-size: 16px; font-weight: 900; color: #111827; }
	.hero-sub { margin-top: 6px; font-size: 12px; color: var(--text-secondary); line-height: 1.5; }
	.right { display: flex; flex-direction: column; gap: 10px; }
	.pill { padding: 10px 12px; border-radius: 14px; border: 1px solid rgba(229, 231, 235, 0.9); background: rgba(255, 255, 255, 0.72); display: flex; flex-direction: column; gap: 6px; min-width: 120px; }
	.pill .k { font-size: 11px; color: #6b7280; }
	.pill .v { font-size: 18px; font-weight: 900; color: #111827; }
	.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; }

	.form { padding: 0 16px 16px; }
	.picker-input {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 10px;
		padding: 12px 12px;
		border: 1px solid var(--border-color);
		border-radius: 12px;
		background: rgba(255, 255, 255, 0.72);
		color: #111827;
	}
	.picker-input.placeholder { color: #9ca3af; }
	.picker-arrow { color: #9ca3af; font-size: 12px; }

	.section { margin: 16px; border-radius: var(--radius-lg); overflow: hidden; }
	.header-actions { display: flex; gap: 10px; }

	.scanner { margin-bottom: 14px; }
	.scanner-row { display: flex; align-items: center; gap: 10px; }
	.scanner-input { flex: 1; }
	.scanner-help { margin-top: 8px; font-size: 12px; color: #9ca3af; }

	.sn-tags .tags { display: flex; flex-wrap: wrap; gap: 10px; }
	.tag {
		display: inline-flex;
		align-items: center;
		gap: 10px;
		padding: 8px 10px;
		border-radius: 999px;
		background: linear-gradient(135deg, var(--color-brand-blue), rgba(var(--color-primary-rgb), 0.85));
		color: #fff;
		box-shadow: 0 8px 18px rgba(0, 0, 0, 0.12);
	}
	.tag-text { font-size: 12px; font-weight: 800; }
	.tag-close { width: 24px; height: 24px; border-radius: 12px; background: rgba(255, 255, 255, 0.20); display: flex; align-items: center; justify-content: center; }

	.aux-list { display: flex; flex-direction: column; gap: 12px; }
	.aux { border: 1px solid rgba(229, 231, 235, 0.9); background: #fff; border-radius: 14px; padding: 12px; }
	.aux-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
	.aux-head .left { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
	.name { font-size: 14px; font-weight: 800; color: #111827; }
	.code { font-size: 12px; color: #9ca3af; }

	.aux-actions { margin-top: 12px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
	.qty { display: flex; align-items: center; border: 1px solid rgba(229, 231, 235, 0.9); border-radius: 12px; overflow: hidden; background: #f9fafb; }
	.qbtn { width: 44px; height: 40px; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 700; color: #111827; background: #f3f4f6; }
	.qinput { width: 80px; height: 40px; text-align: center; font-size: 14px; font-weight: 900; color: #111827; }
	.remove { width: 44px; height: 40px; border-radius: 12px; display: flex; align-items: center; justify-content: center; background: rgba(239, 68, 68, 0.10); }

	.aux-total { margin-top: 12px; padding: 10px 12px; border-radius: 14px; border: 1px solid rgba(229, 231, 235, 0.9); background: rgba(255, 255, 255, 0.72); display: flex; align-items: center; justify-content: space-between; }
	.aux-total .k { font-size: 12px; color: #6b7280; }
	.aux-total .v { font-size: 16px; font-weight: 900; color: #111827; }

	.empty { padding: 10px 0; display: flex; justify-content: center; }
	.empty-text { color: #9ca3af; font-size: 13px; }

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
		grid-template-columns: 1fr 1.2fr;
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
	.modal-title { font-size: 15px; font-weight: 900; color: #111827; }
	.modal-close { width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; border-radius: 12px; background: #f3f4f6; }
	.modal-search { margin: 12px 16px 10px; padding: 10px 12px; border: 1px solid rgba(229, 231, 235, 0.9); border-radius: 14px; background: #f9fafb; display: flex; align-items: center; gap: 10px; }
	.modal-search-input { flex: 1; font-size: 13px; color: #111827; }
	.modal-list { max-height: 56vh; padding: 0 8px 16px; }
	.pick-row {
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
	.pick-left { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
	.pick-name { font-size: 14px; font-weight: 800; color: #111827; }
	.pick-sub { font-size: 12px; color: #9ca3af; }
	.pick-arrow { color: #9ca3af; font-size: 18px; line-height: 1; }

	.short-row { padding: 12px 10px; margin: 8px; border-radius: 14px; border: 1px solid rgba(229, 231, 235, 0.9); background: #fff; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
	.short-left { display: flex; flex-direction: column; gap: 6px; }

	.modal-empty { padding: 18px; display: flex; justify-content: center; }
	.modal-empty-text { color: #9ca3af; font-size: 13px; }
	.modal-foot { padding: 12px 16px 18px; border-top: 1px solid rgba(229, 231, 235, 0.9); }
</style>
