// 地图配置文件
// 根据实际需求配置API key

export const MAP_CONFIG = {
	// 高德地图配置（国内推荐）
	amap: {
		// Web端JS API Key（如需web-view方式）
		webKey: 'YOUR_AMAP_WEB_KEY',
		// Android平台Key
		androidKey: 'YOUR_AMAP_ANDROID_KEY',
		// iOS平台Key
		iosKey: 'YOUR_AMAP_IOS_KEY',
		// 安全密钥（Web服务API使用）
		securityCode: 'YOUR_AMAP_SECURITY_CODE'
	},
	
	// 谷歌地图配置（国际推荐）
	google: {
		// API Key（需要在Google Cloud Console申请）
		apiKey: 'YOUR_GOOGLE_MAPS_API_KEY'
	},
	
	// OpenStreetMap配置（免费开源）
	osm: {
		// Tile服务器地址（可使用官方或自建）
		tileServer: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
		// 归属信息（必须显示）
		attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
	},
	
	// 默认使用的地图类型
	// 选项: 'native' | 'amap' | 'google' | 'osm'
	defaultType: 'native'  // 推荐使用原生map组件
}

// 获取当前环境推荐的地图类型
export function getRecommendedMapType() {
	// #ifdef H5
	// H5环境推荐使用高德或OpenStreetMap
	return 'amap'
	// #endif
	
	// #ifdef APP-PLUS
	// App环境推荐使用原生map组件
	return 'native'
	// #endif
	
	// #ifdef MP
	// 小程序环境只能使用原生map组件
	return 'native'
	// #endif
	
	return 'native'
}

// 检查API key是否已配置
export function checkApiKeyConfigured(mapType) {
	switch(mapType) {
		case 'amap':
			return MAP_CONFIG.amap.webKey && MAP_CONFIG.amap.webKey !== 'YOUR_AMAP_WEB_KEY'
		case 'google':
			return MAP_CONFIG.google.apiKey && MAP_CONFIG.google.apiKey !== 'YOUR_GOOGLE_MAPS_API_KEY'
		case 'osm':
			return true  // OpenStreetMap不需要API key
		case 'native':
			return true  // 原生组件不需要API key
		default:
			return false
	}
}
