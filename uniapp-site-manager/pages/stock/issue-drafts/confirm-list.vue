<template>
	<view class="page" :key="languageStore.currentLocale">
		<CustomNavbar :title="$t('stock.issueConfirmEntry')" :showBack="true" variant="brand" />

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
						<text class="hero-title">{{ $t('stock.issueConfirmHeroTitle') }}</text>
						<text class="hero-sub">{{ $t('stock.issueConfirmHeroSub') }}</text>
					</view>
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
							:placeholder="$t('stock.issueConfirmSearchPlaceholder')"
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

			<view class="list">
				<template v-if="loading && records.length === 0">
					<SkeletonCard mode="list" />
					<SkeletonCard mode="list" />
					<SkeletonCard mode="list" />
				</template>

				<EmptyState
					v-else-if="!loading && records.length === 0"
					icon="📤"
					:title="$t('messages.noData')"
					:description="$t('stock.issueConfirmEmptyTip')"
				/>

				<template v-else>
					<view
						v-for="r in records"
						:key="r.id"
						class="card u-card u-pressable-subtle"
						@click="goDetail(r)"
					>
						<view class="card-head">
							<view class="left">
								<text class="no mono">{{ r.draft_no }}</text>
								<view class="meta">
									<text class="meta-item">{{ r.warehouse_name || '-' }}</text>
									<text class="dot">·</text>
									<text class="meta-item">{{ r.requester_name || '-' }}</text>
								</view>
							</view>
							<view class="right">
								<view class="u-tag" :class="statusTagClass(r.status)">{{ statusLabel(r.status) }}</view>
							</view>
						</view>

						<view v-if="r.request_no" class="summary">
							<text class="summary-k">{{ $t('stock.materialRequestNo') }}</text>
							<text class="summary-v mono">{{ r.request_no }}</text>
						</view>

						<view class="card-foot">
							<text class="time">{{ timeAgo(r.submitted_at || r.created_at) }}</text>
							<view class="u-tag" :class="isConfirmable(r.status) ? 'u-tag-primary' : 'u-tag-info'">
								{{ isConfirmable(r.status) ? $t('stock.issueConfirmActionConfirm') : $t('stock.issueConfirmActionView') }}
							</view>
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
	import { computed, onMounted, ref, getCurrentInstance } from 'vue'
	import { onShow } from '@dcloudio/uni-app'
	import { useUserStore } from '@/stores/user'
	import { useLanguageStore } from '@/stores/language'
	import { buildApiUrl, API_ENDPOINTS, createRequestConfig, getAuthHeaders } from '@/config/api.js'
	import { formatTimeAgo } from '@/utils/time.js'
	import { guardRouteAccess } from '@/utils/feature-access.js'
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
	const currentStatus = ref('pending_confirm')
	const page = ref(1)
	const pageSize = ref(20)
	const total = ref(0)
	const records = ref([])

	const hasMore = computed(() => records.value.length < total.value)
		const canAccessIssueConfirm = computed(() => userStore.can('issue_confirm'))

	const isConfirmable = (status) => {
		const s = String(status || '')
		return s === 'pending_confirm' || s === 'partially_confirmed'
	}

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
			draft: $t('stock.issueDraftStatusDraft'),
			pending_confirm: $t('stock.issueDraftStatusPendingConfirm'),
			partially_confirmed: $t('stock.issueDraftStatusPartiallyConfirmed'),
			confirmed: $t('stock.issueDraftStatusConfirmed'),
			rejected: $t('stock.issueDraftStatusRejected'),
			canceled: $t('stock.issueDraftStatusCanceled'),
		}
		return map[String(status || 'all')] || String(status || '-')
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

	const ensureIssueConfirmAccess = () => guardRouteAccess({
		userStore,
		route: 'pages/stock/issue-drafts/confirm-list',
		t: $t,
		deniedMessage: $t('stock.issueConfirmNoPermission'),
		redirectUrl: '/pages/home/home',
	})

	const ensureReady = async () => {
		if (!ensureIssueConfirmAccess()) return false

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

	const load = async (reset = true) => {
		if (!(await ensureReady())) return
		if (reset) {
			page.value = 1
			records.value = []
			total.value = 0
		}

		const isFirst = reset && records.value.length === 0
		if (isFirst) loading.value = true
		else loadingMore.value = true

		try {
			const skip = (page.value - 1) * pageSize.value
			const params = []
			if (currentStatus.value && currentStatus.value !== 'all') params.push(`status_filter=${encodeURIComponent(currentStatus.value)}`)
			if (keyword.value) params.push(`keyword=${encodeURIComponent(keyword.value.trim())}`)
			params.push(`skip=${skip}`)
			params.push(`limit=${pageSize.value}`)
			const url = `${buildApiUrl(API_ENDPOINTS.STOCK.ISSUE_DRAFTS)}?${params.join('&')}`

			const res = await uni.request({
				url,
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token),
				}),
			})

			if (res.statusCode === 200) {
				const rows = Array.isArray(res.data?.records) ? res.data.records : []
				total.value = Number(res.data?.total || 0)
				records.value = reset ? rows : records.value.concat(rows)
				return
			}

			if (res.statusCode === 401) {
				userStore.logout()
				return
			}
			uni.showToast({ title: extractErrorMessage(res.data), icon: 'none' })
		} catch (e) {
			console.error('加载出库确认列表失败:', e)
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
			{ key: 'pending_confirm', label: statusLabel('pending_confirm') },
			{ key: 'partially_confirmed', label: statusLabel('partially_confirmed') },
			{ key: 'all', label: statusLabel('all') },
			{ key: 'confirmed', label: statusLabel('confirmed') },
			{ key: 'rejected', label: statusLabel('rejected') },
			{ key: 'canceled', label: statusLabel('canceled') },
			{ key: 'draft', label: statusLabel('draft') },
		]
		uni.showActionSheet({
			itemList: options.map(o => o.label),
			success: async (res) => {
				const picked = options[res.tapIndex]
				if (!picked) return
				currentStatus.value = picked.key
				await load(true)
			},
		})
	}

	const doSearch = async () => {
		await load(true)
	}

	const clearKeyword = async () => {
		keyword.value = ''
		await load(true)
	}

	const goDetail = (draft) => {
		uni.navigateTo({ url: `/pages/stock/issue-drafts/confirm?draft_id=${draft.id}` })
	}

	onMounted(async () => {
		await load(true)
	})

	onShow(async () => {
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

	.card-foot {
		margin-top: 12px;
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.time { font-size: 12px; color: #6b7280; }

	.load-more { display: flex; justify-content: center; padding: 8px 0 14px; }
	.bottom-spacer { height: 18px; }
</style>
