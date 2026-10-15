import { reactive } from 'vue'
import { stockApi } from '@/api/stock'

// 库存流程设置（只读）：页面用于决定目标站点等字段是否必填；后端仍会再次校验
const state = reactive({
  material_request_requires_site: false,
  quick_stock_out_requires_site: false,
})

export const loadStockFlowSettings = async () => {
  try {
    const res = await stockApi.getFlowSettings()
    const s = res?.settings || {}
    state.material_request_requires_site = !!s.material_request_requires_site
    state.quick_stock_out_requires_site = !!s.quick_stock_out_requires_site
  } catch (error) {
    console.error('加载库存流程设置失败:', error)
  }
  return state
}

export const useStockFlowSettings = () => state
