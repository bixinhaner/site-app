<template>
  <el-card class="site-progress-trend" v-loading="loading">
    <template #header>
      <div class="trend-header">
        <span class="trend-title">
          <el-icon><TrendCharts /></el-icon>
          {{ t('dashboard.siteTrend.title') }}
        </span>
        <div class="trend-actions">
          <el-radio-group v-model="granularity" size="small" @change="loadTrend">
            <el-radio-button label="day">{{ t('dashboard.siteTrend.granularity.day') }}</el-radio-button>
            <el-radio-button label="week">{{ t('dashboard.siteTrend.granularity.week') }}</el-radio-button>
            <el-radio-button label="month">{{ t('dashboard.siteTrend.granularity.month') }}</el-radio-button>
          </el-radio-group>
          <el-radio-group v-model="valueMode" size="small" @change="renderChart">
            <el-radio-button label="incremental">{{ t('dashboard.siteTrend.valueMode.incremental') }}</el-radio-button>
            <el-radio-button label="cumulative">{{ t('dashboard.siteTrend.valueMode.cumulative') }}</el-radio-button>
          </el-radio-group>
          <el-radio-group v-model="chartMode" size="small" @change="renderChart">
            <el-radio-button label="auto">{{ t('dashboard.siteTrend.chartMode.auto') }}</el-radio-button>
            <el-radio-button label="bar">{{ t('dashboard.siteTrend.chartMode.bar') }}</el-radio-button>
            <el-radio-button label="line">{{ t('dashboard.siteTrend.chartMode.line') }}</el-radio-button>
          </el-radio-group>
        </div>
      </div>
    </template>

    <div ref="chartRef" class="trend-chart"></div>
  </el-card>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { TrendCharts } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import * as echarts from 'echarts'
import { fetchSiteProgressTrend } from '@/api/dashboard'

const { t, locale } = useI18n()
const chartRef = ref(null)
const loading = ref(false)
const granularity = ref('day')
const valueMode = ref('incremental')
const chartMode = ref('auto')
const trendData = ref(null)

let chartInstance = null

const PERIODS_BY_GRANULARITY = {
  day: 30,
  week: 12,
  month: 12,
}

const SERIES_KEYS = [
  'install_started',
  'install_completed',
  'online',
  'activated',
  'ssv',
]

const SERIES_STYLE = {
  install_started: { color: '#1f77b4', lineType: 'solid', symbol: 'circle' },
  install_completed: { color: '#ff7f0e', lineType: 'dashed', symbol: 'rect' },
  online: { color: '#2ca02c', lineType: 'solid', symbol: 'triangle' },
  activated: { color: '#d62728', lineType: 'dotted', symbol: 'diamond' },
  ssv: { color: '#9467bd', lineType: 'dashed', symbol: 'roundRect' },
}

const buildEmptyOption = () => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: [] },
  yAxis: { type: 'value' },
  series: [],
  graphic: {
    type: 'text',
    left: 'center',
    top: 'middle',
    style: {
      text: t('dashboard.siteTrend.empty'),
      fill: '#9ca3af',
      fontSize: 14,
    },
  },
})

const resolveSeriesLabel = (key, fallback = '') => {
  const keyPath = `dashboard.siteTrend.series.${key}`
  const translated = t(keyPath)
  if (translated && translated !== keyPath) return translated
  return fallback || key
}

const ensureChart = () => {
  if (!chartRef.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }
}

const resolveChartType = () => {
  if (chartMode.value === 'bar' || chartMode.value === 'line') {
    return chartMode.value
  }
  return valueMode.value === 'incremental' ? 'bar' : 'line'
}

const buildSeriesValues = (key) => {
  const source = trendData.value?.series?.[key]
  const incremental = Array.isArray(source?.incremental)
    ? source.incremental.map((v) => Number(v || 0))
    : []

  if (valueMode.value === 'incremental') {
    return incremental
  }

  const baseline = Number(source?.baseline || 0)
  let running = baseline
  return incremental.map((v) => {
    running += Number(v || 0)
    return running
  })
}

const renderChart = () => {
  ensureChart()
  if (!chartInstance) return

  const buckets = Array.isArray(trendData.value?.buckets) ? trendData.value.buckets : []
  if (!buckets.length) {
    chartInstance.setOption(buildEmptyOption(), true)
    return
  }

  const xLabels = buckets.map((bucket) => bucket?.label || '')
  const legend = []
  const series = []
  const currentChartType = resolveChartType()

  SERIES_KEYS.forEach((key) => {
    const source = trendData.value?.series?.[key]
    if (!source) return

    const name = resolveSeriesLabel(key, source.label || key)
    const style = SERIES_STYLE[key] || { color: '#3b82f6', lineType: 'solid', symbol: 'circle' }
    legend.push(name)

    if (currentChartType === 'bar') {
      series.push({
        name,
        type: 'bar',
        barMaxWidth: 18,
        emphasis: { focus: 'series' },
        itemStyle: {
          color: style.color,
          borderRadius: [4, 4, 0, 0],
        },
        data: buildSeriesValues(key),
      })
      return
    }

    series.push({
      name,
      type: 'line',
      smooth: true,
      showSymbol: true,
      symbol: style.symbol,
      symbolSize: 7,
      emphasis: { focus: 'series' },
      lineStyle: {
        width: 2,
        type: style.lineType,
        color: style.color,
      },
      itemStyle: { color: style.color },
      areaStyle: valueMode.value === 'cumulative'
        ? { opacity: 0.06, color: style.color }
        : undefined,
      data: buildSeriesValues(key),
    })
  })

  chartInstance.setOption(
    {
      tooltip: {
        trigger: 'axis',
        confine: true,
        valueFormatter: (value) => `${Number(value || 0)}`,
      },
      legend: {
        top: 0,
        data: legend,
      },
      grid: {
        top: 48,
        left: 16,
        right: 16,
        bottom: 16,
        containLabel: true,
      },
      xAxis: {
        type: 'category',
        boundaryGap: currentChartType === 'bar',
        data: xLabels,
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
      },
      series,
    },
    true,
  )
}

const loadTrend = async () => {
  try {
    loading.value = true
    const periods = PERIODS_BY_GRANULARITY[granularity.value] || PERIODS_BY_GRANULARITY.day
    trendData.value = await fetchSiteProgressTrend({
      granularity: granularity.value,
      periods,
      // 与浏览器本地时区口径保持一致（JS 原生定义：UTC - Local）
      tz_offset_minutes: new Date().getTimezoneOffset(),
    })
    await nextTick()
    renderChart()
  } catch (e) {
    console.error(e)
    ElMessage.error(t('dashboard.siteTrend.loadFailed'))
  } finally {
    loading.value = false
  }
}

const resizeChart = () => {
  chartInstance?.resize()
}

onMounted(async () => {
  await loadTrend()
  window.addEventListener('resize', resizeChart)
})

watch(() => locale.value, () => {
  renderChart()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

defineExpose({
  refresh: loadTrend,
})
</script>

<style scoped lang="scss">
.site-progress-trend {
  border-radius: 12px;
  border: 1px solid var(--border-color);
}

.trend-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.trend-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-primary);
  font-weight: 700;
}

.trend-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.trend-chart {
  width: 100%;
  height: 360px;
}

@media (max-width: 768px) {
  .trend-chart {
    height: 300px;
  }
}
</style>
