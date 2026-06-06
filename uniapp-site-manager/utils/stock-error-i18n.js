const CJK_RE = /[\u3400-\u9fff]/

const exactMessageKeyMap = {
	'权限不足': 'messages.permissionDenied',
	'缺少 request_id': 'stock.stockErrorRequestIdRequired',
	'申请单不存在': 'stock.stockErrorMaterialRequestNotFound',
	'仅申请人可创建领料单': 'stock.stockErrorRequesterOnlyCreateIssueDraft',
	'申请单未批准，无法领料': 'stock.stockErrorMaterialRequestNotApprovedCannotPick',
	'申请单已关闭': 'stock.stockErrorMaterialRequestClosed',
	'无可领物料': 'stock.issueDraftErrorNoPickableMaterials',
	'物料申请流程已关闭': 'stock.materialRequestDisabled',
	'快捷出库已关闭': 'stock.manualStockOutDisabled',
	'仓库不存在或已停用': 'stock.stockErrorWarehouseNotAvailable',
	'退入仓库不存在或已停用': 'stock.stockErrorReturnWarehouseNotAvailable',
	'仓库不存在或已删除': 'stock.stockErrorWarehouseNotFoundOrDeleted',
	'无权限操作该仓库': 'stock.stockErrorNoPermissionOperateWarehouse',
	'申请人不存在或已禁用': 'stock.stockErrorRequesterNotFound',
	'领取人不存在或已禁用': 'stock.stockErrorManualStockOutReceiverNotFound',
	'物料不存在或已停用': 'stock.stockErrorEquipmentNotAvailable',
	'审批明细不能为空': 'stock.stockErrorApprovalItemsRequired',
	'入库明细不能为空': 'stock.stockErrorStockInItemsRequired',
	'当前状态不可编辑': 'stock.materialRequestNotEditable',
	'当前状态不可提交': 'stock.stockErrorCannotSubmitStatus',
	'当前状态不可取消': 'stock.stockErrorCannotCancelStatus',
	'当前状态不可审批': 'stock.stockErrorCannotApproveStatus',
	'当前状态不可驳回': 'stock.stockErrorCannotRejectStatus',
	'当前状态不可放弃领货': 'stock.stockErrorCannotAbandonStatus',
	'无权限查看该申请单': 'stock.stockErrorNoPermissionViewMaterialRequest',
	'无权限编辑该申请单': 'stock.stockErrorNoPermissionEditMaterialRequest',
	'无权限编辑该仓库的申请单': 'stock.stockErrorNoPermissionEditWarehouseMaterialRequest',
	'无权限提交该申请单': 'stock.stockErrorNoPermissionSubmitMaterialRequest',
	'无权限提交该仓库的申请单': 'stock.stockErrorNoPermissionSubmitWarehouseMaterialRequest',
	'无权限取消该申请单': 'stock.stockErrorNoPermissionCancelMaterialRequest',
	'无权限放弃该申请单': 'stock.stockErrorNoPermissionAbandonMaterialRequest',
	'无权限审批该仓库的申请单': 'stock.stockErrorNoPermissionApproveWarehouseMaterialRequest',
	'无权限驳回该仓库的申请单': 'stock.stockErrorNoPermissionRejectWarehouseMaterialRequest',
	'领料单不存在': 'stock.issueDraftErrorDraftNotFound',
	'无权限处理该仓库的领料单': 'stock.issueDraftErrorNoWarehousePermission',
	'当前状态不可扫码': 'stock.issueDraftErrorCannotScanStatus',
	'条码不能为空': 'stock.issueDraftErrorBarcodeRequired',
	'该SN实例已撤销': 'stock.issueDraftErrorInstanceVoided',
	'该SN不是主设备，无法加入领料单': 'stock.issueDraftErrorNotMainDevice',
	'当前状态不可删除SN': 'stock.issueDraftErrorCannotDeleteSnStatus',
	'SN记录不存在': 'stock.issueDraftErrorSnRecordNotFound',
	'该SN已确认，不能删除': 'stock.issueDraftErrorSnConfirmedCannotDelete',
	'当前状态不可编辑辅料': 'stock.issueDraftErrorCannotEditAuxStatus',
	'items 参数不合法': 'stock.issueDraftErrorItemsInvalid',
	'辅料数量超过可领上限': 'stock.issueDraftErrorAuxExceedsCap',
	'请至少选择1个SN或填写辅料数量': 'stock.issueDraftErrorNeedSnOrAux',
	'已发生部分确认，不能取消': 'stock.issueDraftErrorPartialConfirmedCannotCancel',
	'当前状态不可确认出库': 'stock.stockErrorCannotConfirmStockOutStatus',
	'无权限确认出库': 'stock.stockErrorNoPermissionConfirmStockOut',
	'退库单不存在': 'stock.stockErrorReturnNotFound',
	'无权限处理该仓库的退库单': 'stock.stockErrorNoPermissionReturnWarehouse',
	'无权限查看该仓库的退库单': 'stock.stockErrorNoPermissionViewReturnWarehouse',
	'无权限取消该退库单': 'stock.stockErrorNoPermissionCancelReturn',
	'关联出库单不存在': 'stock.stockErrorOutOrderNotFound',
	'出库单不存在': 'stock.stockErrorOutOrderNotFound',
	'无权限查看该出库单': 'stock.stockErrorNoPermissionViewStockOut',
	'当前状态不可拒收': 'stock.stockErrorCannotRejectReceiveStatus',
	'退库单中不存在该辅料': 'stock.stockErrorReturnAuxNotFound',
	'设备实例不存在': 'stock.stockErrorDeviceInstanceNotFound',
	'线下票据不存在': 'stock.stockErrorOfflineDocumentNotFound',
}

const translate = (t, key, params = {}) => {
	const value = t(key, params)
	return value && value !== key ? value : ''
}

const isChineseLocale = (t) => {
	return translate(t, 'common.confirm') === '确认' || translate(t, 'messages.operationFailed') === '操作失败'
}

const localizeUnknownText = (text, t, fallback = '') => {
	if (!text) return fallback || translate(t, 'messages.operationFailed') || ''
	if (CJK_RE.test(text) && !isChineseLocale(t)) {
		return fallback || translate(t, 'messages.operationFailed') || ''
	}
	return text
}

export const localizeStockBackendErrorMessage = (message, t, fallback = '') => {
	const text = String(message || '').trim()
	if (!text) return fallback || translate(t, 'messages.operationFailed')

	const exactKey = exactMessageKeyMap[text]
	if (exactKey) {
		return translate(t, exactKey) || localizeUnknownText(text, t, fallback)
	}

	let match = text.match(/^设备ID\s+(\d+)\s+不存在$/)
	if (match) return translate(t, 'stock.stockErrorDeviceIdNotFound', { id: match[1] }) || localizeUnknownText(text, t, fallback)

	match = text.match(/^未找到该SN对应的设备实例：(.+)。请确认扫描的是设备SN，或联系管理员导入库存。$/)
	if (match) return translate(t, 'stock.issueDraftErrorInstanceNotFound', { sn: match[1] }) || localizeUnknownText(text, t, fallback)

	match = text.match(/^设备当前状态为 (.+)，不在库中，无法领料$/)
	if (match) return translate(t, 'stock.issueDraftErrorDeviceNotInStock', { status: match[1] }) || localizeUnknownText(text, t, fallback)

	match = text.match(/^设备不在申请仓库，无法领料（设备仓库：(.+?)，申请仓库：(.+?)）$/)
	if (match) {
		return translate(t, 'stock.issueDraftErrorWarehouseMismatch', {
			deviceWarehouse: match[1],
			requestWarehouse: match[2],
		}) || localizeUnknownText(text, t, fallback)
	}

	match = text.match(/^该SN对应型号【(.+)】不在申请单内，无法领料$/)
	if (match) return translate(t, 'stock.issueDraftErrorModelNotRequested', { equipmentName: match[1] }) || localizeUnknownText(text, t, fallback)

	match = text.match(/^该物料已无剩余可领数量（已审批(\d+)，已出库(\d+)，其他领料单占用(\d+)）$/)
	if (match) {
		return translate(t, 'stock.issueDraftErrorNoRemainingQty', {
			approvedQty: match[1],
			issuedQty: match[2],
			pendingQty: match[3],
		}) || localizeUnknownText(text, t, fallback)
	}

	match = text.match(/^该SN已在其他领料单【(.+)】中待确认，无法重复添加$/)
	if (match) return translate(t, 'stock.issueDraftErrorSnConflict', { draftNo: match[1] }) || localizeUnknownText(text, t, fallback)

	match = text.match(/^扫码添加SN发生冲突（可能是重复提交或并发操作），请刷新后重试（错误编号：(.+)）$/)
	if (match) return translate(t, 'stock.issueDraftErrorScanConflictRetry', { errorId: match[1] }) || localizeUnknownText(text, t, fallback)

	match = text.match(/^系统异常，扫码添加SN失败，请稍后重试或联系管理员（错误编号：(.+)）$/)
	if (match) return translate(t, 'stock.issueDraftErrorScanSystemFailure', { errorId: match[1] }) || localizeUnknownText(text, t, fallback)

	match = text.match(/^SN当前状态不可出库：(.+)$/)
	if (match) return translate(t, 'stock.stockErrorSnCannotStockOut', { sn: match[1] }) || localizeUnknownText(text, t, fallback)

	match = text.match(/^设备SN不存在：(.+)$/)
	if (match) return translate(t, 'stock.stockErrorDeviceSnNotFound', { sns: match[1] }) || localizeUnknownText(text, t, fallback)

	match = text.match(/^无权限退库（设备不在当前用户名下）：(.+)$/)
	if (match) return translate(t, 'stock.stockErrorNoPermissionReturnOwnership', { sns: match[1] }) || localizeUnknownText(text, t, fallback)

	match = text.match(/^退库单中不存在该SN：(.+)$/)
	if (match) return translate(t, 'stock.stockErrorReturnSnNotFound', { sn: match[1] }) || localizeUnknownText(text, t, fallback)

	return localizeUnknownText(text, t, fallback)
}

export const extractStockErrorMessage = (data, t, fallback = '') => {
	const detail = data?.detail ?? data?.message
	if (!detail) return fallback || translate(t, 'messages.operationFailed')
	if (typeof detail === 'string') return localizeStockBackendErrorMessage(detail, t, fallback)
	if (detail?.message) return localizeStockBackendErrorMessage(detail.message, t, fallback)
	if (detail?.detail) return localizeStockBackendErrorMessage(detail.detail, t, fallback)
	return fallback || translate(t, 'messages.operationFailed')
}

export const localizeStockBackendDisplayText = (message, t, fallback = '') => {
	const text = String(message || '').trim()
	if (!text) return fallback
	const localized = localizeStockBackendErrorMessage(text, t, fallback)
	const genericFailure = translate(t, 'messages.operationFailed')
	if (!fallback && CJK_RE.test(text) && !isChineseLocale(t) && localized === genericFailure) return ''
	return localized
}
