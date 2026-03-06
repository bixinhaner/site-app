<template>
	<view class="page" :key="languageStore.currentLocale">
		<CustomNavbar :title="$t('stock.returnBatchEntry')" :showBack="true" variant="brand">
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
						<text class="hero-title">{{ $t('stock.returnBatchEntry') }}</text>
						<text class="hero-sub">{{ $t('stock.returnBatchDimensionHint') }}</text>
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
					<view v-for="batch in records" :key="batch.batch_id" class="card u-card">
						<view class="card-head">
							<view class="left">
								<text class="no mono">{{ batch.batch_id }}</text>
								<view class="meta">
									<text class="meta-item">
										{{ $t('stock.returnBatchCreatedTime') }}: {{ timeAgo(batch.created_at) }}
									</text>
									<text class="dot">·</text>
									<text class="meta-item">
										{{ $t('stock.returnBatchLatestTime') }}: {{ timeAgo(batch.latest_created_at) }}
									</text>
								</view>
							</view>
							<view class="right">
								<view class="u-tag" :class="statusTagClass(batch.status)">{{ statusLabel(batch.status) }}</view>
							</view>
						</view>

						<view v-if="showBatchRejectReason(batch)" class="reject-row u-pressable" @click="openBatchRejectReason(batch)">
							<text class="reject-k">{{ $t('stock.returnBatchRejectReason') }}</text>
							<text class="reject-v">{{ rejectReasonPreview(batch) }}</text>
							<text class="reject-action">{{ $t('stock.returnBatchViewRejectReason') }}</text>
						</view>

						<view class="stats">
							<view class="stat">
								<text class="k">{{ $t('stock.returnBatchDocs') }}</text>
								<text class="v">{{ batch.document_count }}</text>
							</view>
							<view class="stat">
								<text class="k">{{ $t('stock.selectedMainDevices') }}</text>
								<text class="v">{{ batch.main_device_count }}</text>
							</view>
							<view class="stat">
								<text class="k">{{ $t('stock.selectedAux') }}</text>
								<text class="v">{{ batch.aux_total_quantity }}</text>
							</view>
							<view class="stat">
								<text class="k">{{ $t('stock.qtyPending') }}</text>
								<text class="v">{{ batch.pending_total_quantity }}</text>
							</view>
						</view>

						<view v-if="batch.documents.length > 0" class="doc-box">
							<view class="doc-head">
								<text class="doc-title">{{ $t('stock.returnBatchDocList') }}</text>
								<text
									v-if="batch.documents.length > MAX_DOC_PREVIEW"
									class="doc-toggle u-pressable"
									@click="toggleDocs(batch)"
								>
									{{ isDocsExpanded(batch) ? $t('stock.returnBatchCollapseDocs') : $t('stock.returnBatchExpandDocs') }}
								</text>
							</view>

							<view v-for="doc in visibleDocs(batch)" :key="doc.id" class="doc-item">
								<view class="doc-top">
									<text class="doc-no mono">{{ doc.document_number }}</text>
									<view class="u-tag u-tag-small" :class="statusTagClass(doc.status)">{{ statusLabel(doc.status) }}</view>
								</view>
								<view class="doc-meta">
									<text class="doc-meta-item">{{ doc.warehouse_name || '-' }}</text>
									<text class="dot">·</text>
									<text class="doc-meta-item">{{ timeAgo(doc.created_at) }}</text>
								</view>
								<view class="doc-stats">
									<text class="doc-stat">{{ $t('stock.selectedMainDevices') }} {{ doc.main_device_count }}</text>
									<text class="doc-stat">{{ $t('stock.selectedAux') }} {{ doc.aux_total_quantity }}</text>
									<text class="doc-stat">{{ $t('stock.qtyPending') }} {{ doc.pending_total_quantity }}</text>
								</view>
								<view
									v-if="String(doc.status || '') === 'rejected'"
									class="doc-reject u-pressable"
									@click="openDocRejectReason(doc)"
								>
									<text class="doc-reject-text">{{ $t('stock.returnBatchViewRejectReason') }}</text>
								</view>
							</view>

							<view v-if="!isDocsExpanded(batch) && hiddenDocCount(batch) > 0" class="doc-more">
								{{ $t('stock.returnBatchMoreDocs', { count: hiddenDocCount(batch) }) }}
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
	import { computed, getCurrentInstance, ref } from 'vue'
	import { onShow } from '@dcloudio/uni-app'
	import { useUserStore } from '@/stores/user'
	import { useLanguageStore } from '@/stores/language'
	import { API_ENDPOINTS, buildApiUrl, createRequestConfig, getAuthHeaders } from '@/config/api.js'
	import { guardRouteAccess } from '@/utils/feature-access.js'

	const MAX_DOC_PREVIEW = 8

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
	const expandedDocsMap = ref({})

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
		const minute = Math.floor(diff / 60000)
		if (minute < 1) return '刚刚'
		if (minute < 60) return `${minute} 分钟前`
		const hour = Math.floor(minute / 60)
		if (hour < 24) return `${hour} 小时前`
		const day = Math.floor(hour / 24)
		return `${day} 天前`
	}

	const normalizeDocument = (doc) => ({
		id: String(doc?.id || ''),
		document_number: String(doc?.document_number || '-'),
		status: String(doc?.status || ''),
		warehouse_name: String(doc?.warehouse_name || ''),
		main_device_count: Number(doc?.main_device_count || 0),
		aux_total_quantity: Number(doc?.aux_total_quantity || 0),
		pending_total_quantity: Number(doc?.pending_total_quantity || 0),
		approval_comments: String(doc?.approval_comments || ''),
		created_at: doc?.created_at || null,
	})

	const normalizeBatch = (batch) => {
		const docs = Array.isArray(batch?.documents) ? batch.documents.map(normalizeDocument) : []
		docs.sort((a, b) => {
			const t1 = new Date(a.created_at || 0).getTime()
			const t2 = new Date(b.created_at || 0).getTime()
			return t2 - t1
		})
		return {
			batch_id: String(batch?.batch_id || '-'),
			created_at: batch?.created_at || null,
			latest_created_at: batch?.latest_created_at || batch?.created_at || null,
			document_count: Number(batch?.document_count || docs.length || 0),
			main_device_count: Number(batch?.main_device_count || 0),
			aux_total_quantity: Number(batch?.aux_total_quantity || 0),
			pending_total_quantity: Number(batch?.pending_total_quantity || 0),
			status: String(batch?.status || 'pending_receive'),
			reject_reasons: Array.isArray(batch?.reject_reasons)
				? batch.reject_reasons.map(x => String(x || '').trim()).filter(Boolean)
				: [],
			documents: docs,
		}
	}

	const initExpandState = (batchList, reset = false) => {
		const next = reset ? {} : { ...(expandedDocsMap.value || {}) }
		for (const batch of batchList || []) {
			const key = String(batch?.batch_id || '').trim()
			if (!key || Object.prototype.hasOwnProperty.call(next, key)) continue
			const size = Array.isArray(batch?.documents) ? batch.documents.length : 0
			next[key] = size <= MAX_DOC_PREVIEW
		}
		expandedDocsMap.value = next
	}

	const isDocsExpanded = (batch) => {
		const key = String(batch?.batch_id || '').trim()
		if (!key) return true
		if (!Object.prototype.hasOwnProperty.call(expandedDocsMap.value || {}, key)) {
			const size = Array.isArray(batch?.documents) ? batch.documents.length : 0
			return size <= MAX_DOC_PREVIEW
		}
		return !!expandedDocsMap.value[key]
	}

	const visibleDocs = (batch) => {
		const docs = Array.isArray(batch?.documents) ? batch.documents : []
		if (isDocsExpanded(batch)) return docs
		return docs.slice(0, MAX_DOC_PREVIEW)
	}

	const hiddenDocCount = (batch) => {
		const docs = Array.isArray(batch?.documents) ? batch.documents : []
		if (isDocsExpanded(batch)) return 0
		return Math.max(0, docs.length - MAX_DOC_PREVIEW)
	}

	const toggleDocs = (batch) => {
		const key = String(batch?.batch_id || '').trim()
		if (!key) return
		const cur = isDocsExpanded(batch)
		expandedDocsMap.value = { ...(expandedDocsMap.value || {}), [key]: !cur }
	}

	const collectRejectRows = (batch) => {
		const rows = []
		for (const doc of batch?.documents || []) {
			if (String(doc?.status || '') !== 'rejected') continue
			const reason = String(doc?.approval_comments || '').trim() || $t('stock.returnBatchRejectReasonEmpty')
			rows.push({
				document_number: String(doc?.document_number || '-'),
				reason,
			})
		}
		if (rows.length > 0) return rows

		const fallback = Array.isArray(batch?.reject_reasons)
			? batch.reject_reasons.map(x => String(x || '').trim()).filter(Boolean)
			: []
		return fallback.map(reason => ({ document_number: '-', reason }))
	}

	const showBatchRejectReason = (batch) => collectRejectRows(batch).length > 0

	const rejectReasonPreview = (batch) => {
		const rows = collectRejectRows(batch)
		if (rows.length === 0) return $t('stock.returnBatchRejectReasonEmpty')
		const first = rows[0]
		const base = first.document_number && first.document_number !== '-'
			? `${first.document_number}：${first.reason}`
			: first.reason
		if (base.length <= 30) return base
		return `${base.slice(0, 30)}...`
	}

	const openBatchRejectReason = (batch) => {
		const rows = collectRejectRows(batch)
		if (rows.length === 0) {
			uni.showModal({
				title: $t('stock.returnBatchRejectReason'),
				content: $t('stock.returnBatchRejectReasonEmpty'),
				showCancel: false,
				confirmText: $t('common.confirm'),
			})
			return
		}
		const content = rows.map((row, idx) => {
			if (row.document_number && row.document_number !== '-') {
				return `${idx + 1}. ${$t('stock.returnDocumentNumber')}：${row.document_number}\n${row.reason}`
			}
			return `${idx + 1}. ${row.reason}`
		}).join('\n\n')
		uni.showModal({
			title: `${$t('stock.returnBatchRejectReason')} - ${batch.batch_id || '-'}`,
			content,
			showCancel: false,
			confirmText: $t('common.confirm'),
		})
	}

	const openDocRejectReason = (doc) => {
		const reason = String(doc?.approval_comments || '').trim() || $t('stock.returnBatchRejectReasonEmpty')
		uni.showModal({
			title: `${$t('stock.returnBatchRejectReason')} - ${doc?.document_number || '-'}`,
			content: reason,
			showCancel: false,
			confirmText: $t('common.confirm'),
		})
	}

		const ensureReturnAccess = () => guardRouteAccess({
			userStore,
			route: 'pages/stock/returns/list',
			t: $t,
			redirectUrl: '/pages/home/home',
		})

		const load = async (reset = true) => {
			if (!ensureReturnAccess()) return
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
			const url = `${buildApiUrl(API_ENDPOINTS.STOCK.MY_RETURN_BATCHES)}?${params.join('&')}`

			const res = await uni.request({
				url,
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token),
				})
			})

			if (res.statusCode === 200) {
				const list = Array.isArray(res.data?.records) ? res.data.records.map(normalizeBatch) : []
				total.value = Number(res.data?.total || 0)
				records.value = reset ? list : records.value.concat(list)
				initExpandState(reset ? records.value : list, reset)
				return
			}

			if (res.statusCode === 401) {
				userStore.logout()
				return
			}
			uni.showToast({ title: String(res.data?.detail || res.data?.message || '加载失败'), icon: 'none' })
		} catch (e) {
			console.error('加载退库批次失败:', e)
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
			if (!ensureReturnAccess()) return
			uni.navigateTo({ url: '/pages/stock/returns/create' })
		}

	onShow(async () => {
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
	.meta { margin-top: 6px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
	.meta-item { font-size: 12px; color: var(--text-secondary); }
	.dot { color: #d1d5db; }

	.reject-row {
		margin-top: 10px;
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 10px 12px;
		border-radius: 12px;
		border: 1px solid #fecaca;
		background: #fef2f2;
	}
	.reject-k { font-size: 12px; color: #b91c1c; font-weight: 800; flex-shrink: 0; }
	.reject-v {
		flex: 1;
		min-width: 0;
		font-size: 12px;
		color: #7f1d1d;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.reject-action { font-size: 12px; color: #991b1b; font-weight: 800; flex-shrink: 0; }

	.stats { margin-top: 12px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
	.stat { padding: 10px; border-radius: 14px; background: rgba(243, 244, 246, 0.8); border: 1px solid rgba(229, 231, 235, 0.9); }
	.k { font-size: 11px; color: var(--text-secondary); }
	.v { margin-top: 4px; font-size: 14px; font-weight: 800; color: var(--text-primary); }

	.doc-box {
		margin-top: 12px;
		padding: 10px;
		border-radius: 14px;
		background: rgba(243, 244, 246, 0.6);
		border: 1px solid rgba(229, 231, 235, 0.9);
	}
	.doc-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
	.doc-title { font-size: 12px; font-weight: 800; color: var(--text-primary); }
	.doc-toggle { font-size: 12px; color: var(--color-primary); font-weight: 700; }

	.doc-item {
		margin-top: 10px;
		padding: 10px;
		border-radius: 12px;
		background: rgba(255, 255, 255, 0.9);
		border: 1px solid rgba(229, 231, 235, 0.95);
	}
	.doc-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
	.doc-no { font-size: 12px; color: var(--text-primary); font-weight: 700; }
	.doc-meta { margin-top: 6px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
	.doc-meta-item { font-size: 11px; color: var(--text-secondary); }
	.doc-stats { margin-top: 8px; display: flex; gap: 10px; flex-wrap: wrap; }
	.doc-stat { font-size: 11px; color: var(--text-secondary); }

	.doc-reject { margin-top: 8px; display: inline-flex; padding: 4px 8px; border-radius: 999px; background: #fef2f2; border: 1px solid #fecaca; }
	.doc-reject-text { font-size: 11px; color: #b91c1c; font-weight: 700; }

	.doc-more { margin-top: 8px; text-align: center; font-size: 11px; color: var(--text-secondary); }

	.u-tag { padding: 5px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }
	.u-tag-small { padding: 3px 8px; font-size: 11px; }
	.tag-ok { background: rgba(34, 197, 94, 0.12); color: #15803d; border: 1px solid rgba(34, 197, 94, 0.22); }
	.tag-warn { background: rgba(245, 158, 11, 0.14); color: #b45309; border: 1px solid rgba(245, 158, 11, 0.22); }
	.tag-bad { background: rgba(239, 68, 68, 0.10); color: #b91c1c; border: 1px solid rgba(239, 68, 68, 0.20); }
	.tag-muted { background: rgba(148, 163, 184, 0.10); color: #475569; border: 1px solid rgba(148, 163, 184, 0.18); }

	.footer-loading { padding: 14px 0; }
	.spacer { height: 24px; }
	.mono { font-family: monospace; }
</style>
