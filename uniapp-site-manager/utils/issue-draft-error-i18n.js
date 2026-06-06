import {
	extractStockErrorMessage,
	localizeStockBackendErrorMessage,
} from './stock-error-i18n.js'

export const localizeIssueDraftBackendErrorMessage = (message, t, fallback = '') => {
	return localizeStockBackendErrorMessage(message, t, fallback)
}

export const extractIssueDraftErrorMessage = (data, t, fallback = '') => {
	return extractStockErrorMessage(data, t, fallback)
}
