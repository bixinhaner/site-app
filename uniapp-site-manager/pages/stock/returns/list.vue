<template>
	<view class="page" :key="languageStore.currentLocale">
		<CustomNavbar :title="$t('stock.returnEntry')" :showBack="true" variant="brand">
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
						<text class="hero-title">{{ $t('stock.returnEntry') }}</text>
						<text class="hero-sub">{{ $t('stock.returnNeedWarehouseConfirmTip') }}</text>
					</view>
					<button class="u-btn u-btn-primary u-btn-sm u-pressable" @click="goCreate">
						<uni-icons type="plusempty" size="18" color="#fff" />
						<text>{{ $t('stock.returnNew') }}</text>
					</button>
				</view>

				<view class="filters">
					<view class="chip u-pressable" @click="openStatusSheet">
						<text class="chip-k">{{ $t('common.status') }}</text>
						<text class="chip-v">{{ statusLabel(statusFilter) }}</text>
						<text class="chip-arrow">▼</text>
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
					icon="↩️"
					:title="$t('messages.noData')"
					:description="$t('stock.returnEmptyTip')"
					:actionText="$t('stock.returnNew')"
					@action="goCreate"
				/>

				<template v-else>
					<view
						v-for="r in records"
						:key="r.id"
						class="card u-card"
					>
						<view class="card-head">
							<view class="left">
								<text class="no mono">{{ r.document_number }}</text>
								<view class="meta">
									<text class="meta-item">{{ r.warehouse_name || '-' }}</text>
									<text class="dot">·</text>
									<text class="meta-item">{{ timeAgo(r.created_at) }}</text>
								</view>
							</view>
							<view class="right">
								<view class="u-tag" :class="statusTagClass(r.status)">{{ statusLabel(r.status) }}</view>
							</view>
						</view>

						<view v-if="r.out_document_number" class="summary">
							<text class="summary-k">{{ $t('stock.documentNumber') }}</text>
							<text class="summary-v mono">{{ r.out_document_number }}</text>
						</view>

						<view class="stats">
							<view class="stat">
								<text class="k">{{ $t('stock.selectedMainDevices') }}</text>
								<text class="v">{{ mainCount(r) }}</text>
							</view>
							<view class="stat">
								<text class="k">{{ $t('stock.selectedAux') }}</text>
								<text class="v">{{ auxCount(r) }}</text>
							</view>
							<view class="stat">
								<text class="k">{{ $t('stock.qtyPending') }}</text>
								<text class="v">{{ pendingTotal(r) }}</text>
							</view>
						</view>
					</view>
				</template>
			</view>

			<view v-if="loadingMore" class="footer-loading">
				<uni-load-more status="loading" :content-text="loadMoreText" />
			</view>
			<view class="spacer" />
		</scroll-view>
	</view>
</template>

<script setup>
	import { computed, getCurrentInstance, onMounted, ref } from 'vue'
	import { useUserStore } from '@/stores/user'
	import { useLanguageStore } from '@/stores/language'
	import { API_ENDPOINTS, buildApiUrl, createRequestConfig, getAuthHeaders } from '@/config/api.js'

	const userStore = useUserStore()
	const languageStore = useLanguageStore()
	const { appContext } = getCurrentInstance()
	const { $t } = appContext.config.globalProperties

	const loading = ref(false)
	const loadingMore = ref(false)
	const refreshing = ref(false)

	const statusFilter = ref('all')

	const records = ref([])
	const total = ref(0)
	const page = ref(1)
	const pageSize = ref(20)

	const hasMore = computed(() => records.value.length < total.value)

	const loadMoreText = computed(() => ({
		contentdown: ' ',
		contentrefresh: ' ',
		contentnomore: ' ',
	}))

	const statusLabel = (s) => {
		const map = {
			all: $t('common.all'),
			pending_receive: $t('stock.returnStatusPendingReceiveShort'),
			partially_received: $t('stock.returnStatusPartiallyReceivedShort'),
			received: $t('stock.statusReturned'),
			rejected: $t('stock.returnStatusRejectedShort'),
			canceled: $t('stock.returnStatusCanceledShort'),
		}
		return map[s] || s || '-'
	}

	const statusTagClass = (s) => {
		if (s === 'received') return 'tag-ok'
		if (s === 'rejected') return 'tag-bad'
		if (s === 'canceled') return 'tag-muted'
		if (s === 'partially_received') return 'tag-warn'
		if (s === 'pending_receive') return 'tag-warn'
		return 'tag-muted'
	}

	const timeAgo = (iso) => {
		if (!iso) return '-'
		const d = new Date(iso)
		if (Number.isNaN(d.getTime())) return String(iso)
		const diff = Date.now() - d.getTime()
		const m = Math.floor(diff / 60000)
		if (m < 1) return '刚刚'
		if (m < 60) return `${m} 分钟前`
		const h = Math.floor(m / 60)
		if (h < 24) return `${h} 小时前`
		const dd = Math.floor(h / 24)
		return `${dd} 天前`
	}

	const mainCount = (r) => (Array.isArray(r.items) ? r.items.filter(it => it?.is_main_device).length : 0)
	const auxCount = (r) => (Array.isArray(r.items) ? r.items.filter(it => !it?.is_main_device).length : 0)
	const pendingTotal = (r) => {
		if (!Array.isArray(r.items)) return 0
		return r.items.reduce((sum, it) => sum + Number(it?.pending_quantity || 0), 0)
	}

	const load = async (reset = true) => {
		if (!userStore.token) return
		if (reset) {
			page.value = 1
			records.value = []
			total.value = 0
		}

		const isFirst = reset && records.value.length === 0
		if (isFirst) loading.value = true
		else loadingMore.value = true

		try {
			const params = []
			if (statusFilter.value && statusFilter.value !== 'all') params.push(`status_filter=${encodeURIComponent(statusFilter.value)}`)
			params.push(`page=${page.value}`)
			params.push(`page_size=${pageSize.value}`)
			const url = `${buildApiUrl(API_ENDPOINTS.STOCK.MY_RETURNS)}?${params.join('&')}`

			const res = await uni.request({
				url,
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token),
				})
			})

			if (res.statusCode === 200) {
				const list = Array.isArray(res.data?.records) ? res.data.records : []
				total.value = Number(res.data?.total || 0)
				records.value = reset ? list : records.value.concat(list)
				return
			}

			if (res.statusCode === 401) {
				userStore.logout()
				return
			}
			uni.showToast({ title: String(res.data?.detail || res.data?.message || '加载失败'), icon: 'none' })
		} catch (e) {
			console.error('加载退库申请失败:', e)
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
			{ key: 'pending_receive', label: statusLabel('pending_receive') },
			{ key: 'partially_received', label: statusLabel('partially_received') },
			{ key: 'received', label: statusLabel('received') },
			{ key: 'rejected', label: statusLabel('rejected') },
			{ key: 'canceled', label: statusLabel('canceled') },
		]
		uni.showActionSheet({
			itemList: options.map(o => o.label),
			success: async (res) => {
				const picked = options[res.tapIndex]
				if (!picked) return
				statusFilter.value = picked.key
				await load(true)
			}
		})
	}

	const goCreate = () => {
		uni.navigateTo({ url: '/pages/stock/returns/create' })
	}

	onMounted(async () => {
		await load(true)
	})
</script>

<style scoped lang="scss">
	.page { background: var(--bg-page); min-height: 100vh; }
	.content {
		background: var(--bg-page);
		height: calc(100vh - 88rpx - var(--status-bar-height, 0px));
	}

	.hero {
		margin: 14px 16px 0;
		border-radius: var(--radius-lg);
		padding: 14px;
		background:
			radial-gradient(920px 260px at 10% 0%, rgba(var(--color-primary-rgb), 0.14), transparent 62%),
			radial-gradient(920px 260px at 90% 10%, rgba(var(--color-brand-blue-rgb), 0.08), transparent 62%),
			linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(255, 255, 255, 0.90));
		border: 1px solid rgba(229, 231, 235, 0.9);
		box-shadow: var(--shadow-card);
	}

	.hero-inner { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
	.hero-left { flex: 1; min-width: 0; }
	.hero-title { font-size: 16px; font-weight: 800; color: var(--text-primary); }
	.hero-sub { margin-top: 6px; font-size: 12px; color: var(--text-secondary); line-height: 1.5; }

	.filters { margin-top: 12px; display: flex; gap: 10px; flex-wrap: wrap; }
	.chip {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px 10px;
		border-radius: 12px;
		border: 1px solid var(--border-color);
		background: rgba(255, 255, 255, 0.92);
	}
	.chip-k { font-size: 12px; color: var(--text-secondary); }
	.chip-v { font-size: 12px; font-weight: 700; color: var(--text-primary); }
	.chip-arrow { font-size: 10px; color: #9ca3af; }

	.list { padding: 14px 16px 0; }
	.card { margin-bottom: 12px; padding: 14px; }
	.card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
	.no { font-size: 14px; font-weight: 800; color: var(--text-primary); }
	.meta { margin-top: 6px; display: flex; align-items: center; gap: 8px; }
	.meta-item { font-size: 12px; color: var(--text-secondary); }
	.dot { color: #d1d5db; }

	.summary { margin-top: 10px; display: flex; justify-content: space-between; gap: 10px; }
	.summary-k { font-size: 12px; color: var(--text-secondary); }
	.summary-v { font-size: 12px; color: var(--text-primary); font-weight: 700; max-width: 68%; text-align: right; word-break: break-all; }

	.stats { margin-top: 12px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
	.stat { padding: 10px; border-radius: 14px; background: rgba(243, 244, 246, 0.8); border: 1px solid rgba(229, 231, 235, 0.9); }
	.k { font-size: 11px; color: var(--text-secondary); }
	.v { margin-top: 4px; font-size: 14px; font-weight: 800; color: var(--text-primary); }

	.u-tag { padding: 5px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }
	.tag-ok { background: rgba(34, 197, 94, 0.12); color: #15803d; border: 1px solid rgba(34, 197, 94, 0.22); }
	.tag-warn { background: rgba(245, 158, 11, 0.14); color: #b45309; border: 1px solid rgba(245, 158, 11, 0.22); }
	.tag-bad { background: rgba(239, 68, 68, 0.10); color: #b91c1c; border: 1px solid rgba(239, 68, 68, 0.20); }
	.tag-muted { background: rgba(148, 163, 184, 0.10); color: #475569; border: 1px solid rgba(148, 163, 184, 0.18); }

	.footer-loading { padding: 14px 0; }
	.spacer { height: 24px; }
	.mono { font-family: monospace; }
</style>
