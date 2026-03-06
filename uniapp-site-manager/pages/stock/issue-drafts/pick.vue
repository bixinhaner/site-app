<template>
	<view class="page" :key="languageStore.currentLocale">
		<CustomNavbar :title="$t('stock.issueDraftPickTitle')" :showBack="true" variant="brand" />

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
							<view class="u-tag" :class="draftStatusTagClass(draft.status)">{{ draftStatusLabel(draft.status) }}</view>
							<text class="dot">·</text>
							<text class="meta-item">{{ draft.request?.warehouse_name || '-' }}</text>
						</view>
					</view>
					<view class="right">
						<view class="chip">
							<text class="k">{{ $t('stock.issueDraftPickPendingSn') }}</text>
							<text class="v mono">{{ pendingSerials.length }}</text>
						</view>
					</view>
				</view>

				<view class="hint">
					<text class="hint-text">{{ $t('stock.issueDraftPickHint') }}</text>
				</view>
			</view>

			<view v-if="loading && !draft" class="list">
				<SkeletonCard mode="list" />
				<SkeletonCard mode="list" />
			</view>

			<view v-if="draft" class="section u-card">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.issueDraftMainDevices') }}</text>
					<view class="header-actions">
						<button class="u-btn u-btn-primary u-btn-sm u-pressable" :disabled="!canEdit" @click="scanByCamera">
							{{ $t('stock.issueDraftScan') }}
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
								:disabled="!canEdit"
							/>
							<button class="u-btn u-btn-secondary u-btn-sm u-pressable" :disabled="!snInput || !canEdit" @click="addSnFromInput">
								{{ $t('common.add') }}
							</button>
						</view>
						<text class="scanner-help">{{ $t('stock.issueDraftScanInputHelp') }}</text>
					</view>

					<view class="serials">
						<view v-if="draft.serials.length === 0" class="empty">
							<text class="empty-text">{{ $t('stock.issueDraftNoSn') }}</text>
						</view>

						<view v-else class="serial-list">
							<view class="serial" v-for="s in draft.serials" :key="s.id">
								<view class="serial-left">
									<text class="sn mono">{{ s.serial_number }}</text>
									<text class="time">{{ formatDt(s.scanned_at) }}</text>
								</view>
								<view class="serial-right">
									<view class="u-tag" :class="s.status === 'confirmed' ? 'u-tag-success' : 'u-tag-warning'">
										{{ s.status === 'confirmed' ? $t('stock.issueDraftSnConfirmed') : $t('stock.issueDraftSnPending') }}
									</view>
									<view
										v-if="canEdit && s.status === 'pending'"
										class="del u-pressable"
										@click="deleteSerial(s)"
									>
										<uni-icons type="closeempty" size="18" color="#ef4444" />
									</view>
								</view>
							</view>
						</view>
					</view>
				</view>
			</view>

			<view v-if="draft" class="section u-card">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.issueDraftAuxMaterials') }}</text>
					<view class="header-actions">
						<button class="u-btn u-btn-secondary u-btn-sm u-pressable" :disabled="!canEdit" @click="fillAuxMax">
							{{ $t('stock.issueDraftFillAuxMax') }}
						</button>
					</view>
				</view>
				<view class="u-card-content">
					<view v-if="(draft.aux_items || []).length === 0" class="empty">
						<text class="empty-text">{{ $t('stock.issueDraftNoAux') }}</text>
					</view>

					<view v-else class="aux-list">
						<view class="aux" v-for="(row, idx) in (draft.aux_items || [])" :key="row.equipment_id">
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
									<text class="k">{{ $t('stock.qtyRemaining') }}</text>
									<text class="v">{{ auxRemainingQty(row) }}</text>
								</view>
								<view class="n">
									<text class="k">{{ $t('stock.qtyPending') }}</text>
									<text class="v">{{ auxPendingQty(row) }}</text>
								</view>
								<view class="n accent planned">
									<text class="k">{{ $t('stock.issueDraftPlannedThisTime') }}</text>
									<view class="stepper">
										<view class="qbtn u-pressable" :class="{ disabled: !canEdit }" @click="decAux(idx)">−</view>
										<input
											class="qinput mono"
											type="number"
											v-model="row.planned_qty"
											@blur="normalizeAux(idx)"
											:disabled="!canEdit"
										/>
										<view class="qbtn u-pressable" :class="{ disabled: !canEdit }" @click="incAux(idx)">＋</view>
									</view>
								</view>
							</view>
						</view>
					</view>

					<view class="aux-total">
						<text class="k">{{ $t('stock.issueDraftAuxPlannedTotal') }}</text>
						<text class="v mono">{{ auxPlannedTotal }}</text>
					</view>
				</view>
			</view>

			<view class="bottom-spacer" />
		</scroll-view>

		<view class="bottom-bar" v-if="draft">
			<button class="u-btn u-btn-secondary u-pressable" :disabled="acting" @click="cancelDraft">
				{{ $t('common.cancel') }}
			</button>
			<button class="u-btn u-btn-primary u-pressable" :disabled="acting" @click="submitDraft">
				{{ $t('stock.issueDraftSubmit') }}
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
		import { parseBarcode } from '@/utils/barcode-parser.js'
		import { guardRouteAccess } from '@/utils/feature-access.js'
		import { scanAndParseDeviceCode, ScanDeviceCodeError, isScanCanceled } from '@/utils/scan-code.js'
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

	const snInput = ref('')

	const canEdit = computed(() => String(draft.value?.status || '') === 'draft')

	const normalizeDraftPayload = (rawDraft, { preserveAuxEdits = false } = {}) => {
		if (!rawDraft) return null
		const prevAuxMap = new Map((draft.value?.aux_items || []).map(r => [Number(r.equipment_id), r]))
		const next = {
			...rawDraft,
		}
		next.aux_items = (next.aux_items || []).map(r => {
			const equipmentId = Number(r.equipment_id)
			const prev = prevAuxMap.get(equipmentId)
			const plannedQty = preserveAuxEdits
				? Number(prev?.planned_qty ?? r.planned_qty ?? 0)
				: Number(r.planned_qty || 0)
			const basePlanned = preserveAuxEdits
				? Number(prev?._base_planned_qty ?? r.planned_qty ?? 0)
				: Number(r.planned_qty || 0)
			const baseConfirmed = preserveAuxEdits
				? Number(prev?._base_confirmed_qty ?? r.confirmed_qty ?? 0)
				: Number(r.confirmed_qty || 0)
			return {
				...r,
				planned_qty: plannedQty,
				_base_planned_qty: basePlanned,
				_base_confirmed_qty: baseConfirmed,
			}
		})
		return next
	}

	const pendingSerials = computed(() => {
		return (draft.value?.serials || []).filter(s => String(s.status) === 'pending')
	})

	const auxPlannedTotal = computed(() => {
		return (draft.value?.aux_items || []).reduce((s, r) => s + Number(r.planned_qty || 0), 0)
	})

	const formatDt = (ts) => {
		return formatDateTime(ts) || ''
	}

	const extractErrorMessage = (data, fallback = '') => {
		const detail = data?.detail
		if (!detail) return fallback || $t('messages.operationFailed')
		if (typeof detail === 'string') return detail
		return detail?.message || fallback || $t('messages.operationFailed')
	}

	const draftStatusLabel = (status) => {
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

	const draftStatusTagClass = (status) => {
		const s = String(status || '')
		if (s === 'draft') return 'u-tag-info'
		if (s === 'pending_confirm') return 'u-tag-warning'
		if (s === 'partially_confirmed') return 'u-tag-primary'
		if (s === 'confirmed') return 'u-tag-success'
		if (s === 'rejected') return 'u-tag-error'
		if (s === 'canceled') return 'u-tag-error'
		return 'u-tag-info'
	}

	const ensureLoggedIn = () => guardRouteAccess({
		userStore,
		route: 'pages/stock/issue-drafts/pick',
		t: $t,
		redirectUrl: '/pages/home/home',
	})

	const load = async () => {
		if (!ensureLoggedIn()) return
		if (!draftId.value) return
		loading.value = true
		try {
			const res = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.STOCK.ISSUE_DRAFT_DETAIL(draftId.value)),
				method: 'GET',
				header: getAuthHeaders(userStore.token),
			})
			if (res.statusCode === 200 && res.data?.draft) {
				draft.value = normalizeDraftPayload(res.data.draft, { preserveAuxEdits: false })
				if (String(draft.value?.status || '') !== 'draft') {
					setTimeout(() => {
						uni.redirectTo({ url: `/pages/stock/issue-drafts/detail?draft_id=${draftId.value}` })
					}, 50)
				}
				return
			}
			if (res.statusCode === 401) {
				userStore.logout()
				return
			}
			uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
		} catch (e) {
			console.error('加载领料草稿失败:', e)
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

		const scanByCamera = async () => {
			if (!canEdit.value) return
			const scanned = await scanAndParseDeviceCode()
			if (!scanned.ok) {
				if (scanned.error === ScanDeviceCodeError.UNSUPPORTED_SCAN_TYPE) {
					uni.showToast({
						title: $t('stock.unsupportedScanType', { type: scanned.scanType || 'UNKNOWN' }),
						icon: 'none',
					})
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
			await submitScan(scanned.raw, scanned.parsed)
		}

	const addSnFromInput = async () => {
		if (!canEdit.value) return
		const raw = String(snInput.value || '').trim()
		if (!raw) return
		snInput.value = ''
		await submitScan(raw)
	}

		const submitScan = async (barcode, parsedBarcode = null) => {
			if (!draftId.value) return
			acting.value = true
			try {
				const parsed = parsedBarcode || parseBarcode(barcode)
				const res = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.STOCK.ISSUE_DRAFT_SCAN_MAIN(draftId.value)),
				method: 'POST',
				header: getAuthHeaders(userStore.token),
				data: {
					barcode,
					parsed_barcode: parsed,
				},
			})
			if (res.statusCode === 200 && res.data?.draft) {
				draft.value = normalizeDraftPayload(res.data.draft, { preserveAuxEdits: canEdit.value })
				uni.showToast({ title: $t('stock.issueDraftScanSuccess'), icon: 'success' })
				return
			}
			if (res.statusCode === 401) {
				userStore.logout()
				return
			}
			uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
		} catch (e) {
			console.error('扫码失败:', e)
			uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
		} finally {
			acting.value = false
		}
	}

	const deleteSerial = async (s) => {
		if (!canEdit.value) return
		const serialId = Number(s?.id)
		if (!serialId) return
		uni.showModal({
			title: $t('common.confirm'),
			content: $t('stock.issueDraftDeleteSnConfirm'),
			success: async (r) => {
				if (!r.confirm) return
				acting.value = true
				try {
					const res = await uni.request({
						url: buildApiUrl(API_ENDPOINTS.STOCK.ISSUE_DRAFT_SERIAL_DELETE(draftId.value, serialId)),
						method: 'DELETE',
						header: getAuthHeaders(userStore.token),
					})
					if (res.statusCode === 200) {
						await load()
						return
					}
					if (res.statusCode === 401) {
						userStore.logout()
						return
					}
					uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
				} catch (e) {
					console.error('删除SN失败:', e)
					uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
				} finally {
					acting.value = false
				}
			}
		})
	}

	const requestItemByEquipId = (equipmentId) => {
		const items = draft.value?.request?.items || []
		return items.find(it => Number(it.equipment_id) === Number(equipmentId)) || null
	}

	const auxBasePendingQty = (row) => {
		const basePlanned = Number(row?._base_planned_qty ?? row?.planned_qty ?? 0)
		const baseConfirmed = Number(row?._base_confirmed_qty ?? row?.confirmed_qty ?? 0)
		return Math.max(0, basePlanned - baseConfirmed)
	}

	const auxPendingQty = (row) => {
		return Math.max(0, Number(row?.planned_qty || 0) - Number(row?.confirmed_qty || 0))
	}

	const auxPlannedCap = (row) => {
		const reqIt = requestItemByEquipId(row.equipment_id)
		const remaining = Number(reqIt?.remaining_qty || 0)
		return Math.max(0, remaining + auxBasePendingQty(row))
	}

	const auxRemainingQty = (row) => {
		const cap = auxPlannedCap(row)
		return Math.max(0, cap - auxPendingQty(row))
	}

	const normalizeAux = (idx) => {
		if (!canEdit.value) return
		const rows = draft.value?.aux_items || []
		const row = rows[idx]
		if (!row) return
		let n = Number(String(row.planned_qty || '').trim())
		if (!Number.isFinite(n) || n < 0) n = 0
		const max = auxPlannedCap(row)
		if (n > max) n = max
		row.planned_qty = Math.floor(n)
	}

	const incAux = (idx) => {
		if (!canEdit.value) return
		const row = (draft.value?.aux_items || [])[idx]
		if (!row) return
		const max = auxPlannedCap(row)
		row.planned_qty = Math.min(max, Number(row.planned_qty || 0) + 1)
	}

	const decAux = (idx) => {
		if (!canEdit.value) return
		const row = (draft.value?.aux_items || [])[idx]
		if (!row) return
		row.planned_qty = Math.max(0, Number(row.planned_qty || 0) - 1)
	}

	const fillAuxMax = () => {
		if (!canEdit.value) return
		const rows = draft.value?.aux_items || []
		rows.forEach((r) => {
			r.planned_qty = auxPlannedCap(r)
		})
		uni.showToast({ title: $t('stock.issueDraftAuxFilled'), icon: 'success' })
	}

	const saveAux = async () => {
		const rows = draft.value?.aux_items || []
		const payload = rows.map(r => ({
			equipment_id: Number(r.equipment_id),
			planned_qty: Number(r.planned_qty || 0),
		}))
		const res = await uni.request({
			url: buildApiUrl(API_ENDPOINTS.STOCK.ISSUE_DRAFT_AUX_ITEMS(draftId.value)),
			method: 'PUT',
			header: getAuthHeaders(userStore.token),
			data: { items: payload },
		})
		if (res.statusCode === 200 && res.data?.draft) {
			draft.value = normalizeDraftPayload(res.data.draft, { preserveAuxEdits: false })
			return true
		}
		if (res.statusCode === 401) {
			userStore.logout()
			return false
		}
		uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
		return false
	}

	const submitDraft = async () => {
		if (!canEdit.value) {
			uni.redirectTo({ url: `/pages/stock/issue-drafts/detail?draft_id=${draftId.value}` })
			return
		}
		uni.showModal({
			title: $t('common.confirm'),
			content: $t('stock.issueDraftSubmitConfirm'),
			success: async (r) => {
				if (!r.confirm) return
				acting.value = true
				try {
					const saved = await saveAux()
					if (!saved) return
					const res = await uni.request({
						url: buildApiUrl(API_ENDPOINTS.STOCK.ISSUE_DRAFT_SUBMIT(draftId.value)),
						method: 'POST',
						header: getAuthHeaders(userStore.token),
					})
					if (res.statusCode === 200) {
						const st = String(res.data?.status || res.data?.draft_status || '')
						const toastTitle = st && st !== 'pending_confirm'
							? $t('stock.issueDraftIssued')
							: $t('stock.issueDraftSubmitted')
						uni.showToast({ title: toastTitle, icon: 'success' })
						setTimeout(() => {
							uni.redirectTo({ url: `/pages/stock/issue-drafts/detail?draft_id=${draftId.value}` })
						}, 500)
						return
					}
					if (res.statusCode === 401) {
						userStore.logout()
						return
					}
					uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
				} catch (e) {
					console.error('提交领料单失败:', e)
					uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
				} finally {
					acting.value = false
				}
			}
		})
	}

	const cancelDraft = async () => {
		if (!draftId.value) return
		if (!canEdit.value) {
			uni.navigateBack()
			return
		}
		uni.showModal({
			title: $t('common.confirm'),
			content: $t('stock.issueDraftCancelConfirm'),
			success: async (r) => {
				if (!r.confirm) return
				acting.value = true
				try {
					const res = await uni.request({
						url: buildApiUrl(API_ENDPOINTS.STOCK.ISSUE_DRAFT_CANCEL(draftId.value)),
						method: 'POST',
						header: getAuthHeaders(userStore.token),
						data: { reason: '' },
					})
					if (res.statusCode === 200) {
						uni.showToast({ title: $t('stock.issueDraftCanceled'), icon: 'success' })
						setTimeout(() => uni.navigateBack(), 500)
						return
					}
					if (res.statusCode === 401) {
						userStore.logout()
						return
					}
					uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
				} catch (e) {
					console.error('取消领料单失败:', e)
					uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
				} finally {
					acting.value = false
				}
			}
		})
	}

	onLoad((query) => {
		draftId.value = String(query?.draft_id || '').trim()
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
	.chip { padding: 10px 12px; border-radius: 14px; border: 1px solid rgba(var(--color-primary-rgb), 0.22); background: rgba(255, 255, 255, 0.72); display: flex; flex-direction: column; gap: 6px; min-width: 120px; }
	.chip .k { font-size: 11px; color: #6b7280; }
	.chip .v { font-size: 18px; font-weight: 900; color: #111827; }

	.hint { padding: 0 16px 16px; }
	.hint-text { display: block; padding: 10px 12px; border-radius: 14px; border: 1px solid rgba(229, 231, 235, 0.9); background: rgba(255, 255, 255, 0.72); color: #6b7280; font-size: 12px; line-height: 1.5; }

	.section { margin: 16px; border-radius: var(--radius-lg); overflow: hidden; }
	.header-actions { display: flex; align-items: center; gap: 10px; }

	.scanner { margin-bottom: 14px; }
	.scanner-row { display: flex; align-items: center; gap: 10px; }
	.scanner-input { flex: 1; }
	.scanner-help { margin-top: 8px; font-size: 12px; color: #9ca3af; }

	.serials { display: flex; flex-direction: column; gap: 10px; }
	.serial-list { display: flex; flex-direction: column; gap: 10px; }
	.serial { border: 1px solid rgba(229, 231, 235, 0.9); background: #fff; border-radius: 14px; padding: 12px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
	.serial-left { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
	.sn { font-size: 14px; font-weight: 900; color: #111827; }
	.time { font-size: 12px; color: #9ca3af; }
	.serial-right { display: flex; align-items: center; gap: 10px; }
	.del { width: 36px; height: 36px; border-radius: 12px; display: flex; align-items: center; justify-content: center; background: rgba(239, 68, 68, 0.10); }

	.aux-list { display: flex; flex-direction: column; gap: 12px; }
	.aux { border: 1px solid rgba(229, 231, 235, 0.9); background: #fff; border-radius: 14px; padding: 10px; }
	.aux-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
	.aux-head .left { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
	.name { font-size: 14px; font-weight: 800; color: #111827; }
	.code { font-size: 12px; color: #9ca3af; }

	.aux-nums {
		margin-top: 10px;
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 8px;
		align-items: stretch;
	}
	.n {
		min-width: 0;
		padding: 8px 9px;
		border-radius: 12px;
		background: #f9fafb;
		border: 1px solid rgba(229, 231, 235, 0.9);
	}
	.n .k { display: block; font-size: 11px; line-height: 1.3; color: #6b7280; }
	.n .v { margin-top: 4px; font-size: 15px; line-height: 1.2; font-weight: 900; color: #111827; }
	.n.accent { border-color: rgba(var(--color-primary-rgb), 0.28); background: rgba(var(--color-primary-rgb), 0.06); }
	.n.planned { grid-column: 1 / -1; }

	.stepper {
		margin-top: 6px;
		display: flex;
		align-items: center;
		min-width: 0;
		width: 100%;
		border: 1px solid rgba(229, 231, 235, 0.9);
		border-radius: 10px;
		overflow: hidden;
		background: #f9fafb;
	}
	.qbtn {
		flex: 0 0 34px;
		height: 34px;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 17px;
		font-weight: 700;
		color: #111827;
		background: #f3f4f6;
	}
	.qbtn.disabled { opacity: 0.5; pointer-events: none; }
	.qinput {
		flex: 1;
		min-width: 0;
		width: auto;
		height: 34px;
		text-align: center;
		font-size: 14px;
		font-weight: 900;
		color: #111827;
	}

	.aux-total { margin-top: 12px; padding: 10px 12px; border-radius: 14px; border: 1px solid rgba(229, 231, 235, 0.9); background: rgba(255, 255, 255, 0.72); display: flex; align-items: center; justify-content: space-between; }
	.aux-total .k { font-size: 12px; color: #6b7280; }
	.aux-total .v { font-size: 16px; font-weight: 900; color: #111827; }

	.empty { padding: 10px 0; display: flex; justify-content: center; }
	.empty-text { color: #9ca3af; font-size: 13px; }

	.bottom-spacer {
		height: calc(110px + constant(safe-area-inset-bottom));
		height: calc(110px + env(safe-area-inset-bottom));
	}
	.bottom-bar {
		position: fixed;
		left: 0;
		right: 0;
		bottom: 0;
		padding: 10px 16px calc(16px + constant(safe-area-inset-bottom));
		padding: 10px 16px calc(16px + env(safe-area-inset-bottom));
		background: rgba(247, 248, 251, 0.90);
		backdrop-filter: blur(10px);
		border-top: 1px solid rgba(229, 231, 235, 0.9);
		display: grid;
		grid-template-columns: 1fr 1.2fr;
		gap: 12px;
	}

	@media (max-width: 375px) {
		.n {
			padding: 8px;
		}
		.qbtn {
			flex-basis: 32px;
			height: 32px;
		}
		.qinput {
			height: 32px;
			font-size: 13px;
		}
	}
</style>
