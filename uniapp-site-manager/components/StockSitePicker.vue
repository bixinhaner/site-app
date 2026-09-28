<template>
	<view>
		<view class="picker-input u-pressable" :class="{ placeholder: !modelValue }" @click="open">
			<text class="picker-text">{{ modelValue ? siteLabel(modelValue) : $t('stock.targetSitePlaceholder') }}</text>
			<uni-icons v-if="modelValue" type="clear" size="18" color="#9ca3af" @click.stop="select(null)" />
			<text v-else class="picker-arrow">▼</text>
		</view>

		<view class="modal-mask" v-if="visible" @click="close">
			<view class="modal" @click.stop>
				<view class="modal-head">
					<text class="modal-title">{{ $t('stock.targetSite') }}</text>
					<view class="modal-close u-pressable" @click="close">
						<uni-icons type="closeempty" size="22" color="#6b7280" />
					</view>
				</view>

				<view class="modal-search">
					<uni-icons type="search" size="18" color="#6b7280" />
					<input
						class="modal-search-input"
						v-model="keyword"
						:placeholder="$t('stock.targetSiteSearchPlaceholder')"
						confirm-type="search"
						@input="onKeywordInput"
						@confirm="search"
					/>
					<uni-icons v-if="keyword" type="clear" size="18" color="#9ca3af" @click="clearKeyword" />
				</view>

				<scroll-view class="modal-list" scroll-y>
					<view v-if="modelValue" class="pick-row u-pressable-subtle" @click="select(null)">
						<view class="pick-left">
							<text class="pick-name muted">{{ $t('stock.targetSiteClear') }}</text>
						</view>
					</view>
					<view class="pick-row u-pressable-subtle" v-for="s in options" :key="s.id" @click="select(s)">
						<view class="pick-left">
							<text class="pick-name">{{ s.site_name || s.site_code }}</text>
							<text class="pick-sub mono">{{ [s.site_code !== s.site_name ? s.site_code : '', s.city].filter(Boolean).join(' · ') }}</text>
						</view>
						<text v-if="s.recent" class="recent-tag">{{ $t('stock.targetSiteRecent') }}</text>
						<text v-else class="pick-arrow">›</text>
					</view>
					<view v-if="loading" class="modal-empty">
						<text class="modal-empty-text">{{ $t('common.loading') }}</text>
					</view>
					<view v-else-if="options.length === 0" class="modal-empty">
						<text class="modal-empty-text">{{ $t('messages.noSearchResults') }}</text>
					</view>
				</scroll-view>
			</view>
		</view>
	</view>
</template>

<script setup>
	import { onMounted, ref } from 'vue'
	import { useUserStore } from '@/stores/user'
	import { buildApiUrl, API_ENDPOINTS, getAuthHeaders } from '@/config/api.js'

	// modelValue: 已选站点对象 { id, site_name, site_code } 或 null
	const props = defineProps({
		modelValue: { type: Object, default: null },
		// 为空时自动带出最近一次使用的站点（新建单据时使用）
		autofillLastUsed: { type: Boolean, default: false },
	})
	const emit = defineEmits(['update:modelValue'])

	const userStore = useUserStore()
	const visible = ref(false)
	const keyword = ref('')
	const options = ref([])
	const loading = ref(false)
	let timer = null

	const siteLabel = (s) => {
		if (!s) return ''
		const name = s.site_name || ''
		const code = s.site_code || ''
		return name && code && name !== code ? `${name}（${code}）` : name || code
	}

	const fetchOptions = async (kw = '') => {
		const params = ['limit=30']
		if (kw) params.push(`keyword=${encodeURIComponent(kw)}`)
		const res = await uni.request({
			url: `${buildApiUrl(API_ENDPOINTS.STOCK.SITE_OPTIONS)}?${params.join('&')}`,
			method: 'GET',
			header: getAuthHeaders(userStore.token),
		})
		if (res.statusCode === 200) return res.data || {}
		if (res.statusCode === 401) userStore.logout()
		return null
	}

	const search = async () => {
		loading.value = true
		try {
			const data = await fetchOptions(String(keyword.value || '').trim())
			options.value = data?.sites || []
		} catch (e) {
			console.error('加载站点失败:', e)
			options.value = []
		} finally {
			loading.value = false
		}
	}

	const onKeywordInput = () => {
		if (timer) clearTimeout(timer)
		timer = setTimeout(search, 400)
	}

	const clearKeyword = () => {
		keyword.value = ''
		search()
	}

	const open = () => {
		visible.value = true
		keyword.value = ''
		search()
	}

	const close = () => {
		visible.value = false
	}

	const select = (s) => {
		emit('update:modelValue', s ? { id: s.id, site_name: s.site_name, site_code: s.site_code } : null)
		close()
	}

	onMounted(async () => {
		if (!props.autofillLastUsed || props.modelValue) return
		try {
			const data = await fetchOptions('')
			const lastId = data?.last_used_site_id
			const last = (data?.sites || []).find((x) => x.id === lastId)
			if (last && !props.modelValue) select(last)
		} catch (e) {
			// 自动带出失败不影响填单
		}
	})
</script>

<style scoped>
	.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; }
	.picker-input {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 10px;
		padding: 12px 12px;
		border: 1px solid var(--border-color);
		border-radius: 12px;
		background: rgba(255, 255, 255, 0.72);
		color: #111827;
	}
	.picker-input.placeholder { color: #9ca3af; }
	.picker-text { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.picker-arrow { color: #9ca3af; font-size: 12px; }
	.modal-mask {
		position: fixed;
		left: 0;
		top: 0;
		right: 0;
		bottom: 0;
		background: rgba(17, 24, 39, 0.46);
		display: flex;
		align-items: flex-end;
		justify-content: center;
		z-index: 999;
	}
	.modal {
		width: 100%;
		max-height: 82vh;
		background: #fff;
		border-top-left-radius: 18px;
		border-top-right-radius: 18px;
		overflow: hidden;
		box-shadow: 0 -18px 50px rgba(0, 0, 0, 0.20);
	}
	.modal-head {
		padding: 14px 16px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		border-bottom: 1px solid rgba(229, 231, 235, 0.9);
	}
	.modal-title { font-size: 15px; font-weight: 900; color: #111827; }
	.modal-close { width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; border-radius: 12px; background: #f3f4f6; }
	.modal-search { margin: 12px 16px 10px; padding: 10px 12px; border: 1px solid rgba(229, 231, 235, 0.9); border-radius: 14px; background: #f9fafb; display: flex; align-items: center; gap: 10px; }
	.modal-search-input { flex: 1; font-size: 13px; color: #111827; }
	.modal-list { max-height: 56vh; padding: 0 8px 16px; }
	.pick-row {
		padding: 12px 10px;
		margin: 8px;
		border-radius: 14px;
		border: 1px solid rgba(229, 231, 235, 0.9);
		background: #fff;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}
	.pick-left { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
	.pick-name { font-size: 14px; font-weight: 800; color: #111827; }
	.pick-name.muted { color: #6b7280; font-weight: 600; }
	.pick-sub { font-size: 12px; color: #9ca3af; }
	.pick-arrow { color: #9ca3af; font-size: 18px; line-height: 1; }
	.recent-tag { font-size: 11px; color: #f97316; border: 1px solid rgba(249, 115, 22, 0.4); border-radius: 8px; padding: 2px 6px; }
	.modal-empty { padding: 18px; display: flex; justify-content: center; }
	.modal-empty-text { color: #9ca3af; font-size: 13px; }
</style>
