<template>
  <div class="page-container">
    <div class="page-header">
      <h2>出入库 / SN 导入记录</h2>
      <el-button @click="loadAll" :loading="loading">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <!-- 筛选条件 -->
    <div class="card filters-card">
      <el-row :gutter="16">
        <el-col :xs="24" :sm="12" :md="4">
          <el-select v-model="recordTypeFilter" placeholder="记录类型" clearable>
            <el-option label="全部" value="all" />
            <el-option label="出入库记录" value="transaction" />
            <el-option label="SN 导入记录" value="import" />
          </el-select>
        </el-col>
        <el-col :xs="24" :sm="12" :md="4">
          <el-select v-model="filters.transaction_type" placeholder="操作类型" clearable>
            <el-option label="入库" value="stock_in" />
            <el-option label="出库" value="stock_out" />
            <el-option label="调拨" value="transfer" />
            <el-option label="退库" value="return" />
            <el-option label="调整" value="adjustment" />
          </el-select>
        </el-col>
        <el-col :xs="24" :sm="24" :md="8">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            @change="onDateRangeChange"
          />
        </el-col>
        <el-col :xs="24" :sm="24" :md="8">
          <div class="keyword-search">
            <el-input v-model="keyword" class="keyword-input" placeholder="搜索单据/设备/SN" clearable>
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
              <template #append>
                <el-button type="primary" @click="loadAll">查询</el-button>
              </template>
            </el-input>
	            <el-tooltip
	              content="支持：单据号、文件名、仓库、操作人、领取人、设备编码、设备名称、SN"
	              placement="top"
	            >
              <span class="keyword-help" aria-label="搜索提示">?</span>
            </el-tooltip>
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- 记录表 -->
    <div class="card">
      <el-table
        :data="pagedRecords"
        :fit="false"
        style="width: 100%"
        v-loading="loading"
      >
        <el-table-column prop="recordType" :label="tableI18n.typeLabel" :width="isCompactTable ? 92 : 130">
          <template #default="{ row }">
            <el-tag class="en-table-compact-tag" :type="row.recordType === 'import' ? 'info' : 'primary'">
              {{ recordTypeText(row.recordType) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="documentLabel" :label="tableI18n.documentLabel" :min-width="isCompactTable ? 180 : 280" show-overflow-tooltip />

        <el-table-column v-if="!isCompactTable" prop="direction" :label="tableI18n.directionLabel" width="120">
          <template #default="{ row }">
            <el-tag
              class="en-table-compact-tag"
              :type="row.direction === 'in' ? 'success' : (row.direction === 'out' ? 'warning' : 'info')"
              size="small"
            >
              {{ directionText(row) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column v-if="!isCompactTable" prop="warehouseName" :label="tableI18n.warehouseLabel" min-width="200" show-overflow-tooltip />

        <el-table-column v-if="!isCompactTable" :label="tableI18n.quantityLabel" width="140">
          <template #default="{ row }">
            <div v-if="row.recordType === 'import'" class="counts">
              <el-tag size="small">总 {{ row.totalQuantity }}</el-tag>
              <el-tag size="small" type="success">成功 {{ row.importCounts.success }}</el-tag>
              <el-tag size="small" type="warning" v-if="row.importCounts.duplicate > 0">重复 {{ row.importCounts.duplicate }}</el-tag>
              <el-tag size="small" type="danger" v-if="row.importCounts.failed > 0">失败 {{ row.importCounts.failed }}</el-tag>
            </div>
            <span v-else>{{ row.totalQuantity }}</span>
          </template>
	        </el-table-column>

	        <el-table-column v-if="!isCompactTable" prop="operatorName" :label="tableI18n.operatorLabel" width="120" show-overflow-tooltip />
	        <el-table-column v-if="!isCompactTable" prop="receiverName" :label="tableI18n.receiverLabel" width="160" show-overflow-tooltip>
	          <template #default="{ row }">
	            <span v-if="row.recordType === 'transaction' && row.transactionType === 'stock_out'">
	              <span class="cell-ellipsis">{{ row.receiverName || '-' }}</span>
	            </span>
	            <span v-else>-</span>
	          </template>
	        </el-table-column>

	        <el-table-column v-if="!isCompactTable" prop="operationTime" :label="tableI18n.timeLabel" width="180">
	          <template #default="{ row }">
	            {{ formatDateTime(row.operationTime) }}
	          </template>
        </el-table-column>

        <el-table-column prop="notes" :label="tableI18n.notesLabel" min-width="220" v-if="showNotesColumn" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ row.notes || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column :label="tableI18n.actionsLabel" :width="isCompactTable ? 96 : 120" fixed="right">
          <template #default="{ row }">
            <div class="en-op-actions en-op-actions--stack">
              <el-button
                v-if="row.recordType === 'import'"
                size="small"
                type="primary"
                link
                @click="openImportDetails(row)"
              >
                {{ tableI18n.snDetailsLabel }}
              </el-button>
              <el-button
                v-else
                size="small"
                text
                @click="viewTransaction(row)"
              >
                {{ tableI18n.detailsLabel }}
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="filteredRecords.length"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
        />
      </div>
    </div>

    <!-- SN 导入明细抽屉 -->
    <el-drawer v-model="importDetailsVisible" size="70%" :with-header="false">
      <div class="drawer-header">
        <div>
          <h3>SN 导入详情</h3>
          <div class="sub">
            文件：{{ currentImportRecord?.file_name || '-' }} ｜ 时间：{{ formatDateTime(currentImportRecord?.import_date) }}
          </div>
        </div>
        <el-button circle @click="importDetailsVisible = false">
          <el-icon><Close /></el-icon>
        </el-button>
      </div>

      <el-card class="summary-card" v-if="currentImportRecord">
        <div class="summary-grid">
          <div class="summary-item">
            <span class="label">设备类型</span>
            <span class="value">{{ currentImportRecord.equipment_type_name || '-' }}</span>
          </div>
          <div class="summary-item">
            <span class="label">仓库</span>
            <span class="value">{{ currentImportRecord.warehouse_name || '-' }}</span>
          </div>
          <div class="summary-item">
            <span class="label">导入人</span>
            <span class="value">{{ currentImportRecord.importer_name || '-' }}</span>
          </div>
          <div class="summary-item">
            <span class="label">状态</span>
            <span class="value">
              <el-tag :type="importStatusTagType(currentImportRecord.status)">
                {{ importStatusText(currentImportRecord.status) }}
              </el-tag>
            </span>
          </div>
        </div>
      </el-card>

      <el-card class="details-card">
        <template #header>
          <div class="table-header">
            <span>导入 SN 明细</span>
            <div class="table-actions">
              <el-button
                size="small"
                type="danger"
                plain
                :disabled="selectedImportRows.length === 0"
                @click="openBatchVoid"
              >
                批量撤销入库
              </el-button>
              <el-input
                v-model="importDetailKeyword"
                placeholder="按SN/MAC/供应商过滤"
                clearable
                style="width: 260px"
              />
              <el-tag type="info">共 {{ filteredImportDetails.length }} 条</el-tag>
            </div>
          </div>
        </template>

        <el-table
          ref="importDetailsTableRef"
          :data="filteredImportDetails"
          v-loading="importDetailsLoading"
          height="60vh"
          stripe
          @selection-change="onImportSelectionChange"
        >
          <el-table-column
            type="selection"
            width="52"
            :selectable="importDetailSelectable"
          />
          <el-table-column prop="line_number" label="行号" width="80" />
          <el-table-column prop="serial_number" label="SN序列号" width="200" />
          <el-table-column prop="mac_address" label="MAC地址" width="160" />
          <el-table-column prop="imei" label="IMEI" width="160" />
          <el-table-column prop="vendor" label="供应商" width="120" />
          <el-table-column prop="batch_number" label="批次号" width="140" />
          <el-table-column prop="import_status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="importDetailStatusTagType(row.import_status)">
                {{ importDetailStatusText(row.import_status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="error_message"
            label="错误信息"
            min-width="220"
            show-overflow-tooltip
          />
        </el-table>
      </el-card>
    </el-drawer>

    <!-- SN 导入明细：批量撤销 -->
    <el-dialog v-model="batchVoidVisible" title="批量撤销入库" width="520px">
      <el-form label-width="90px">
        <el-form-item label="数量">
          <el-input :model-value="`已选择 ${selectedImportRows.length} 条`" disabled />
        </el-form-item>
        <el-form-item label="原因" required>
          <el-input v-model="batchVoidForm.reason" placeholder="请填写撤销原因" />
        </el-form-item>
        <el-alert
          type="warning"
          :closable="false"
          title="撤销会释放 SN 以便重导，并生成“调整”记录。"
        />
      </el-form>
      <template #footer>
        <el-button @click="batchVoidVisible = false">取消</el-button>
        <el-button type="danger" :loading="batchVoidSubmitting" @click="submitBatchVoid">确认撤销</el-button>
      </template>
    </el-dialog>

    <!-- 出入库记录详情抽屉 -->
    <el-drawer v-model="transactionDetailsVisible" size="60%" :with-header="false">
      <div class="drawer-header">
        <div>
          <h3>出入库记录详情</h3>
          <div class="sub">
            单据：{{ currentTransactionRecord?.document_number || '-' }} ｜ 时间：{{ formatDateTime(currentTransactionRecord?.operation_time) }}
          </div>
        </div>
        <el-button circle @click="transactionDetailsVisible = false">
          <el-icon><Close /></el-icon>
        </el-button>
      </div>

      <el-card class="summary-card" v-if="currentTransactionRecord">
        <div class="summary-grid">
          <div class="summary-item">
            <span class="label">操作类型</span>
            <span class="value">
              <el-tag :type="txTypeColor(currentTransactionRecord.transaction_type)">
                {{ txTypeText(currentTransactionRecord.transaction_type) }}
              </el-tag>
            </span>
          </div>
          <div class="summary-item">
            <span class="label">仓库</span>
            <span class="value">{{ currentTransactionWarehouseName }}</span>
          </div>
          <div class="summary-item">
            <span class="label">操作人</span>
            <span class="value">{{ currentTransactionRecord.operator_name || '-' }}</span>
          </div>
          <div class="summary-item">
            <span class="label">审批状态</span>
            <span class="value">
              <el-tag :type="txApprovalColor(currentTransactionRecord.approval_status)">
                {{ txApprovalText(currentTransactionRecord.approval_status) }}
              </el-tag>
            </span>
          </div>
          <div class="summary-item">
            <span class="label">总数量</span>
            <span class="value">{{ currentTransactionRecord.total_quantity || 0 }}</span>
          </div>
          <div class="summary-item">
            <span class="label">备注</span>
            <span class="value notes-value">
              <span>{{ currentTransactionRecord.notes || '-' }}</span>
              <el-button link type="primary" size="small" @click="openEditTxNotes">编辑</el-button>
            </span>
          </div>
        </div>
      </el-card>

      <el-card class="details-card" v-if="currentTransactionRecord">
        <template #header>
          <div class="table-header">
            <span>出入库明细</span>
          </div>
        </template>

        <el-table :data="currentTransactionRecord.items || []" size="small" stripe>
          <el-table-column prop="equipment_code" label="设备编码" width="120" />
          <el-table-column prop="equipment_name" label="设备名称" width="200" />
          <el-table-column prop="serial_number" label="SN" width="220">
            <template #default="{ row }">
              <el-space>
                <span>{{ row.serial_number || '-' }}</span>
                <el-tag v-if="row.instance_is_voided" size="small" type="info">已撤销</el-tag>
              </el-space>
            </template>
          </el-table-column>
          <el-table-column prop="batch_number" label="批次号" width="140" />
          <el-table-column prop="vendor" label="供应商" width="120" />
          <el-table-column prop="item_notes" label="行备注" min-width="160" show-overflow-tooltip />
          <el-table-column prop="quantity" label="数量" width="80" />
          <el-table-column prop="unit" label="单位" width="80" />
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="{ row }">
              <el-button
                size="small"
                type="primary"
                link
                :disabled="!canEditCurrentTransaction"
                @click="openEditItem(row)"
              >
                编辑信息
              </el-button>
              <el-button
                v-if="!row.equipment_instance_id && row.equipment_category === 'auxiliary'"
                size="small"
                type="warning"
                link
                :disabled="!canEditCurrentTransaction"
                @click="openAdjustQty(row)"
              >
                更正数量
              </el-button>
              <el-button
                v-if="row.equipment_instance_id"
                size="small"
                type="danger"
                link
                :disabled="!canEditCurrentTransaction || row.instance_is_voided"
                @click="openVoidInstance(row)"
              >
                撤销入库
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div
          v-if="currentTransactionRecord.scan_barcode"
          style="margin-top: 16px; padding: 12px; background: #f8fafc; border-radius: 6px;"
        >
          <div><strong>扫码信息:</strong></div>
          <div>扫描条码: {{ currentTransactionRecord.scan_barcode }}</div>
          <div v-if="currentTransactionRecord.package_name">
            关联套装: {{ currentTransactionRecord.package_name }}
          </div>
          <div v-if="currentTransactionRecord.task_id">
            关联任务: {{ currentTransactionRecord.task_id }}
          </div>
        </div>
      </el-card>
    </el-drawer>

    <!-- 编辑单据备注 -->
    <el-dialog v-model="editTxNotesVisible" title="编辑备注" width="520px">
      <el-form label-width="90px">
        <el-form-item label="备注">
          <el-input v-model="editTxNotesForm.notes" type="textarea" :rows="3" placeholder="可为空" />
        </el-form-item>
        <el-form-item label="原因" required>
          <el-input v-model="editTxNotesForm.reason" placeholder="请填写修改原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editTxNotesVisible = false">取消</el-button>
        <el-button type="primary" :loading="editTxNotesSubmitting" @click="submitEditTxNotes">确定</el-button>
      </template>
    </el-dialog>

    <!-- 编辑明细信息 -->
    <el-dialog v-model="editItemVisible" title="编辑明细信息" width="560px">
      <el-form label-width="90px">
        <el-form-item label="设备">
          <el-input :model-value="editItemTitle" disabled />
        </el-form-item>
        <el-form-item label="批次号">
          <el-input v-model="editItemForm.batch_number" placeholder="可为空" />
        </el-form-item>
        <el-form-item label="供应商">
          <el-input v-model="editItemForm.vendor" placeholder="可为空" />
        </el-form-item>
        <el-form-item label="行备注">
          <el-input v-model="editItemForm.item_notes" type="textarea" :rows="3" placeholder="可为空" />
        </el-form-item>
        <el-form-item label="原因" required>
          <el-input v-model="editItemForm.reason" placeholder="请填写修改原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editItemVisible = false">取消</el-button>
        <el-button type="primary" :loading="editItemSubmitting" @click="submitEditItem">确定</el-button>
      </template>
    </el-dialog>

    <!-- 更正数量（辅材） -->
    <el-dialog v-model="adjustQtyVisible" title="更正数量" width="560px">
      <el-form label-width="90px">
        <el-form-item label="设备">
          <el-input :model-value="adjustQtyTitle" disabled />
        </el-form-item>
        <el-form-item label="本次数量" required>
          <el-row :gutter="12" style="width: 100%">
            <el-col :span="8">
              <el-select v-model="adjustQtyForm.mode" style="width: 100%">
                <el-option label="增加" value="increase" />
                <el-option label="减少" value="decrease" />
              </el-select>
            </el-col>
            <el-col :span="16">
              <el-input-number v-model="adjustQtyForm.amount" :min="1" :step="1" style="width: 100%" />
            </el-col>
          </el-row>
        </el-form-item>
        <el-form-item label="原因" required>
          <el-input v-model="adjustQtyForm.reason" placeholder="请填写更正原因" />
        </el-form-item>
        <el-alert
          type="info"
          :closable="false"
          title="说明：更正会生成一条“调整”记录，不修改原入库明细。"
        />
      </el-form>
      <template #footer>
        <el-button @click="adjustQtyVisible = false">取消</el-button>
        <el-button type="primary" :loading="adjustQtySubmitting" @click="submitAdjustQty">确定</el-button>
      </template>
    </el-dialog>

    <!-- 撤销入库（主设备） -->
    <el-dialog v-model="voidVisible" title="撤销入库" width="520px">
      <el-form label-width="90px">
        <el-form-item label="SN">
          <el-input :model-value="voidSn" disabled />
        </el-form-item>
        <el-form-item label="原因" required>
          <el-input v-model="voidForm.reason" placeholder="请填写撤销原因" />
        </el-form-item>
        <el-alert
          type="warning"
          :closable="false"
          title="撤销会释放 SN 以便重导，并生成一条“调整”记录。"
        />
      </el-form>
      <template #footer>
        <el-button @click="voidVisible = false">取消</el-button>
        <el-button type="danger" :loading="voidSubmitting" @click="submitVoid">确认撤销</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search, Close } from '@element-plus/icons-vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { stockApi } from '../../api/stock'

const route = useRoute()
const { locale } = useI18n()
const isEnglish = computed(() => locale.value === 'en-US')
const tableI18n = computed(() => (isEnglish.value
  ? {
      typeLabel: 'Type',
      documentLabel: 'Document / File',
      directionLabel: 'Direction',
      warehouseLabel: 'Warehouse',
      quantityLabel: 'Quantity',
      operatorLabel: 'Operator',
      receiverLabel: 'Receiver',
      timeLabel: 'Operation time',
      notesLabel: 'Notes',
      actionsLabel: 'Actions',
      detailsLabel: 'Details',
      snDetailsLabel: 'SN details',
    }
  : {
      typeLabel: '类型',
      documentLabel: '单据/文件',
      directionLabel: '方向',
      warehouseLabel: '仓库',
      quantityLabel: '数量',
      operatorLabel: '操作人',
      receiverLabel: '领取人',
      timeLabel: '操作时间',
      notesLabel: '备注',
      actionsLabel: '操作',
      detailsLabel: '详情',
      snDetailsLabel: 'SN 明细',
    }))

const loading = ref(false)
const rawTransactions = ref([])
const rawImports = ref([])
const warehouses = ref([])
const warehouseMap = ref({})
const isCompactTable = ref(typeof window !== 'undefined' ? window.innerWidth <= 980 : false)

const recordTypeFilter = ref('all') // all / transaction / import
const keyword = ref('')
const dateRange = ref([])
const filters = ref({
  transaction_type: '',
  start_date: '',
  end_date: '',
  search: ''
})

const syncCompactTable = () => {
  if (typeof window === 'undefined') return
  isCompactTable.value = window.innerWidth <= 980
}

const currentPage = ref(1)
const pageSize = ref(20)

const importDetailsVisible = ref(false)
const currentImportRecord = ref(null)
const importDetailsLoading = ref(false)
const importDetails = ref([])
const importDetailKeyword = ref('')
const importDetailsTableRef = ref(null)
const selectedImportRows = ref([])

const batchVoidVisible = ref(false)
const batchVoidSubmitting = ref(false)
const batchVoidForm = ref({ reason: '' })

const transactionDetailsVisible = ref(false)
const currentTransactionRecord = ref(null)

const showNotesColumn = computed(() => recordTypeFilter.value !== 'import' && !isCompactTable.value)
const canEditCurrentTransaction = computed(() => currentTransactionRecord.value?.transaction_type === 'stock_in')

// ===== 编辑/更正/撤销相关状态 =====
const editTxNotesVisible = ref(false)
const editTxNotesSubmitting = ref(false)
const editTxNotesForm = ref({ notes: '', reason: '' })

const editItemVisible = ref(false)
const editItemSubmitting = ref(false)
const editingItem = ref(null)
const editItemForm = ref({ batch_number: '', vendor: '', item_notes: '', reason: '' })

const adjustQtyVisible = ref(false)
const adjustQtySubmitting = ref(false)
const adjustingItem = ref(null)
const adjustQtyForm = ref({ mode: 'increase', amount: 1, reason: '' })

const voidVisible = ref(false)
const voidSubmitting = ref(false)
const voidingItem = ref(null)
const voidForm = ref({ reason: '' })

const editItemTitle = computed(() => {
  const row = editingItem.value
  if (!row) return '-'
  return `${row.equipment_name || '-'} (${row.equipment_code || '-'})`
})

const adjustQtyTitle = computed(() => {
  const row = adjustingItem.value
  if (!row) return '-'
  return `${row.equipment_name || '-'} (${row.equipment_code || '-'})`
})

const voidSn = computed(() => voidingItem.value?.serial_number || '-')

const currentTransactionWarehouseName = computed(() => {
  const rec = currentTransactionRecord.value
  if (!rec) return '-'
  return warehouseMap.value[rec.warehouse_id] || '-'
})

const recordTypeText = (recordType) => {
  if (!isEnglish.value) return recordType === 'import' ? 'SN导入' : '出入库'
  return recordType === 'import' ? 'SN import' : 'In/Out'
}

const directionText = (row) => {
  if (row.recordType === 'import') return isEnglish.value ? 'Inbound' : '入库'
  const type = row.transactionType
  const map = isEnglish.value
    ? {
        stock_in: 'Inbound',
        stock_out: 'Outbound',
        transfer: 'Transfer',
        return: 'Return',
        adjustment: 'Adjust',
      }
    : {
        stock_in: '入库',
        stock_out: '出库',
        transfer: '调拨',
        return: '退库',
        adjustment: '调整',
      }
  return map[type] || (isEnglish.value ? 'Unknown' : '未知')
}

const importStatusText = (s) =>
  ({ processing: '处理中', completed: '已完成', failed: '失败' }[s] || s || '-')

const importStatusTagType = (s) =>
  ({ processing: 'info', completed: 'success', failed: 'danger' }[s] || 'info')

const importDetailStatusText = (s) =>
  ({ success: '成功', failed: '失败', duplicate: '重复', voided: '已撤销' }[s] || s || '-')

const importDetailStatusTagType = (s) =>
  ({ success: 'success', failed: 'danger', duplicate: 'warning', voided: 'info' }[s] || 'info')

const txTypeText = (type) => {
  const map = {
    stock_in: '入库',
    stock_out: '出库',
    transfer: '调拨',
    return: '退库',
    adjustment: '调整'
  }
  return map[type] || type || '-'
}

const txTypeColor = (type) => {
  const map = {
    stock_in: 'success',
    stock_out: 'warning',
    transfer: 'info',
    return: 'primary',
    adjustment: 'danger'
  }
  return map[type] || 'info'
}

const txApprovalText = (status) => {
  const map = {
    pending: '待审批',
    approved: '已通过',
    rejected: '已驳回'
  }
  return map[status] || status || '-'
}

const txApprovalColor = (status) => {
  const map = {
    pending: 'warning',
    approved: 'success',
    rejected: 'danger'
  }
  return map[status] || 'info'
}

const formatDateTime = (dateString) => {
  if (!dateString) return '-'
  const d = new Date(dateString)
  if (Number.isNaN(d.getTime())) return dateString
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const onDateRangeChange = (dates) => {
  if (dates && dates.length === 2) {
    filters.value.start_date = dates[0]
    filters.value.end_date = dates[1]
  } else {
    filters.value.start_date = ''
    filters.value.end_date = ''
  }
}

const buildRecords = computed(() => {
  const list = []

  rawTransactions.value.forEach((t) => {
    const wname = warehouseMap.value[t.warehouse_id] || ''
    list.push({
      key: `tx-${t.id}`,
      recordType: 'transaction',
      transactionType: t.transaction_type,
      documentLabel: t.document_number || '-',
      direction: t.transaction_type === 'stock_out' ? 'out' : 'in',
	      warehouseName: wname,
	      totalQuantity: t.total_quantity || 0,
	      importCounts: null,
	      operatorName: t.operator_name || '',
	      receiverName: t.receiver_name || '',
	      operationTime: t.operation_time,
	      status: t.approval_status,
	      notes: t.notes || '',
	      raw: t
	    })
  })

  rawImports.value.forEach((r) => {
    list.push({
      key: `imp-${r.id}`,
      recordType: 'import',
      transactionType: 'stock_in',
      documentLabel: r.file_name || '-',
      direction: 'in',
      warehouseName: r.warehouse_name || '',
      totalQuantity: r.total_count || 0,
	      importCounts: {
	        success: r.success_count || 0,
	        duplicate: r.duplicate_count || 0,
	        failed: r.failed_count || 0
	      },
	      operatorName: r.importer_name || '',
	      receiverName: '',
	      operationTime: r.import_date,
	      status: r.status,
	      notes: '',
	      importId: r.id,
	      file_name: r.file_name,
      equipment_type_name: r.equipment_type_name,
      warehouse_name: r.warehouse_name,
      importer_name: r.importer_name,
      import_date: r.import_date
    })
  })

  return list
})

const filteredRecords = computed(() => {
  let data = buildRecords.value

  if (recordTypeFilter.value === 'transaction') {
    data = data.filter((r) => r.recordType === 'transaction')
  } else if (recordTypeFilter.value === 'import') {
    data = data.filter((r) => r.recordType === 'import')
  }

  if (filters.value.transaction_type) {
    data = data.filter(
      (r) =>
        r.recordType !== 'transaction' ||
        r.transactionType === filters.value.transaction_type
    )
  }

  if (keyword.value) {
    const kw = keyword.value.toLowerCase()
    data = data.filter((r) => {
      const txItems = r.recordType === 'transaction' ? r.raw?.items || [] : []
      const hitTxItem = txItems.some((it) => {
        return (
          (it.equipment_code || '').toLowerCase().includes(kw) ||
          (it.equipment_name || '').toLowerCase().includes(kw) ||
          (it.serial_number || '').toLowerCase().includes(kw)
        )
      })
	      return (
	        (r.documentLabel || '').toLowerCase().includes(kw) ||
	        (r.warehouseName || '').toLowerCase().includes(kw) ||
	        (r.operatorName || '').toLowerCase().includes(kw) ||
	        (r.receiverName || '').toLowerCase().includes(kw) ||
	        (r.notes || '').toLowerCase().includes(kw) ||
	        hitTxItem
	      )
	    })
	  }

  // 日期范围过滤：针对 operationTime
  if (filters.value.start_date && filters.value.end_date) {
    const start = new Date(filters.value.start_date)
    const end = new Date(filters.value.end_date)
    data = data.filter((r) => {
      if (!r.operationTime) return false
      const d = new Date(r.operationTime)
      return d >= start && d <= end
    })
  }

  // 按时间降序
  data.sort((a, b) => {
    const da = a.operationTime ? new Date(a.operationTime).getTime() : 0
    const db = b.operationTime ? new Date(b.operationTime).getTime() : 0
    return db - da
  })

  return data
})

const pagedRecords = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredRecords.value.slice(start, end)
})

const filteredImportDetails = computed(() => {
  if (!importDetailKeyword.value) return importDetails.value
  const kw = importDetailKeyword.value.toLowerCase()
  return importDetails.value.filter((d) => {
    return (
      (d.serial_number || '').toLowerCase().includes(kw) ||
      (d.mac_address || '').toLowerCase().includes(kw) ||
      (d.vendor || '').toLowerCase().includes(kw) ||
      (d.batch_number || '').toLowerCase().includes(kw)
    )
  })
})

const importDetailSelectable = (row) => {
  return row.import_status === 'success' && !!row.equipment_instance_id && !row.instance_is_voided
}

const onImportSelectionChange = (rows) => {
  selectedImportRows.value = rows || []
}

const loadTransactions = async () => {
  try {
    const res = await stockApi.getStockTransactions(filters.value)
    rawTransactions.value = res.transactions || []
  } catch (error) {
    console.error('加载出入库记录失败:', error)
    ElMessage.error('加载出入库记录失败')
  }
}

const reloadTransactionsAndKeepDrawer = async () => {
  const keepId = currentTransactionRecord.value?.id
  await loadTransactions()
  if (keepId) {
    const found = rawTransactions.value.find((t) => t.id === keepId)
    if (found) currentTransactionRecord.value = found
  }
}

const loadImportHistory = async () => {
  try {
    const res = await stockApi.getImportHistory()
    rawImports.value = res.records || []
  } catch (error) {
    console.error('加载导入记录失败:', error)
    ElMessage.error('加载导入记录失败')
  }
}

const loadWarehouses = async () => {
  try {
    const res = await stockApi.getWarehouses()
    warehouses.value = res.warehouses || []
    const map = {}
    warehouses.value.forEach((w) => {
      map[w.id] = w.warehouse_name
    })
    warehouseMap.value = map
  } catch (error) {
    console.error('加载仓库列表失败:', error)
  }
}

const loadAll = async () => {
  try {
    loading.value = true
    await Promise.all([loadTransactions(), loadImportHistory(), loadWarehouses()])
  } finally {
    loading.value = false
  }
}

const openImportDetails = async (row) => {
  currentImportRecord.value = row
  importDetailsVisible.value = true
  await loadImportDetails(row.importId)
}

const loadImportDetails = async (importId) => {
  try {
    importDetailsLoading.value = true
    const res = await stockApi.getImportDetails(importId)
    importDetails.value = res.details || []
    selectedImportRows.value = []
    importDetailsTableRef.value?.clearSelection?.()
  } catch (error) {
    console.error('加载导入明细失败:', error)
    ElMessage.error('加载导入明细失败')
  } finally {
    importDetailsLoading.value = false
  }
}

const openBatchVoid = () => {
  if (selectedImportRows.value.length === 0) return
  batchVoidForm.value = { reason: '' }
  batchVoidVisible.value = true
}

const submitBatchVoid = async () => {
  if (selectedImportRows.value.length === 0) return
  if (!batchVoidForm.value.reason?.trim()) {
    ElMessage.warning('请填写撤销原因')
    return
  }
  const instanceIds = selectedImportRows.value
    .map((r) => r.equipment_instance_id)
    .filter(Boolean)

  if (instanceIds.length === 0) {
    ElMessage.warning('所选行缺少实例信息，无法撤销')
    return
  }

  try {
    batchVoidSubmitting.value = true
    const res = await stockApi.voidInstances({
      instance_ids: instanceIds,
      reason: batchVoidForm.value.reason
    })
    const ok = (res?.success_count || 0) > 0
    if (!ok) {
      const firstErr = res?.results?.find((r) => !r.success)?.error
      ElMessage.error(firstErr || '撤销失败')
      return
    }
    const failedCount = res?.failed_count || 0
    if (failedCount > 0) {
      ElMessage.warning(`撤销完成：成功 ${res.success_count} 条，失败 ${failedCount} 条`)
    } else {
      ElMessage.success(`撤销成功：共 ${res.success_count} 条`)
    }
    batchVoidVisible.value = false
    await Promise.all([
      currentImportRecord.value?.importId ? loadImportDetails(currentImportRecord.value.importId) : Promise.resolve(),
      reloadTransactionsAndKeepDrawer(),
    ])
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '撤销失败')
  } finally {
    batchVoidSubmitting.value = false
  }
}

const viewTransaction = (row) => {
  if (!row || row.recordType !== 'transaction') return
  currentTransactionRecord.value = row.raw || null
  if (!currentTransactionRecord.value) {
    ElMessage.warning('未找到该出入库记录的原始数据')
    return
  }
  transactionDetailsVisible.value = true
}

const openEditTxNotes = () => {
  if (!currentTransactionRecord.value) return
  editTxNotesForm.value = {
    notes: currentTransactionRecord.value.notes || '',
    reason: ''
  }
  editTxNotesVisible.value = true
}

const submitEditTxNotes = async () => {
  if (!currentTransactionRecord.value) return
  if (!editTxNotesForm.value.reason?.trim()) {
    ElMessage.warning('请填写修改原因')
    return
  }
  try {
    editTxNotesSubmitting.value = true
    await stockApi.updateTransactionNotes(currentTransactionRecord.value.id, {
      notes: editTxNotesForm.value.notes,
      reason: editTxNotesForm.value.reason
    })
    ElMessage.success('备注已更新')
    editTxNotesVisible.value = false
    currentTransactionRecord.value.notes = editTxNotesForm.value.notes
    await reloadTransactionsAndKeepDrawer()
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '更新失败')
  } finally {
    editTxNotesSubmitting.value = false
  }
}

const openEditItem = (row) => {
  editingItem.value = row
  editItemForm.value = {
    batch_number: row.batch_number || '',
    vendor: row.vendor || '',
    item_notes: row.item_notes || '',
    reason: ''
  }
  editItemVisible.value = true
}

const submitEditItem = async () => {
  const row = editingItem.value
  if (!row) return
  if (!editItemForm.value.reason?.trim()) {
    ElMessage.warning('请填写修改原因')
    return
  }
  try {
    editItemSubmitting.value = true
    await stockApi.updateTransactionItem(row.item_id, {
      batch_number: editItemForm.value.batch_number,
      vendor: editItemForm.value.vendor,
      item_notes: editItemForm.value.item_notes,
      reason: editItemForm.value.reason
    })
    ElMessage.success('明细信息已更新')
    editItemVisible.value = false
    await reloadTransactionsAndKeepDrawer()
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '更新失败')
  } finally {
    editItemSubmitting.value = false
  }
}

const openAdjustQty = (row) => {
  adjustingItem.value = row
  adjustQtyForm.value = { mode: 'increase', amount: 1, reason: '' }
  adjustQtyVisible.value = true
}

const submitAdjustQty = async () => {
  const row = adjustingItem.value
  if (!row) return
  const amount = Number(adjustQtyForm.value.amount)
  if (!Number.isFinite(amount) || amount <= 0) {
    ElMessage.warning('请输入正确的数量')
    return
  }
  if (!adjustQtyForm.value.reason?.trim()) {
    ElMessage.warning('请填写更正原因')
    return
  }
  const delta = adjustQtyForm.value.mode === 'decrease' ? -Math.abs(amount) : Math.abs(amount)
  try {
    adjustQtySubmitting.value = true
    await stockApi.adjustTransactionItem(row.item_id, {
      delta,
      reason: adjustQtyForm.value.reason
    })
    ElMessage.success('数量更正成功（已生成调整记录）')
    adjustQtyVisible.value = false
    await reloadTransactionsAndKeepDrawer()
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '更正失败')
  } finally {
    adjustQtySubmitting.value = false
  }
}

const openVoidInstance = (row) => {
  voidingItem.value = row
  voidForm.value = { reason: '' }
  voidVisible.value = true
}

const submitVoid = async () => {
  const row = voidingItem.value
  if (!row?.equipment_instance_id) return
  if (!voidForm.value.reason?.trim()) {
    ElMessage.warning('请填写撤销原因')
    return
  }
  try {
    voidSubmitting.value = true
    const res = await stockApi.voidInstances({
      instance_ids: [row.equipment_instance_id],
      reason: voidForm.value.reason
    })
    const ok = (res?.success_count || 0) > 0
    if (ok) {
      ElMessage.success('撤销成功')
      voidVisible.value = false
      await reloadTransactionsAndKeepDrawer()
      return
    }
    const firstErr = res?.results?.find((r) => !r.success)?.error
    ElMessage.error(firstErr || '撤销失败')
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '撤销失败')
  } finally {
    voidSubmitting.value = false
  }
}

onMounted(async () => {
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', syncCompactTable, { passive: true })
    syncCompactTable()
  }

  // 如果通过 /import-history 跳转，默认只看 SN 导入记录
  if (route.query.type === 'import') {
    recordTypeFilter.value = 'import'
  }
  if (route.query.type === 'transaction') {
    recordTypeFilter.value = 'transaction'
  }
  if (route.query.keyword) {
    keyword.value = String(route.query.keyword)
  }
  await loadAll()
  // 兼容历史链接：附带 importId 时，自动打开对应导入记录的 SN 明细
  const importId = route.query.importId
  if (importId) {
    const rec = rawImports.value.find((r) => r.id === importId)
    if (rec) {
      await openImportDetails({
        importId: rec.id,
        file_name: rec.file_name,
        equipment_type_name: rec.equipment_type_name,
        warehouse_name: rec.warehouse_name,
        importer_name: rec.importer_name,
        import_date: rec.import_date,
        status: rec.status
      })
    }
  }
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', syncCompactTable)
  }
})
</script>

<style scoped>
.page-container {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.filters-card {
  margin-bottom: 16px;
  padding: 16px;
}

.card {
  margin-bottom: 16px;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.counts {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
  row-gap: 6px;
}

.cell-ellipsis {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
}

.keyword-search {
  display: flex;
  align-items: center;
  gap: 8px;
}

.keyword-input {
  flex: 1;
}

.keyword-help {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 1px solid var(--el-border-color);
  color: var(--el-text-color-regular);
  cursor: pointer;
  user-select: none;
  font-weight: 700;
  line-height: 1;
}

.keyword-help:hover {
  color: var(--el-color-primary);
  border-color: var(--el-color-primary);
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0 16px 0;
}

.drawer-header h3 {
  margin: 0;
  font-size: 18px;
}

.drawer-header .sub {
  color: var(--text-secondary);
  margin-top: 4px;
}

.summary-card {
  margin-bottom: 12px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.summary-item {
  display: flex;
  gap: 8px;
}

.summary-item .label {
  color: var(--text-secondary);
}

.summary-item .value {
  color: var(--text-primary);
  font-weight: 500;
}

.notes-value {
  display: inline-flex;
  gap: 8px;
  align-items: center;
}

.details-card .table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.details-card .table-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

@media (max-width: 980px) {
  .page-container {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .filters-card :deep(.el-row) {
    row-gap: 10px;
  }

  .keyword-search {
    flex-wrap: wrap;
  }

  .keyword-input {
    width: 100%;
  }

  .details-card .table-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .details-card .table-actions {
    width: 100%;
    flex-wrap: wrap;
  }
}
</style>
