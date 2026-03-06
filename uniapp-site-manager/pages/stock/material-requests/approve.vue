<template>
	<view class="page" :key="languageStore.currentLocale">
		<CustomNavbar :title="$t('stock.materialApproveTitle')" :showBack="true" variant="brand" />

		<scroll-view
			class="content"
			scroll-y
			refresher-enabled
			:refresher-triggered="refreshing"
			@refresherrefresh="handleRefresh"
			refresher-background="#f7f8fb"
		>
			<view v-if="request" class="hero u-card">
				<view class="hero-top">
					<view class="left">
						<text class="no mono">{{ request.request_no }}</text>
						<view class="meta">
							<view class="u-tag" :class="statusTagClass(request.status)">{{ statusLabel(request.status) }}</view>
							<text class="dot">·</text>
							<text class="meta-item">{{ request.warehouse_name || '-' }}</text>
						</view>
					</view>
				</view>

				<view class="summary-grid">
					<view class="s-item">
						<text class="k">{{ $t('stock.materialRequestMain') }}</text>
						<text class="v">{{ mainRequested }}</text>
					</view>
					<view class="s-item">
						<text class="k">{{ $t('stock.materialRequestAux') }}</text>
						<text class="v">{{ auxRequested }}</text>
					</view>
					<view class="s-item accent">
						<text class="k">{{ $t('stock.qtyRemaining') }}</text>
						<text class="v">{{ remainingTotal }}</text>
					</view>
				</view>

				<view class="notes" v-if="request.notes">
					<text class="notes-k">{{ $t('stock.materialRequestNotes') }}</text>
					<text class="notes-v">{{ request.notes }}</text>
				</view>

				<view class="tip" v-if="tipText">
					<text class="tip-text">{{ tipText }}</text>
				</view>
			</view>

			<view v-if="loading && !request" class="list">
				<SkeletonCard mode="list" />
				<SkeletonCard mode="list" />
			</view>

			<view class="section u-card" v-if="request">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.materialRequestItems') }}</text>
					<view v-if="canOperate" class="header-actions">
						<button class="u-btn u-btn-secondary u-btn-sm u-pressable" @click="fillApproveAll">
							{{ $t('stock.materialApproveFillAll') }}
						</button>
						<button class="u-btn u-btn-secondary u-btn-sm u-pressable" @click="fillApproveZero">
							{{ $t('stock.materialApproveFillZero') }}
						</button>
					</view>
				</view>

				<view class="u-card-content">
					<view class="items">
						<view class="item" v-for="row in approveRows" :key="row.equipment_id">
							<view class="item-head">
								<view class="left">
									<text class="name">{{ row.equipment_name }}</text>
									<text class="code mono">{{ row.equipment_code }}</text>
								</view>
								<view class="right">
									<view class="u-tag" :class="row.equipment_category === 'main_device' ? 'u-tag-warning' : 'u-tag-info'">
										{{ row.equipment_category === 'main_device' ? $t('stock.mainDevice') : $t('stock.auxMaterial') }}
									</view>
								</view>
							</view>

							<view class="nums">
								<view class="n">
									<text class="k">{{ $t('stock.qtyRequested') }}</text>
									<text class="v">{{ row.requested_qty }}</text>
								</view>
								<view class="n" v-if="canOperate">
									<text class="k">{{ $t('stock.qtyApproved') }}</text>
									<view class="stepper">
										<view class="qbtn u-pressable" @click="decApprove(row)">−</view>
										<input class="qinput mono" type="number" v-model="row.approved_qty" @blur="normalizeApprove(row)" />
										<view class="qbtn u-pressable" @click="incApprove(row)">＋</view>
									</view>
								</view>
								<view class="n" v-else>
									<text class="k">{{ $t('stock.qtyApproved') }}</text>
									<text class="v">{{ row.approved_qty }}</text>
								</view>
							</view>
						</view>
					</view>
				</view>
			</view>

			<view class="section u-card" v-if="request && canOperate">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.materialApprovePanel') }}</text>
				</view>
				<view class="u-card-content">
					<view class="u-form-item">
						<text class="u-form-label">{{ $t('stock.materialApproveComment') }}</text>
						<textarea class="u-textarea" v-model="approveComments" :placeholder="$t('stock.materialApproveCommentPlaceholder')" maxlength="200" />
					</view>
					<view class="u-form-item">
						<text class="u-form-label">{{ $t('stock.materialRejectReason') }}</text>
						<textarea class="u-textarea" v-model="rejectReason" :placeholder="$t('stock.materialRejectReasonPlaceholder')" maxlength="200" />
					</view>
				</view>
			</view>

			<view class="bottom-spacer" />
		</scroll-view>

		<view class="bottom-bar" v-if="request">
			<button class="u-btn u-btn-secondary u-pressable" @click="goBack">
				{{ $t('common.back') }}
			</button>
			<button class="u-btn u-btn-danger u-pressable" v-if="canOperate" :disabled="acting" @click="reject">
				{{ $t('stock.materialRejectAction') }}
			</button>
			<button class="u-btn u-btn-primary u-pressable" v-if="canOperate" :disabled="acting" @click="approve">
				{{ acting ? $t('common.loading') : $t('stock.materialApproveAction') }}
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
	import { guardRouteAccess } from '@/utils/feature-access.js'
	import CustomNavbar from '@/components/CustomNavbar.vue'
	import SkeletonCard from '@/components/SkeletonCard.vue'

	const userStore = useUserStore()
	const languageStore = useLanguageStore()
	const { $t } = getCurrentInstance().appContext.config.globalProperties

	const requestId = ref('')
	const request = ref(null)
	const loading = ref(false)
	const refreshing = ref(false)
	const acting = ref(false)

	const approveRows = ref([])
	const approveComments = ref('')
	const rejectReason = ref('')

		const canAccessApproval = computed(() => userStore.can('material_approval'))
		const canOperate = computed(() => canAccessApproval.value && String(request.value?.status || '') === 'submitted')

	const mainRequested = computed(() => {
		const rows = request.value?.items || []
		return rows.filter(it => it.equipment_category === 'main_device').reduce((s, it) => s + Number(it.requested_qty || 0), 0)
	})
	const auxRequested = computed(() => {
		const rows = request.value?.items || []
		return rows.filter(it => it.equipment_category === 'auxiliary').reduce((s, it) => s + Number(it.requested_qty || 0), 0)
	})
	const remainingTotal = computed(() => {
		const rows = request.value?.items || []
		return rows.reduce((s, it) => s + Number(it.remaining_qty || 0), 0)
	})

	const tipText = computed(() => {
		const s = String(request.value?.status || '')
		if (s === 'submitted') return $t('stock.materialApprovalTipSubmitted')
		if (s === 'approved' || s === 'partially_approved') return $t('stock.materialApprovalTipApproved')
		if (s === 'abandoned') return $t('stock.materialRequestTipAbandoned')
		if (s === 'rejected') return $t('stock.materialRequestTipRejected')
		if (s === 'canceled') return $t('stock.materialRequestTipCanceled')
		if (s === 'closed') return $t('stock.materialRequestTipClosed')
		return ''
	})

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
		if (s === 'submitted') return 'u-tag-warning'
		if (s === 'approved') return 'u-tag-success'
		if (s === 'partially_approved') return 'u-tag-primary'
		if (s === 'closed') return 'u-tag-success'
		if (s === 'abandoned' || s === 'rejected' || s === 'canceled') return 'u-tag-error'
		return 'u-tag-info'
	}

	const normalizeApprove = (row) => {
		const max = Number(row?.requested_qty || 0)
		let v = Number(String(row?.approved_qty || '').trim())
		if (!Number.isFinite(v) || v < 0) v = 0
		if (v > max) v = max
		row.approved_qty = Math.floor(v)
	}

	const decApprove = (row) => {
		row.approved_qty = Math.max(0, Number(row.approved_qty || 0) - 1)
	}

	const incApprove = (row) => {
		const max = Number(row?.requested_qty || 0)
		row.approved_qty = Math.min(max, Number(row.approved_qty || 0) + 1)
	}

	const fillApproveAll = () => {
		approveRows.value = approveRows.value.map(r => ({ ...r, approved_qty: Number(r.requested_qty || 0) }))
	}

	const fillApproveZero = () => {
		approveRows.value = approveRows.value.map(r => ({ ...r, approved_qty: 0 }))
	}

	const ensureReady = async () => {
		return guardRouteAccess({
			userStore,
			route: 'pages/stock/material-requests/approve',
			t: $t,
			deniedMessage: $t('stock.materialApprovalNoPermission'),
			redirectUrl: '/pages/home/home',
		})
	}

	const load = async () => {
		if (!(await ensureReady())) return
		if (!requestId.value) return

		loading.value = true
		try {
			const res = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.STOCK.MATERIAL_REQUEST_DETAIL(requestId.value)),
				method: 'GET',
				header: getAuthHeaders(userStore.token),
			})
			if (res.statusCode === 200 && res.data?.request) {
				request.value = res.data.request
				approveRows.value = (request.value.items || []).map(it => ({
					equipment_id: Number(it.equipment_id),
					equipment_name: it.equipment_name,
					equipment_code: it.equipment_code,
					equipment_category: it.equipment_category,
					requested_qty: Number(it.requested_qty || 0),
					approved_qty: Number(it.approved_qty || it.requested_qty || 0),
				}))
				return
			}
			if (res.statusCode === 401) {
				userStore.logout()
				return
			}
			uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
		} catch (e) {
			console.error('加载申请审批详情失败:', e)
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

	const approve = async () => {
		if (!canOperate.value) return
		const totalApproved = approveRows.value.reduce((sum, row) => sum + Number(row.approved_qty || 0), 0)
		if (totalApproved <= 0) {
			uni.showToast({ title: $t('stock.materialApproveNeedPositive'), icon: 'none' })
			return
		}

		uni.showModal({
			title: $t('common.confirm'),
			content: $t('stock.materialApproveSubmitConfirm'),
			success: async (mr) => {
				if (!mr.confirm) return
				acting.value = true
				try {
					const res = await uni.request({
						url: buildApiUrl(API_ENDPOINTS.STOCK.MATERIAL_REQUEST_APPROVE(requestId.value)),
						method: 'POST',
						header: getAuthHeaders(userStore.token),
						data: {
							items: approveRows.value.map(row => ({
								equipment_id: Number(row.equipment_id),
								approved_qty: Number(row.approved_qty || 0),
							})),
							comments: String(approveComments.value || '').trim(),
						},
					})
					if (res.statusCode === 200) {
						uni.showToast({ title: $t('stock.materialApproveSuccess'), icon: 'success' })
						await load()
						return
					}
					if (res.statusCode === 401) {
						userStore.logout()
						return
					}
					uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
				} catch (e) {
					console.error('审批申请失败:', e)
					uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
				} finally {
					acting.value = false
				}
			},
		})
	}

	const reject = async () => {
		if (!canOperate.value) return
		const reason = String(rejectReason.value || '').trim()
		if (!reason) {
			uni.showToast({ title: $t('stock.materialRejectReasonRequired'), icon: 'none' })
			return
		}

		uni.showModal({
			title: $t('common.confirm'),
			content: $t('stock.materialRejectConfirm'),
			success: async (mr) => {
				if (!mr.confirm) return
				acting.value = true
				try {
					const res = await uni.request({
						url: buildApiUrl(API_ENDPOINTS.STOCK.MATERIAL_REQUEST_REJECT(requestId.value)),
						method: 'POST',
						header: getAuthHeaders(userStore.token),
						data: { reason },
					})
					if (res.statusCode === 200) {
						uni.showToast({ title: $t('stock.materialRejectSuccess'), icon: 'success' })
						await load()
						return
					}
					if (res.statusCode === 401) {
						userStore.logout()
						return
					}
					uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
				} catch (e) {
					console.error('驳回申请失败:', e)
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
		requestId.value = String(query?.id || '').trim()
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
			radial-gradient(900px 260px at 8% 0%, rgba(var(--color-primary-rgb), 0.16), transparent 62%),
			radial-gradient(900px 260px at 90% 10%, rgba(var(--color-brand-blue-rgb), 0.10), transparent 62%),
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

	.summary-grid {
		padding: 0 16px 14px;
		display: grid;
		grid-template-columns: 1fr 1fr 1fr;
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

	.notes { padding: 0 16px 14px; display: flex; gap: 10px; }
	.notes-k { font-size: 12px; color: #6b7280; }
	.notes-v { font-size: 12px; color: #111827; line-height: 1.5; flex: 1; }

	.tip { padding: 0 16px 16px; }
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

	.section { margin: 16px; border-radius: var(--radius-lg); overflow: hidden; }
	.header-actions { display: flex; gap: 8px; }

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

	.bottom-spacer { height: 98px; }
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
		grid-template-columns: 1fr 1fr 1fr;
		gap: 10px;
	}
	.bottom-bar :deep(.u-btn) { height: 48px; }
</style>
