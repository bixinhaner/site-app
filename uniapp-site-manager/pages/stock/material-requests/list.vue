<template>
	<view class="page" :key="languageStore.currentLocale">
		<CustomNavbar :title="$t('stock.materialRequestEntry')" :showBack="true" variant="brand">
			<template #right>
				<view class="u-nav-btn u-nav-btn--brand" @click="goCreate">
					<uni-icons type="plusempty" size="36rpx" color="#fff" />
				</view>
			</template>
		</CustomNavbar>

		<scroll-view
			class="content"
			scroll-y
			refresher-enabled
			:refresher-triggered="refreshing"
			@refresherrefresh="handleRefresh"
			@scrolltolower="loadMore"
			lower-threshold="160"
			refresher-background="#f7f8fb"
		>
			<view class="hero u-card">
				<view class="hero-inner">
					<view class="hero-left">
						<text class="hero-title">{{ $t('stock.materialRequestHeroTitle') }}</text>
						<text class="hero-sub">{{ $t('stock.materialRequestHeroSub') }}</text>
					</view>
					<button class="u-btn u-btn-primary u-btn-sm u-pressable" @click="goCreate">
						<uni-icons type="plusempty" size="18" color="#fff" />
						<text>{{ $t('stock.materialRequestNew') }}</text>
					</button>
				</view>

				<view class="filters">
					<view class="chip u-pressable" @click="openStatusSheet">
						<text class="chip-k">{{ $t('common.status') }}</text>
						<text class="chip-v">{{ statusLabel(currentStatus) }}</text>
						<text class="chip-arrow">▼</text>
					</view>

					<view class="search">
						<uni-icons type="search" size="18" color="#6b7280" />
						<input
							class="search-input"
							v-model="keyword"
							:placeholder="$t('stock.materialRequestSearchPlaceholder')"
							confirm-type="search"
							@confirm="doSearch"
						/>
						<uni-icons
							v-if="keyword"
							type="clear"
							size="18"
							color="#9ca3af"
							@click="clearKeyword"
						/>
					</view>
				</view>
			</view>

			<!-- 列表 -->
			<view class="list">
				<template v-if="loading && requests.length === 0">
					<SkeletonCard mode="list" />
					<SkeletonCard mode="list" />
					<SkeletonCard mode="list" />
				</template>

				<EmptyState
					v-else-if="!loading && requests.length === 0"
					icon="🧾"
					:title="$t('messages.noData')"
					:description="$t('stock.materialRequestEmptyTip')"
					:actionText="$t('stock.materialRequestNew')"
					@action="goCreate"
				/>

				<template v-else>
					<view
						v-for="r in requests"
						:key="r.id"
						class="card u-card u-pressable-subtle"
						@click="goDetail(r)"
					>
						<view class="card-head">
							<view class="left">
								<text class="no mono">{{ r.request_no }}</text>
								<view class="meta">
									<text class="meta-item">{{ r.warehouse_name || '-' }}</text>
									<text class="dot">·</text>
									<text class="meta-item">{{ timeAgo(r.submitted_at || r.created_at) }}</text>
								</view>
							</view>
							<view class="right">
								<view class="u-tag" :class="statusTagClass(r.status)">{{ statusLabel(r.status) }}</view>
							</view>
						</view>

						<view v-if="r.main_summary" class="summary">
							<text class="summary-k">{{ $t('stock.materialRequestMainSummary') }}</text>
							<text class="summary-v">{{ r.main_summary }}</text>
						</view>

						<view class="stats">
							<view class="stat">
								<text class="k">{{ $t('stock.materialRequestStatRemaining') }}</text>
								<text class="v">{{ remainingTotal(r) }}</text>
							</view>
							<view class="stat">
								<text class="k">{{ $t('stock.materialRequestStatPending') }}</text>
								<text class="v">{{ pendingTotal(r) }}</text>
							</view>
							<view class="stat">
								<text class="k">{{ $t('stock.materialRequestStatIssued') }}</text>
								<text class="v">{{ issuedTotal(r) }}</text>
							</view>
						</view>

						<view class="card-foot">
							<text class="notes" v-if="r.notes">{{ r.notes }}</text>
							<text class="arrow">›</text>
						</view>
					</view>

					<view class="load-more" v-if="hasMore">
						<button class="u-btn u-btn-secondary u-btn-sm" :disabled="loadingMore" @click="loadMore">
							{{ loadingMore ? $t('common.loading') : $t('stock.loadMore') }}
						</button>
					</view>
				</template>
			</view>
			<view class="bottom-spacer" />
		</scroll-view>
	</view>
</template>

<script setup>
	import { computed, onMounted, ref, reactive, getCurrentInstance } from 'vue'
	import { onShow } from '@dcloudio/uni-app'
	import { useUserStore } from '@/stores/user'
	import { useLanguageStore } from '@/stores/language'
	import { buildApiUrl, API_ENDPOINTS, createRequestConfig, getAuthHeaders } from '@/config/api.js'
	import { formatTimeAgo } from '@/utils/time.js'
	import CustomNavbar from '@/components/CustomNavbar.vue'
	import SkeletonCard from '@/components/SkeletonCard.vue'
	import EmptyState from '@/components/EmptyState.vue'

	const userStore = useUserStore()
	const languageStore = useLanguageStore()
	const { $t } = getCurrentInstance().appContext.config.globalProperties

	const refreshing = ref(false)
	const loading = ref(false)
	const loadingMore = ref(false)

	const keyword = ref('')
	const currentStatus = ref('all')
	const page = ref(1)
	const pageSize = ref(20)
	const total = ref(0)
	const requests = ref([])

	const flowSettings = reactive({
		enable_material_request: true,
	})

	const hasMore = computed(() => requests.value.length < total.value)

	const timeAgo = (ts) => {
		return formatTimeAgo(ts, $t) || ''
	}

	const extractErrorMessage = (data, fallback = '') => {
		const detail = data?.detail
		if (!detail) return fallback || $t('messages.operationFailed')
		if (typeof detail === 'string') return detail
		return detail?.message || fallback || $t('messages.operationFailed')
	}

	const statusLabel = (status) => {
		const map = {
			all: $t('common.all'),
			draft: $t('stock.statusDraft'),
			submitted: $t('stock.statusSubmitted'),
			approved: $t('stock.statusApproved'),
			partially_approved: $t('stock.statusPartiallyApproved'),
			rejected: $t('stock.statusRejected'),
			canceled: $t('stock.statusCanceled'),
			closed: $t('stock.statusClosed'),
		}
		return map[String(status || 'all')] || String(status || '-')
	}

	const statusTagClass = (status) => {
		const s = String(status || '')
		if (s === 'draft') return 'u-tag-info'
		if (s === 'submitted') return 'u-tag-warning'
		if (s === 'approved') return 'u-tag-success'
		if (s === 'partially_approved') return 'u-tag-primary'
		if (s === 'closed') return 'u-tag-success'
		if (s === 'canceled') return 'u-tag-error'
		if (s === 'rejected') return 'u-tag-error'
		return 'u-tag-info'
	}

	const remainingTotal = (req) => {
		const items = req?.items || []
		return items.reduce((sum, it) => sum + Number(it?.remaining_qty || 0), 0)
	}
	const pendingTotal = (req) => {
		const items = req?.items || []
		return items.reduce((sum, it) => sum + Number(it?.pending_qty || 0), 0)
	}
	const issuedTotal = (req) => {
		const items = req?.items || []
		return items.reduce((sum, it) => sum + Number(it?.issued_qty || 0), 0)
	}

	const ensureReady = async () => {
		if (!userStore.isLoggedIn) {
			uni.reLaunch({ url: '/pages/login/login' })
			return false
		}
		if (userStore.isSurveyor) {
			uni.showToast({ title: $t('stock.surveyorNoPermission'), icon: 'none' })
			setTimeout(() => uni.navigateBack(), 600)
			return false
		}

		try {
			const flowRes = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.STOCK.FLOW_SETTINGS),
				method: 'GET',
				header: getAuthHeaders(userStore.token),
			})
			if (flowRes.statusCode === 200 && flowRes.data?.settings) {
				flowSettings.enable_material_request = flowRes.data.settings.enable_material_request !== false
			}
		} catch (e) {
			// ignore
		}

		if (!flowSettings.enable_material_request) {
			uni.showToast({ title: $t('stock.materialRequestDisabled'), icon: 'none' })
			setTimeout(() => uni.navigateBack(), 700)
			return false
		}
		return true
	}

	const load = async (reset = true) => {
		if (!(await ensureReady())) return
		if (reset) {
			page.value = 1
			requests.value = []
			total.value = 0
		}

		const isFirst = reset && requests.value.length === 0
		if (isFirst) loading.value = true
		else loadingMore.value = true

		try {
			const skip = (page.value - 1) * pageSize.value
			const params = []
			if (currentStatus.value && currentStatus.value !== 'all') params.push(`status_filter=${encodeURIComponent(currentStatus.value)}`)
			if (keyword.value) params.push(`keyword=${encodeURIComponent(keyword.value.trim())}`)
			params.push(`skip=${skip}`)
			params.push(`limit=${pageSize.value}`)
			const url = `${buildApiUrl(API_ENDPOINTS.STOCK.MATERIAL_REQUESTS)}?${params.join('&')}`

			const res = await uni.request({
				url,
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token),
				})
			})

			if (res.statusCode === 200) {
				const records = Array.isArray(res.data?.records) ? res.data.records : []
				total.value = Number(res.data?.total || 0)
				requests.value = reset ? records : requests.value.concat(records)
				return
			}

			if (res.statusCode === 401) {
				userStore.logout()
				return
			}
			uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
		} catch (e) {
			console.error('加载物料申请失败:', e)
			uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
		} finally {
			loading.value = false
			loadingMore.value = false
			refreshing.value = false
		}
	}

	const handleRefresh = async () => {
		refreshing.value = true
		await load(true)
	}

	const loadMore = async () => {
		if (loading.value || loadingMore.value) return
		if (!hasMore.value) return
		page.value += 1
		await load(false)
	}

	const openStatusSheet = () => {
		const options = [
			{ key: 'all', label: statusLabel('all') },
			{ key: 'draft', label: statusLabel('draft') },
			{ key: 'submitted', label: statusLabel('submitted') },
			{ key: 'approved', label: statusLabel('approved') },
			{ key: 'partially_approved', label: statusLabel('partially_approved') },
			{ key: 'rejected', label: statusLabel('rejected') },
			{ key: 'canceled', label: statusLabel('canceled') },
			{ key: 'closed', label: statusLabel('closed') },
		]
		uni.showActionSheet({
			itemList: options.map(o => o.label),
			success: async (res) => {
				const picked = options[res.tapIndex]
				if (!picked) return
				currentStatus.value = picked.key
				await load(true)
			}
		})
	}

	const doSearch = async () => {
		await load(true)
	}

	const clearKeyword = async () => {
		keyword.value = ''
		await load(true)
	}

	const goCreate = () => {
		if (userStore.isSurveyor) {
			uni.showToast({ title: $t('stock.surveyorNoPermission'), icon: 'none' })
			return
		}
		uni.navigateTo({ url: '/pages/stock/material-requests/create' })
	}

	const goDetail = (req) => {
		uni.navigateTo({ url: `/pages/stock/material-requests/detail?id=${req.id}` })
	}

	onMounted(async () => {
		await load(true)
	})

	onShow(async () => {
		// 返回列表时刷新一次，避免状态延迟（例如审批/出库确认后）
		await load(true)
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
			radial-gradient(900px 260px at 8% 0%, rgba(var(--color-primary-rgb), 0.18), transparent 62%),
			radial-gradient(900px 260px at 90% 10%, rgba(var(--color-brand-blue-rgb), 0.10), transparent 62%),
			linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(255, 255, 255, 0.90));
		border: 1px solid rgba(229, 231, 235, 0.9);
		box-shadow: 0 10px 26px rgba(17, 24, 39, 0.08);
	}

	.hero-inner {
		padding: 16px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}

	.hero-left { display: flex; flex-direction: column; gap: 6px; }
	.hero-title { font-size: 16px; font-weight: 700; color: #111827; }
	.hero-sub { font-size: 12px; color: var(--text-secondary); line-height: 1.5; }

	.filters {
		padding: 0 16px 16px;
		display: grid;
		grid-template-columns: 168px 1fr;
		gap: 10px;
	}

	.chip {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 10px 12px;
		border: 1px solid rgba(229, 231, 235, 0.9);
		border-radius: 12px;
		background: rgba(255, 255, 255, 0.78);
	}
	.chip-k { font-size: 12px; color: #6b7280; }
	.chip-v { font-size: 13px; color: #111827; font-weight: 600; }
	.chip-arrow { margin-left: auto; color: #9ca3af; font-size: 12px; }

	.search {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 10px 12px;
		border: 1px solid rgba(229, 231, 235, 0.9);
		border-radius: 12px;
		background: rgba(255, 255, 255, 0.78);
	}
	.search-input {
		flex: 1;
		font-size: 13px;
		color: #111827;
	}

	.list { padding: 0 16px 16px; }

	.card {
		border-radius: var(--radius-lg);
		margin-bottom: 14px;
		padding: 14px;
		border: 1px solid rgba(229, 231, 235, 0.9);
		background: rgba(255, 255, 255, 0.96);
	}

	.card-head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 12px;
	}
	.no { font-size: 13px; font-weight: 800; color: #111827; }
	.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; }
	.meta { margin-top: 4px; display: flex; align-items: center; gap: 8px; color: var(--text-secondary); font-size: 12px; }
	.dot { opacity: 0.6; }

	.summary { margin-top: 10px; display: flex; gap: 8px; }
	.summary-k { font-size: 12px; color: #6b7280; flex-shrink: 0; }
	.summary-v { font-size: 12px; color: #111827; line-height: 1.5; }

	.stats {
		margin-top: 12px;
		display: grid;
		grid-template-columns: 1fr 1fr 1fr;
		gap: 10px;
	}
	.stat {
		padding: 10px 10px;
		border-radius: 12px;
		background: #f9fafb;
		border: 1px solid rgba(229, 231, 235, 0.9);
	}
	.k { font-size: 11px; color: #6b7280; }
	.v { margin-top: 6px; font-size: 16px; font-weight: 800; color: #111827; }

	.card-foot { margin-top: 12px; display: flex; align-items: center; gap: 10px; }
	.notes { flex: 1; font-size: 12px; color: #6b7280; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.arrow { color: #9ca3af; font-size: 20px; line-height: 1; }

	.load-more { display: flex; justify-content: center; padding: 8px 0 14px; }
	.bottom-spacer { height: 18px; }
</style>

