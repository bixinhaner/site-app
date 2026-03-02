<template>
	<view class="page" :key="languageStore.currentLocale">
		<CustomNavbar :title="$t('stock.issueDraftDetailTitle')" :showBack="true" variant="brand" />

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
							<text class="meta-item">{{ draft.request?.warehouse_name || '-' }}</text>
						</view>
					</view>
					<view class="right">
						<view class="mini">
							<text class="k">{{ $t('stock.materialRequestNo') }}</text>
							<text class="v mono">{{ draft.request?.request_no || draft.request_id }}</text>
						</view>
					</view>
				</view>

				<view class="chips">
					<view class="chip">
						<text class="k">{{ $t('stock.issueDraftConfirmedSn') }}</text>
						<text class="v">{{ confirmedSnCount }}</text>
					</view>
					<view class="chip">
						<text class="k">{{ $t('stock.issueDraftPendingSn') }}</text>
						<text class="v">{{ pendingSnCount }}</text>
					</view>
					<view class="chip">
						<text class="k">{{ $t('stock.issueDraftAuxConfirmed') }}</text>
						<text class="v">{{ auxConfirmedTotal }}</text>
					</view>
					<view class="chip accent">
						<text class="k">{{ $t('stock.issueDraftAuxPending') }}</text>
						<text class="v">{{ auxPendingTotal }}</text>
					</view>
				</view>

				<view class="tip" v-if="tipText">
					<text class="tip-text">{{ tipText }}</text>
				</view>

				<view v-if="draft.reject_reason" class="reject">
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
					<text class="hint">{{ $t('stock.issueDraftSnListHint') }}</text>
				</view>
				<view class="u-card-content">
					<view v-if="(draft.serials || []).length === 0" class="empty">
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
							</view>
						</view>
					</view>
				</view>
			</view>

			<view v-if="draft" class="section u-card">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.issueDraftAuxMaterials') }}</text>
					<text class="hint">{{ $t('stock.issueDraftAuxHint') }}</text>
				</view>
				<view class="u-card-content">
					<view v-if="(draft.aux_items || []).length === 0" class="empty">
						<text class="empty-text">{{ $t('stock.issueDraftNoAux') }}</text>
					</view>
					<view v-else class="aux-list">
						<view class="aux" v-for="a in draft.aux_items" :key="a.equipment_id">
							<view class="aux-head">
								<view class="left">
									<text class="name">{{ a.equipment_name }}</text>
									<text class="code mono">{{ a.equipment_code }}</text>
								</view>
								<view class="right">
									<view class="u-tag u-tag-info">{{ displayUnit(a.unit) || '-' }}</view>
								</view>
							</view>
							<view class="nums">
								<view class="n">
									<text class="k">{{ $t('stock.issueDraftPlannedThisTime') }}</text>
									<text class="v">{{ a.planned_qty }}</text>
								</view>
								<view class="n">
									<text class="k">{{ $t('stock.issueDraftConfirmedThisTime') }}</text>
									<text class="v">{{ a.confirmed_qty }}</text>
								</view>
								<view class="n accent">
									<text class="k">{{ $t('stock.qtyPending') }}</text>
									<text class="v">{{ a.pending_qty }}</text>
								</view>
							</view>
						</view>
					</view>
				</view>
			</view>

			<view class="bottom-spacer" />
		</scroll-view>

		<view class="bottom-bar" v-if="draft">
			<button class="u-btn u-btn-secondary u-pressable" :disabled="acting" @click="goRequest">
				{{ $t('stock.issueDraftGoRequest') }}
			</button>
			<button class="u-btn u-btn-primary u-pressable" :disabled="acting" @click="continuePick">
				{{ primaryActionText }}
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

	const extractErrorMessage = (data, fallback = '') => {
		const detail = data?.detail
		if (!detail) return fallback || $t('messages.operationFailed')
		if (typeof detail === 'string') return detail
		return detail?.message || fallback || $t('messages.operationFailed')
	}

	const formatDt = (ts) => formatDateTime(ts) || ''

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
		if (s === 'rejected') return 'u-tag-error'
		if (s === 'canceled') return 'u-tag-error'
		return 'u-tag-info'
	}

	const confirmedSnCount = computed(() => (draft.value?.serials || []).filter(s => s.status === 'confirmed').length)
	const pendingSnCount = computed(() => (draft.value?.serials || []).filter(s => s.status === 'pending').length)
	const auxConfirmedTotal = computed(() => (draft.value?.aux_items || []).reduce((s, a) => s + Number(a.confirmed_qty || 0), 0))
	const auxPendingTotal = computed(() => (draft.value?.aux_items || []).reduce((s, a) => s + Number(a.pending_qty || 0), 0))

	const tipText = computed(() => {
		const s = String(draft.value?.status || '')
		if (s === 'pending_confirm') return $t('stock.issueDraftTipPendingConfirm')
		if (s === 'partially_confirmed') return $t('stock.issueDraftTipPartiallyConfirmed')
		if (s === 'confirmed') return $t('stock.issueDraftTipConfirmed')
		if (s === 'rejected') return $t('stock.issueDraftTipRejected')
		if (s === 'canceled') return $t('stock.issueDraftTipCanceled')
		return ''
	})

	const primaryActionText = computed(() => {
		const s = String(draft.value?.status || '')
		if (s === 'draft') return $t('stock.issueDraftContinueEdit')
		return $t('stock.issueDraftContinuePick')
	})

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
				draft.value = res.data.draft
				return
			}
			if (res.statusCode === 401) {
				userStore.logout()
				return
			}
			uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
		} catch (e) {
			console.error('加载领料单失败:', e)
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

	const goRequest = () => {
		const requestId = draft.value?.request_id || draft.value?.request?.id
		if (!requestId) return
		uni.navigateTo({ url: `/pages/stock/material-requests/detail?id=${requestId}` })
	}

	const continuePick = async () => {
		if (!draft.value) return
		const s = String(draft.value.status || '')
		if (s === 'draft') {
			uni.redirectTo({ url: `/pages/stock/issue-drafts/pick?draft_id=${draftId.value}` })
			return
		}

		const requestId = draft.value?.request_id || draft.value?.request?.id
		if (!requestId) return

		acting.value = true
		try {
			const res = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.STOCK.ISSUE_DRAFTS),
				method: 'POST',
				header: getAuthHeaders(userStore.token),
				data: { request_id: requestId },
			})
			if (res.statusCode === 200 && res.data?.draft?.id) {
				uni.navigateTo({ url: `/pages/stock/issue-drafts/pick?draft_id=${res.data.draft.id}` })
				return
			}
			if (res.statusCode === 401) {
				userStore.logout()
				return
			}
			uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
		} catch (e) {
			console.error('继续领料失败:', e)
			uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
		} finally {
			acting.value = false
		}
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

	.mini { padding: 10px 12px; border-radius: 14px; border: 1px solid rgba(229, 231, 235, 0.9); background: rgba(255, 255, 255, 0.72); display: flex; flex-direction: column; gap: 6px; min-width: 140px; }
	.mini .k { font-size: 11px; color: #6b7280; }
	.mini .v { font-size: 12px; font-weight: 900; color: #111827; }

	.chips { padding: 0 16px 14px; display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 10px; }
	.chip { padding: 10px 10px; border-radius: 14px; border: 1px solid rgba(229, 231, 235, 0.9); background: rgba(255, 255, 255, 0.72); display: flex; flex-direction: column; gap: 6px; }
	.chip .k { font-size: 11px; color: #6b7280; }
	.chip .v { font-size: 16px; font-weight: 900; color: #111827; }
	.chip.accent { border-color: rgba(var(--color-primary-rgb), 0.22); background: rgba(var(--color-primary-rgb), 0.06); }

	.tip { padding: 0 16px 14px; }
	.tip-text { display: block; padding: 10px 12px; border-radius: 14px; border: 1px solid rgba(229, 231, 235, 0.9); background: rgba(255, 255, 255, 0.72); color: #6b7280; font-size: 12px; line-height: 1.5; }

	.reject { padding: 0 16px 16px; }
	.reject-k { font-size: 12px; color: #b91c1c; font-weight: 800; }
	.reject-v { margin-top: 6px; font-size: 12px; color: #7f1d1d; line-height: 1.5; }

	.section { margin: 16px; border-radius: var(--radius-lg); overflow: hidden; }
	.hint { font-size: 12px; color: #9ca3af; }

	.serial-list { display: flex; flex-direction: column; gap: 10px; }
	.serial { border: 1px solid rgba(229, 231, 235, 0.9); background: #fff; border-radius: 14px; padding: 12px; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
	.serial-left { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
	.sn { font-size: 14px; font-weight: 900; color: #111827; }
	.time { font-size: 12px; color: #9ca3af; }

	.aux-list { display: flex; flex-direction: column; gap: 12px; }
	.aux { border: 1px solid rgba(229, 231, 235, 0.9); background: #fff; border-radius: 14px; padding: 12px; }
	.aux-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
	.aux-head .left { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
	.name { font-size: 14px; font-weight: 800; color: #111827; }
	.code { font-size: 12px; color: #9ca3af; }

	.nums { margin-top: 12px; display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }
	.n { padding: 10px 10px; border-radius: 12px; background: #f9fafb; border: 1px solid rgba(229, 231, 235, 0.9); }
	.n .k { font-size: 11px; color: #6b7280; }
	.n .v { margin-top: 6px; font-size: 16px; font-weight: 900; color: #111827; }
	.n.accent { border-color: rgba(var(--color-primary-rgb), 0.22); background: rgba(var(--color-primary-rgb), 0.06); }

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
</style>
