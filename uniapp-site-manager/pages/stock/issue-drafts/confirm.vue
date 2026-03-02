<template>
	<view class="page" :key="languageStore.currentLocale">
		<CustomNavbar :title="$t('stock.issueConfirmTitle')" :showBack="true" variant="brand" />

		<scroll-view
			class="content"
			scroll-y
			refresher-enabled
			:refresher-triggered="refreshing"
			@refresherrefresh="handleRefresh"
			refresher-background="#f7f8fb"
		>
			<view v-if="draft" class="hero u-card">
				<view class="hero-top">
					<view class="left">
						<text class="no mono">{{ draft.draft_no }}</text>
						<view class="meta">
							<view class="u-tag" :class="statusTagClass(draft.status)">{{ statusLabel(draft.status) }}</view>
							<text class="dot">·</text>
							<text class="meta-item">{{ draft.warehouse_name || '-' }}</text>
						</view>
					</view>
					<view class="right" v-if="draft.request?.request_no">
						<view class="mini">
							<text class="k">{{ $t('stock.materialRequestNo') }}</text>
							<text class="v mono">{{ draft.request.request_no }}</text>
						</view>
					</view>
				</view>

				<view class="summary-grid">
					<view class="s-item">
						<text class="k">{{ $t('stock.issueDraftPendingSn') }}</text>
						<text class="v">{{ pendingSerials.length }}</text>
					</view>
					<view class="s-item">
						<text class="k">{{ $t('stock.issueConfirmSelectedSn') }}</text>
						<text class="v">{{ selectedSerials.length }}</text>
					</view>
					<view class="s-item">
						<text class="k">{{ $t('stock.issueDraftAuxPending') }}</text>
						<text class="v">{{ auxPendingTotal }}</text>
					</view>
					<view class="s-item accent">
						<text class="k">{{ $t('stock.issueConfirmAuxThisTime') }}</text>
						<text class="v">{{ auxConfirmTotal }}</text>
					</view>
				</view>

				<view class="tip" v-if="tipText">
					<text class="tip-text">{{ tipText }}</text>
				</view>

				<view class="reject" v-if="draft.reject_reason">
					<text class="reject-k">{{ $t('stock.issueDraftRejectReason') }}</text>
					<text class="reject-v">{{ draft.reject_reason }}</text>
				</view>
			</view>

			<view v-if="loading && !draft" class="list">
				<SkeletonCard mode="list" />
				<SkeletonCard mode="list" />
			</view>

			<view v-if="draft" class="section u-card">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.issueDraftMainDevices') }}</text>
					<view class="header-actions" v-if="canConfirm">
						<button
							class="u-btn u-btn-primary u-btn-sm u-pressable"
							:disabled="acting || pendingSerials.length === 0 || selectedSerials.length === pendingSerials.length"
							@click="selectAllPendingSn"
						>
							{{ $t('stock.issueConfirmSelectAllSn') }}
						</button>
						<button class="u-btn u-btn-secondary u-btn-sm u-pressable" :disabled="acting || selectedSerials.length === 0" @click="clearSelectedSn">
							{{ $t('stock.issueConfirmDeselectAllSn') }}
						</button>
					</view>
				</view>
				<view class="u-card-content">
					<view class="sub-title-wrap">
						<text class="sub-title">{{ $t('stock.issueConfirmPendingReference') }}</text>
					</view>
					<text v-if="canConfirm" class="select-help">{{ $t('stock.issueConfirmSnAutoSelectedHelp') }}</text>
					<view v-if="pendingSerials.length === 0" class="empty compact">
						<text class="empty-text">{{ $t('stock.issueConfirmNoPendingSn') }}</text>
					</view>
					<view v-else class="serial-list">
						<view
							class="serial"
							v-for="s in pendingSerials"
							:key="s.id"
							:class="{ selected: isSerialSelected(s.id) }"
							@click="togglePendingSn(s.id)"
						>
							<view class="serial-left">
								<text class="sn mono">{{ s.serial_number }}</text>
								<text class="time">{{ formatDt(s.scanned_at) }}</text>
							</view>
							<view class="serial-right">
								<view class="u-tag" :class="isSerialSelected(s.id) ? 'u-tag-primary' : 'u-tag-warning'">
									{{ isSerialSelected(s.id) ? $t('common.selected') : $t('stock.issueDraftSnPending') }}
								</view>
							</view>
						</view>
					</view>
				</view>
			</view>

			<view v-if="draft" class="section u-card">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.issueDraftAuxMaterials') }}</text>
					<view class="header-actions" v-if="canConfirm && auxConfirmRows.length > 0">
						<button class="u-btn u-btn-secondary u-btn-sm u-pressable" :disabled="acting" @click="fillAuxPending">
							{{ $t('stock.issueConfirmFillAuxPending') }}
						</button>
						<button class="u-btn u-btn-secondary u-btn-sm u-pressable" :disabled="acting || auxConfirmTotal === 0" @click="clearAuxConfirm">
							{{ $t('stock.issueConfirmClearAux') }}
						</button>
					</view>
				</view>
				<view class="u-card-content">
					<view v-if="auxConfirmRows.length === 0" class="empty">
						<text class="empty-text">{{ $t('stock.issueDraftNoAux') }}</text>
					</view>

					<view v-else class="aux-list">
						<view class="aux" v-for="(row, idx) in auxConfirmRows" :key="row.equipment_id">
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
									<text class="v">{{ row.pending_qty }}</text>
								</view>
								<view class="n accent">
									<text class="k">{{ $t('stock.issueConfirmAuxThisTime') }}</text>
									<view v-if="canConfirm" class="stepper">
										<view class="qbtn u-pressable" :class="{ disabled: acting || row.pending_qty <= 0 }" @click="decAux(idx)">−</view>
										<input
											class="qinput mono"
											type="number"
											v-model="row.quantity"
											@blur="normalizeAux(idx)"
											:disabled="acting || row.pending_qty <= 0"
										/>
										<view class="qbtn u-pressable" :class="{ disabled: acting || row.pending_qty <= 0 }" @click="incAux(idx)">＋</view>
									</view>
									<text v-else class="v">{{ row.quantity }}</text>
								</view>
							</view>
						</view>
					</view>

					<view class="aux-total">
						<text class="k">{{ $t('stock.issueConfirmAuxThisTime') }}</text>
						<text class="v mono">{{ auxConfirmTotal }}</text>
					</view>
				</view>
			</view>

			<view class="section u-card" v-if="draft && canConfirm">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.issueConfirmNotes') }}</text>
				</view>
				<view class="u-card-content">
					<view class="u-form-item">
						<textarea class="u-textarea" v-model="notes" :placeholder="$t('stock.issueConfirmNotesPlaceholder')" maxlength="200" />
					</view>
				</view>
			</view>

				<view class="section u-card" v-if="draft && (canReject || canRejectRemaining)">
					<view class="u-card-header">
						<text class="u-card-title">{{ canRejectRemaining ? $t('stock.issueConfirmRejectRemainingReason') : $t('stock.issueConfirmRejectReason') }}</text>
					</view>
					<view class="u-card-content">
						<view class="u-form-item">
							<textarea
								class="u-textarea"
								v-model="rejectReason"
								:placeholder="canRejectRemaining ? $t('stock.issueConfirmRejectRemainingReasonPlaceholder') : $t('stock.issueConfirmRejectReasonPlaceholder')"
								maxlength="200"
							/>
						</view>
					</view>
				</view>

			<view class="bottom-spacer" />
		</scroll-view>

		<view class="bottom-bar" v-if="draft" :class="bottomBarClass">
			<button class="u-btn u-btn-secondary u-pressable" @click="goBack">
				{{ $t('common.back') }}
			</button>
				<button class="u-btn u-btn-danger u-pressable" v-if="canReject || canRejectRemaining" :disabled="acting" @click="rejectCurrent">
					{{ canRejectRemaining ? $t('stock.issueConfirmRejectRemainingAction') : $t('stock.issueConfirmRejectAction') }}
				</button>
				<button class="u-btn u-btn-primary u-pressable" v-if="canConfirm" :disabled="acting || !canSubmitOrClose" @click="submitConfirm">
					{{ acting ? $t('common.loading') : $t('stock.issueConfirmSubmit') }}
				</button>
			</view>
		</view>
</template>

<script setup>
	import { computed, getCurrentInstance, onMounted, ref } from 'vue'
	import { onLoad, onShow } from '@dcloudio/uni-app'
	import { useUserStore } from '@/stores/user'
	import { useLanguageStore } from '@/stores/language'
	import { buildApiUrl, API_ENDPOINTS, getAuthHeaders } from '@/config/api.js'
	import { formatDateTime } from '@/utils/time.js'
	import { getLocalizedStockUnit } from '@/utils/unit-i18n.js'
	import CustomNavbar from '@/components/CustomNavbar.vue'
	import SkeletonCard from '@/components/SkeletonCard.vue'

	const userStore = useUserStore()
	const languageStore = useLanguageStore()
	const { $t } = getCurrentInstance().appContext.config.globalProperties
	const displayUnit = (unit) => getLocalizedStockUnit(unit, $t)

	const draftId = ref('')
	const draft = ref(null)
	const loading = ref(false)
	const refreshing = ref(false)
	const acting = ref(false)

	const notes = ref('')
	const rejectReason = ref('')

	const selectedSerialIds = ref([])
	const auxConfirmRows = ref([])

	const statusValue = computed(() => String(draft.value?.status || ''))
	const isWarehouseSide = computed(() => {
		const role = String(userStore.userInfo?.role || '')
		return ['admin', 'manager', 'warehouse_manager'].includes(role)
	})

	const canConfirm = computed(() => {
		return ['pending_confirm', 'partially_confirmed'].includes(statusValue.value)
	})
	const canReject = computed(() => statusValue.value === 'pending_confirm')
	const canRejectRemaining = computed(() => statusValue.value === 'partially_confirmed')

	const pendingSerials = computed(() => {
		return (draft.value?.serials || []).filter(s => String(s.status) === 'pending')
	})

	const selectedSerials = computed(() => {
		const selectedSet = new Set((selectedSerialIds.value || []).map(id => Number(id)))
		return pendingSerials.value.filter(s => selectedSet.has(Number(s.id)))
	})

	const auxPendingTotal = computed(() => {
		return (draft.value?.aux_items || []).reduce((sum, row) => sum + Number(row.pending_qty || 0), 0)
	})

	const auxConfirmTotal = computed(() => {
		return (auxConfirmRows.value || []).reduce((sum, row) => sum + Number(row.quantity || 0), 0)
	})
	const hasPendingRemaining = computed(() => {
		const hasPendingSn = pendingSerials.value.length > 0
		const hasPendingAux = (auxConfirmRows.value || []).some(row => Number(row.pending_qty || 0) > 0)
		return hasPendingSn || hasPendingAux
	})

	const canSubmit = computed(() => selectedSerials.value.length > 0 || auxConfirmTotal.value > 0)
	const canSubmitOrClose = computed(() => canSubmit.value || !hasPendingRemaining.value)

	const tipText = computed(() => {
		const s = statusValue.value
		if (s === 'pending_confirm') return $t('stock.issueConfirmTipPending')
		if (s === 'partially_confirmed') return $t('stock.issueConfirmTipPartial')
		if (s === 'confirmed') return $t('stock.issueConfirmTipDone')
		if (s === 'rejected') return $t('stock.issueDraftTipRejected')
		if (s === 'canceled') return $t('stock.issueDraftTipCanceled')
		return ''
	})

	const bottomBarClass = computed(() => {
		if (canConfirm.value && (canReject.value || canRejectRemaining.value)) return 'triple'
		if (canConfirm.value) return 'double'
		return 'single'
	})

	const extractErrorMessage = (data, fallback = '') => {
		const detail = data?.detail
		if (!detail) return fallback || $t('messages.operationFailed')
		if (typeof detail === 'string') return detail
		return detail?.message || fallback || $t('messages.operationFailed')
	}
	const isNoPendingConfirmError = (data) => {
		return String(data?.detail?.code || '') === 'no_pending_items'
	}

	const AUTO_CLOSE_REASON = '无待确认项，确认按钮触发收口'

	const formatDt = (ts) => {
		return formatDateTime(ts) || ''
	}

	const statusLabel = (status) => {
		const map = {
			draft: $t('stock.issueDraftStatusDraft'),
			pending_confirm: $t('stock.issueDraftStatusPendingConfirm'),
			partially_confirmed: $t('stock.issueDraftStatusPartiallyConfirmed'),
			confirmed: $t('stock.issueDraftStatusConfirmed'),
			rejected: $t('stock.issueDraftStatusRejected'),
			canceled: $t('stock.issueDraftStatusCanceled'),
		}
		return map[String(status || '')] || String(status || '-')
	}

	const statusTagClass = (status) => {
		const s = String(status || '')
		if (s === 'draft') return 'u-tag-info'
		if (s === 'pending_confirm') return 'u-tag-warning'
		if (s === 'partially_confirmed') return 'u-tag-primary'
		if (s === 'confirmed') return 'u-tag-success'
		if (s === 'rejected' || s === 'canceled') return 'u-tag-error'
		return 'u-tag-info'
	}

	const syncAuxRows = () => {
		const prev = new Map((auxConfirmRows.value || []).map(row => [Number(row.equipment_id), Number(row.quantity || 0)]))
		auxConfirmRows.value = (draft.value?.aux_items || []).map(row => {
			const pendingQty = Math.max(0, Number(row.pending_qty || 0))
			const prevQty = prev.get(Number(row.equipment_id))
			let quantity = Number.isFinite(prevQty) ? prevQty : 0
			if (quantity < 0) quantity = 0
			if (quantity > pendingQty) quantity = pendingQty
			return {
				equipment_id: Number(row.equipment_id),
				equipment_name: row.equipment_name,
				equipment_code: row.equipment_code,
				unit: row.unit,
				pending_qty: pendingQty,
				quantity,
			}
		})
	}

	const ensureReady = async () => {
		if (!userStore.isLoggedIn) {
			uni.reLaunch({ url: '/pages/login/login' })
			return false
		}
		if (!isWarehouseSide.value) {
			uni.showToast({ title: $t('stock.issueConfirmNoPermission'), icon: 'none' })
			setTimeout(() => uni.navigateBack(), 700)
			return false
		}

		try {
			const flowRes = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.STOCK.FLOW_SETTINGS),
				method: 'GET',
				header: getAuthHeaders(userStore.token),
			})
			if (flowRes.statusCode === 200 && flowRes.data?.settings?.enable_material_request === false) {
				uni.showToast({ title: $t('stock.materialRequestDisabled'), icon: 'none' })
				setTimeout(() => uni.navigateBack(), 700)
				return false
			}
		} catch (e) {
			// ignore
		}
		return true
	}

	const load = async () => {
		if (!(await ensureReady())) return
		if (!draftId.value) return

		loading.value = true
		try {
			const res = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.STOCK.ISSUE_DRAFT_DETAIL(draftId.value)),
				method: 'GET',
				header: getAuthHeaders(userStore.token),
			})
			if (res.statusCode === 200 && res.data?.draft) {
				draft.value = res.data.draft
				selectedSerialIds.value = (draft.value?.serials || [])
					.filter(s => String(s.status) === 'pending')
					.map(s => Number(s.id))
					.filter(id => Number.isFinite(id) && id > 0)
				syncAuxRows()
				return
			}
			if (res.statusCode === 401) {
				userStore.logout()
				return
			}
			uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
		} catch (e) {
			console.error('加载出库确认详情失败:', e)
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

	const isSerialSelected = (serialId) => {
		const sid = Number(serialId)
		return selectedSerialIds.value.includes(sid)
	}

	const togglePendingSn = (serialId) => {
		if (!canConfirm.value) return
		const sid = Number(serialId)
		if (!Number.isFinite(sid) || sid <= 0) return
		if (isSerialSelected(sid)) {
			selectedSerialIds.value = (selectedSerialIds.value || []).filter(id => Number(id) !== sid)
			return
		}
		selectedSerialIds.value.push(sid)
	}

	const selectAllPendingSn = () => {
		if (!canConfirm.value) return
		selectedSerialIds.value = pendingSerials.value.map(s => Number(s.id)).filter(id => Number.isFinite(id) && id > 0)
	}

	const clearSelectedSn = () => {
		if (!canConfirm.value) return
		selectedSerialIds.value = []
	}

	const normalizeAux = (idx) => {
		if (!canConfirm.value) return
		const row = auxConfirmRows.value?.[idx]
		if (!row) return
		let n = Number(String(row.quantity || '').trim())
		if (!Number.isFinite(n) || n < 0) n = 0
		const max = Math.max(0, Number(row.pending_qty || 0))
		if (n > max) n = max
		row.quantity = Math.floor(n)
	}

	const incAux = (idx) => {
		if (!canConfirm.value) return
		const row = auxConfirmRows.value?.[idx]
		if (!row) return
		const max = Math.max(0, Number(row.pending_qty || 0))
		row.quantity = Math.min(max, Number(row.quantity || 0) + 1)
	}

	const decAux = (idx) => {
		if (!canConfirm.value) return
		const row = auxConfirmRows.value?.[idx]
		if (!row) return
		row.quantity = Math.max(0, Number(row.quantity || 0) - 1)
	}

	const fillAuxPending = () => {
		if (!canConfirm.value) return
		auxConfirmRows.value = (auxConfirmRows.value || []).map(row => ({
			...row,
			quantity: Math.max(0, Number(row.pending_qty || 0)),
		}))
	}

	const clearAuxConfirm = () => {
		if (!canConfirm.value) return
		auxConfirmRows.value = (auxConfirmRows.value || []).map(row => ({
			...row,
			quantity: 0,
		}))
	}

	const closeDraftWithoutPending = async () => {
		const res = await uni.request({
			url: buildApiUrl(API_ENDPOINTS.STOCK.ISSUE_DRAFT_REJECT_REMAINING(draftId.value)),
			method: 'POST',
			header: getAuthHeaders(userStore.token),
			data: { reason: AUTO_CLOSE_REASON },
		})
		if (res.statusCode === 200) {
			uni.showToast({ title: $t('stock.issueConfirmNoPendingCloseSuccess'), icon: 'success' })
			await load()
			return true
		}
		if (res.statusCode === 401) {
			userStore.logout()
			return false
		}
		uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
		return false
	}

	const promptCloseDraftWithoutPending = async () => {
		uni.showModal({
			title: $t('common.confirm'),
			content: $t('stock.issueConfirmNoPendingCloseConfirm'),
			success: async (mr) => {
				if (!mr.confirm) return
				acting.value = true
				try {
					await closeDraftWithoutPending()
				} catch (e) {
					console.error('收口出库单失败:', e)
					uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
				} finally {
					acting.value = false
				}
			},
		})
	}

	const submitConfirm = async () => {
		if (!canConfirm.value) return
		if (!canSubmit.value) {
			if (!hasPendingRemaining.value && statusValue.value === 'partially_confirmed') {
				await promptCloseDraftWithoutPending()
				return
			}
			uni.showToast({ title: $t('stock.issueConfirmNeedItems'), icon: 'none' })
			return
		}

		uni.showModal({
			title: $t('common.confirm'),
			content: $t('stock.issueConfirmSubmitConfirm'),
			success: async (mr) => {
				if (!mr.confirm) return
				acting.value = true
				try {
					const payload = {
						serial_ids: selectedSerialIds.value.map(id => Number(id)).filter(id => Number.isFinite(id) && id > 0),
						aux_items: (auxConfirmRows.value || [])
							.filter(row => Number(row.quantity || 0) > 0)
							.map(row => ({
								equipment_id: Number(row.equipment_id),
								quantity: Number(row.quantity || 0),
							})),
						notes: String(notes.value || '').trim(),
					}

					const res = await uni.request({
						url: buildApiUrl(API_ENDPOINTS.STOCK.ISSUE_DRAFT_CONFIRM(draftId.value)),
						method: 'POST',
						header: getAuthHeaders(userStore.token),
						data: payload,
					})
					if (res.statusCode === 200) {
						uni.showToast({ title: $t('stock.issueConfirmSubmitSuccess'), icon: 'success' })
						notes.value = ''
						selectedSerialIds.value = []
						await load()
						return
					}
					if (res.statusCode === 401) {
						userStore.logout()
						return
					}
					if (isNoPendingConfirmError(res.data) && statusValue.value === 'partially_confirmed') {
						acting.value = false
						await promptCloseDraftWithoutPending()
						return
					}
					uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
				} catch (e) {
					console.error('确认出库失败:', e)
					uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
				} finally {
					acting.value = false
				}
			},
		})
	}

	const rejectDraft = async () => {
		if (!canReject.value) return
		const reason = String(rejectReason.value || '').trim()
		if (!reason) {
			uni.showToast({ title: $t('stock.issueConfirmRejectReasonRequired'), icon: 'none' })
			return
		}

		uni.showModal({
			title: $t('common.confirm'),
			content: $t('stock.issueConfirmRejectConfirm'),
			success: async (mr) => {
				if (!mr.confirm) return
				acting.value = true
				try {
					const res = await uni.request({
						url: buildApiUrl(API_ENDPOINTS.STOCK.ISSUE_DRAFT_REJECT(draftId.value)),
						method: 'POST',
						header: getAuthHeaders(userStore.token),
						data: { reason },
					})
					if (res.statusCode === 200) {
						uni.showToast({ title: $t('stock.issueConfirmRejectSuccess'), icon: 'success' })
						rejectReason.value = ''
						await load()
						return
					}
					if (res.statusCode === 401) {
						userStore.logout()
						return
					}
					uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
				} catch (e) {
					console.error('驳回领料单失败:', e)
					uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
				} finally {
					acting.value = false
				}
			},
		})
	}

	const rejectRemainingDraft = async () => {
		if (!canRejectRemaining.value) return
		const reason = String(rejectReason.value || '').trim()
		if (!reason) {
			uni.showToast({ title: $t('stock.issueConfirmRejectRemainingReasonRequired'), icon: 'none' })
			return
		}

		uni.showModal({
			title: $t('common.confirm'),
			content: $t('stock.issueConfirmRejectRemainingConfirm'),
			success: async (mr) => {
				if (!mr.confirm) return
				acting.value = true
				try {
					const res = await uni.request({
						url: buildApiUrl(API_ENDPOINTS.STOCK.ISSUE_DRAFT_REJECT_REMAINING(draftId.value)),
						method: 'POST',
						header: getAuthHeaders(userStore.token),
						data: { reason },
					})
					if (res.statusCode === 200) {
						uni.showToast({ title: $t('stock.issueConfirmRejectRemainingSuccess'), icon: 'success' })
						rejectReason.value = ''
						await load()
						return
					}
					if (res.statusCode === 401) {
						userStore.logout()
						return
					}
					uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
				} catch (e) {
					console.error('驳回剩余待确认项失败:', e)
					uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
				} finally {
					acting.value = false
				}
			},
		})
	}

	const rejectCurrent = async () => {
		if (canRejectRemaining.value) {
			await rejectRemainingDraft()
			return
		}
		if (canReject.value) {
			await rejectDraft()
		}
	}

	const goBack = () => {
		uni.navigateBack()
	}

	onLoad((query) => {
		draftId.value = String(query?.draft_id || query?.id || '').trim()
	})

	onMounted(async () => {
		await load()
	})

	onShow(async () => {
		await load()
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
	.hero-top { padding: 16px; display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
	.no { font-size: 14px; font-weight: 900; color: #111827; }
	.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; }
	.meta { margin-top: 8px; display: flex; align-items: center; gap: 10px; color: var(--text-secondary); font-size: 12px; }
	.dot { opacity: 0.6; }
	.meta-item { color: #6b7280; }
	.mini { padding: 8px 10px; border-radius: 12px; border: 1px solid rgba(229, 231, 235, 0.9); background: rgba(255, 255, 255, 0.72); display: flex; flex-direction: column; gap: 4px; }
	.mini .k { font-size: 11px; color: #6b7280; }
	.mini .v { font-size: 12px; color: #111827; font-weight: 700; }

	.summary-grid {
		padding: 0 16px 14px;
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 10px;
	}
	.s-item {
		padding: 10px 10px;
		border-radius: 12px;
		background: rgba(255, 255, 255, 0.72);
		border: 1px solid rgba(229, 231, 235, 0.9);
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.s-item .k { font-size: 11px; color: #6b7280; }
	.s-item .v { font-size: 16px; font-weight: 900; color: #111827; }
	.s-item.accent { border-color: rgba(var(--color-primary-rgb), 0.2); background: rgba(var(--color-primary-rgb), 0.06); }

	.tip { padding: 0 16px 12px; }
	.tip-text {
		display: block;
		padding: 10px 12px;
		border-radius: 14px;
		border: 1px solid rgba(229, 231, 235, 0.9);
		background: rgba(255, 255, 255, 0.72);
		color: #6b7280;
		font-size: 12px;
		line-height: 1.5;
	}

	.reject {
		margin: 0 16px 16px;
		padding: 10px 12px;
		border-radius: 14px;
		border: 1px solid rgba(239, 68, 68, 0.25);
		background: rgba(254, 242, 242, 0.9);
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.reject-k { font-size: 12px; color: #b91c1c; font-weight: 700; }
	.reject-v { font-size: 12px; color: #7f1d1d; line-height: 1.5; }

	.section { margin: 16px; border-radius: var(--radius-lg); overflow: hidden; }
	.header-actions { display: flex; align-items: center; gap: 10px; }

	.sub-title-wrap { margin-top: 10px; margin-bottom: 8px; }
	.sub-title { font-size: 12px; color: #6b7280; font-weight: 700; }
	.select-help { margin-bottom: 8px; display: block; font-size: 12px; color: #9ca3af; line-height: 1.5; }

	.serial-list { display: flex; flex-direction: column; gap: 10px; }
	.serial {
		border: 1px solid rgba(229, 231, 235, 0.9);
		background: #fff;
		border-radius: 14px;
		padding: 12px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}
	.serial.selected { border-color: rgba(var(--color-primary-rgb), 0.32); background: rgba(var(--color-primary-rgb), 0.04); }
	.serial-left { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
	.sn { font-size: 14px; font-weight: 900; color: #111827; }
	.time { font-size: 12px; color: #9ca3af; }
	.serial-right { display: flex; align-items: center; gap: 10px; }

	.aux-list { display: flex; flex-direction: column; gap: 12px; }
	.aux {
		border: 1px solid rgba(229, 231, 235, 0.9);
		background: #fff;
		border-radius: 14px;
		padding: 12px;
	}
	.aux-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
	.name { font-size: 14px; font-weight: 800; color: #111827; }
	.code { margin-top: 6px; font-size: 12px; color: #9ca3af; }

	.aux-nums {
		margin-top: 12px;
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 10px;
	}
	.n {
		padding: 10px 10px;
		border-radius: 12px;
		background: #f9fafb;
		border: 1px solid rgba(229, 231, 235, 0.9);
	}
	.n .k { font-size: 11px; color: #6b7280; }
	.n .v { margin-top: 6px; font-size: 16px; font-weight: 900; color: #111827; }
	.n.accent { border-color: rgba(var(--color-primary-rgb), 0.2); background: rgba(var(--color-primary-rgb), 0.06); }

	.stepper {
		margin-top: 6px;
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.qbtn {
		width: 30px;
		height: 30px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 8px;
		border: 1px solid #e5e7eb;
		background: #fff;
		color: #374151;
		font-size: 18px;
	}
	.qbtn.disabled {
		opacity: 0.45;
		pointer-events: none;
	}
	.qinput {
		flex: 1;
		height: 30px;
		padding: 0 8px;
		border-radius: 8px;
		border: 1px solid #e5e7eb;
		background: #fff;
		font-size: 13px;
		color: #111827;
	}

	.aux-total {
		margin-top: 12px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 10px 12px;
		border: 1px solid rgba(229, 231, 235, 0.9);
		border-radius: 12px;
		background: #f9fafb;
	}
	.aux-total .k { font-size: 12px; color: #6b7280; }
	.aux-total .v { font-size: 16px; font-weight: 900; color: #111827; }

	.empty {
		padding: 28px 16px;
		display: flex;
		justify-content: center;
		align-items: center;
	}
	.empty.compact { padding: 16px 12px; }
	.empty-text {
		font-size: 12px;
		color: #9ca3af;
		text-align: center;
	}

	.bottom-spacer { height: 108px; }
	.bottom-bar {
		position: fixed;
		left: 0;
		right: 0;
		bottom: 0;
		padding: 10px 16px 16px;
		background: rgba(247, 248, 251, 0.9);
		backdrop-filter: blur(10px);
		border-top: 1px solid rgba(229, 231, 235, 0.9);
		display: grid;
		gap: 10px;
	}
	.bottom-bar.single { grid-template-columns: 1fr; }
	.bottom-bar.double { grid-template-columns: 1fr 1fr; }
	.bottom-bar.triple { grid-template-columns: 1fr 1fr 1fr; }
	.bottom-bar :deep(.u-btn) { height: 48px; }
</style>
