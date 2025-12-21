<template>
  <div class="app-usage-stats">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <el-button type="default" :icon="ArrowLeft" @click="goBack">返回</el-button>
        <h1>App 使用统计</h1>
      </div>
      <div class="header-right">
        <el-select v-model="selectedDays" @change="loadStats" style="width: 150px">
          <el-option label="最近7天" :value="7" />
          <el-option label="最近30天" :value="30" />
          <el-option label="最近90天" :value="90" />
          <el-option label="最近365天" :value="365" />
        </el-select>
        <el-button :icon="Refresh" @click="loadStats" :loading="loading">刷新</el-button>
      </div>
    </div>

    <!-- 概览卡片 -->
    <div class="stats-summary">
      <div class="stat-card">
        <div class="stat-icon total">
          <el-icon><User /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats?.summary?.total_devices || 0 }}</div>
          <div class="stat-label">总设备数</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon dau">
          <el-icon><Sunny /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats?.summary?.dau || 0 }}</div>
          <div class="stat-label">今日活跃 (DAU)</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon wau">
          <el-icon><Calendar /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats?.summary?.wau || 0 }}</div>
          <div class="stat-label">7日活跃 (WAU)</div>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon mau">
          <el-icon><TrendCharts /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats?.summary?.mau || 0 }}</div>
          <div class="stat-label">30日活跃 (MAU)</div>
        </div>
      </div>
    </div>

    <!-- 图表区域 -->
    <div class="charts-section">
      <!-- 日活趋势 -->
      <div class="chart-card full-width">
        <h3>📈 日活跃趋势</h3>
        <div class="chart-container" ref="trendChartRef"></div>
      </div>
      
      <!-- 版本分布 -->
      <div class="chart-card">
        <h3>📱 版本分布</h3>
        <div v-if="stats?.version_distribution?.length" class="distribution-list">
          <div 
            v-for="(item, index) in stats.version_distribution" 
            :key="index"
            class="dist-item"
          >
            <div class="dist-label">
              <span class="version-badge">{{ item.version_name }}</span>
            </div>
            <div class="dist-bar">
              <div 
                class="dist-bar-fill" 
                :style="{ width: getPercentage(item.device_count, 'version') + '%' }"
              ></div>
            </div>
            <div class="dist-count">{{ item.device_count }}</div>
          </div>
        </div>
        <el-empty v-else description="暂无数据" :image-size="60" />
      </div>
      
      <!-- 设备品牌分布 -->
      <div class="chart-card">
        <h3>🏭 设备品牌分布</h3>
        <div v-if="stats?.brand_distribution?.length" class="distribution-list">
          <div 
            v-for="(item, index) in stats.brand_distribution" 
            :key="index"
            class="dist-item"
          >
            <div class="dist-label">{{ item.brand }}</div>
            <div class="dist-bar">
              <div 
                class="dist-bar-fill brand-bar" 
                :style="{ width: getPercentage(item.count, 'brand') + '%' }"
              ></div>
            </div>
            <div class="dist-count">{{ item.count }}</div>
          </div>
        </div>
        <el-empty v-else description="暂无数据" :image-size="60" />
      </div>
      
      <!-- 系统版本分布 -->
      <div class="chart-card">
        <h3>🤖 Android 版本分布</h3>
        <div v-if="stats?.os_distribution?.length" class="distribution-list">
          <div 
            v-for="(item, index) in stats.os_distribution" 
            :key="index"
            class="dist-item"
          >
            <div class="dist-label">Android {{ item.os_version }}</div>
            <div class="dist-bar">
              <div 
                class="dist-bar-fill os-bar" 
                :style="{ width: getPercentage(item.count, 'os') + '%' }"
              ></div>
            </div>
            <div class="dist-count">{{ item.count }}</div>
          </div>
        </div>
        <el-empty v-else description="暂无数据" :image-size="60" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Refresh, User, Sunny, Calendar, TrendCharts } from '@element-plus/icons-vue'
import { appVersionAPI } from '@/api/appVersion'
import * as echarts from 'echarts'

const router = useRouter()
const loading = ref(false)
const selectedDays = ref(30)
const stats = ref(null)
const trendChartRef = ref(null)
let trendChart = null

// 返回上一页
const goBack = () => {
  router.push('/settings/app-version')
}

// 加载统计数据
const loadStats = async () => {
  loading.value = true
  try {
    const data = await appVersionAPI.getUsageStats(selectedDays.value)
    stats.value = data
    await nextTick()
    renderTrendChart()
  } catch (error) {
    console.error('加载统计数据失败:', error)
    ElMessage.error('加载统计数据失败')
  } finally {
    loading.value = false
  }
}

// 计算百分比
const getPercentage = (value, type) => {
  if (!stats.value) return 0
  let max = 0
  
  if (type === 'version') {
    max = Math.max(...stats.value.version_distribution.map(i => i.device_count))
  } else if (type === 'brand') {
    max = Math.max(...stats.value.brand_distribution.map(i => i.count))
  } else if (type === 'os') {
    max = Math.max(...stats.value.os_distribution.map(i => i.count))
  }
  
  return max > 0 ? (value / max) * 100 : 0
}

// 渲染趋势图
const renderTrendChart = () => {
  if (!trendChartRef.value || !stats.value?.daily_active_trend?.length) return
  
  if (!trendChart) {
    trendChart = echarts.init(trendChartRef.value)
  }
  
  const data = stats.value.daily_active_trend
  
  trendChart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: '{b}<br/>活跃设备: {c}'
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: data.map(d => d.date),
      axisLabel: {
        rotate: 45
      }
    },
    yAxis: {
      type: 'value',
      name: '活跃设备数'
    },
    series: [{
      data: data.map(d => d.count),
      type: 'line',
      smooth: true,
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(102, 126, 234, 0.4)' },
          { offset: 1, color: 'rgba(102, 126, 234, 0.05)' }
        ])
      },
      lineStyle: {
        color: '#667eea',
        width: 3
      },
      itemStyle: {
        color: '#667eea'
      }
    }]
  })
}

// 窗口大小变化时重绘图表
const handleResize = () => {
  trendChart?.resize()
}

onMounted(() => {
  loadStats()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
})
</script>

<style scoped>
.app-usage-stats {
  padding: 20px;
  background: #f5f7fa;
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-left h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
}

.header-right {
  display: flex;
  gap: 12px;
}

/* 概览卡片 */
.stats-summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 24px;
}

.stat-card {
  background: white;
  border-radius: 16px;
  padding: 24px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.stat-icon.total {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
}

.stat-icon.dau {
  background: linear-gradient(135deg, #f093fb, #f5576c);
  color: white;
}

.stat-icon.wau {
  background: linear-gradient(135deg, #4facfe, #00f2fe);
  color: white;
}

.stat-icon.mau {
  background: linear-gradient(135deg, #43e97b, #38f9d7);
  color: white;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #1f2937;
  line-height: 1;
}

.stat-label {
  font-size: 14px;
  color: #6b7280;
  margin-top: 4px;
}

/* 图表区域 */
.charts-section {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.chart-card {
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.chart-card.full-width {
  grid-column: 1 / -1;
}

.chart-card h3 {
  margin: 0 0 20px 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.chart-container {
  height: 300px;
}

/* 分布列表 */
.distribution-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dist-item {
  display: grid;
  grid-template-columns: 100px 1fr 50px;
  align-items: center;
  gap: 12px;
}

.dist-label {
  font-size: 13px;
  color: #4b5563;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.version-badge {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: white;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.dist-bar {
  height: 8px;
  background: #f3f4f6;
  border-radius: 4px;
  overflow: hidden;
}

.dist-bar-fill {
  height: 100%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border-radius: 4px;
  transition: width 0.5s ease;
}

.dist-bar-fill.brand-bar {
  background: linear-gradient(135deg, #f093fb, #f5576c);
}

.dist-bar-fill.os-bar {
  background: linear-gradient(135deg, #43e97b, #38f9d7);
}

.dist-count {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  text-align: right;
}

/* 响应式 */
@media (max-width: 1200px) {
  .stats-summary {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .charts-section {
    grid-template-columns: 1fr;
  }
  
  .chart-card.full-width {
    grid-column: 1;
  }
}

@media (max-width: 768px) {
  .stats-summary {
    grid-template-columns: 1fr;
  }
  
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}
</style>
