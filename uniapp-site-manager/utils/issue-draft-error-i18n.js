export const localizeIssueDraftBackendErrorMessage = (message, t) => {
	const text = String(message || '').trim()
	if (!text) return ''
	if (text === '领料单不存在') return t('stock.issueDraftErrorDraftNotFound')
	if (text === '权限不足') return t('messages.permissionDenied')
	if (text === '物料申请流程已关闭') return t('stock.materialRequestDisabled')
	if (text === '无权限处理该仓库的领料单') return t('stock.issueDraftErrorNoWarehousePermission')
	if (text === '当前状态不可扫码') return t('stock.issueDraftErrorCannotScanStatus')
	if (text === '条码不能为空') return t('stock.issueDraftErrorBarcodeRequired')
	if (text === '该SN实例已撤销') return t('stock.issueDraftErrorInstanceVoided')
	if (text === '该SN不是主设备，无法加入领料单') return t('stock.issueDraftErrorNotMainDevice')
	if (text === '当前状态不可删除SN') return t('stock.issueDraftErrorCannotDeleteSnStatus')
	if (text === 'SN记录不存在') return t('stock.issueDraftErrorSnRecordNotFound')
	if (text === '该SN已确认，不能删除') return t('stock.issueDraftErrorSnConfirmedCannotDelete')
	if (text === '当前状态不可编辑辅料') return t('stock.issueDraftErrorCannotEditAuxStatus')
	if (text === 'items 参数不合法') return t('stock.issueDraftErrorItemsInvalid')
	if (text === '辅料数量超过可领上限') return t('stock.issueDraftErrorAuxExceedsCap')
	if (text === '当前状态不可提交') return t('stock.issueDraftErrorCannotSubmitStatus')
	if (text === '请至少选择1个SN或填写辅料数量') return t('stock.issueDraftErrorNeedSnOrAux')
	if (text === '当前状态不可取消') return t('stock.issueDraftErrorCannotCancelStatus')
	if (text === '已发生部分确认，不能取消') return t('stock.issueDraftErrorPartialConfirmedCannotCancel')
	if (text === '无可领物料') return t('stock.issueDraftErrorNoPickableMaterials')

	let match = text.match(/^未找到该SN对应的设备实例：(.+)。请确认扫描的是设备SN，或联系管理员导入库存。$/)
	if (match) return t('stock.issueDraftErrorInstanceNotFound', { sn: match[1] })

	match = text.match(/^设备当前状态为 (.+)，不在库中，无法领料$/)
	if (match) return t('stock.issueDraftErrorDeviceNotInStock', { status: match[1] })

	match = text.match(/^设备不在申请仓库，无法领料（设备仓库：(.+?)，申请仓库：(.+?)）$/)
	if (match) {
		return t('stock.issueDraftErrorWarehouseMismatch', {
			deviceWarehouse: match[1],
			requestWarehouse: match[2],
		})
	}

	match = text.match(/^该SN对应型号【(.+)】不在申请单内，无法领料$/)
	if (match) return t('stock.issueDraftErrorModelNotRequested', { equipmentName: match[1] })

	match = text.match(/^该物料已无剩余可领数量（已审批(\d+)，已出库(\d+)，其他领料单占用(\d+)）$/)
	if (match) {
		return t('stock.issueDraftErrorNoRemainingQty', {
			approvedQty: match[1],
			issuedQty: match[2],
			pendingQty: match[3],
		})
	}

	match = text.match(/^该SN已在其他领料单【(.+)】中待确认，无法重复添加$/)
	if (match) return t('stock.issueDraftErrorSnConflict', { draftNo: match[1] })

	match = text.match(/^扫码添加SN发生冲突（可能是重复提交或并发操作），请刷新后重试（错误编号：(.+)）$/)
	if (match) return t('stock.issueDraftErrorScanConflictRetry', { errorId: match[1] })

	match = text.match(/^系统异常，扫码添加SN失败，请稍后重试或联系管理员（错误编号：(.+)）$/)
	if (match) return t('stock.issueDraftErrorScanSystemFailure', { errorId: match[1] })

	return text
}

export const extractIssueDraftErrorMessage = (data, t, fallback = '') => {
	const detail = data?.detail
	if (!detail) return fallback || t('messages.operationFailed')
	if (typeof detail === 'string') return localizeIssueDraftBackendErrorMessage(detail, t)
	if (detail?.message) return localizeIssueDraftBackendErrorMessage(detail.message, t)
	return fallback || t('messages.operationFailed')
}
