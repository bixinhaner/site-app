<template>
	<view class="page" :key="languageStore.currentLocale">
		<CustomNavbar :title="$t('stock.materialRequestDetailTitle')" :showBack="true" variant="brand" />

		<scroll-view
			class="content"
			scroll-y
			refresher-enabled
			:refresher-triggered="refreshing"
			@refresherrefresh="handleRefresh"
			refresher-background="#f7f8fb"
		>
			<view class="hero u-card" v-if="request">
				<view class="hero-top">
					<view class="left">
						<text class="no mono">{{ request.request_no }}</text>
						<view class="meta">
							<view class="u-tag" :class="statusTagClass(request.status)">{{ statusLabel(request.status) }}</view>
							<text class="dot">·</text>
							<text class="meta-item">{{ request.warehouse_name || '-' }}</text>
						</view>
					</view>
					<view class="right">
						<view class="stat-card">
							<text class="k">{{ $t('stock.materialRequestStatRemaining') }}</text>
							<text class="v">{{ remainingTotal }}</text>
						</view>
					</view>
				</view>

				<view class="steps">
					<view class="step" :class="{ active: stepActive >= 1 }">
						<view class="dot" />
						<text class="label">{{ $t('stock.stepRequest') }}</text>
					</view>
					<view class="line" :class="{ active: stepActive >= 2 }" />
					<view class="step" :class="{ active: stepActive >= 2 }">
						<view class="dot" />
						<text class="label">{{ $t('stock.stepApprove') }}</text>
					</view>
					<view class="line" :class="{ active: stepActive >= 3 }" />
					<view class="step" :class="{ active: stepActive >= 3 }">
						<view class="dot" />
						<text class="label">{{ $t('stock.stepPick') }}</text>
					</view>
					<view class="line" :class="{ active: stepActive >= 4 }" />
					<view class="step" :class="{ active: stepActive >= 4 }">
						<view class="dot" />
						<text class="label">{{ $t('stock.stepStockOut') }}</text>
					</view>
				</view>

				<view class="notes" v-if="request.notes">
					<text class="notes-k">{{ $t('stock.materialRequestNotes') }}</text>
					<text class="notes-v">{{ request.notes }}</text>
				</view>

				<view class="tips" v-if="tipText">
					<text class="tips-text">{{ tipText }}</text>
				</view>
			</view>

			<view v-if="loading && !request" class="list">
				<SkeletonCard mode="list" />
				<SkeletonCard mode="list" />
			</view>

			<view class="section u-card" v-if="request">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.materialRequestItems') }}</text>
					<view class="tiny">
						<text class="tiny-item">{{ $t('stock.materialRequestMain') }} {{ mainRequested }}</text>
						<text class="tiny-dot">·</text>
						<text class="tiny-item">{{ $t('stock.materialRequestAux') }} {{ auxRequested }}</text>
					</view>
				</view>
				<view class="u-card-content">
					<view class="items">
						<view class="item" v-for="it in request.items" :key="it.id">
							<view class="item-head">
								<view class="left">
									<text class="name">{{ it.equipment_name }}</text>
									<text class="code mono">{{ it.equipment_code }}</text>
								</view>
								<view class="right">
									<view class="u-tag" :class="it.equipment_category === 'main_device' ? 'u-tag-warning' : 'u-tag-info'">
										{{ it.equipment_category === 'main_device' ? $t('stock.mainDevice') : $t('stock.auxMaterial') }}
									</view>
								</view>
							</view>

							<view class="nums">
								<view class="n">
									<text class="k">{{ $t('stock.qtyRequested') }}</text>
									<text class="v">{{ it.requested_qty }}</text>
								</view>
								<view class="n">
									<text class="k">{{ $t('stock.qtyApproved') }}</text>
									<text class="v">{{ it.approved_qty }}</text>
								</view>
								<view class="n">
									<text class="k">{{ $t('stock.qtyIssued') }}</text>
									<text class="v">{{ it.issued_qty }}</text>
								</view>
								<view class="n">
									<text class="k">{{ $t('stock.qtyPending') }}</text>
									<text class="v">{{ it.pending_qty }}</text>
								</view>
								<view class="n accent">
									<text class="k">{{ $t('stock.qtyRemaining') }}</text>
									<text class="v">{{ it.remaining_qty }}</text>
								</view>
							</view>
						</view>
					</view>

					<view v-if="request.approval_comments && (request.status === 'rejected' || request.status === 'canceled' || request.status === 'abandoned')" class="reason">
						<text class="reason-k">{{ $t('stock.materialRequestReason') }}</text>
						<text class="reason-v">{{ request.approval_comments }}</text>
					</view>
				</view>
			</view>

			<view class="bottom-spacer" />
		</scroll-view>

		<view class="bottom-bar" v-if="request">
			<template v-if="request.status === 'draft'">
				<button class="u-btn u-btn-secondary u-pressable" :disabled="acting" @click="goEdit">
					{{ $t('common.edit') }}
				</button>
				<button class="u-btn u-btn-primary u-pressable" :disabled="acting" @click="submitDraft">
					{{ $t('common.submit') }}
				</button>
				<button class="u-btn u-btn-danger u-pressable" :disabled="acting" @click="cancelDraft">
					{{ $t('stock.materialRequestCancel') }}
				</button>
			</template>

			<template v-else-if="canStartPick || canAbandon">
				<button class="u-btn u-btn-danger u-pressable" v-if="canAbandon" :disabled="acting" @click="abandonRequest">
					{{ $t('stock.materialRequestAbandon') }}
				</button>
				<button class="u-btn u-btn-primary u-pressable" v-if="canStartPick" :disabled="acting" @click="startPick">
					{{ $t('stock.materialRequestStartPick') }}
				</button>
			</template>

			<template v-else>
				<button class="u-btn u-btn-secondary u-pressable" @click="goList">
					{{ $t('stock.materialRequestBackToList') }}
				</button>
			</template>
		</view>
		<ReasonInputDialog
			:visible="abandonDialogVisible"
			v-model="abandonReason"
			:title="$t('stock.materialRequestAbandonDialogTitle')"
			:message="$t('stock.materialRequestAbandonConfirm')"
			:label="$t('stock.materialRequestAbandonReasonLabel')"
			:placeholder="$t('stock.materialRequestAbandonReasonPlaceholder')"
			:helper-text="$t('stock.materialRequestAbandonReasonHelper')"
			:error-text="abandonError"
			:confirm-text="$t('stock.materialRequestAbandonSubmit')"
			:cancel-text="$t('common.cancel')"
			:submitting-text="$t('common.loading')"
			:submitting="abandonSubmitting"
			:maxlength="200"
			@close="closeAbandonDialog"
			@confirm="submitAbandonRequest"
		/>
	</view>
</template>

<script setup>
	import { computed, getCurrentInstance, onMounted, ref } from 'vue'
	import { onLoad, onShow } from '@dcloudio/uni-app'
	import { useUserStore } from '@/stores/user'
	import { useLanguageStore } from '@/stores/language'
	import { buildApiUrl, API_ENDPOINTS, getAuthHeaders } from '@/config/api.js'
	import { guardRouteAccess } from '@/utils/feature-access.js'
	import CustomNavbar from '@/components/CustomNavbar.vue'
	import ReasonInputDialog from '@/components/ReasonInputDialog.vue'
	import SkeletonCard from '@/components/SkeletonCard.vue'
	import { reportMobileLog } from '@/utils/mobileLogReporter.js'

	const userStore = useUserStore()
	const languageStore = useLanguageStore()
	const { $t } = getCurrentInstance().appContext.config.globalProperties

	const id = ref('')
	const request = ref(null)
	const loading = ref(false)
	const refreshing = ref(false)
	const acting = ref(false)
	const abandonDialogVisible = ref(false)
	const abandonReason = ref('')
	const abandonError = ref('')
	const abandonSubmitting = ref(false)

	const extractErrorMessage = (data, fallback = '') => {
		const detail = data?.detail
		if (!detail) return fallback || $t('messages.operationFailed')
		if (typeof detail === 'string') return detail
		return detail?.message || fallback || $t('messages.operationFailed')
	}

	const statusLabel = (status) => {
		const map = {
			draft: $t('stock.statusDraft'),
			submitted: $t('stock.statusSubmitted'),
			approved: $t('stock.statusApproved'),
			partially_approved: $t('stock.statusPartiallyApproved'),
			abandoned: $t('stock.statusAbandoned'),
			rejected: $t('stock.statusRejected'),
			canceled: $t('stock.statusCanceled'),
			closed: $t('stock.statusClosed'),
		}
		return map[String(status || '')] || String(status || '-')
	}

	const statusTagClass = (status) => {
		const s = String(status || '')
		if (s === 'draft') return 'u-tag-info'
		if (s === 'submitted') return 'u-tag-warning'
		if (s === 'approved') return 'u-tag-success'
		if (s === 'partially_approved') return 'u-tag-primary'
		if (s === 'closed') return 'u-tag-success'
		if (s === 'abandoned') return 'u-tag-error'
		if (s === 'canceled') return 'u-tag-error'
		if (s === 'rejected') return 'u-tag-error'
		return 'u-tag-info'
	}

	const mainRequested = computed(() => {
		const items = request.value?.items || []
		return items.filter(it => it.equipment_category === 'main_device').reduce((s, it) => s + Number(it.requested_qty || 0), 0)
	})
	const auxRequested = computed(() => {
		const items = request.value?.items || []
		return items.filter(it => it.equipment_category === 'auxiliary').reduce((s, it) => s + Number(it.requested_qty || 0), 0)
	})
	const remainingTotal = computed(() => {
		const items = request.value?.items || []
		return items.reduce((s, it) => s + Number(it.remaining_qty || 0), 0)
	})
	const issuedTotal = computed(() => {
		const items = request.value?.items || []
		return items.reduce((s, it) => s + Number(it.issued_qty || 0), 0)
	})
	const currentUserId = computed(() => Number(userStore.userInfo?.id || 0) || 0)
	const isRequester = computed(() => {
		return currentUserId.value > 0 && Number(request.value?.requester_id || 0) === currentUserId.value
	})
	const hasWarehouseAccess = computed(() => {
		if (userStore.hasGlobalInventoryAccess) return true
		const warehouseId = Number(request.value?.warehouse_id || 0)
		if (!warehouseId) return false
		const managedIds = Array.isArray(userStore.managedWarehouseIds) ? userStore.managedWarehouseIds : []
		return managedIds.includes(warehouseId)
	})

	const canStartPick = computed(() => {
		const s = String(request.value?.status || '')
		return (s === 'approved' || s === 'partially_approved') && remainingTotal.value > 0 && isRequester.value
	})
	const canAbandon = computed(() => {
		const s = String(request.value?.status || '')
		return (s === 'approved' || s === 'partially_approved') && issuedTotal.value <= 0 && (isRequester.value || hasWarehouseAccess.value)
	})

	const stepActive = computed(() => {
		const s = String(request.value?.status || '')
		if (s === 'draft') return 1
		if (s === 'submitted') return 2
		if (s === 'approved' || s === 'partially_approved') return 3
		if (s === 'abandoned') return 3
		if (s === 'closed') return 4
		return 2
	})

	const tipText = computed(() => {
		const s = String(request.value?.status || '')
		if ((s === 'approved' || s === 'partially_approved') && remainingTotal.value > 0 && !isRequester.value) {
			return $t('stock.materialRequestStartPickRequesterOnly')
		}
		if (s === 'submitted') return $t('stock.materialRequestTipSubmitted')
		if (s === 'approved' || s === 'partially_approved') return $t('stock.materialRequestTipApproved')
		if (s === 'abandoned') return $t('stock.materialRequestTipAbandoned')
		if (s === 'closed') return $t('stock.materialRequestTipClosed')
		if (s === 'rejected') return $t('stock.materialRequestTipRejected')
		if (s === 'canceled') return $t('stock.materialRequestTipCanceled')
		return ''
	})

	const ensureLoggedIn = () => guardRouteAccess({
		userStore,
		route: 'pages/stock/material-requests/detail',
		t: $t,
		redirectUrl: '/pages/home/home',
	})

	const load = async () => {
		if (!ensureLoggedIn()) return
		if (!id.value) return

		loading.value = true
		try {
			const res = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.STOCK.MATERIAL_REQUEST_DETAIL(id.value)),
				method: 'GET',
				header: getAuthHeaders(userStore.token),
			})
			if (res.statusCode === 200 && res.data?.request) {
				request.value = res.data.request
				return
			}
			if (res.statusCode === 401) {
				userStore.logout()
				return
			}
			uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
		} catch (e) {
			console.error('加载申请详情失败:', e)
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

	const goEdit = () => {
		uni.navigateTo({ url: `/pages/stock/material-requests/create?id=${id.value}` })
	}

	const logAbandonEvent = (message, level = 'INFO', extra = {}) => {
		reportMobileLog({
			level,
			tag: 'material_request_abandon',
			message,
			context: {
				request_id: request.value?.id || id.value || '',
				request_no: request.value?.request_no || '',
				request_status: request.value?.status || '',
				warehouse_id: request.value?.warehouse_id || null,
				requester_id: request.value?.requester_id || null,
				current_user_id: currentUserId.value || null,
				is_requester: isRequester.value,
				has_warehouse_access: hasWarehouseAccess.value,
				reason_length: String(abandonReason.value || '').trim().length,
				...extra,
			},
		})
	}

	const submitDraft = async () => {
		if (!request.value) return
		uni.showModal({
			title: $t('common.confirm'),
			content: $t('stock.materialRequestSubmitConfirm'),
			success: async (r) => {
				if (!r.confirm) return
				acting.value = true
				try {
					const res = await uni.request({
						url: buildApiUrl(API_ENDPOINTS.STOCK.MATERIAL_REQUEST_SUBMIT(id.value)),
						method: 'POST',
						header: getAuthHeaders(userStore.token),
					})
					if (res.statusCode === 200 && res.data?.request) {
						request.value = res.data.request
						uni.showToast({ title: $t('stock.materialRequestSubmitted'), icon: 'success' })
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
					acting.value = false
				}
			}
		})
	}

	const cancelDraft = async () => {
		if (!request.value) return
		uni.showModal({
			title: $t('common.confirm'),
			content: $t('stock.materialRequestCancelConfirm'),
			success: async (r) => {
				if (!r.confirm) return
				acting.value = true
				try {
					const res = await uni.request({
						url: buildApiUrl(API_ENDPOINTS.STOCK.MATERIAL_REQUEST_CANCEL(id.value)),
						method: 'POST',
						header: getAuthHeaders(userStore.token),
						data: { reason: '' },
					})
					if (res.statusCode === 200) {
						uni.showToast({ title: $t('stock.materialRequestCanceled'), icon: 'success' })
						await load()
						return
					}
					if (res.statusCode === 401) {
						userStore.logout()
						return
					}
					uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
				} catch (e) {
					console.error('取消申请失败:', e)
					uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
				} finally {
					acting.value = false
				}
			}
		})
	}

	const abandonRequest = async () => {
		if (!request.value) return
		if (!canAbandon.value) return
		abandonReason.value = ''
		abandonError.value = ''
		abandonDialogVisible.value = true
		logAbandonEvent('open_dialog')
	}

	const closeAbandonDialog = () => {
		if (abandonSubmitting.value) return
		abandonDialogVisible.value = false
		abandonReason.value = ''
		abandonError.value = ''
	}

	const submitAbandonRequest = async () => {
		if (!request.value || abandonSubmitting.value) return
		const reason = String(abandonReason.value || '').trim()
		if (!reason) {
			abandonError.value = $t('stock.materialRequestAbandonReasonRequired')
			logAbandonEvent('validate_failed', 'WARN', { error: abandonError.value })
			return
		}

		abandonError.value = ''
		abandonSubmitting.value = true
		acting.value = true
		logAbandonEvent('submit_start')
		try {
			const res = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.STOCK.MATERIAL_REQUEST_ABANDON(id.value)),
				method: 'POST',
				header: getAuthHeaders(userStore.token),
				data: { reason },
			})
			if (res.statusCode === 200) {
				logAbandonEvent('submit_success')
				abandonDialogVisible.value = false
				abandonReason.value = ''
				abandonError.value = ''
				uni.showToast({ title: $t('stock.materialRequestAbandoned'), icon: 'success' })
				await load()
				return
			}
			if (res.statusCode === 401) {
				userStore.logout()
				return
			}
			abandonError.value = extractErrorMessage(res.data)
			logAbandonEvent('submit_failed', 'WARN', {
				error: abandonError.value,
				response_status: res.statusCode,
			})
			uni.showToast({ title: abandonError.value, icon: 'none' })
		} catch (e) {
			console.error('放弃领货失败:', e)
			abandonError.value = $t('messages.networkError')
			logAbandonEvent('submit_failed', 'ERROR', {
				error: abandonError.value,
				exception: String(e?.message || e || ''),
			})
			uni.showToast({ title: abandonError.value, icon: 'none' })
		} finally {
			abandonSubmitting.value = false
			acting.value = false
		}
	}

	const startPick = async () => {
		if (!request.value) return
		if (!canStartPick.value) return
		acting.value = true
		try {
			const res = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.STOCK.ISSUE_DRAFTS),
				method: 'POST',
				header: getAuthHeaders(userStore.token),
				data: { request_id: id.value },
			})
			if (res.statusCode === 200 && res.data?.draft?.id) {
				const draftId = res.data.draft.id
				uni.navigateTo({ url: `/pages/stock/issue-drafts/pick?draft_id=${draftId}` })
				return
			}
			if (res.statusCode === 401) {
				userStore.logout()
				return
			}
			uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
		} catch (e) {
			console.error('创建领料草稿失败:', e)
			uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
		} finally {
			acting.value = false
		}
	}

	const goList = () => {
		uni.navigateBack()
	}

	onLoad((query) => {
		id.value = String(query?.id || '').trim()
	})

	onMounted(async () => {
		await load()
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
			radial-gradient(920px 260px at 8% 0%, rgba(var(--color-primary-rgb), 0.16), transparent 62%),
			radial-gradient(920px 260px at 90% 10%, rgba(var(--color-brand-blue-rgb), 0.10), transparent 62%),
			linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(255, 255, 255, 0.90));
		border: 1px solid rgba(229, 231, 235, 0.9);
		box-shadow: 0 10px 26px rgba(17, 24, 39, 0.08);
	}

	.hero-top {
		padding: 16px;
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 12px;
	}
	.no { font-size: 14px; font-weight: 900; color: #111827; }
	.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; }
	.meta { margin-top: 8px; display: flex; align-items: center; gap: 10px; color: var(--text-secondary); font-size: 12px; }
	.dot { opacity: 0.6; }
	.meta-item { color: #6b7280; }

	.stat-card {
		padding: 12px 12px;
		border-radius: 14px;
		border: 1px solid rgba(var(--color-primary-rgb), 0.22);
		background: rgba(255, 255, 255, 0.72);
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-width: 120px;
	}
	.stat-card .k { font-size: 11px; color: #6b7280; }
	.stat-card .v { font-size: 18px; font-weight: 900; color: #111827; }

	.steps {
		padding: 0 16px 14px;
		display: flex;
		align-items: center;
	}
	.step { display: flex; flex-direction: column; align-items: center; gap: 8px; width: 20%; }
	.step .dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: #d1d5db;
		box-shadow: 0 0 0 4px rgba(209, 213, 219, 0.35);
	}
	.step.active .dot {
		background: var(--color-primary);
		box-shadow: 0 0 0 4px rgba(var(--color-primary-rgb), 0.20);
	}
	.step .label { font-size: 11px; color: #6b7280; }
	.step.active .label { color: #111827; font-weight: 700; }
	.line { height: 2px; flex: 1; background: #e5e7eb; margin: 0 6px; border-radius: 999px; }
	.line.active { background: rgba(var(--color-primary-rgb), 0.55); }

	.notes { padding: 0 16px 14px; display: flex; gap: 10px; }
	.notes-k { font-size: 12px; color: #6b7280; }
	.notes-v { font-size: 12px; color: #111827; line-height: 1.5; flex: 1; }

	.tips { padding: 0 16px 16px; }
	.tips-text {
		display: block;
		padding: 10px 12px;
		border-radius: 14px;
		border: 1px solid rgba(229, 231, 235, 0.9);
		background: rgba(255, 255, 255, 0.72);
		color: #6b7280;
		font-size: 12px;
		line-height: 1.5;
	}

	.section { margin: 16px; border-radius: var(--radius-lg); overflow: hidden; }
	.tiny { display: flex; align-items: center; gap: 8px; color: #6b7280; font-size: 12px; }
	.tiny-dot { opacity: 0.5; }

	.items { display: flex; flex-direction: column; gap: 12px; }
	.item {
		border: 1px solid rgba(229, 231, 235, 0.9);
		background: #fff;
		border-radius: 14px;
		padding: 12px;
	}
	.item-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
	.name { font-size: 14px; font-weight: 800; color: #111827; }
	.code { margin-top: 6px; font-size: 12px; color: #9ca3af; }

	.nums {
		margin-top: 12px;
		display: grid;
		grid-template-columns: 1fr 1fr 1fr;
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
	.n.accent { border-color: rgba(var(--color-primary-rgb), 0.28); background: rgba(var(--color-primary-rgb), 0.06); }

	.reason { margin-top: 12px; padding: 10px 12px; border-radius: 14px; background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.18); }
	.reason-k { font-size: 12px; color: #b91c1c; font-weight: 700; }
	.reason-v { margin-top: 6px; font-size: 12px; color: #7f1d1d; line-height: 1.5; }

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
		display: flex;
		gap: 10px;
	}
	.bottom-bar :deep(.u-btn) { flex: 1; height: 48px; }
</style>
