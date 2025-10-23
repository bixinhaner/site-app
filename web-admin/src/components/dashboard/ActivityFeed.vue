<template>
  <el-card class="block-card" :body-style="{ padding: '12px' }">
    <template #header>
      <div class="card-header">
        <span class="card-title"><el-icon><Bell /></el-icon> 最近动态</span>
      </div>
    </template>

    <el-row :gutter="16">
      <el-col :md="12" :sm="24">
        <div class="section">
          <div class="section-title">出入库</div>
          <el-empty v-if="!transactions.length" description="暂无记录" :image-size="56" />
          <el-timeline v-else>
            <el-timeline-item v-for="t in transactions" :key="t.id || t.document_number" :timestamp="formatDateTime(t.operation_time)">
              <div class="row">
                <el-tag size="small" :type="t.transaction_type === 'stock_in' ? 'success' : 'info'">{{ t.transaction_type === 'stock_in' ? '入库' : '出库' }}</el-tag>
                <span class="mono">#{{ t.document_number || '-' }}</span>
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-button link size="small" @click="emit('goto', { name: 'StockHistory' })">查看全部</el-button>
        </div>
      </el-col>

      <el-col :md="12" :sm="24">
        <div class="section">
          <div class="section-title">工单</div>
          <el-empty v-if="!workOrders.length" description="暂无记录" :image-size="56" />
          <el-timeline v-else>
            <el-timeline-item v-for="o in workOrders" :key="o.id" :timestamp="formatDateTime(o.created_at || o.assigned_at)">
              <div class="row">
                <span class="title" @click="emit('goto', { name: 'WorkOrderList' })">{{ o.title }}</span>
                <el-tag size="small">{{ o.status }}</el-tag>
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-button link size="small" @click="emit('goto', { name: 'WorkOrderList' })">查看全部</el-button>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="mt-16">
      <el-col :md="12" :sm="24">
        <div class="section">
          <div class="section-title">勘察档案</div>
          <el-empty v-if="!surveys.length" description="暂无记录" :image-size="56" />
          <el-timeline v-else>
            <el-timeline-item v-for="s in surveys" :key="s.id" :timestamp="formatDateTime(s.created_at)">
              <div class="row">
                <span class="title" @click="emit('goto', { name: 'SiteSurveyDetail', params: { id: s.id } })">{{ s.site_name || s.site_code || '-' }}</span>
                <span class="mono">{{ s.surveyor_name || '' }}</span>
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-button link size="small" @click="emit('goto', { name: 'SiteSurveys' })">查看全部</el-button>
        </div>
      </el-col>

      <el-col :md="12" :sm="24">
        <div class="section">
          <div class="section-title">用户日志</div>
          <el-empty v-if="!logs.length" description="暂无记录" :image-size="56" />
          <el-timeline v-else>
            <el-timeline-item v-for="l in logs" :key="l.id" :timestamp="formatDateTime(l.timestamp)">
              <div class="row">
                <span class="mono">{{ l.username || '用户' }}</span>
                <span class="mono">{{ l.action || '-' }}</span>
              </div>
            </el-timeline-item>
          </el-timeline>
        </div>
      </el-col>
    </el-row>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ data: { type: Object, default: null }, loading: { type: Boolean, default: false } })
const emit = defineEmits(['goto'])

const transactions = computed(() => props.data?.stock_transactions || [])
const workOrders = computed(() => props.data?.work_orders || [])
const surveys = computed(() => props.data?.site_surveys || [])
const logs = computed(() => props.data?.logs || [])

const formatDateTime = (v) => v ? new Date(v).toLocaleString() : ''
</script>

<style scoped>
.block-card { border-radius: 12px; border: 1px solid var(--border-color); }
.card-header { display:flex; justify-content: space-between; align-items: center; }
.card-title { font-weight: 600; color: var(--text-primary); }
.section { padding: 4px 8px 12px; }
.section-title { font-weight: 600; color: var(--text-secondary); margin: 4px 0 8px; }
.row { display:flex; align-items:center; gap: 10px; }
.title { color: var(--text-primary); cursor: pointer; }
.title:hover { text-decoration: underline; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color:#909399; font-size: 12px; }
.mt-16 { margin-top: 16px; }
</style>

