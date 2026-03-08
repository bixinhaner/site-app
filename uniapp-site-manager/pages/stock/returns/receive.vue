<template>
	<view class="page" :key="languageStore.currentLocale">
		<CustomNavbar :title="$t('stock.returnReceivingDetailTitle')" :showBack="true" variant="brand" />

		<scroll-view
			class="content"
			scroll-y
			refresher-enabled
			:refresher-triggered="refreshing"
			@refresherrefresh="handleRefresh"
			refresher-background="#f7f8fb"
		>
			<view v-if="record" class="hero u-card">
				<view class="hero-top">
					<view class="left">
						<text class="no mono">{{ record.document_number }}</text>
						<view class="meta">
							<view class="u-tag" :class="statusTagClass(record.status)">{{ statusLabel(record.status) }}</view>
							<text class="dot">·</text>
							<text class="meta-item">{{ record.warehouse_name || '-' }}</text>
						</view>
					</view>
					<view class="right">
						<view class="mini">
							<text class="k">{{ $t('stock.returnDocumentNumber') }}</text>
							<text class="v mono">{{ record.out_document_number || '-' }}</text>
						</view>
					</view>
				</view>

				<view class="summary-grid">
					<view class="s-item">
						<text class="k">{{ $t('stock.returnReceivingPendingMain') }}</text>
						<text class="v">{{ pendingMainItems.length }}</text>
					</view>
					<view class="s-item">
						<text class="k">{{ $t('stock.returnReceivingSelectedMain') }}</text>
						<text class="v">{{ selectedMainSns.length }}</text>
					</view>
					<view class="s-item">
						<text class="k">{{ $t('stock.returnReceivingAuxThisTime') }}</text>
						<text class="v">{{ auxReceiveTotal }}</text>
					</view>
					<view class="s-item accent">
						<text class="k">{{ $t('stock.returnReceivingThisTimeTotal') }}</text>
						<text class="v">{{ totalReceive }}</text>
					</view>
				</view>

				<view class="tip" v-if="tipText">
					<text class="tip-text">{{ tipText }}</text>
				</view>

				<view class="info-grid">
					<view class="info-row">
						<text class="info-k">{{ $t('stock.returnWarehouseLabel') }}</text>
						<text class="info-v">{{ record.warehouse_name || '-' }}</text>
					</view>
					<view class="info-row">
						<text class="info-k">{{ $t('stock.materialRequestRequester') }}</text>
						<text class="info-v">{{ record.operator_name || '-' }}</text>
					</view>
					<view class="info-row">
						<text class="info-k">{{ $t('stock.returnBatchCreatedTime') }}</text>
						<text class="info-v">{{ formatDt(record.created_at || record.operation_time) }}</text>
					</view>
				</view>

				<view class="reject" v-if="String(record.status || '') === 'rejected' && record.approval_comments">
					<text class="reject-k">{{ $t('stock.returnReceivingRejectReason') }}</text>
					<text class="reject-v">{{ record.approval_comments }}</text>
				</view>
			</view>

			<view v-if="loading && !record" class="list">
				<SkeletonCard mode="list" />
				<SkeletonCard mode="list" />
			</view>

			<view v-if="record" class="section u-card">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.mainDevice') }}</text>
					<view class="header-actions" v-if="canReceive">
						<button class="u-btn u-btn-primary u-btn-sm u-pressable" :disabled="selectedMainSns.length === pendingMainItems.length || pendingMainItems.length === 0 || acting" @click="selectAllPendingMain">
							{{ $t('stock.returnReceivingSelectAllSn') }}
						</button>
						<button class="u-btn u-btn-secondary u-btn-sm u-pressable" :disabled="selectedMainSns.length === 0 || acting" @click="clearSelectedMain">
							{{ $t('stock.returnReceivingClearSn') }}
						</button>
					</view>
				</view>
				<view class="u-card-content">
					<view v-if="pendingMainItems.length === 0" class="empty">
						<text class="empty-text">{{ $t('stock.returnReceivingNoPendingSn') }}</text>
					</view>
					<view v-else class="serial-list">
						<view
							v-for="item in pendingMainItems"
							:key="item.serial_number"
							class="serial"
							:class="{ selected: isMainSelected(item.serial_number) }"
							@click="toggleMain(item.serial_number)"
						>
							<view class="serial-left">
								<text class="sn mono">{{ item.serial_number }}</text>
								<text class="time">{{ item.equipment_name || '-' }}</text>
							</view>
							<view class="serial-right">
								<view class="u-tag" :class="isMainSelected(item.serial_number) ? 'u-tag-primary' : 'u-tag-warning'">
									{{ isMainSelected(item.serial_number) ? $t('common.selected') : $t('stock.qtyPending') }}
								</view>
							</view>
						</view>
					</view>
				</view>
			</view>

			<view v-if="record" class="section u-card">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.auxMaterial') }}</text>
				</view>
				<view class="u-card-content">
					<view v-if="auxReceiveRows.length === 0" class="empty">
						<text class="empty-text">{{ $t('stock.returnReceivingNoAux') }}</text>
					</view>
					<view v-else class="aux-list">
						<view class="aux" v-for="(row, idx) in auxReceiveRows" :key="row.equipment_id">
							<view class="aux-head">
								<view class="left">
									<text class="name">{{ row.equipment_name }}</text>
									<text class="code mono">{{ row.equipment_code }}</text>
								</view>
								<view class="right">
									<view class="u-tag u-tag-info">{{ displayUnit(row.unit) || '-' }}</view>
								</view>
							</view>

							<view class="aux-nums">
								<view class="n">
									<text class="k">{{ $t('stock.qtyPending') }}</text>
									<text class="v">{{ row.pending_quantity }}</text>
								</view>
								<view class="n accent">
									<text class="k">{{ $t('stock.returnReceivingAuxThisTime') }}</text>
									<view v-if="canReceive" class="stepper">
										<view class="qbtn u-pressable" :class="{ disabled: acting || row.pending_quantity <= 0 }" @click="decAux(idx)">−</view>
										<input
											class="qinput mono"
											type="number"
											v-model="row.quantity"
											@blur="normalizeAux(idx)"
											:disabled="acting || row.pending_quantity <= 0"
										/>
										<view class="qbtn u-pressable" :class="{ disabled: acting || row.pending_quantity <= 0 }" @click="incAux(idx)">＋</view>
									</view>
									<text v-else class="v">{{ row.quantity }}</text>
								</view>
							</view>
						</view>
					</view>
				</view>
			</view>

			<view class="section u-card" v-if="record && canReceive">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.returnReceivingNotes') }}</text>
				</view>
				<view class="u-card-content">
					<view class="u-form-item">
						<textarea class="u-textarea" v-model="receiveNotes" :placeholder="$t('stock.returnReceivingNotesPlaceholder')" maxlength="200" />
					</view>
				</view>
			</view>

			<view class="section u-card" v-if="record && canReject">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.returnReceivingRejectReason') }}</text>
				</view>
				<view class="u-card-content">
					<view class="u-form-item">
						<textarea class="u-textarea" v-model="rejectReason" :placeholder="$t('stock.returnReceivingRejectReasonPlaceholder')" maxlength="200" />
					</view>
				</view>
			</view>

			<view class="bottom-spacer" />
		</scroll-view>

		<view class="bottom-bar" v-if="record" :class="bottomBarClass">
			<button class="u-btn u-btn-secondary u-pressable" @click="goBack">
				{{ $t('common.back') }}
			</button>
			<button class="u-btn u-btn-danger u-pressable" v-if="canReject" :disabled="acting" @click="submitReject">
				{{ $t('stock.returnReceivingRejectAction') }}
			</button>
			<button class="u-btn u-btn-primary u-pressable" v-if="canReceive" :disabled="acting || !canSubmit" @click="submitReceive">
				{{ acting ? $t('common.loading') : $t('stock.returnReceivingSubmit') }}
			</button>
		</view>
	</view>
</template>

<script setup>
	import { computed, getCurrentInstance, ref } from 'vue'
	import { onLoad, onShow } from '@dcloudio/uni-app'
	import { API_ENDPOINTS, buildApiUrl, getAuthHeaders } from '@/config/api.js'
	import { guardRouteAccess } from '@/utils/feature-access.js'
	import { formatDateTime } from '@/utils/time.js'
	import { getLocalizedStockUnit } from '@/utils/unit-i18n.js'
	import { useUserStore } from '@/stores/user'
	import { useLanguageStore } from '@/stores/language'
	import CustomNavbar from '@/components/CustomNavbar.vue'
	import SkeletonCard from '@/components/SkeletonCard.vue'

	const userStore = useUserStore()
	const languageStore = useLanguageStore()
	const { $t } = getCurrentInstance().appContext.config.globalProperties
	const displayUnit = (unit) => getLocalizedStockUnit(unit, $t)

	const returnId = ref('')
	const record = ref(null)
	const loading = ref(false)
	const refreshing = ref(false)
	const acting = ref(false)
	const receiveNotes = ref('')
	const rejectReason = ref('')
	const selectedMainSns = ref([])
	const auxReceiveRows = ref([])

	const ensureAccess = () => guardRouteAccess({
		userStore,
		route: 'pages/stock/returns/receive',
		t: $t,
		deniedMessage: $t('stock.returnReceivingNoPermission'),
		redirectUrl: '/pages/stock/returns/receive-list',
	})

	const statusValue = computed(() => String(record.value?.status || ''))
	const canReceive = computed(() => ['pending_receive', 'partially_received'].includes(statusValue.value))
	const canReject = computed(() => statusValue.value === 'pending_receive')
	const canSubmit = computed(() => selectedMainSns.value.length > 0 || auxReceiveTotal.value > 0)
	const bottomBarClass = computed(() => {
		if (canReceive.value && canReject.value) return 'triple'
		if (canReceive.value) return 'double'
		return 'single'
	})

	const pendingMainItems = computed(() => {
		return (record.value?.items || []).filter(item => item.is_main_device && Number(item.pending_quantity || 0) > 0)
	})

	const auxReceiveTotal = computed(() => {
		return (auxReceiveRows.value || []).reduce((sum, row) => sum + Number(row.quantity || 0), 0)
	})

	const totalReceive = computed(() => selectedMainSns.value.length + auxReceiveTotal.value)

	const tipText = computed(() => {
		if (statusValue.value === 'pending_receive') return $t('stock.returnReceivingTipPending')
		if (statusValue.value === 'partially_received') return $t('stock.returnReceivingTipPartial')
		if (statusValue.value === 'received') return $t('stock.returnReceivingTipDone')
		if (statusValue.value === 'rejected') return $t('stock.returnReceivingTipRejected')
		return ''
	})

	const formatDt = (ts) => formatDateTime(ts) || '-'

	const statusLabel = (s) => {
		const map = {
			pending_receive: $t('stock.returnStatusPendingReceiveShort'),
			partially_received: $t('stock.returnStatusPartiallyReceivedShort'),
			received: $t('stock.statusReturned'),
			rejected: $t('stock.returnStatusRejectedShort'),
			canceled: $t('stock.returnStatusCanceledShort'),
		}
		return map[s] || s || '-'
	}

	const statusTagClass = (s) => {
		if (s === 'received') return 'u-tag-success'
		if (s === 'rejected') return 'u-tag-error'
		if (s === 'canceled') return 'u-tag-info'
		if (s === 'partially_received') return 'u-tag-primary'
		if (s === 'pending_receive') return 'u-tag-warning'
		return 'u-tag-info'
	}

	const extractErrorMessage = (data, fallback = '') => {
		const detail = data?.detail
		if (!detail) return fallback || $t('messages.operationFailed')
		if (typeof detail === 'string') return detail
		return detail?.message || fallback || $t('messages.operationFailed')
	}

	const syncAuxRows = () => {
		const prev = new Map((auxReceiveRows.value || []).map(row => [Number(row.equipment_id), Number(row.quantity || 0)]))
		auxReceiveRows.value = (record.value?.items || [])
			.filter(item => !item.is_main_device && Number(item.pending_quantity || 0) > 0)
			.map((item) => {
				const equipmentId = Number(item.equipment_id || 0)
				const pendingQuantity = Math.max(0, Number(item.pending_quantity || 0))
				const prevQty = prev.get(equipmentId)
				let quantity = Number.isFinite(prevQty) ? prevQty : 0
				if (quantity < 0) quantity = 0
				if (quantity > pendingQuantity) quantity = pendingQuantity
				return {
					equipment_id: equipmentId,
					equipment_name: item.equipment_name,
					equipment_code: item.equipment_code,
					unit: item.unit,
					pending_quantity: pendingQuantity,
					quantity,
				}
			})
	}

	const selectAllPendingMain = () => {
		selectedMainSns.value = pendingMainItems.value
			.map(item => String(item.serial_number || '').trim())
			.filter(Boolean)
	}

	const clearSelectedMain = () => {
		selectedMainSns.value = []
	}

	const isMainSelected = (sn) => {
		return selectedMainSns.value.includes(String(sn || '').trim())
	}

	const toggleMain = (sn) => {
		if (!canReceive.value || acting.value) return
		const value = String(sn || '').trim()
		if (!value) return
		if (isMainSelected(value)) {
			selectedMainSns.value = selectedMainSns.value.filter(item => item !== value)
			return
		}
		selectedMainSns.value = selectedMainSns.value.concat(value)
	}

	const normalizeAux = (index) => {
		const row = auxReceiveRows.value[index]
		if (!row) return
		let value = Number(String(row.quantity || '').trim())
		if (!Number.isFinite(value) || value < 0) value = 0
		if (value > Number(row.pending_quantity || 0)) value = Number(row.pending_quantity || 0)
		row.quantity = Math.floor(value)
		auxReceiveRows.value.splice(index, 1, { ...row })
	}

	const decAux = (index) => {
		const row = auxReceiveRows.value[index]
		if (!row || acting.value) return
		row.quantity = Math.max(0, Number(row.quantity || 0) - 1)
		auxReceiveRows.value.splice(index, 1, { ...row })
	}

	const incAux = (index) => {
		const row = auxReceiveRows.value[index]
		if (!row || acting.value) return
		row.quantity = Math.min(Number(row.pending_quantity || 0), Number(row.quantity || 0) + 1)
		auxReceiveRows.value.splice(index, 1, { ...row })
	}

	const load = async () => {
		if (!(ensureAccess())) return
		if (!returnId.value) return

		loading.value = true
		try {
			const res = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.STOCK.RETURN_DETAIL(returnId.value)),
				method: 'GET',
				header: getAuthHeaders(userStore.token),
			})
			if (res.statusCode === 200 && res.data?.record) {
				record.value = res.data.record
				selectAllPendingMain()
				syncAuxRows()
				return
			}
			if (res.statusCode === 401) {
				userStore.logout()
				return
			}
			uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
		} catch (e) {
			console.error('加载退库收货详情失败:', e)
			uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
		} finally {
			loading.value = false
			refreshing.value = false
		}
	}

	const handleRefresh = async () => {
		refreshing.value = true
		await load()
	}

	const submitReceive = async () => {
		if (!canReceive.value || acting.value) return
		if (!canSubmit.value) {
			uni.showToast({ title: $t('stock.returnReceivingSelectAtLeastOne'), icon: 'none' })
			return
		}

		uni.showModal({
			title: $t('common.confirm'),
			content: $t('stock.returnReceivingSubmitConfirm'),
			success: async (mr) => {
				if (!mr.confirm) return
				acting.value = true
				try {
					const res = await uni.request({
						url: buildApiUrl(API_ENDPOINTS.STOCK.RETURN_RECEIVE(returnId.value)),
						method: 'POST',
						header: getAuthHeaders(userStore.token),
						data: {
							main_sns: selectedMainSns.value,
							aux_items: auxReceiveRows.value
								.filter(row => Number(row.quantity || 0) > 0)
								.map(row => ({
									equipment_id: Number(row.equipment_id),
									quantity: Number(row.quantity || 0),
								})),
							receive_notes: String(receiveNotes.value || '').trim(),
						},
					})
					if (res.statusCode === 200) {
						uni.showToast({ title: $t('stock.returnReceivingSuccess'), icon: 'success' })
						await load()
						return
					}
					if (res.statusCode === 401) {
						userStore.logout()
						return
					}
					uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
				} catch (e) {
					console.error('确认退库收货失败:', e)
					uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
				} finally {
					acting.value = false
				}
			},
		})
	}

	const submitReject = async () => {
		if (!canReject.value || acting.value) return
		const reason = String(rejectReason.value || '').trim()
		if (!reason) {
			uni.showToast({ title: $t('stock.returnReceivingRejectReasonPlaceholder'), icon: 'none' })
			return
		}

		uni.showModal({
			title: $t('common.confirm'),
			content: $t('stock.returnReceivingRejectConfirm'),
			success: async (mr) => {
				if (!mr.confirm) return
				acting.value = true
				try {
					const res = await uni.request({
						url: buildApiUrl(API_ENDPOINTS.STOCK.RETURN_REJECT(returnId.value)),
						method: 'POST',
						header: getAuthHeaders(userStore.token),
						data: { reason },
					})
					if (res.statusCode === 200) {
						uni.showToast({ title: $t('stock.returnReceivingRejectSuccess'), icon: 'success' })
						await load()
						return
					}
					if (res.statusCode === 401) {
						userStore.logout()
						return
					}
					uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
				} catch (e) {
					console.error('拒收退库单失败:', e)
					uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
				} finally {
					acting.value = false
				}
			},
		})
	}

	const goBack = () => {
		uni.navigateBack()
	}

	onLoad((query) => {
		returnId.value = String(query?.return_id || '').trim()
	})

	onShow(async () => {
		await load()
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
		overflow: hidden;
		position: relative;
		background:
			radial-gradient(900px 260px at 8% 0%, rgba(var(--color-primary-rgb), 0.16), transparent 62%),
			radial-gradient(900px 260px at 90% 10%, rgba(var(--color-brand-blue-rgb), 0.10), transparent 62%),
			linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(255, 255, 255, 0.92));
		border: 1px solid rgba(229, 231, 235, 0.9);
		box-shadow: var(--shadow-card);
		padding: 14px;
	}

	.hero-top {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 12px;
	}
	.left { flex: 1; min-width: 0; }
	.no { font-size: 14px; font-weight: 800; color: var(--text-primary); }
	.meta { margin-top: 6px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
	.meta-item { font-size: 12px; color: var(--text-secondary); }
	.dot { color: #d1d5db; }
	.mini {
		padding: 8px 10px;
		border-radius: 12px;
		background: rgba(255, 255, 255, 0.86);
		border: 1px solid rgba(229, 231, 235, 0.9);
	}
	.summary-grid {
		margin-top: 14px;
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 10px;
	}
	.s-item {
		padding: 10px;
		border-radius: 14px;
		background: rgba(243, 244, 246, 0.8);
		border: 1px solid rgba(229, 231, 235, 0.9);
	}
	.s-item .k,
	.info-k,
	.n .k { font-size: 11px; color: var(--text-secondary); }
	.s-item .v,
	.info-v,
	.n .v { margin-top: 4px; font-size: 14px; font-weight: 800; color: var(--text-primary); }
	.accent {
		background: rgba(var(--color-primary-rgb), 0.08);
		border-color: rgba(var(--color-primary-rgb), 0.18);
	}
	.tip {
		margin-top: 12px;
		padding: 10px 12px;
		border-radius: 12px;
		background: rgba(37, 99, 235, 0.08);
		border: 1px solid rgba(37, 99, 235, 0.18);
	}
	.tip-text { font-size: 12px; color: #1d4ed8; line-height: 1.5; }
	.info-grid {
		margin-top: 12px;
		display: grid;
		grid-template-columns: 1fr;
		gap: 8px;
	}
	.info-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}
	.info-v {
		margin-top: 0;
		font-size: 12px;
		text-align: right;
	}
	.reject {
		margin-top: 12px;
		padding: 10px 12px;
		border-radius: 12px;
		border: 1px solid #fecaca;
		background: #fef2f2;
	}
	.reject-k { font-size: 12px; color: #b91c1c; font-weight: 800; }
	.reject-v { display: block; margin-top: 6px; font-size: 12px; color: #7f1d1d; line-height: 1.5; }

	.section { margin: 0 16px 12px; }
	.empty {
		padding: 18px 12px;
		text-align: center;
	}
	.empty-text { font-size: 12px; color: var(--text-secondary); }

	.serial-list { display: flex; flex-direction: column; gap: 10px; }
	.serial {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 10px;
		padding: 10px 12px;
		border-radius: 12px;
		background: rgba(255, 255, 255, 0.88);
		border: 1px solid rgba(229, 231, 235, 0.95);
	}
	.serial.selected {
		border-color: rgba(var(--color-primary-rgb), 0.3);
		background: rgba(var(--color-primary-rgb), 0.06);
	}
	.serial-left { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
	.sn { font-size: 13px; color: var(--text-primary); font-weight: 700; }
	.time { font-size: 11px; color: var(--text-secondary); }

	.aux-list { display: flex; flex-direction: column; gap: 12px; }
	.aux {
		padding: 12px;
		border-radius: 14px;
		background: rgba(255, 255, 255, 0.9);
		border: 1px solid rgba(229, 231, 235, 0.95);
	}
	.aux-head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 10px;
	}
	.name { font-size: 13px; font-weight: 700; color: var(--text-primary); }
	.code { margin-top: 4px; display: block; font-size: 11px; color: var(--text-secondary); }
	.aux-nums {
		margin-top: 10px;
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 10px;
	}
	.n {
		padding: 10px;
		border-radius: 12px;
		background: rgba(243, 244, 246, 0.72);
		border: 1px solid rgba(229, 231, 235, 0.9);
	}
	.stepper {
		margin-top: 6px;
		display: flex;
		align-items: center;
		gap: 6px;
	}
	.qbtn {
		width: 28px;
		height: 28px;
		border-radius: 10px;
		background: rgba(var(--color-primary-rgb), 0.12);
		color: var(--color-primary);
		display: flex;
		align-items: center;
		justify-content: center;
		font-weight: 800;
	}
	.qbtn.disabled {
		opacity: 0.4;
	}
	.qinput {
		flex: 1;
		height: 30px;
		text-align: center;
		border-radius: 10px;
		background: #fff;
		border: 1px solid rgba(209, 213, 219, 0.9);
		font-size: 13px;
		color: var(--text-primary);
	}

	.bottom-spacer { height: 92px; }
	.bottom-bar {
		position: fixed;
		left: 0;
		right: 0;
		bottom: 0;
		display: grid;
		gap: 10px;
		padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
		background: rgba(255, 255, 255, 0.96);
		border-top: 1px solid rgba(229, 231, 235, 0.9);
		backdrop-filter: blur(12px);
	}
	.bottom-bar.single { grid-template-columns: 1fr; }
	.bottom-bar.double { grid-template-columns: 1fr 1fr; }
	.bottom-bar.triple { grid-template-columns: 1fr 1fr 1fr; }
	.mono { font-family: monospace; }
</style>
