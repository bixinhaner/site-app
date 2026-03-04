<template>
	<view class="page" :key="languageStore.currentLocale">
		<CustomNavbar :title="$t('stock.returnNew')" :showBack="true" variant="brand" />

		<scroll-view class="content" scroll-y>
			<view class="hero u-card">
				<text class="hero-title">{{ $t('stock.returnNew') }}</text>
				<text class="hero-sub">{{ $t('stock.returnActualHint') }}</text>
			</view>

			<view class="section u-card">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.selectReturnWarehouse') }}</text>
					<text class="hint">{{ $t('common.optional') }}</text>
				</view>
				<view class="u-card-content">
					<picker @change="onWarehouseChange" :value="warehouseIndex" :range="warehouseOptions">
						<view class="picker-input" :class="{ placeholder: !selectedWarehouse }">
							<text>{{ selectedWarehouse ? selectedWarehouse.warehouse_name : $t('common.pleaseSelect') }}</text>
							<text class="picker-arrow">▼</text>
						</view>
					</picker>
				</view>
			</view>

			<view class="section u-card">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.mainDevice') }}</text>
					<text class="hint">
						{{ $t('stock.returnMainPoolSummary', { count: candidateSummary.main_returnable_count || 0 }) }}
					</text>
				</view>
				<view class="u-card-content">
					<view class="block">
						<view class="block-head">
							<text class="block-title">{{ $t('stock.scanAddMainDevice') }}</text>
							<text class="block-sub">{{ $t('stock.returnMainScanOnlyHint') }}</text>
						</view>
						<button class="u-btn u-btn-primary u-btn-sm u-pressable" @click="scanAddMain">
							<uni-icons type="scan" size="18" color="#fff" />
							<text>{{ $t('stock.scanAddMainDevice') }}</text>
						</button>
						<view v-if="selectedMainSns.length" class="picked-list">
							<view v-for="sn in selectedMainSns" :key="sn" class="picked-row">
								<text class="mono">{{ sn }}</text>
								<text class="remove u-pressable" @click="removeMain(sn)">×</text>
							</view>
						</view>
						<view v-else class="main-sn-empty">{{ $t('stock.returnSelectedMainEmpty') }}</view>
					</view>
				</view>
			</view>

			<view class="section u-card">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.auxMaterial') }}</text>
					<view class="header-actions">
						<button class="u-btn u-btn-secondary u-btn-xs u-pressable" @click="selectAllReturnable">
							{{ $t('stock.returnSelectAll') }}
						</button>
						<button class="u-btn u-btn-ghost u-btn-xs u-pressable" @click="clearAuxSelection">
							{{ $t('stock.returnClearSelection') }}
						</button>
					</view>
				</view>
				<view class="u-card-content">
					<view class="block">
						<view class="block-head">
							<text class="block-title">{{ $t('stock.auxMaterial') }}</text>
							<text class="block-sub">{{ $t('stock.returnMaxLabel') }} = {{ $t('stock.qtyRemaining') }}</text>
						</view>
						<view v-if="auxLoading" class="main-sn-empty">{{ $t('common.loading') }}</view>
						<view v-else-if="auxItems.length === 0" class="main-sn-empty">{{ $t('messages.noData') }}</view>
						<view v-else class="aux-list">
							<view v-for="it in auxItems" :key="it.equipment_id" class="aux-row">
								<view class="aux-left">
									<text class="aux-name">{{ it.equipment_name }}</text>
									<text class="aux-meta">{{ $t('stock.returnMaxLabel') }} {{ it.max_returnable || 0 }} {{ displayUnit(it.unit) || '' }}</text>
								</view>
								<view class="stepper">
									<view class="step u-pressable" @click="decAux(it)">−</view>
									<text class="num mono">{{ auxQtyMap[it.equipment_id] || 0 }}</text>
									<view class="step u-pressable" @click="incAux(it)">＋</view>
								</view>
							</view>
						</view>
					</view>
				</view>
			</view>

			<view class="section u-card">
				<view class="u-card-header">
					<text class="u-card-title">{{ $t('stock.offlineDocTitle') }}</text>
					<text class="hint">{{ $t('common.optional') }}</text>
				</view>
				<view class="u-card-content">
					<OfflineDocumentSection v-model="offlineDocumentId" :disabled="submitting" :showHeader="false" />
				</view>
			</view>

			<view class="section u-card">
				<view class="u-card-content">
					<text class="hero-sub">{{ $t('stock.returnAutoSplitTip') }}</text>
				</view>
			</view>

			<view class="footer">
				<button class="u-btn u-btn-primary u-pressable" :disabled="submitting" @click="submit">
					{{ submitting ? $t('stock.processing') : $t('stock.submitReturnRequest') }}
				</button>
			</view>

			<view class="spacer" />
		</scroll-view>

		<view v-if="bindModalVisible" class="bind-modal-mask" @click="closeBindModal">
			<view class="bind-modal" @click.stop>
				<view class="bind-modal-header">
					<text class="bind-modal-title">
						{{ bindModalAction === 'need_unbind' ? $t('stock.oneClickUnbind') : $t('common.hint') }}
					</text>
					<text class="bind-modal-close u-pressable" @click="closeBindModal">×</text>
				</view>

				<view class="bind-modal-body">
					<text class="bind-modal-desc">{{ bindModalMessage }}</text>

					<scroll-view v-if="bindModalBindings.length" class="bind-list" scroll-y>
						<view v-for="(b, idx) in bindModalBindings" :key="idx" class="bind-item">
							<view class="bind-item-row">
								<text class="bind-sn mono">{{ b.sn || '-' }}</text>
								<text class="bind-title">{{ bindingTitle(b) }}</text>
							</view>
							<text v-if="bindingSiteName(b)" class="bind-sub">{{ bindingSiteName(b) }}</text>
							<text v-if="bindingReasonText(b)" class="bind-reason">{{ bindingReasonText(b) }}</text>
						</view>
					</scroll-view>
				</view>

				<view class="bind-modal-footer">
					<button class="u-btn u-btn-secondary u-pressable" :disabled="unbindSubmitting" @click="closeBindModal">
						{{ $t('common.close') }}
					</button>
					<button
						v-if="bindModalAction === 'need_unbind'"
						class="u-btn u-btn-primary u-pressable"
						:disabled="unbindSubmitting"
						@click="confirmUnbindAndRetry"
					>
						{{ unbindSubmitting ? $t('stock.processing') : $t('stock.oneClickUnbind') }}
					</button>
				</view>
			</view>
		</view>
	</view>
</template>

<script setup>
	import { computed, getCurrentInstance, onMounted, ref } from 'vue'
	import { onLoad } from '@dcloudio/uni-app'
	import { API_ENDPOINTS, buildApiUrl, createRequestConfig, getAuthHeaders } from '@/config/api.js'
	import { scanAndParseDeviceCode, ScanDeviceCodeError, isScanCanceled } from '@/utils/scan-code.js'
	import { getLocalizedStockUnit } from '@/utils/unit-i18n.js'
	import { useUserStore } from '@/stores/user'
	import { useLanguageStore } from '@/stores/language'

	const userStore = useUserStore()
	const languageStore = useLanguageStore()
	const { appContext } = getCurrentInstance()
	const { $t } = appContext.config.globalProperties
	const displayUnit = (unit) => getLocalizedStockUnit(unit, $t)

	const warehouses = ref([])
	const warehouseIndex = ref(0)
	const warehouseOptions = computed(() => (warehouses.value || []).map(w => w.warehouse_name))
	const selectedWarehouse = computed(() => warehouses.value?.[warehouseIndex.value] || null)

	const selectedMainSns = ref([])
	const auxItems = ref([])
	const auxQtyMap = ref({})
	const auxLoading = ref(false)
	const candidateSummary = ref({
		main_returnable_count: 0,
		main_pending_return_count: 0,
		aux_item_count: 0,
		aux_total_max_returnable: 0,
	})

	const offlineDocumentId = ref(null)
	const submitting = ref(false)

	const preselectSn = ref('')
	const preselectApplied = ref(false)

	const bindModalVisible = ref(false)
	const bindModalAction = ref('')
	const bindModalMessage = ref('')
	const bindModalBindings = ref([])
	const unbindSubmitting = ref(false)

	const onWarehouseChange = (e) => {
		warehouseIndex.value = Number(e.detail.value || 0)
	}

	const loadWarehouses = async () => {
		try {
			const res = await uni.request({
				url: buildApiUrl('/api/stock/warehouses'),
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token),
				})
			})
			if (res.statusCode === 200) {
				warehouses.value = Array.isArray(res.data?.warehouses) ? res.data.warehouses : []
			}
		} catch (e) {
			console.error('加载仓库失败:', e)
		}
	}

	const loadActualCandidates = async () => {
		if (!userStore.token) return
		auxLoading.value = true
		try {
			const res = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.STOCK.RETURN_ACTUAL_CANDIDATES),
				...createRequestConfig({
					method: 'GET',
					headers: getAuthHeaders(userStore.token),
				})
			})
			if (res.statusCode === 200) {
				auxItems.value = Array.isArray(res.data?.aux_items) ? res.data.aux_items : []
				candidateSummary.value = res.data?.summary || candidateSummary.value
				const map = {}
				for (const row of auxItems.value) {
					const eid = Number(row?.equipment_id)
					if (!Number.isFinite(eid)) continue
					map[eid] = Number(auxQtyMap.value?.[eid] || 0)
				}
				auxQtyMap.value = map
				return
			}
			if (res.statusCode === 401) userStore.logout()
		} catch (e) {
			console.error('加载退库候选失败:', e)
		} finally {
			auxLoading.value = false
		}
	}

	const bindingTitle = (binding) => {
		const fallback = $t('stock.unknownWorkOrderOrSite')
		if (!binding) return fallback
		return binding.work_order_title || binding.site_name || fallback
	}

	const bindingSiteName = (binding) => {
		if (!binding) return ''
		if (binding.work_order_title && binding.site_name) return binding.site_name
		return ''
	}

	const bindingReasonText = (binding) => {
		if (!binding) return ''
		const code = String(binding.reason_code || '').trim()
		const map = {
			other_inspector: $t('stock.unbindReasonOtherInspector'),
			inspection_locked: $t('stock.unbindReasonInspectionLocked'),
			status_not_supported: $t('stock.unbindReasonStatusNotSupported'),
		}
		return map[code] || binding.reason || ''
	}

	const openBindModalFromDetail = (detail) => {
		const action = String(detail?.action || '').trim()
		if (action !== 'need_unbind' && action !== 'unbind_blocked') return false
		bindModalAction.value = action
		bindModalMessage.value = String(detail?.message || detail?.detail || $t('messages.operationFailed') || '').trim()
		bindModalBindings.value = Array.isArray(detail?.need_unbind)
			? detail.need_unbind
			: Array.isArray(detail?.blocked_bindings)
				? detail.blocked_bindings
				: []
		bindModalVisible.value = true
		return true
	}

	const closeBindModal = (force = false) => {
		if (unbindSubmitting.value && !force) return
		bindModalVisible.value = false
		bindModalAction.value = ''
		bindModalMessage.value = ''
		bindModalBindings.value = []
	}

	const formatRelatedInfoLines = (relatedInfo) => {
		if (!relatedInfo || typeof relatedInfo !== 'object') return []
		const map = {
			sn: $t('stock.serialNumber'),
			current_owner_name: $t('common.user'),
			out_document_number: $t('stock.documentNumber'),
			existing_return_document_number: $t('stock.returnDocumentNumber'),
			existing_return_status: $t('common.status'),
			out_warehouse_name: $t('stock.warehouse'),
			existing_return_warehouse_name: $t('stock.returnWarehouseLabel'),
			out_operator_name: $t('stock.operator'),
			current_status: $t('common.status'),
		}
		const lines = []
		Object.keys(map).forEach((k) => {
			const v = relatedInfo?.[k]
			if (v === undefined || v === null || String(v).trim() === '') return
			lines.push(`${map[k]}：${v}`)
		})
		return lines
	}

	const showDetailedError = (detail, fallbackSn = '') => {
		if (!detail || typeof detail !== 'object') {
			uni.showToast({ title: String(detail || $t('messages.operationFailed')), icon: 'none' })
			return
		}
		const reason = String(detail.reason || detail.message || detail.detail || '').trim()
		const suggestion = String(detail.suggestion || '').trim()
		const infoLines = formatRelatedInfoLines(detail.related_info)
		const contentParts = []
		if (reason) contentParts.push(`原因：${reason}`)
		if (suggestion) contentParts.push(`建议：${suggestion}`)
		if (infoLines.length > 0) {
			contentParts.push('相关信息：')
			contentParts.push(infoLines.join('\n'))
		}
		if (contentParts.length === 0 && fallbackSn) {
			contentParts.push(`扫码SN为：${fallbackSn}`)
		}
		uni.showModal({
			title: String(detail.title || $t('common.hint')),
			content: contentParts.join('\n\n') || $t('messages.operationFailed'),
			showCancel: false,
			confirmText: $t('common.confirm'),
		})
	}

	const addValidatedSn = (sn) => {
		const value = String(sn || '').trim()
		if (!value) return
		if (selectedMainSns.value.includes(value)) return
		selectedMainSns.value = selectedMainSns.value.concat([value])
	}

	const validateAndAddSn = async (sn) => {
		const value = String(sn || '').trim()
		if (!value) return false
		try {
			const res = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.STOCK.RETURN_VALIDATE_SN),
				...createRequestConfig({
					method: 'POST',
					headers: getAuthHeaders(userStore.token),
					data: { sn: value },
				})
			})
			if (res.statusCode === 200) {
				addValidatedSn(value)
				return true
			}
			if (res.statusCode === 401) {
				userStore.logout()
				return false
			}
			showDetailedError(res.data?.detail || res.data?.message, value)
			return false
		} catch (e) {
			console.error('校验SN失败:', e)
			uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
			return false
		}
	}

	const scanAddMain = async () => {
		try {
			const scanned = await scanAndParseDeviceCode()
			if (!scanned.ok) {
				if (scanned.error === ScanDeviceCodeError.UNSUPPORTED_SCAN_TYPE) {
					uni.showToast({ title: $t('stock.unsupportedScanType', { type: scanned.scanType || 'UNKNOWN' }), icon: 'none' })
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
			await validateAndAddSn(scanned.sn)
		} catch (e) {
			const msg = String(e?.errMsg || e?.message || '').toLowerCase()
			if (msg.includes('cancel')) return
		}
	}

	const removeMain = (sn) => {
		selectedMainSns.value = selectedMainSns.value.filter(s => s !== sn)
	}

	const decAux = (it) => {
		const eid = Number(it?.equipment_id)
		if (!Number.isFinite(eid)) return
		const cur = Number(auxQtyMap.value?.[eid] || 0)
		auxQtyMap.value = { ...(auxQtyMap.value || {}), [eid]: Math.max(0, cur - 1) }
	}

	const incAux = (it) => {
		const eid = Number(it?.equipment_id)
		if (!Number.isFinite(eid)) return
		const cur = Number(auxQtyMap.value?.[eid] || 0)
		const max = Number(it?.max_returnable || 0)
		auxQtyMap.value = { ...(auxQtyMap.value || {}), [eid]: Math.min(max, cur + 1) }
	}

	const selectAllReturnable = () => {
		const map = { ...(auxQtyMap.value || {}) }
		for (const it of auxItems.value) {
			const eid = Number(it?.equipment_id)
			if (!Number.isFinite(eid)) continue
			map[eid] = Math.max(0, Number(it?.max_returnable || 0))
		}
		auxQtyMap.value = map
	}

	const clearAuxSelection = () => {
		const map = { ...(auxQtyMap.value || {}) }
		Object.keys(map).forEach((k) => { map[k] = 0 })
		auxQtyMap.value = map
	}

	const buildSubmitPayload = () => {
		if (!selectedWarehouse.value) {
			uni.showToast({ title: $t('stock.selectReturnWarehouse'), icon: 'none' })
			return null
		}
		const auxPayload = []
		Object.keys(auxQtyMap.value || {}).forEach((k) => {
			const eid = Number(k)
			const qty = Number(auxQtyMap.value[k] || 0)
			if (!Number.isFinite(eid) || qty <= 0) return
			auxPayload.push({ equipment_id: eid, quantity: qty })
		})
		if (selectedMainSns.value.length === 0 && auxPayload.length === 0) {
			uni.showToast({ title: $t('stock.returnSelectAtLeastOne'), icon: 'none' })
			return null
		}
		return {
			return_warehouse_id: selectedWarehouse.value.id,
			main_sns: selectedMainSns.value,
			aux_items: auxPayload,
			offline_document_id: offlineDocumentId.value || undefined,
		}
	}

	const buildSubmitConfirmAuxRows = (payload) => {
		const map = new Map((auxItems.value || []).map(it => [Number(it?.equipment_id), it]))
		return (payload?.aux_items || []).map((row) => {
			const eid = Number(row?.equipment_id)
			const qty = Number(row?.quantity || 0)
			const matched = map.get(eid)
			return {
				equipment_name: String(matched?.equipment_name || eid),
				unit: String(matched?.unit || ''),
				quantity: qty,
			}
		}).filter(r => r.quantity > 0)
	}

	const buildSubmitConfirmContent = (payload) => {
		const mainList = Array.isArray(payload?.main_sns) ? payload.main_sns : []
		const auxRows = buildSubmitConfirmAuxRows(payload)
		const mainLines = mainList.length
			? mainList.map((sn, idx) => `${idx + 1}. ${sn}`).join('\n')
			: $t('stock.returnSubmitConfirmNone')
		const auxLines = auxRows.length
			? auxRows.map((row, idx) => `${idx + 1}. ${row.equipment_name} x ${row.quantity}${row.unit ? ` ${displayUnit(row.unit)}` : ''}`).join('\n')
			: $t('stock.returnSubmitConfirmNone')
		return [
			`${$t('stock.returnSubmitConfirmWarehouse')}: ${selectedWarehouse.value?.warehouse_name || '-'}`,
			`${$t('stock.returnSubmitConfirmMainTitle', { count: mainList.length })}:`,
			mainLines,
			`${$t('stock.returnSubmitConfirmAuxTitle', { count: auxRows.length })}:`,
			auxLines,
			'',
			$t('stock.returnAutoSplitTip'),
		].join('\n')
	}

	const confirmSubmitPayload = async (payload) => await new Promise((resolve) => {
		uni.showModal({
			title: $t('stock.returnSubmitConfirmTitle'),
			content: buildSubmitConfirmContent(payload),
			confirmText: $t('common.confirm'),
			cancelText: $t('common.cancel'),
			success: (r) => resolve(!!r.confirm),
			fail: () => resolve(false),
		})
	})

	const showSubmitSuccess = async (data) => await new Promise((resolve) => {
		const mainCount = Number(data?.summary?.main_device_count || 0)
		const auxQty = Number(data?.summary?.aux_total_quantity || 0)
		const createdCount = Number(data?.created_count || 0)
		const batchId = String(data?.batch_id || '-')
		uni.showModal({
			title: $t('stock.createReturnSuccess'),
			content: [
				`${$t('stock.returnBatchIdLabel')}: ${batchId}`,
				`${$t('stock.returnSplitCountLabel')}: ${createdCount}`,
				`${$t('stock.returnSubmitConfirmMainTitle', { count: mainCount })}`,
				`${$t('stock.returnSubmitConfirmAuxTitle', { count: auxQty })}`,
			].join('\n'),
			showCancel: false,
			confirmText: $t('common.confirm'),
			success: () => resolve(true),
			fail: () => resolve(true),
		})
	})

	const goAfterCreateSuccess = () => {
		try {
			const pages = typeof getCurrentPages === 'function' ? getCurrentPages() : []
			const prev = pages?.[pages.length - 2]
			const rawRoute = String(prev?.route || prev?.__route__ || prev?.$page?.route || prev?.$page?.fullPath || '').trim()
			const route = rawRoute.replace(/^\//, '').split('?')[0]
			if (route === 'pages/stock/returns/list') {
				uni.navigateBack({ delta: 1 })
				return
			}
		} catch (e) {
			// ignore
		}
		uni.redirectTo({ url: '/pages/stock/returns/list' })
	}

	const doSubmit = async (preparedPayload = null) => {
		const payload = preparedPayload || buildSubmitPayload()
		if (!payload) return
		try {
			submitting.value = true
			const res = await uni.request({
				url: buildApiUrl(API_ENDPOINTS.STOCK.CREATE_RETURN_BY_ACTUAL),
				...createRequestConfig({
					method: 'POST',
					headers: getAuthHeaders(userStore.token),
					data: payload,
				})
			})

			if (res.statusCode === 200) {
				await showSubmitSuccess(res.data || {})
				goAfterCreateSuccess()
				return
			}
			if (res.statusCode === 401) {
				userStore.logout()
				return
			}

			const detail = res.data?.detail
			if (detail && typeof detail === 'object') {
				const handled = openBindModalFromDetail(detail)
				if (handled) return
				showDetailedError(detail)
				return
			}
			uni.showToast({ title: String(detail || res.data?.message || $t('messages.operationFailed')), icon: 'none' })
		} catch (e) {
			console.error('提交退库失败:', e)
			uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
		} finally {
			submitting.value = false
		}
	}

	const submit = async () => {
		if (submitting.value) return
		const payload = buildSubmitPayload()
		if (!payload) return
		const confirmed = await confirmSubmitPayload(payload)
		if (!confirmed) return
		await doSubmit(payload)
	}

	const tryPreselectSn = async () => {
		if (preselectApplied.value) return
		const sn = String(preselectSn.value || '').trim()
		if (!sn) return
		preselectApplied.value = true
		await validateAndAddSn(sn)
	}

	const confirmUnbindAndRetry = async () => {
		if (unbindSubmitting.value) return
		const sns = Array.from(new Set((bindModalBindings.value || []).map(b => String(b?.sn || '').trim()).filter(Boolean)))
		if (sns.length === 0) {
			closeBindModal()
			return
		}
		uni.showModal({
			title: $t('stock.oneClickUnbind'),
			content: $t('stock.unbindWillClearAndDelete'),
			confirmText: $t('common.confirm'),
			cancelText: $t('common.cancel'),
			success: async (r) => {
				if (!r.confirm) return
				unbindSubmitting.value = true
				try {
					for (const sn of sns) {
						const ret = await uni.request({
							url: buildApiUrl(API_ENDPOINTS.STOCK.SCAN_RETURN_UNBIND),
							...createRequestConfig({
								method: 'POST',
								headers: getAuthHeaders(userStore.token),
								data: { sn },
							})
						})
						if (ret.statusCode === 401) {
							userStore.logout()
							return
						}
						if (ret.statusCode !== 200) {
							const msg = ret.data?.detail || ret.data?.message || $t('messages.operationFailed')
							uni.showToast({ title: String(msg), icon: 'none' })
							return
						}
					}
					uni.showToast({ title: $t('messages.operationSuccess'), icon: 'success' })
					closeBindModal(true)
					await doSubmit()
				} catch (e) {
					console.error('解绑失败:', e)
					uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
				} finally {
					unbindSubmitting.value = false
				}
			}
		})
	}

	onMounted(async () => {
		await loadWarehouses()
		await loadActualCandidates()
		await tryPreselectSn()
	})

	onLoad((query) => {
		preselectSn.value = String(query?.sn || '').trim()
	})
</script>

<style scoped lang="scss">
	.page { background: var(--bg-page); min-height: 100vh; }
	.content { background: var(--bg-page); }

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
	.hero-title { font-size: 16px; font-weight: 900; color: var(--text-primary); }
	.hero-sub { margin-top: 8px; font-size: 12px; color: var(--text-secondary); line-height: 1.5; }

	.section { margin: 14px 16px 0; border-radius: var(--radius-lg); overflow: hidden; }

	.search {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 10px 12px;
		border-radius: 14px;
		border: 1px solid var(--border-color);
		background: rgba(255, 255, 255, 0.92);
	}
	.search-input { flex: 1; font-size: 13px; color: var(--text-primary); }

	.out-list { margin-top: 12px; display: grid; gap: 10px; }
	.out-card {
		padding: 12px;
		border-radius: 16px;
		background: rgba(255, 255, 255, 0.94);
		border: 1px solid rgba(229, 231, 235, 0.95);
	}
	.out-card.active { border-color: rgba(var(--color-primary-rgb), 0.55); background: rgba(var(--color-primary-rgb), 0.06); }
	.out-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
	.out-no { font-size: 14px; font-weight: 900; color: var(--text-primary); }
	.out-meta { margin-top: 6px; display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--text-secondary); }
	.dot { color: #d1d5db; }

	.picker-input {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 10px;
		padding: 12px;
		border-radius: 14px;
		border: 1px solid var(--border-color);
		background: rgba(255, 255, 255, 0.92);
	}
	.picker-input.placeholder { color: #9ca3af; }
	.picker-arrow { font-size: 11px; color: #9ca3af; }

	.block { margin-top: 14px; padding: 12px; border-radius: 16px; background: rgba(243, 244, 246, 0.7); border: 1px solid rgba(229, 231, 235, 0.9); }
	.block-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
	.block-title { font-size: 13px; font-weight: 900; color: var(--text-primary); }
	.block-sub { font-size: 11px; color: var(--text-secondary); }

	.picked-list { margin-top: 10px; display: grid; gap: 8px; }
	.picked-row { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; border-radius: 14px; background: rgba(255, 255, 255, 0.9); border: 1px solid rgba(229, 231, 235, 0.9); }
	.remove { font-size: 18px; font-weight: 900; color: #ef4444; }
	.main-sn-list { margin-bottom: 10px; padding: 10px; border-radius: 14px; background: rgba(255, 255, 255, 0.9); border: 1px solid rgba(229, 231, 235, 0.9); display: grid; gap: 8px; }
	.main-sn-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
	.main-sn-title { font-size: 12px; color: var(--text-secondary); }
	.main-sn-toggle { font-size: 12px; font-weight: 700; color: var(--color-primary); }
	.main-sn-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 8px 10px; border-radius: 12px; background: rgba(243, 244, 246, 0.72); border: 1px solid rgba(229, 231, 235, 0.9); }
	.main-sn-value { font-size: 12px; color: var(--text-primary); flex: 1; min-width: 0; word-break: break-all; }
	.main-sn-status { font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 999px; white-space: nowrap; }
	.status-returnable { color: #15803d; background: rgba(34, 197, 94, 0.12); border: 1px solid rgba(34, 197, 94, 0.22); }
	.status-already_requested { color: #475569; background: rgba(148, 163, 184, 0.10); border: 1px solid rgba(148, 163, 184, 0.18); }
	.status-missing_sn { color: #b45309; background: rgba(245, 158, 11, 0.14); border: 1px solid rgba(245, 158, 11, 0.22); }
	.main-sn-more { font-size: 11px; color: var(--text-secondary); text-align: center; }
	.main-sn-empty { margin-bottom: 10px; font-size: 12px; color: var(--text-secondary); }

	.aux-list { display: grid; gap: 10px; }
	.aux-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
	.aux-left { flex: 1; min-width: 0; }
	.aux-name { display: block; font-size: 13px; font-weight: 800; color: var(--text-primary); }
	.aux-meta { display: block; margin-top: 4px; font-size: 11px; color: var(--text-secondary); }

	.stepper { display: flex; align-items: center; gap: 10px; }
	.step { width: 34px; height: 34px; border-radius: 12px; background: #f3f4f6; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 900; color: #111827; }
	.num { width: 42px; text-align: center; font-size: 14px; font-weight: 900; color: var(--text-primary); }

	.footer { margin: 16px; }
	.spacer { height: 24px; }
	.mono { font-family: monospace; }

	.bind-modal-mask {
		position: fixed;
		left: 0;
		top: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.45);
		display: flex;
		align-items: flex-end;
		justify-content: center;
		z-index: 999;
	}
	.bind-modal {
		width: 100%;
		max-height: 78vh;
		background: #fff;
		border-top-left-radius: 18px;
		border-top-right-radius: 18px;
		overflow: hidden;
		box-shadow: 0 -12px 30px rgba(17, 24, 39, 0.16);
	}
	.bind-modal-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 14px 16px;
		border-bottom: 1px solid rgba(229, 231, 235, 0.9);
	}
	.bind-modal-title { font-size: 14px; font-weight: 900; color: var(--text-primary); }
	.bind-modal-close { font-size: 22px; color: #6b7280; padding: 2px 6px; }
	.bind-modal-body { padding: 12px 16px 6px; }
	.bind-modal-desc { font-size: 12px; color: var(--text-secondary); line-height: 1.5; }

	.bind-list { margin-top: 12px; max-height: 40vh; }
	.bind-item { padding: 10px 12px; border-radius: 14px; background: rgba(243, 244, 246, 0.7); border: 1px solid rgba(229, 231, 235, 0.95); margin-bottom: 10px; }
	.bind-item-row { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }
	.bind-sn { font-size: 12px; font-weight: 900; color: var(--text-primary); }
	.bind-title { flex: 1; min-width: 0; text-align: right; font-size: 12px; color: var(--text-primary); }
	.bind-sub { margin-top: 6px; font-size: 11px; color: var(--text-secondary); }
	.bind-reason { margin-top: 6px; font-size: 11px; color: #ef4444; }

	.bind-modal-footer { padding: 12px 16px 16px; display: flex; gap: 10px; }
	.bind-modal-footer .u-btn { flex: 1; }
</style>
