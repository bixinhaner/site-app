<template>
  <div class="page">
    <div class="page-header">
      <h1>{{ t('workOrderList.pageTitle') }}</h1>
      <div class="header-actions">
        <el-input
          v-model="searchKeyword"
          :placeholder="t('workOrderList.filters.searchPlaceholder')"
          style="width: 240px"
          clearable
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select v-model="statusFilter" clearable :placeholder="t('workOrderList.filters.statusPlaceholder')" style="width: 140px">
          <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-tooltip
          v-if="statusInFilter.length > 0 && !statusFilter"
          :content="multiStatusFilterText"
          placement="bottom"
        >
          <el-tag closable @close="clearStatusInFilter">{{ t('workOrderList.filters.multiStatusActive') }}</el-tag>
        </el-tooltip>
        <el-select v-model="typeFilter" clearable :placeholder="t('workOrderList.filters.typePlaceholder')" style="width: 180px">
          <el-option v-for="option in filterTypeOptions" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
        <el-popover placement="bottom" :width="280" trigger="click">
          <template #reference>
            <el-button>
              <el-icon><Sort /></el-icon>
              {{ t('workOrderList.sort.button') }}
            </el-button>
          </template>
          <div class="sort-panel">
            <el-form label-width="72px" size="small">
              <el-form-item :label="t('workOrderList.sort.fieldLabel')">
                <el-select v-model="sortBy" style="width: 100%">
                  <el-option v-for="option in sortFieldOptions" :key="option.value" :label="option.label" :value="option.value" />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('workOrderList.sort.directionLabel')">
                <el-radio-group v-model="sortOrder">
                  <el-radio-button label="desc">{{ t('workOrderList.sort.orders.desc') }}</el-radio-button>
                  <el-radio-button label="asc">{{ t('workOrderList.sort.orders.asc') }}</el-radio-button>
                </el-radio-group>
              </el-form-item>
              <el-form-item label=" ">
                <el-button size="small" @click="resetSort">{{ t('workOrderList.sort.reset') }}</el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-popover>
        <el-button @click="load"><el-icon><Refresh /></el-icon>{{ t('workOrderList.actions.refresh') }}</el-button>
        <el-button :loading="exporting" @click="exportCurrentFilters">
          <el-icon><Download /></el-icon>{{ t('workOrderList.actions.export') }}
        </el-button>
        <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>{{ t('workOrderList.actions.create') }}</el-button>
      </div>
    </div>
    
    <!-- 批量操作栏 -->
    <el-card v-if="selectedWorkOrders.length > 0" class="batch-operations">
      <div class="batch-info">
        <span>{{ t('workOrderList.batch.selectedCount', { count: selectedWorkOrders.length }) }}</span>
        <div class="batch-actions">
          <el-button size="small" @click="clearSelection">{{ t('workOrderList.actions.clearSelection') }}</el-button>
          <!-- <el-button size="small" type="primary" @click="showBatchStatusDialog = true">批量修改状态</el-button> -->
          <el-button size="small" type="warning" @click="showBatchAssignDialog = true">{{ t('workOrderList.actions.batchAssign') }}</el-button>
          <el-button size="small" type="info" @click="showBatchPriorityDialog = true">{{ t('workOrderList.actions.batchPriority') }}</el-button>
          <el-button v-if="canVoidPermission" size="small" type="warning" @click="confirmBatchVoid">{{ t('workOrderList.actions.batchVoid') }}</el-button>
          <el-button size="small" type="danger" @click="confirmBatchDelete">{{ t('workOrderList.actions.batchDelete') }}</el-button>
        </div>
      </div>
    </el-card>
    <el-card>
      <div class="table-wheel-area" @wheel.capture="handleTableWheel">
        <el-table 
          :data="items" 
          v-loading="loading" 
          stripe
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="55" />
          <el-table-column prop="title" :label="t('workOrderList.table.title')" min-width="220">
            <template #default="{ row }">
              <div>
                <div class="title-with-duplicate">
                  <span>{{ row.title }}</span>
                  <el-tooltip
                    v-if="row.has_duplicate_photos"
                    :content="t('workOrderList.tooltips.duplicatePhotos')"
                    placement="top"
                  >
                    <el-icon class="duplicate-warning-icon"><WarningFilled /></el-icon>
                  </el-tooltip>
                  <el-tooltip
                    v-if="row.has_similar_photos"
                    :content="t('workOrderList.tooltips.similarPhotos')"
                    placement="top"
                  >
                    <el-icon class="similar-warning-icon"><WarningFilled /></el-icon>
                  </el-tooltip>
                </div>
                <div class="work-order-id">ID: {{ row.id }}</div>
                <div v-if="row.status === 'VOIDED'" class="work-order-void-meta">
                  {{ t('workOrderList.voidMeta.label') }}：{{ row.void_reason || t('workOrderList.voidMeta.noReason') }}
                  <span v-if="row.voided_by_name"> · {{ row.voided_by_name }}</span>
                  <span v-if="row.voided_at"> · {{ formatDateTime(row.voided_at) }}</span>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="type" :label="t('workOrderList.table.type')" width="160">
            <template #default="{ row }">{{ typeText(row.type) }}</template>
          </el-table-column>
          <el-table-column prop="site_name" :label="t('workOrderList.table.site')" width="160">
            <template #default="{ row }">{{ row.site_name || row.site_id }}</template>
          </el-table-column>
          <el-table-column prop="assignee_name" :label="t('workOrderList.table.assignee')" width="140" />
          <el-table-column prop="reviewer_name" :label="t('workOrderList.table.reviewer')" width="140">
            <template #default="{ row }">{{ row.reviewer_name || '' }}</template>
          </el-table-column>
          <el-table-column prop="priority" :label="t('workOrderList.table.priority')" width="100">
            <template #default="{ row }"><el-tag>{{ priorityText(row.priority) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="status" :label="t('workOrderList.table.status')" width="240">
            <template #default="{ row }">
              <div class="status-progress-card">
                <div class="status-progress-head">
                  <el-tag :type="statusTagType(row.status)" size="small">{{ statusText(row.status, row.type) }}</el-tag>
                  <span
                    v-if="row._progress?.text"
                    class="status-progress-value"
                    :class="`is-${row._progress.tone}`"
                  >
                    {{ row._progress.text }}
                  </span>
                </div>
                <div
                  class="status-progress-track"
                  :class="[`is-${row._progress?.tone || 'pending'}`, { 'is-exception': row._progress?.isException }]"
                >
                  <div class="status-progress-rail">
                    <div
                      v-if="!row._progress?.isException"
                      class="status-progress-fill"
                      :style="{ width: row._progress?.fillWidth || '0%' }"
                    />
                  </div>
                  <div class="status-progress-dots">
                    <el-tooltip
                      v-for="dot in row._progress?.dots || []"
                      :key="dot.index"
                      :content="progressDotTooltip(row, dot)"
                      placement="top"
                    >
                      <span
                        class="status-progress-dot"
                        :class="[`is-${dot.state}`, `is-${row._progress?.tone || 'pending'}`]"
                      />
                    </el-tooltip>
                  </div>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="assigned_at" :label="t('workOrderList.table.assignedAt')" width="180">
            <template #default="{ row }">{{ formatDateTime(row.assigned_at) }}</template>
          </el-table-column>
          <el-table-column :label="t('workOrderList.table.actions')" width="420" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openEdit(row)" v-if="canEdit(row)">
                <el-icon><Edit /></el-icon>{{ t('workOrderList.actions.edit') }}
              </el-button>
              <el-button link type="primary" size="small" @click="openReview(row)">
                <el-icon><Stamp /></el-icon>{{ t('workOrderList.actions.review') }}
              </el-button>
              <el-button link type="warning" size="small" @click="confirmVoid(row)" v-if="canVoid(row)">
                {{ t('workOrderList.actions.void') }}
              </el-button>
              <el-button link type="danger" size="small" @click="confirmDelete(row)" v-if="canDelete(row)">
                <el-icon><Delete /></el-icon>{{ t('workOrderList.actions.delete') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :total="total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="load"
            @current-change="load"
          />
        </div>
      </div>
    </el-card>
  </div>

  <el-dialog v-model="createVisible" :title="t('workOrderList.dialogs.createTitle')" width="680px">
    <el-form :model="createForm" label-width="96px" :rules="rules" ref="formRef">
      <el-form-item :label="t('workOrderList.form.site')" prop="site_id">
        <el-select
          v-model="createForm.site_id"
          filterable
          remote
          clearable
          default-first-option
          remote-show-suffix
          :loading="siteOptionsLoading"
          :remote-method="handleSiteRemoteSearch"
          :no-data-text="siteSelectNoDataText"
          :loading-text="t('workOrderList.siteSearch.loading')"
          :placeholder="siteSearchPlaceholder"
          style="width: 100%"
          @visible-change="handleSiteDropdownVisible"
          @change="handleSiteChange"
        >
          <el-option
            v-for="s in siteOptions"
            :key="s.id"
            :label="siteOptionLabel(s)"
            :value="s.id"
            :disabled="isSiteOptionDisabledForCreate(s)"
          />
        </el-select>
        <div class="form-hint">{{ siteSelectHint }}</div>
      </el-form-item>
      <el-form-item :label="t('workOrderList.form.type')" prop="type">
        <el-select v-model="createForm.type" :placeholder="t('workOrderList.form.placeholders.selectType')" style="width: 100%" @change="handleTypeChange">
          <el-option v-for="option in createTypeOptions" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('workOrderList.form.assignee')" prop="assigned_to">
        <el-select v-model="createForm.assigned_to" filterable :placeholder="t('workOrderList.form.placeholders.selectAssignee')" style="width: 100%" @visible-change="v=> v && loadUsers()">
          <el-option v-for="u in userOptions" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('workOrderList.form.title')" prop="title">
        <el-input v-model="createForm.title" :placeholder="t('workOrderList.form.placeholders.enterTitle')" />
      </el-form-item>
      <el-form-item
        :label="t('workOrderList.form.inspectionTemplate')"
        prop="template_id"
        :required="isTemplateRequiredForCreate"
      >
        <el-select
          v-model="createForm.template_id"
          clearable
          filterable
          :loading="templateOptionsLoading"
          :placeholder="templatePlaceholder"
          :no-data-text="templateNoDataText"
          style="width: 100%"
          @visible-change="v => v && loadTemplates()"
        >
          <el-option v-for="tpl in templateOptions" :key="tpl.id" :label="tpl.template_name" :value="tpl.id" />
        </el-select>
        <div v-if="createForm.type === 'cell_expansion'" class="form-hint">
          {{ t('workOrderList.form.cellExpansionTemplateHint') }}
        </div>
      </el-form-item>
      <el-form-item v-if="createForm.type === 'equipment_replacement'" :label="t('workOrderList.form.replacementTargets')" prop="replacement_targets">
        <el-select
          v-model="createForm.replacement_targets"
          multiple
          filterable
          collapse-tags
          collapse-tags-tooltip
          :placeholder="t('workOrderList.form.placeholders.replacementTargets')"
          style="width: 100%"
          :loading="replacementTargetsLoading"
          @visible-change="v => v && loadReplacementTargets()"
        >
          <el-option v-for="opt in replacementTargetOptions" :key="opt.key" :label="replacementTargetLabel(opt)" :value="opt.key" />
        </el-select>
        <div class="form-hint">{{ t('workOrderList.form.replacementTargetHint') }}</div>
      </el-form-item>
      <el-form-item v-if="createForm.type === 'cell_expansion'" :label="t('workOrderList.form.expansionLld')" prop="expansion_target_cells">
        <div class="expansion-lld-card">
          <div class="expansion-lld-main">
            <el-tag :type="expansionPreview ? 'success' : 'info'" effect="plain">
              {{ expansionPreview ? t('workOrderList.form.expansionLldReady') : t('workOrderList.form.expansionLldPending') }}
            </el-tag>
            <div>
              <div class="expansion-lld-title">
                {{ expansionPreview ? expansionFileName : t('workOrderList.form.expansionLldNotPrepared') }}
              </div>
              <div class="form-hint">{{ expansionPreview ? expansionCommittedSummaryTitle : t('workOrderList.form.expansionLldHint') }}</div>
            </div>
          </div>
          <el-button type="primary" plain @click="openExpansionDialog">
            {{ expansionPreview ? t('workOrderList.actions.reprepareExpansionLld') : t('workOrderList.actions.prepareExpansionLld') }}
          </el-button>
        </div>
        <div v-if="expansionPreview" class="expansion-preview">
          <div class="expansion-cell-list">
            <el-tag
              v-for="cell in getExpansionPreviewCells(expansionPreview)"
              :key="`${cell.sector_id || cell.local_cell_id}_${cell.band}_${cell.rat || ''}`"
              type="success"
              effect="plain"
            >
              {{ expansionCellLabel(cell) }}
            </el-tag>
          </div>
        </div>
      </el-form-item>
      <el-form-item :label="t('workOrderList.form.priority')">
        <el-select v-model="createForm.priority" :placeholder="t('workOrderList.form.placeholders.selectPriority')" style="width: 100%">
          <el-option v-for="option in priorityOptions" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('workOrderList.form.dueDate')">
        <el-date-picker v-model="createForm.due_date" type="datetime" style="width: 100%" />
      </el-form-item>
      <el-form-item :label="t('workOrderList.form.description')">
        <el-input v-model="createForm.description" type="textarea" :rows="3" :placeholder="t('workOrderList.form.placeholders.description')" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="createVisible=false">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" :loading="creating" @click="submitCreate">{{ t('workOrderList.actions.create') }}</el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="expansionDialogVisible"
    :title="t('workOrderList.expansionDialog.title')"
    width="760px"
    class="expansion-dialog"
    destroy-on-close
  >
    <div class="expansion-dialog-body">
      <el-steps :active="expansionDialogStep" finish-status="success" simple>
        <el-step :title="t('workOrderList.expansionDialog.steps.download')" />
        <el-step :title="t('workOrderList.expansionDialog.steps.upload')" />
        <el-step :title="t('workOrderList.expansionDialog.steps.preview')" />
        <el-step :title="t('workOrderList.expansionDialog.steps.use')" />
      </el-steps>

      <div class="expansion-dialog-panel">
        <div class="expansion-dialog-actions">
          <el-button :loading="expansionDraftDownloading" @click="downloadExpansionDraft">
            <el-icon><Download /></el-icon>
            {{ t('workOrderList.actions.downloadExpansionDraft') }}
          </el-button>
          <el-upload
            :auto-upload="false"
            :show-file-list="false"
            accept=".xlsx,.xls"
            :on-change="handleExpansionDialogFileChange"
          >
            <el-button type="primary" plain :loading="expansionPreviewLoading">
              <el-icon><Upload /></el-icon>
              {{ t('workOrderList.actions.uploadExpansionLld') }}
            </el-button>
          </el-upload>
        </div>
        <div class="form-hint">{{ t('workOrderList.expansionDialog.bodyHint') }}</div>
      </div>

      <div v-if="expansionDraftPreview" class="expansion-dialog-preview">
        <el-alert
          type="success"
          :closable="false"
          show-icon
          :title="expansionDraftSummaryTitle"
        />
        <div class="expansion-preview-meta">
          <span>{{ expansionDraftFileName }}</span>
          <span>{{ t('workOrderList.expansionDialog.newCells', { count: getExpansionPreviewCells(expansionDraftPreview).length }) }}</span>
        </div>
        <div class="expansion-cell-list">
          <el-tag
            v-for="cell in getExpansionPreviewCells(expansionDraftPreview)"
            :key="`${cell.sector_id || cell.local_cell_id}_${cell.band}_${cell.rat || ''}`"
            type="success"
            effect="plain"
          >
            {{ expansionCellLabel(cell) }}
          </el-tag>
        </div>
      </div>
      <el-empty
        v-else
        class="expansion-dialog-empty"
        :description="t('workOrderList.expansionDialog.empty')"
      />
    </div>
    <template #footer>
      <el-button @click="expansionDialogVisible = false">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" :disabled="!expansionDraftPreview" @click="useExpansionDraft">
        {{ t('workOrderList.actions.useExpansionLld') }}
      </el-button>
    </template>
  </el-dialog>

  <!-- 重复安装工单提示对话框 -->
  <el-dialog v-model="dupVisible" :title="t('workOrderList.dialogs.duplicateTitle')" width="720px">
    <el-alert type="warning" :closable="false" show-icon style="margin-bottom:8px"
      :title="t('workOrderList.dialogs.duplicateAlert')" />
    <div style="margin-bottom:12px; color:#606266;">
      {{ t('workOrderList.dialogs.siteLabel') }}：<b>{{ dupSiteDisplay }}</b>
    </div>
    <el-table :data="dupExisting" size="small" style="width:100%" v-if="dupExisting && dupExisting.length">
      <el-table-column prop="title" :label="t('workOrderList.table.title')" min-width="180" />
      <el-table-column prop="status" :label="t('workOrderList.table.status')" width="120">
        <template #default="{ row }">
          <el-tag>{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="assigner_name" :label="t('workOrderList.table.creator')" width="140" />
      <el-table-column prop="assignee_name" :label="t('workOrderList.table.assignee')" width="140" />
      <el-table-column prop="assigned_at" :label="t('workOrderList.table.assignedAt')" width="180">
        <template #default="{ row }">{{ formatDateTime(row.assigned_at) }}</template>
      </el-table-column>
    </el-table>
    <template #footer>
      <el-button @click="dupVisible=false">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" :loading="creating" @click="confirmDuplicateCreate">{{ t('workOrderList.actions.confirmContinueCreate') }}</el-button>
    </template>
  </el-dialog>

  <!-- 编辑工单对话框 -->
  <el-dialog v-model="editVisible" :title="t('workOrderList.dialogs.editTitle')" width="560px">
    <el-form :model="editForm" label-width="96px" :rules="rules" ref="editFormRef">
      <el-form-item :label="t('workOrderList.form.site')" prop="site_id">
        <el-input :model-value="editSiteDisplay" disabled />
      </el-form-item>
      <el-form-item :label="t('workOrderList.form.type')" prop="type">
        <el-input :model-value="typeText(editForm.type)" disabled />
      </el-form-item>
      <el-form-item :label="t('workOrderList.form.inspectionTemplate')">
        <el-input :model-value="editTemplateDisplay" disabled />
      </el-form-item>
      <el-form-item :label="t('workOrderList.form.assignee')" prop="assigned_to">
        <el-select v-model="editForm.assigned_to" filterable :placeholder="t('workOrderList.form.placeholders.selectAssignee')" style="width: 100%" @visible-change="v=> v && loadUsers()">
          <el-option v-for="u in userOptions" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('workOrderList.form.title')" prop="title">
        <el-input v-model="editForm.title" :placeholder="t('workOrderList.form.placeholders.enterTitle')" />
      </el-form-item>
      <el-form-item :label="t('workOrderList.form.priority')">
        <el-select v-model="editForm.priority" :placeholder="t('workOrderList.form.placeholders.selectPriority')" style="width: 100%">
          <el-option v-for="option in priorityOptions" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('workOrderList.form.dueDate')">
        <el-date-picker v-model="editForm.due_date" type="datetime" style="width: 100%" />
      </el-form-item>
      <el-form-item :label="t('workOrderList.form.description')">
        <el-input v-model="editForm.description" type="textarea" :rows="3" :placeholder="t('workOrderList.form.placeholders.description')" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="editVisible=false">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" :loading="updating" @click="submitUpdate">{{ t('workOrderList.actions.save') }}</el-button>
    </template>
  </el-dialog>

  <!-- 批量修改状态对话框（暂时隐藏） -->
  <!-- <el-dialog v-model="showBatchStatusDialog" title="批量修改状态" width="400px">
    <el-form label-width="80px">
      <el-form-item label="新状态">
        <el-select v-model="batchStatusValue" placeholder="选择状态" style="width: 100%">
          <el-option v-for="s in statuses" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showBatchStatusDialog = false">取消</el-button>
      <el-button type="primary" :loading="batchLoading" @click="executeBatchStatus">确认修改</el-button>
    </template>
  </el-dialog> -->

  <!-- 批量重新分配对话框 -->
  <el-dialog v-model="showBatchAssignDialog" :title="t('workOrderList.dialogs.batchAssignTitle')" width="400px">
    <el-form label-width="80px">
      <el-form-item :label="t('workOrderList.form.assignee')">
        <el-select v-model="batchAssignValue" filterable :placeholder="t('workOrderList.form.placeholders.selectAssignee')" style="width: 100%" @visible-change="v=> v && loadUsers()">
          <el-option v-for="u in userOptions" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showBatchAssignDialog = false">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" :loading="batchLoading" @click="executeBatchAssign">{{ t('workOrderList.actions.confirmAssign') }}</el-button>
    </template>
  </el-dialog>

  <!-- 批量修改优先级对话框 -->
  <el-dialog v-model="showBatchPriorityDialog" :title="t('workOrderList.dialogs.batchPriorityTitle')" width="400px">
    <el-form label-width="80px">
      <el-form-item :label="t('workOrderList.form.priority')">
        <el-select v-model="batchPriorityValue" :placeholder="t('workOrderList.form.placeholders.selectPriority')" style="width: 100%">
          <el-option v-for="option in priorityOptions" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showBatchPriorityDialog = false">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" :loading="batchLoading" @click="executeBatchPriority">{{ t('workOrderList.actions.confirmUpdate') }}</el-button>
    </template>
  </el-dialog>

  <!-- 批量操作错误详情对话框 -->
  <el-dialog v-model="showErrorDialog" :title="t('workOrderList.dialogs.batchResultTitle')" width="600px">
    <el-alert 
      v-if="batchResult.updated_count > 0"
      :title="t('workOrderList.batch.successHandled', { count: batchResult.updated_count })" 
      type="success" 
      :closable="false"
      style="margin-bottom: 16px"
    />
    <el-alert 
      v-if="batchResult.error_count > 0"
      :title="t('workOrderList.batch.failedHandled', { count: batchResult.error_count })" 
      type="error" 
      :closable="false"
      style="margin-bottom: 16px"
    />
    <div v-if="batchResult.errors && batchResult.errors.length > 0" style="margin-top: 16px">
      <div style="font-weight: bold; margin-bottom: 8px; color: #606266;">{{ t('workOrderList.batch.errorDetails') }}：</div>
      <el-scrollbar max-height="300px">
        <ul style="margin: 0; padding-left: 20px; color: #909399; font-size: 14px;">
          <li v-for="(error, index) in batchResult.errors" :key="index" style="margin-bottom: 8px;">
            {{ error }}
          </li>
        </ul>
      </el-scrollbar>
    </div>
    <template #footer>
      <el-button type="primary" @click="showErrorDialog = false">{{ t('workOrderList.actions.confirm') }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import request from '@/utils/request'
import { workOrderAPI } from '../../api/workorder'
import { sitePlanningApi } from '@/api/sitePlanning'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Edit, Delete, Search, Refresh, Plus, Sort, WarningFilled, Download, Upload } from '@element-plus/icons-vue'
import { createDebouncedTracker } from '@/utils/operationTrack'
import { getApiErrorMessage, getApiErrorStatus } from '@/utils/apiError'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const { t, locale } = useI18n()
const loading = ref(false)
const items = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const statusFilter = ref('')
const statusInFilter = ref([])
const typeFilter = ref('')
const searchKeyword = ref('')
const sortBy = ref('created_at')
const sortOrder = ref('desc')
const exporting = ref(false)

const buildSearchParams = ({ includePagination = true, includeLocale = false } = {}) => {
  const params = {}
  if (includePagination) {
    params.skip = (currentPage.value - 1) * pageSize.value
    params.limit = pageSize.value
  }
  if (searchKeyword.value) params.keyword = searchKeyword.value
  if (statusFilter.value) {
    params.status = statusFilter.value
  } else if (statusInFilter.value.length > 0) {
    params.status_in = statusInFilter.value.join(',')
  }
  if (typeFilter.value) params.type = typeFilter.value
  if (sortBy.value) params.sort_by = sortBy.value
  if (sortOrder.value) params.sort_order = sortOrder.value
  if (includeLocale) params.locale = locale.value
  return params
}

const trackSearchDebounced = createDebouncedTracker(800)
const trackSearch = () => {
  const params = buildSearchParams({ includePagination: false })
  trackSearchDebounced({
    module: '工单管理',
    action: '查询',
    object_type: '工单',
    data: params,
  })
}

// 批量操作相关
const selectedWorkOrders = ref([])
const batchLoading = ref(false)
const showBatchStatusDialog = ref(false)
const showBatchAssignDialog = ref(false)
const showBatchPriorityDialog = ref(false)
const batchStatusValue = ref('')
const batchAssignValue = ref('')
const batchPriorityValue = ref('')
const showErrorDialog = ref(false)
const batchResult = ref({ updated_count: 0, error_count: 0, errors: [] })

const STATUS_VALUES = ['PENDING', 'ACTIVE', 'SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'ACTIVATED', 'REJECTED', 'COMPLETED', 'VOIDED']
const statusValueSet = new Set(STATUS_VALUES)
const INSTALLED_SITE_PRESET_STATUSES = ['SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'ACTIVATED', 'COMPLETED']
const VOIDABLE_STATUSES = ['PENDING', 'ACTIVE', 'SUBMITTED', 'UNDER_REVIEW', 'REJECTED']
const canVoidPermission = computed(() => userStore.hasPermission('workorder:void:write'))
const WORK_ORDER_PROGRESS_DOT_COUNT = 5
const WORK_ORDER_PROGRESS_META = {
  PENDING: { percent: 0, text: '0%', tone: 'pending', currentDot: 0 },
  ACTIVE: { percent: 25, text: '25%', tone: 'primary', currentDot: 1 },
  SUBMITTED: { percent: 50, text: '50%', tone: 'warning', currentDot: 2 },
  UNDER_REVIEW: { percent: 70, text: '70%', tone: 'warning', currentDot: 3 },
  APPROVED: { percent: 80, text: '80%', tone: 'success', currentDot: 3 },
  ACTIVATED: { percent: 90, text: '90%', tone: 'success', currentDot: 3 },
  REJECTED: { percent: 70, text: '70%', tone: 'danger', currentDot: 3 },
  COMPLETED: { percent: 100, text: '100%', tone: 'success', currentDot: 4 },
  VOIDED: { percent: 0, text: '', tone: 'muted', currentDot: -1, isException: true },
}
const DEFAULT_PROGRESS_STAGE_KEYS = ['pending', 'active', 'submitted', 'review', 'completed']
const OPENING_PROGRESS_STAGE_KEYS = ['pending', 'active', 'submitted', 'reviewActivation', 'activated']

const parseCsvQuery = (value) => {
  const raw = String(_firstQueryValue(value) || '').trim()
  if (!raw) return []
  return raw.split(',').map(v => v.trim()).filter(Boolean)
}

const normalizeStatusList = (list) => {
  const out = []
  for (const s of list || []) {
    if (statusValueSet.has(s) && !out.includes(s)) out.push(s)
  }
  return out
}
const createTypeValues = ['site_survey', 'opening_inspection', 'equipment_replacement', 'cell_expansion', 'ssv']
const sortFieldOptions = computed(() => [
  { label: t('workOrderList.sort.fields.createdAt'), value: 'created_at' },
  { label: t('workOrderList.sort.fields.updatedAt'), value: 'updated_at' },
  { label: t('workOrderList.sort.fields.assignedAt'), value: 'assigned_at' },
  { label: t('workOrderList.sort.fields.dueDate'), value: 'due_date' },
  { label: t('workOrderList.sort.fields.priority'), value: 'priority' },
  { label: t('workOrderList.sort.fields.status'), value: 'status' },
  { label: t('workOrderList.sort.fields.type'), value: 'type' },
  { label: t('workOrderList.sort.fields.siteCode'), value: 'site_code' },
  { label: t('workOrderList.sort.fields.siteName'), value: 'site_name' },
])
const statusOptions = computed(() => STATUS_VALUES.map((value) => ({ value, label: statusText(value) })))
const createTypeOptions = computed(() => createTypeValues.map((value) => ({ value, label: typeText(value) })))
const filterTypeOptions = computed(() => createTypeValues.map((value) => ({ value, label: typeText(value) })))
const priorityOptions = computed(() => ['low', 'normal', 'high', 'urgent'].map((value) => ({ value, label: priorityText(value) })))
const multiStatusFilterText = computed(() => t('workOrderList.filters.multiStatusTooltip', {
  statuses: statusInFilter.value.map((status) => statusText(status)).join(' / ')
}))

const resetSort = () => {
  sortBy.value = 'created_at'
  sortOrder.value = 'desc'
}

const load = async () => {
  try {
    loading.value = true
    const params = buildSearchParams()
    const response = await workOrderAPI.searchWorkOrders(params)
    const list = Array.isArray(response?.work_orders) ? response.work_orders : []
    items.value = list.map((item) => ({
      ...item,
      _progress: buildWorkOrderProgress(item),
    }))
    total.value = typeof response?.total === 'number' ? response.total : list.length
  } catch (e) {
    console.error(e)
    ElMessage.error(t('workOrderList.messages.loadFailed'))
  } finally {
    loading.value = false
  }
}

const openReview = (row) => {
  router.push({ name: 'WorkOrderReview', query: { id: row.id } })
}

// Create dialog state
const createVisible = ref(false)
const creating = ref(false)
const createForm = ref({
  site_id: null,
  type: '',
  assigned_to: null,
  title: '',
  priority: 'normal',
  due_date: null,
  description: '',
  template_id: null,
  // 设备更换工单：多选设备位（用 key 数组承载，提交时转换为 [{sector_id, band}]）
  replacement_targets: [],
  expansion_target_cells: [],
})
const SITE_SUGGEST_LIMIT = 20
const SITE_SEARCH_LIMIT = 50
const SITE_SEARCH_DEBOUNCE_MS = 300
const CELL_EXPANSION_ALLOWED_SITE_STATUSES = [
  'pending_online',
  'online_pending_activation',
  'operational',
  'maintenance',
]
const CELL_EXPANSION_ALLOWED_SITE_STATUS_SET = new Set(CELL_EXPANSION_ALLOWED_SITE_STATUSES)
const siteOptions = ref([])
const siteOptionsLoading = ref(false)
const siteSearchKeyword = ref('')
const siteSearchTotal = ref(0)
const selectedSiteOption = ref(null)
const userOptions = ref([])
const templateOptions = ref([])
const templateOptionsLoading = ref(false)
const templateLoadFailed = ref(false)
const formRef = ref()

const isCellExpansionCreate = computed(() => createForm.value.type === 'cell_expansion')

// 设备更换：设备位候选项（来自站点规划）
const replacementTargetOptions = ref([])
const replacementTargetsLoading = ref(false)
const lastReplacementTargetsSiteId = ref(null)
const expansionPreview = ref(null)
const expansionFileName = ref('')
const expansionPreviewLoading = ref(false)
const expansionDialogVisible = ref(false)
const expansionDraftPreview = ref(null)
const expansionDraftFileName = ref('')
const expansionDraftDownloading = ref(false)

// 重复安装工单对话框
const dupVisible = ref(false)
const dupExisting = ref([])
const dupPayload = ref(null)
const dupSiteName = ref('')
const dupSiteCode = ref('')
const dupSiteDisplay = computed(() => {
  if (dupSiteName.value && dupSiteCode.value) return `${dupSiteName.value} (${dupSiteCode.value})`
  return dupSiteName.value || dupSiteCode.value || '-'
})

// Edit dialog state
const editVisible = ref(false)
const updating = ref(false)
const editForm = ref({ id: '', site_id: null, type: '', assigned_to: null, title: '', priority: 'normal', due_date: null, description: '' })
const editFormRef = ref()

const validateReplacementTargets = (rule, value, callback) => {
  if (createForm.value.type !== 'equipment_replacement') {
    callback()
    return
  }
  if (Array.isArray(value) && value.length > 0) {
    callback()
    return
  }
  callback(new Error(t('workOrderList.validation.selectReplacementTarget')))
}

const validateExpansionTargetCells = (rule, value, callback) => {
  if (createForm.value.type !== 'cell_expansion') {
    callback()
    return
  }
  if (Array.isArray(value) && value.length > 0 && expansionPreview.value) {
    callback()
    return
  }
  callback(new Error(t('workOrderList.validation.uploadExpansionLld')))
}

const isTemplateRequiredForCreate = computed(() => true)

const templatePlaceholder = computed(() => t('workOrderList.form.placeholders.template'))

const templateNoDataText = computed(() => (
  templateLoadFailed.value
    ? t('workOrderList.form.templateLoadFailed')
    : t('workOrderList.form.noTemplates')
))

const siteSearchPlaceholder = computed(() => (
  isCellExpansionCreate.value
    ? t('workOrderList.siteSearch.cellExpansionInputHint')
    : t('workOrderList.form.placeholders.siteSearch')
))

const getSelectedCreateSite = () => {
  const selectedId = createForm.value.site_id
  if (!selectedId) return null
  if (selectedSiteOption.value?.id === selectedId) return selectedSiteOption.value
  return siteOptions.value.find(s => s.id === selectedId) || null
}

const siteStatusText = (status) => {
  const value = String(status || '').trim()
  if (!value) return '-'
  const translated = t(`workOrderList.siteStatuses.${value}`)
  return translated === `workOrderList.siteStatuses.${value}` ? value : translated
}

const siteOptionLabel = (site) => {
  if (!site) return '-'
  const name = site.site_name || site.site_code || site.id || '-'
  const code = site.site_code || site.id || '-'
  return `${name} (${code})`
}

const isCellExpansionAllowedSite = (site) => {
  const status = String(site?.status || '').trim()
  return CELL_EXPANSION_ALLOWED_SITE_STATUS_SET.has(status)
}

const isSiteOptionDisabledForCreate = (site) => (
  isCellExpansionCreate.value && !isCellExpansionAllowedSite(site)
)

const validateTemplateId = (rule, value, callback) => {
  if (value) {
    callback()
    return
  }
  callback(new Error(t('workOrderList.validation.selectTemplate')))
}

const validateCreateSiteId = (rule, value, callback) => {
  if (!value) {
    callback(new Error(t('workOrderList.validation.selectSite')))
    return
  }
  if (isCellExpansionCreate.value) {
    const site = getSelectedCreateSite()
    if (site && !isCellExpansionAllowedSite(site)) {
      callback(new Error(t('workOrderList.validation.cellExpansionSiteRequired')))
      return
    }
  }
  callback()
}

const rules = computed(() => ({
  site_id: [{ validator: validateCreateSiteId, trigger: 'change' }],
  type: [{ required: true, message: t('workOrderList.validation.selectType'), trigger: 'change' }],
  assigned_to: [{ required: true, message: t('workOrderList.validation.selectAssignee'), trigger: 'change' }],
  title: [{ required: true, message: t('workOrderList.validation.enterTitle'), trigger: 'blur' }],
  template_id: [{ validator: validateTemplateId, trigger: 'change' }],
  replacement_targets: [{ validator: validateReplacementTargets, trigger: 'change' }],
  expansion_target_cells: [{ validator: validateExpansionTargetCells, trigger: 'change' }],
}))

const siteSelectNoDataText = computed(() => {
  if (siteOptionsLoading.value) return t('workOrderList.siteSearch.loading')
  if (isCellExpansionCreate.value) return t('workOrderList.siteSearch.cellExpansionNoMatch')
  return siteSearchKeyword.value.trim() ? t('workOrderList.siteSearch.noMatch') : t('workOrderList.siteSearch.inputHint')
})

const siteSelectHint = computed(() => {
  if (siteOptionsLoading.value) return t('workOrderList.siteSearch.loadingHint')

  const keyword = siteSearchKeyword.value.trim()
  const visibleCount = siteOptions.value.length
  const prefix = isCellExpansionCreate.value ? `${t('workOrderList.siteSearch.cellExpansionScopeHint')} ` : ''

  if (keyword) {
    if (!visibleCount) return prefix + t('workOrderList.siteSearch.noKeywordResults', { keyword })
    if (siteSearchTotal.value > SITE_SEARCH_LIMIT) {
      return prefix + t('workOrderList.siteSearch.totalTruncated', { total: siteSearchTotal.value, visible: visibleCount })
    }
    return prefix + t('workOrderList.siteSearch.foundCount', { count: siteSearchTotal.value || visibleCount })
  }

  if (!visibleCount) return prefix + t('workOrderList.siteSearch.defaultHint')
  if (siteSearchTotal.value > SITE_SUGGEST_LIMIT) {
    return prefix + t('workOrderList.siteSearch.suggestTruncated', { visible: visibleCount })
  }
  return prefix + t('workOrderList.siteSearch.visibleCount', { visible: visibleCount })
})

const dedupeSites = (sites = []) => {
  const list = []
  const seenIds = new Set()
  for (const site of sites) {
    if (!site || site.id == null || seenIds.has(site.id)) continue
    seenIds.add(site.id)
    list.push(site)
  }
  return list
}

const applySiteOptions = (sites = []) => {
  const visibleSites = isCellExpansionCreate.value
    ? sites.filter(isCellExpansionAllowedSite)
    : sites
  const selectedCandidate = selectedSiteOption.value && selectedSiteOption.value.id === createForm.value.site_id
    ? selectedSiteOption.value
    : null
  const selected = selectedCandidate && (!isCellExpansionCreate.value || isCellExpansionAllowedSite(selectedCandidate))
    ? selectedCandidate
    : null
  siteOptions.value = dedupeSites(selected ? [selected, ...visibleSites] : visibleSites)
}

let siteSearchTimer = null
let siteSearchRequestId = 0

const clearSiteSearchTimer = () => {
  if (!siteSearchTimer) return
  clearTimeout(siteSearchTimer)
  siteSearchTimer = null
}

const resetSiteSearchState = () => {
  clearSiteSearchTimer()
  siteSearchRequestId += 1
  siteOptionsLoading.value = false
  siteSearchKeyword.value = ''
  siteSearchTotal.value = 0
  selectedSiteOption.value = null
  siteOptions.value = []
}

const openCreate = () => {
  // reset form
  createForm.value = {
    site_id: null,
    type: '',
    assigned_to: null,
    title: '',
    priority: 'normal',
    due_date: null,
    description: '',
    template_id: null,
    replacement_targets: [],
    expansion_target_cells: [],
  }
  resetSiteSearchState()
  templateOptions.value = []
  templateLoadFailed.value = false
  replacementTargetOptions.value = []
  lastReplacementTargetsSiteId.value = null
  resetExpansionPreview()
  createVisible.value = true
  loadTemplates()
}

const _firstQueryValue = (v) => (Array.isArray(v) ? v[0] : v)

const applyListFiltersFromRoute = () => {
  const q = route.query || {}
  if (String(_firstQueryValue(q.create) || '') === '1') return

  const preset = String(_firstQueryValue(q.preset) || '').trim()
  if (preset === 'installed_sites') {
    currentPage.value = 1
    typeFilter.value = 'opening_inspection'
    statusFilter.value = ''
    statusInFilter.value = [...INSTALLED_SITE_PRESET_STATUSES]
    return
  }

  const hasFilterQuery = ['type', 'status', 'status_in'].some((key) => {
    const val = String(_firstQueryValue(q[key]) || '').trim()
    return !!val
  })
  if (!hasFilterQuery) return

  currentPage.value = 1
  typeFilter.value = String(_firstQueryValue(q.type) || '').trim()

  const statusList = normalizeStatusList(parseCsvQuery(q.status_in))
  if (statusList.length > 0) {
    statusFilter.value = ''
    statusInFilter.value = statusList
    return
  }

  const status = String(_firstQueryValue(q.status) || '').trim()
  if (statusValueSet.has(status)) {
    statusFilter.value = status
    statusInFilter.value = []
    return
  }
  statusFilter.value = ''
  statusInFilter.value = []
}

const clearStatusInFilter = () => {
  statusInFilter.value = []
}

const ensureSiteOption = async (siteId) => {
  if (!siteId) return
  const existing = siteOptions.value.find(s => s.id === siteId)
  if (existing) {
    selectedSiteOption.value = existing
    applySiteOptions(siteOptions.value)
    return existing
  }
  if (selectedSiteOption.value?.id === siteId) {
    applySiteOptions(siteOptions.value)
    return selectedSiteOption.value
  }
  try {
    const s = await request.get(`/api/sites/${siteId}`)
    if (s && s.id != null) {
      selectedSiteOption.value = s
      applySiteOptions(siteOptions.value)
      return s
    }
  } catch (e) {
    // ignore
  }
  return null
}

const openCreateWithPreset = async ({ siteId, type, title } = {}) => {
  openCreate()
  if (siteId) createForm.value.site_id = siteId
  if (type) createForm.value.type = type
  if (title) createForm.value.title = title

  // preload options for better UX
  await Promise.allSettled([loadSites(), loadUsers()])
  if (siteId) await ensureSiteOption(siteId)
  await onTypeOrSiteChange()
}

let applyCreatePrefillBusy = false
const applyCreatePrefillFromRoute = async () => {
  if (applyCreatePrefillBusy) return
  const q = route.query || {}
  if (String(_firstQueryValue(q.create) || '') !== '1') return

  const siteId = Number(_firstQueryValue(q.site_id))
  if (!Number.isFinite(siteId) || siteId <= 0) return

  const type = String(_firstQueryValue(q.type) || 'site_survey')
  const isResurvey = String(_firstQueryValue(q.resurvey) || '') === '1'

  applyCreatePrefillBusy = true
  try {
    // 尝试获取站点信息用于拼标题/展示（即使失败也不阻塞创建）
    let s = null
    try {
      s = await request.get(`/api/sites/${siteId}`)
    } catch (e) {
      s = null
    }
    const siteCode = s?.site_code ? String(s.site_code) : ''
    const baseTitle = type === 'site_survey' ? typeText(type) : t('workOrderList.prefill.genericTitle')
    const prefix = isResurvey ? t('workOrderList.prefill.resurveyPrefix') : ''
    const title = siteCode ? `${prefix}${baseTitle}-${siteCode}` : `${prefix}${baseTitle}`

    await openCreateWithPreset({ siteId, type, title })

    // 清理 query，避免刷新/返回时重复弹窗
    const nextQuery = { ...q }
    delete nextQuery.create
    delete nextQuery.site_id
    delete nextQuery.type
    delete nextQuery.resurvey
    router.replace({ query: nextQuery })
  } finally {
    applyCreatePrefillBusy = false
  }
}

const fetchSiteOptions = async ({ keyword = '' } = {}) => {
  const requestId = ++siteSearchRequestId
  const normalizedKeyword = String(keyword || '').trim()
  siteSearchKeyword.value = normalizedKeyword
  siteOptionsLoading.value = true

  try {
    const params = {
      skip: 0,
      limit: normalizedKeyword ? SITE_SEARCH_LIMIT : SITE_SUGGEST_LIMIT,
      sort_by: normalizedKeyword ? 'site_code' : 'updated_at',
      sort_order: normalizedKeyword ? 'asc' : 'desc',
    }
    if (normalizedKeyword) params.keyword = normalizedKeyword
    if (isCellExpansionCreate.value) {
      params.status_in = CELL_EXPANSION_ALLOWED_SITE_STATUSES.join(',')
    }

    const res = await request.get('/api/sites/search', { params })
    if (requestId !== siteSearchRequestId) return

    const list = Array.isArray(res?.sites) ? res.sites : []
    siteSearchTotal.value = typeof res?.total === 'number' ? res.total : list.length
    applySiteOptions(list)
  } catch (e) {
    if (requestId !== siteSearchRequestId) return
    siteSearchTotal.value = 0
    applySiteOptions([])
  } finally {
    if (requestId === siteSearchRequestId) {
      siteOptionsLoading.value = false
    }
  }
}

const loadSites = async (keyword = '') => {
  await fetchSiteOptions({ keyword })
}

const handleSiteRemoteSearch = (query) => {
  clearSiteSearchTimer()
  siteSearchTimer = setTimeout(() => {
    fetchSiteOptions({ keyword: query })
  }, SITE_SEARCH_DEBOUNCE_MS)
}

const handleSiteDropdownVisible = async (visible) => {
  if (!visible) {
    clearSiteSearchTimer()
    return
  }

  if (createForm.value.site_id) {
    await ensureSiteOption(createForm.value.site_id)
  }
  await loadSites()
}

const ensureSelectedSiteAllowedForCellExpansion = async () => {
  if (!isCellExpansionCreate.value || !createForm.value.site_id) return true
  const site = await ensureSiteOption(createForm.value.site_id)
  if (!site || isCellExpansionAllowedSite(site)) return true

  createForm.value.site_id = null
  selectedSiteOption.value = null
  resetExpansionPreview()
  applySiteOptions(siteOptions.value)
  ElMessage.warning(t('workOrderList.messages.cellExpansionSiteNotAllowed', {
    status: siteStatusText(site.status),
  }))
  formRef.value?.validateField?.('site_id')
  return false
}

const handleTypeChange = async () => {
  resetExpansionPreview()
  await ensureSelectedSiteAllowedForCellExpansion()
  siteSearchTotal.value = 0
  applySiteOptions([])
  await loadSites(siteSearchKeyword.value)
  await onTypeOrSiteChange()
}

const handleSiteChange = async (siteId) => {
  resetExpansionPreview()
  if (siteId) {
    await ensureSiteOption(siteId)
  } else {
    selectedSiteOption.value = null
    applySiteOptions(siteOptions.value)
  }
  await onTypeOrSiteChange()
}

const loadUsers = async () => {
  try {
    const res = await request.get('/api/users/', { params: { limit: 100 } })
    userOptions.value = Array.isArray(res) ? res : []
  } catch (e) {
    // ignore (权限不足时隐藏选项)
  }
}

const loadTemplates = async () => {
  if (templateOptionsLoading.value) return
  templateOptionsLoading.value = true
  templateLoadFailed.value = false
  try {
    const params = { limit: 100 }
    const list = await request.get('/api/inspections/templates', { params })
    templateOptions.value = Array.isArray(list) ? list : []
  } catch (e) {
    templateOptions.value = []
    templateLoadFailed.value = true
    const detail = e?.response?.data?.detail
    const message = (typeof detail === 'string' && detail) || detail?.message || e?.message || t('workOrderList.messages.templateLoadFailedFallback')
    ElMessage.error(t('workOrderList.messages.templateLoadFailed', { message }))
  } finally {
    templateOptionsLoading.value = false
  }
}

const applyTemplateOptionIfMissing = (templateId, templateName) => {
  const id = String(templateId || '').trim()
  if (!id) return
  const exists = templateOptions.value.some(t => t.id === id)
  if (!exists) {
    templateOptions.value.push({
      id,
      template_name: templateName || id,
    })
  }
}

const applyHistoricalOpeningTemplate = async () => {
  if (createForm.value.type !== 'cell_expansion' || !createForm.value.site_id) {
    return false
  }

  try {
    const res = await request.get('/api/inspections/templates/preferred-opening', {
      params: { site_id: createForm.value.site_id },
    })
    if (res?.success && res?.template_id) {
      createForm.value.template_id = res.template_id
      applyTemplateOptionIfMissing(res.template_id, res.template_name)
      formRef.value?.validateField?.('template_id')
      return true
    }
  } catch (e) {
    // 历史模板只是默认值优化，失败时继续走模板绑定推荐。
  }

  return false
}

const _parseReplacementTargetKey = (key) => {
  const raw = String(key || '').trim()
  const parts = raw.split('__')
  if (parts.length !== 2) return null
  const sectorId = String(parts[0] || '').trim()
  const band = String(parts[1] || '').trim()
  if (!sectorId || !band) return null
  return { sector_id: sectorId, band }
}

const resetExpansionPreview = () => {
  expansionPreview.value = null
  expansionFileName.value = ''
  expansionDraftPreview.value = null
  expansionDraftFileName.value = ''
  if (createForm.value) {
    createForm.value.expansion_target_cells = []
  }
}

const openExpansionDialog = () => {
  if (!createForm.value.site_id) {
    ElMessage.warning(t('workOrderList.validation.selectSite'))
    return
  }
  expansionDraftPreview.value = expansionPreview.value
  expansionDraftFileName.value = expansionFileName.value
  expansionDialogVisible.value = true
}

const _extractExpansionPreviewError = (detail) => {
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  const issues = Array.isArray(detail?.issues) ? detail.issues : []
  if (issues.length) {
    return issues
      .slice(0, 3)
      .map((issue) => issue?.message || issue?.code)
      .filter(Boolean)
      .join('；')
  }
  return t('workOrderList.messages.expansionPreviewFailed')
}

const handleExpansionDialogFileChange = async (uploadFile) => {
  const siteId = createForm.value.site_id
  const file = uploadFile?.raw
  if (!siteId) {
    ElMessage.warning(t('workOrderList.validation.selectSite'))
    return
  }
  if (!file) return

  expansionPreviewLoading.value = true
  try {
    const preview = await sitePlanningApi.previewCellExpansion(siteId, file)
    expansionDraftPreview.value = preview
    expansionDraftFileName.value = file.name || uploadFile.name || ''
    ElMessage.success(t('workOrderList.messages.expansionPreviewSuccess'))
  } catch (e) {
    console.error(e)
    expansionDraftPreview.value = null
    expansionDraftFileName.value = ''
    ElMessage.error(_extractExpansionPreviewError(e?.response?.data?.detail))
  } finally {
    expansionPreviewLoading.value = false
  }
}

const downloadExpansionDraft = async () => {
  const siteId = createForm.value.site_id
  if (!siteId) {
    ElMessage.warning(t('workOrderList.validation.selectSite'))
    return
  }
  if (expansionDraftDownloading.value) return

  try {
    expansionDraftDownloading.value = true
    const response = await sitePlanningApi.exportSiteLldCells(siteId)
    const filename = parseFilenameFromDisposition(response?.headers?.['content-disposition']) ||
      `target_lld_draft_${siteId}_${formatExportDate()}.xlsx`
    downloadBlob(response?.data, filename)
    ElMessage.success(t('workOrderList.messages.expansionDraftDownloaded'))
  } catch (e) {
    console.error(e)
    const detail = await extractErrorDetail(e)
    ElMessage.error(detail || t('workOrderList.messages.expansionDraftDownloadFailed'))
  } finally {
    expansionDraftDownloading.value = false
  }
}

const useExpansionDraft = () => {
  if (!expansionDraftPreview.value || !Array.isArray(expansionDraftPreview.value.target_cells)) {
    ElMessage.error(t('workOrderList.messages.expansionTargetRequired'))
    return
  }
  expansionPreview.value = expansionDraftPreview.value
  expansionFileName.value = expansionDraftFileName.value
  createForm.value.expansion_target_cells = expansionDraftPreview.value.target_cells
  formRef.value?.validateField?.('expansion_target_cells')
  expansionDialogVisible.value = false
}

const loadReplacementTargets = async () => {
  const siteId = createForm.value.site_id
  if (!siteId) {
    replacementTargetOptions.value = []
    createForm.value.replacement_targets = []
    lastReplacementTargetsSiteId.value = null
    return
  }
  if (lastReplacementTargetsSiteId.value === siteId && replacementTargetOptions.value.length > 0) return
  replacementTargetsLoading.value = true
  try {
    const planning = await request.get(`/api/sites/${siteId}/planning`)
    const sectors = Array.isArray(planning?.sectors) ? planning.sectors : []
    const globalBands = Array.isArray(planning?.bands) ? planning.bands : []
    const opts = []

    for (const s of sectors) {
      const sectorId = String(s?.sector_index ?? '').trim()
      if (!sectorId) continue
      const bands = Array.isArray(s?.bands) && s.bands.length ? s.bands : globalBands
      for (const b of bands || []) {
        const band = String(b ?? '').trim()
        if (!band) continue
        const key = `${sectorId}__${band}`
        opts.push({ key, sectorId, band })
      }
    }

    replacementTargetOptions.value = opts
    lastReplacementTargetsSiteId.value = siteId

    // 清理不再存在的已选项
    const valid = new Set(opts.map(o => o.key))
    const picked = Array.isArray(createForm.value.replacement_targets) ? createForm.value.replacement_targets : []
    createForm.value.replacement_targets = picked.filter(k => valid.has(k))
  } catch (e) {
    console.error(e)
    replacementTargetOptions.value = []
    lastReplacementTargetsSiteId.value = null
    ElMessage.warning(t('workOrderList.messages.planningNotFound'))
  } finally {
    replacementTargetsLoading.value = false
  }
}

const onTypeOrSiteChange = async () => {
  if (createForm.value.type !== 'cell_expansion') {
    resetExpansionPreview()
  }
  if (isCellExpansionCreate.value && !(await ensureSelectedSiteAllowedForCellExpansion())) {
    return
  }
  if (!createForm.value.site_id) {
    replacementTargetOptions.value = []
    createForm.value.replacement_targets = []
    lastReplacementTargetsSiteId.value = null
  }

  // load candidate templates
  await loadTemplates()
  // try resolve default
  if (!createForm.value.site_id || !createForm.value.type) return

  if (createForm.value.type === 'equipment_replacement') {
    await loadReplacementTargets()
  } else {
    replacementTargetOptions.value = []
    createForm.value.replacement_targets = []
    lastReplacementTargetsSiteId.value = null
  }

  const appliedHistoricalTemplate = await applyHistoricalOpeningTemplate()
  if (appliedHistoricalTemplate) return
}

const submitCreate = () => {
  // 防止重复提交
  if (creating.value) return
  creating.value = true

  formRef.value.validate(async (valid) => {
    if (!valid) {
      creating.value = false
      return
    }
    try {
      // SSV 创建规则支持后台开关切换，统一以后端校验结果为准。
      const payload = { ...createForm.value }
      if (payload.type === 'equipment_replacement') {
        const keys = Array.isArray(payload.replacement_targets) ? payload.replacement_targets : []
        payload.replacement_targets = keys
          .map(_parseReplacementTargetKey)
          .filter(Boolean)
        if (!payload.replacement_targets.length) {
          ElMessage.error(t('workOrderList.messages.replacementTargetRequired'))
          creating.value = false
          return
        }
      } else {
        delete payload.replacement_targets
      }
      if (payload.type === 'cell_expansion') {
        if (!expansionPreview.value || !Array.isArray(expansionPreview.value.target_cells)) {
          ElMessage.error(t('workOrderList.messages.expansionTargetRequired'))
          creating.value = false
          return
        }
        payload.expansion_targets = expansionPreview.value.expansion_targets || expansionPreview.value.new_slots || []
        payload.expansion_target_cells = expansionPreview.value.target_cells
        payload.expansion_summary = {
          current_planning_id: expansionPreview.value.current_planning_id,
          current_planning_version: expansionPreview.value.current_planning_version,
          current_sector_count: expansionPreview.value.current_sector_count,
          target_sector_count: expansionPreview.value.target_sector_count,
          current_physical_sector_count: expansionPreview.value.current_physical_sector_count,
          target_physical_sector_count: expansionPreview.value.target_physical_sector_count,
          current_cell_count: expansionPreview.value.current_cell_count,
          target_cell_count: expansionPreview.value.target_cell_count,
          new_cell_count: expansionPreview.value.new_cell_count,
          new_device_count: expansionPreview.value.new_device_count,
          bands: expansionPreview.value.bands || [],
          current_slots: expansionPreview.value.current_slots || [],
          target_slots: expansionPreview.value.target_slots || [],
          new_slots: expansionPreview.value.new_slots || [],
          new_cells: expansionPreview.value.new_cells || [],
        }
      } else {
        delete payload.expansion_targets
        delete payload.expansion_target_cells
        delete payload.expansion_summary
      }
      if (payload.due_date) payload.due_date = new Date(payload.due_date).toISOString()
      await request.post('/api/work-orders', payload)
      ElMessage.success(t('workOrderList.messages.createSuccess'))
      createVisible.value = false
      await load()
    } catch (e) {
      console.error(e)
      const status = e?.response?.status
      const detail = e?.response?.data?.detail
      if (status === 409 && detail?.code === 'DUPLICATE_OPENING_ORDER' && detail?.require_confirm_duplicate) {
        dupExisting.value = Array.isArray(detail.existing_work_orders) ? detail.existing_work_orders : []
        dupPayload.value = { ...createForm.value, confirm_duplicate: true }
        dupSiteName.value = detail?.site_name || ''
        dupSiteCode.value = detail?.site_code || ''
        dupVisible.value = true
      } else {
        ElMessage.error((typeof detail === 'string' && detail) || detail?.message || t('workOrderList.messages.createFailed'))
      }
    } finally {
      creating.value = false
    }
  })
}

const confirmDuplicateCreate = async () => {
  if (!dupPayload.value) {
    dupVisible.value = false
    return
  }
  // 防止重复提交
  if (creating.value) return

  try {
    creating.value = true
    const payload = { ...dupPayload.value }
    if (payload.due_date) payload.due_date = new Date(payload.due_date).toISOString()
    await request.post('/api/work-orders', payload)
    ElMessage.success(t('workOrderList.messages.createSuccess'))
    dupVisible.value = false
    createVisible.value = false
    await load()
  } catch (e) {
    console.error(e)
    const detail = e?.response?.data?.detail
    ElMessage.error((typeof detail === 'string' && detail) || detail?.message || t('workOrderList.messages.createFailed'))
  } finally {
    creating.value = false
  }
}

// 权限检查函数
const canEdit = (row) => {
  // 只能编辑待分配和已分配状态的工单
  return ['PENDING', 'ACTIVE'].includes(row.status)
}

const canDelete = (row) => {
  // 只能删除待分配和已分配状态的工单
  return ['PENDING', 'ACTIVE'].includes(row.status)
}

const canVoid = (row) => {
  return canVoidPermission.value && VOIDABLE_STATUSES.includes(row.status)
}

// 编辑功能
const editSiteName = ref('')
const editSiteCode = ref('')
const editTemplateId = ref('')
const editTemplateName = ref('')
const editTemplateLoading = ref(false)
const editSiteDisplay = computed(() => {
  if (editSiteName.value && editSiteCode.value) return `${editSiteName.value} (${editSiteCode.value})`
  return editSiteName.value || editSiteCode.value || (editForm.value?.site_id ?? '-')
})
const editTemplateDisplay = computed(() => {
  if (editTemplateLoading.value) return t('workOrderList.form.loading')
  return editTemplateName.value || '-'
})

const loadEditTemplate = async (row) => {
  editTemplateId.value = ''
  editTemplateName.value = ''
  editTemplateLoading.value = true
  try {
    let templateId = row?.extra_data?.template_id
    let inspectionId = row?.inspection_id
    if (!templateId && !inspectionId && row?.id) {
      const wo = await request.get(`/api/work-orders/${row.id}`)
      templateId = wo?.extra_data?.template_id
      inspectionId = wo?.inspection_id
    }
    if (!templateId && inspectionId) {
      const insp = await request.get(`/api/inspections/detail/${inspectionId}`)
      templateId = insp?.template_id
    }
    if (!templateId) {
      editTemplateName.value = '-'
      return
    }
    editTemplateId.value = templateId
    const tpl = await request.get(`/api/inspections/templates/${templateId}`)
    editTemplateName.value = tpl?.template_name || templateId
  } catch (e) {
    console.error(e)
    editTemplateName.value = t('workOrderList.form.loadFailed')
  } finally {
    editTemplateLoading.value = false
  }
}

const openEdit = (row) => {
  editSiteName.value = row?.site_name || ''
  editSiteCode.value = row?.site_code || ''
  editForm.value = {
    id: row.id,
    site_id: row.site_id,
    type: row.type,
    assigned_to: row.assigned_to,
    title: row.title,
    priority: row.priority,
    due_date: row.due_date ? new Date(row.due_date) : null,
    description: row.description || '',
  }
  editVisible.value = true
  loadEditTemplate(row)
}

const submitUpdate = () => {
  editFormRef.value.validate(async (valid) => {
    if (!valid) return
    try {
      updating.value = true
      const payload = { ...editForm.value }
      delete payload.id // 移除id字段
      // 后端更新接口不支持修改站点/类型（编辑弹窗仅展示且置灰）
      delete payload.site_id
      delete payload.type
      if (payload.due_date) payload.due_date = new Date(payload.due_date).toISOString()
      await request.put(`/api/work-orders/${editForm.value.id}`, payload)
      ElMessage.success(t('workOrderList.messages.updateSuccess'))
      editVisible.value = false
      await load()
    } catch (e) {
      console.error(e)
      ElMessage.error(e?.response?.data?.detail || t('workOrderList.messages.updateFailed'))
    } finally {
      updating.value = false
    }
  })
}

// 删除功能
const confirmDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      t('workOrderList.prompts.deleteSingleMessage', { title: row.title }),
      t('workOrderList.prompts.deleteSingleTitle'),
      {
        confirmButtonText: t('workOrderList.actions.delete'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    )
    await deleteWorkOrder(row.id)
  } catch (e) {
    // 用户取消删除
  }
}

const deleteWorkOrder = async (id) => {
  try {
    await request.delete(`/api/work-orders/${id}`)
    ElMessage.success(t('workOrderList.messages.deleteSuccess'))
    await load()
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || t('workOrderList.messages.deleteFailed'))
  }
}

const promptVoidReason = async (title, message) => {
  const result = await ElMessageBox.prompt(
    `${message}\n\n${t('workOrderList.prompts.voidReasonNote')}`,
    title,
    {
      confirmButtonText: t('workOrderList.actions.voidConfirm'),
      cancelButtonText: t('common.cancel'),
      type: 'warning',
      inputType: 'textarea',
      inputPlaceholder: t('workOrderList.validation.voidReasonPlaceholder'),
      closeOnClickModal: false,
      inputValidator: (value) => {
        const text = String(value || '').trim()
        if (text.length < 5) return t('workOrderList.validation.voidReasonMin')
        if (text.length > 200) return t('workOrderList.validation.voidReasonMax')
        return true
      },
    }
  )
  return String(result.value || '').trim()
}

const confirmVoid = async (row) => {
  try {
    const reason = await promptVoidReason(
      t('workOrderList.prompts.voidSingleTitle'),
      t('workOrderList.prompts.voidSingleMessage', { title: row.title })
    )
    await voidWorkOrder(row.id, reason)
  } catch (e) {
    // 用户取消作废
  }
}

const voidWorkOrder = async (id, reason) => {
  try {
    await workOrderAPI.voidWorkOrder(id, reason)
    ElMessage.success(t('workOrderList.messages.voidSuccess'))
    await load()
  } catch (e) {
    console.error(e)
    const isConflict = getApiErrorStatus(e) === 409
    const message = getApiErrorMessage(
      e,
      t(
        isConflict
          ? 'workOrderList.messages.voidBlockedFallback'
          : 'workOrderList.messages.voidFailed'
      )
    )
    if (isConflict) {
      await ElMessageBox.alert(message, t('workOrderList.messages.voidBlockedTitle'), {
        type: 'warning',
        confirmButtonText: t('workOrderList.actions.confirm'),
        closeOnClickModal: false,
      }).catch(() => {})
      return
    }
    ElMessage.error(message)
  }
}

const buildProgressDots = (status, currentDot, isException) => {
  return Array.from({ length: WORK_ORDER_PROGRESS_DOT_COUNT }, (_, index) => {
    let state = 'pending'

    if (isException) {
      state = 'muted'
    } else if (status === 'COMPLETED') {
      state = index <= currentDot ? 'done' : 'pending'
    } else if (status === 'REJECTED') {
      if (index < currentDot) state = 'done'
      else if (index === currentDot) state = 'rejected'
    } else {
      if (index < currentDot) state = 'done'
      else if (index === currentDot) state = 'current'
    }

    return { index, state }
  })
}

const buildWorkOrderProgress = (row) => {
  const meta = WORK_ORDER_PROGRESS_META[row?.status] || WORK_ORDER_PROGRESS_META.PENDING
  return {
    ...meta,
    fillWidth: `${meta.percent}%`,
    dots: buildProgressDots(row?.status, meta.currentDot, meta.isException === true),
  }
}

const progressStageKeys = (type) => (
  ['opening_inspection', 'equipment_replacement', 'cell_expansion'].includes(type)
    ? OPENING_PROGRESS_STAGE_KEYS
    : DEFAULT_PROGRESS_STAGE_KEYS
)

const progressStageKey = (type, index) => progressStageKeys(type)[index] || DEFAULT_PROGRESS_STAGE_KEYS[index] || 'completed'
const progressStageTitle = (type, index) => t(`workOrderList.progress.stages.${progressStageKey(type, index)}.title`)
const progressStageDescription = (type, index) => t(`workOrderList.progress.stages.${progressStageKey(type, index)}.desc`)

const progressDotStateLabel = (state) => {
  if (state === 'done') return t('workOrderList.progress.stateLabels.done')
  if (state === 'current') return t('workOrderList.progress.stateLabels.current')
  if (state === 'rejected') return t('workOrderList.progress.stateLabels.rejected')
  if (state === 'muted') return t('workOrderList.progress.stateLabels.muted')
  return t('workOrderList.progress.stateLabels.pending')
}

const progressDotTooltip = (row, dot) => {
  const title = progressStageTitle(row?.type, dot.index)
  const desc = progressStageDescription(row?.type, dot.index)
  return `${progressDotStateLabel(dot.state)} · ${title}：${desc}`
}

const statusText = (status, type) => {
  if (['opening_inspection', 'equipment_replacement', 'cell_expansion'].includes(type)) {
    if (status === 'APPROVED') return t('workOrderList.statusOverrides.APPROVED')
    if (status === 'ACTIVATED') return t('workOrderList.statusOverrides.ACTIVATED')
    if (status === 'COMPLETED') return t('workOrderList.statusOverrides.COMPLETED')
  }
  const translated = t(`workOrderList.statuses.${status}`)
  return translated === `workOrderList.statuses.${status}` ? status : translated
}
const statusTagType = (status) => {
  if (status === 'VOIDED') return 'info'
  if (status === 'REJECTED') return 'danger'
  if (['SUBMITTED', 'UNDER_REVIEW'].includes(status)) return 'warning'
  if (['APPROVED', 'ACTIVATED', 'COMPLETED'].includes(status)) return 'success'
  if (status === 'ACTIVE') return 'primary'
  return ''
}
const typeText = (v) => {
  const translated = t(`workOrderList.types.${v}`)
  return translated === `workOrderList.types.${v}` ? v : translated
}
const priorityText = (v) => {
  const translated = t(`workOrderList.priorities.${v}`)
  return translated === `workOrderList.priorities.${v}` ? v : translated
}
const replacementTargetLabel = (opt) => t('workOrderList.form.replacementTargetOption', {
  sectorId: opt?.sectorId ?? '-',
  band: opt?.band ?? '-',
})

const getExpansionPreviewCells = (preview) => {
  if (Array.isArray(preview?.new_cells) && preview.new_cells.length) return preview.new_cells
  if (Array.isArray(preview?.expansion_targets) && preview.expansion_targets.length) return preview.expansion_targets
  return Array.isArray(preview?.new_slots) ? preview.new_slots : []
}

const expansionCellLabel = (cell) => t('workOrderList.form.expansionCellLabel', {
  physicalSector: cell?.physical_sector_id || cell?.physicalSectorId || cell?.sector_id || '-',
  localCellId: cell?.local_cell_id || cell?.localCellId || cell?.sector_id || '-',
  band: cell?.band || cell?.band_code || '-',
})

const buildExpansionSummaryTitle = (preview) => {
  if (!preview) return ''
  return t('workOrderList.form.expansionPreviewTitle', {
    currentSectors: preview.current_physical_sector_count ?? preview.current_sector_count ?? '-',
    currentCells: preview.current_cell_count ?? '-',
    targetSectors: preview.target_physical_sector_count ?? preview.target_sector_count ?? '-',
    targetCells: preview.target_cell_count ?? '-',
    newCells: preview.new_cell_count ?? getExpansionPreviewCells(preview).length,
    newDevices: preview.new_device_count ?? getExpansionPreviewCells(preview).length,
  })
}

const expansionCommittedSummaryTitle = computed(() => buildExpansionSummaryTitle(expansionPreview.value))
const expansionDraftSummaryTitle = computed(() => buildExpansionSummaryTitle(expansionDraftPreview.value))
const expansionDialogStep = computed(() => (expansionDraftPreview.value ? 3 : 0))
const formatDateTime = (val) => (val ? new Date(val).toLocaleString() : '-')

const formatExportDate = () => {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}`
}

const downloadBlob = (blob, filename) => {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

const parseFilenameFromDisposition = (disposition) => {
  const raw = String(disposition || '')
  if (!raw) return ''
  const utf8Match = raw.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch {
      return utf8Match[1]
    }
  }
  const fallbackMatch = raw.match(/filename="?([^";]+)"?/i)
  return fallbackMatch?.[1] || ''
}

const buildFallbackExportFilename = () => {
  if (locale.value === 'en-US') return `Work_Orders_${formatExportDate()}.xlsx`
  if (locale.value === 'id-ID') return `Daftar_Perintah_Kerja_${formatExportDate()}.xlsx`
  return `工单列表_${formatExportDate()}.xlsx`
}

const extractErrorDetail = async (error) => {
  const data = error?.response?.data
  if (!data) return error?.message || t('workOrderList.messages.exportFailed')
  if (data instanceof Blob) {
    try {
      const text = await data.text()
      try {
        const parsed = JSON.parse(text)
        if (typeof parsed?.detail === 'string') return parsed.detail
        return text || error?.message || t('workOrderList.messages.exportFailed')
      } catch {
        return text || error?.message || t('workOrderList.messages.exportFailed')
      }
    } catch {
      return error?.message || t('workOrderList.messages.exportFailed')
    }
  }
  if (typeof data?.detail === 'string') return data.detail
  return error?.message || t('workOrderList.messages.exportFailed')
}

const exportCurrentFilters = async () => {
  if (exporting.value) return
  if (!Number(total.value || 0)) {
    ElMessage.warning(t('workOrderList.messages.exportEmpty'))
    return
  }

  try {
    exporting.value = true
    const response = await workOrderAPI.exportWorkOrders(
      buildSearchParams({ includePagination: false, includeLocale: true }),
    )
    const filename = parseFilenameFromDisposition(response?.headers?.['content-disposition']) || buildFallbackExportFilename()
    downloadBlob(response?.data, filename)
    ElMessage.success(t('workOrderList.messages.exportSuccess'))
  } catch (error) {
    console.error(error)
    const detail = await extractErrorDetail(error)
    ElMessage.error(t('workOrderList.messages.exportFailedWithReason', { message: detail }))
  } finally {
    exporting.value = false
  }
}

const isScrollableY = (el) => {
  if (!el || !(el instanceof HTMLElement)) return false
  const style = window.getComputedStyle(el)
  const overflowY = style.overflowY
  if (overflowY !== 'auto' && overflowY !== 'scroll') return false
  return el.scrollHeight > el.clientHeight + 1
}

const findScrollableWithin = (startEl, stopEl) => {
  let el = startEl instanceof Element ? startEl : null
  while (el && el !== stopEl && el !== document.body) {
    if (isScrollableY(el)) return el
    el = el.parentElement
  }
  return null
}

const handleTableWheel = (e) => {
  if (e.ctrlKey) return
  const absX = Math.abs(e.deltaX || 0)
  const absY = Math.abs(e.deltaY || 0)
  if (absY <= absX) return

  const currentTarget = e.currentTarget
  if (!currentTarget || !(currentTarget instanceof HTMLElement)) return

  const internalScrollable = findScrollableWithin(e.target, currentTarget)
  if (internalScrollable) return

  const scrollEl = currentTarget.closest('.layout-main')
  if (!scrollEl) return

  const maxTop = scrollEl.scrollHeight - scrollEl.clientHeight
  if (maxTop <= 0) return

  const prev = scrollEl.scrollTop
  const next = Math.max(0, Math.min(maxTop, prev + e.deltaY))
  if (next === prev) return

  scrollEl.scrollTop = next
  e.preventDefault()
}

// 批量操作相关函数
const handleSelectionChange = (selection) => {
  selectedWorkOrders.value = selection
}

const clearSelection = () => {
  selectedWorkOrders.value = []
}

const confirmBatchVoid = async () => {
  try {
    const reason = await promptVoidReason(
      t('workOrderList.prompts.voidBatchTitle'),
      t('workOrderList.prompts.voidBatchMessage', { count: selectedWorkOrders.value.length })
    )
    await executeBatchVoid(reason)
  } catch (e) {
    // 用户取消作废
  }
}

const confirmBatchDelete = async () => {
  try {
    await ElMessageBox.confirm(
      `${t('workOrderList.prompts.deleteBatchMessage', { count: selectedWorkOrders.value.length })}\n\n${t('workOrderList.prompts.deleteBatchNote')}`,
      t('workOrderList.prompts.deleteBatchTitle'),
      {
        confirmButtonText: t('workOrderList.actions.delete'),
        cancelButtonText: t('common.cancel'),
        type: 'warning'
      }
    )
    await executeBatchDelete()
  } catch (e) {
    // 用户取消删除
  }
}

const executeBatchDelete = async () => {
  try {
    batchLoading.value = true
    const workOrderIds = selectedWorkOrders.value.map(wo => wo.id)
    const result = await workOrderAPI.batchOperation(workOrderIds, 'delete')
    
    // 保存结果用于详情对话框
    batchResult.value = result
    
    if (result.error_count > 0) {
      // 有失败的工单，显示详情对话框
      showErrorDialog.value = true
    } else {
      // 全部成功
      ElMessage.success(t('workOrderList.messages.batchDeleteSuccess', { count: result.updated_count }))
    }
    
    clearSelection()
    await load()
  } catch (e) {
    console.error(e)
    ElMessage.error(`${t('workOrderList.messages.batchDeleteFailed')}: ${e.message}`)
  } finally {
    batchLoading.value = false
  }
}

const executeBatchVoid = async (reason) => {
  try {
    batchLoading.value = true
    const workOrderIds = selectedWorkOrders.value.map(wo => wo.id)
    const result = await workOrderAPI.batchOperation(workOrderIds, 'void', null, reason)

    batchResult.value = result

    if (result.error_count > 0) {
      showErrorDialog.value = true
    } else {
      ElMessage.success(t('workOrderList.messages.batchVoidSuccess', { count: result.updated_count }))
    }

    clearSelection()
    await load()
  } catch (e) {
    console.error(e)
    ElMessage.error(`${t('workOrderList.messages.batchVoidFailed')}: ${e?.message || e}`)
  } finally {
    batchLoading.value = false
  }
}

const executeBatchStatus = async () => {
  if (!batchStatusValue.value) {
    ElMessage.warning(t('workOrderList.validation.selectNewStatus'))
    return
  }
  
  try {
    batchLoading.value = true
    const workOrderIds = selectedWorkOrders.value.map(wo => wo.id)
    const result = await workOrderAPI.batchOperation(workOrderIds, 'change_status', batchStatusValue.value)
    
    // 保存结果用于详情对话框
    batchResult.value = result
    
    if (result.error_count > 0) {
      // 有失败的工单，显示详情对话框
      showErrorDialog.value = true
    } else {
      // 全部成功
      ElMessage.success(t('workOrderList.messages.batchStatusSuccess', { count: result.updated_count }))
    }
    
    showBatchStatusDialog.value = false
    batchStatusValue.value = ''
    clearSelection()
    await load()
  } catch (e) {
    console.error(e)
    ElMessage.error(`${t('workOrderList.messages.batchStatusFailed')}: ${e.message}`)
  } finally {
    batchLoading.value = false
  }
}

const executeBatchAssign = async () => {
  if (!batchAssignValue.value) {
    ElMessage.warning(t('workOrderList.validation.selectAssigneeForBatch'))
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `${t('workOrderList.prompts.assignBatchMessage', { count: selectedWorkOrders.value.length })}\n\n${t('workOrderList.prompts.assignBatchNote')}`,
      t('workOrderList.prompts.assignBatchTitle'),
      {
        confirmButtonText: t('workOrderList.actions.confirm'),
        cancelButtonText: t('common.cancel'),
        type: 'warning'
      }
    )
    
    batchLoading.value = true
    const workOrderIds = selectedWorkOrders.value.map(wo => wo.id)
    const result = await workOrderAPI.batchOperation(workOrderIds, 'change_assignee', batchAssignValue.value.toString())
    
    // 保存结果用于详情对话框
    batchResult.value = result
    
    if (result.error_count > 0) {
      // 有失败的工单，显示详情对话框
      showErrorDialog.value = true
    } else {
      // 全部成功
      ElMessage.success(t('workOrderList.messages.batchAssignSuccess', { count: result.updated_count }))
    }
    
    showBatchAssignDialog.value = false
    batchAssignValue.value = ''
    clearSelection()
    await load()
  } catch (e) {
    if (e !== 'cancel') {
      console.error(e)
      ElMessage.error(`${t('workOrderList.messages.batchAssignFailed')}: ${e.message || e}`)
    }
  } finally {
    batchLoading.value = false
  }
}

const executeBatchPriority = async () => {
  if (!batchPriorityValue.value) {
    ElMessage.warning(t('workOrderList.validation.selectPriorityForBatch'))
    return
  }
  
  try {
    batchLoading.value = true
    const workOrderIds = selectedWorkOrders.value.map(wo => wo.id)
    const result = await workOrderAPI.batchOperation(workOrderIds, 'change_priority', batchPriorityValue.value)
    
    // 保存结果用于详情对话框
    batchResult.value = result
    
    if (result.error_count > 0) {
      // 有失败的工单，显示详情对话框
      showErrorDialog.value = true
    } else {
      // 全部成功
      ElMessage.success(t('workOrderList.messages.batchPrioritySuccess', { count: result.updated_count }))
    }
    
    showBatchPriorityDialog.value = false
    batchPriorityValue.value = ''
    clearSelection()
    await load()
  } catch (e) {
    console.error(e)
    ElMessage.error(`${t('workOrderList.messages.batchPriorityFailed')}: ${e.message}`)
  } finally {
    batchLoading.value = false
  }
}

onMounted(async () => {
  await load()
})

watch(() => route.query, () => {
  applyListFiltersFromRoute()
  applyCreatePrefillFromRoute()
}, { immediate: true })

watch(statusFilter, (val) => {
  if (val && statusInFilter.value.length) {
    statusInFilter.value = []
  }
})

watch(createVisible, (visible) => {
  if (visible) return
  clearSiteSearchTimer()
  siteSearchRequestId += 1
  siteOptionsLoading.value = false
})

// 动态筛选/排序：变化时回到第 1 页并刷新
watch([searchKeyword, statusFilter, typeFilter, statusInFilter], () => {
  currentPage.value = 1
  trackSearch()
  load()
})

watch([sortBy, sortOrder], () => {
  currentPage.value = 1
  trackSearch()
  load()
})

onBeforeUnmount(() => {
  clearSiteSearchTimer()
})
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; gap: 8px; align-items:center; }
.table-wheel-area { width: 100%; }
.pagination { margin-top: 12px; display:flex; justify-content: flex-end; }
.sort-panel :deep(.el-radio-group) { width: 100%; }
.sort-panel :deep(.el-radio-button) { width: 50%; }
.sort-panel :deep(.el-radio-button__inner) { width: 100%; text-align: center; }
.work-order-id { 
  font-size: 12px; 
  color: #909399; 
  margin-top: 4px; 
  font-family: 'Courier New', monospace;
}

.work-order-void-meta {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.4;
  color: #909399;
}

.title-with-duplicate {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.duplicate-warning-icon {
  color: #e6a23c;
  font-size: 15px;
}

.similar-warning-icon {
  color: #f56c6c;
  font-size: 15px;
}

.status-progress-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.status-progress-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.status-progress-value {
  flex-shrink: 0;
  min-width: 38px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  text-align: right;
  color: #909399;
}

.status-progress-value.is-primary { color: #409eff; }
.status-progress-value.is-warning { color: #e6a23c; }
.status-progress-value.is-success { color: #67c23a; }
.status-progress-value.is-danger { color: #f56c6c; }
.status-progress-value.is-muted { color: #c0c4cc; }

.status-progress-track {
  position: relative;
  height: 14px;
}

.status-progress-rail {
  position: absolute;
  top: 50%;
  left: 4px;
  right: 4px;
  height: 4px;
  transform: translateY(-50%);
  border-radius: 999px;
  background: #ebeef5;
  overflow: hidden;
}

.status-progress-fill {
  height: 100%;
  border-radius: inherit;
  transition: width 0.2s ease;
}

.status-progress-dots {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.status-progress-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid #dcdfe6;
  background: #fff;
  box-sizing: border-box;
}

.status-progress-dot.is-done {
  background: currentColor;
  border-color: currentColor;
}

.status-progress-dot.is-current {
  background: #fff;
  border-color: currentColor;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.9);
}

.status-progress-dot.is-rejected {
  background: #fff2f0;
  border-color: #f56c6c;
}

.status-progress-dot.is-muted {
  background: #f5f7fa;
  border-color: #dcdfe6;
}

.status-progress-track.is-primary,
.status-progress-dot.is-primary { color: #409eff; }

.status-progress-track.is-warning,
.status-progress-dot.is-warning { color: #e6a23c; }

.status-progress-track.is-success,
.status-progress-dot.is-success { color: #67c23a; }

.status-progress-track.is-danger,
.status-progress-dot.is-danger { color: #f56c6c; }

.status-progress-track.is-pending,
.status-progress-dot.is-pending { color: #909399; }

.status-progress-track.is-muted,
.status-progress-dot.is-muted { color: #c0c4cc; }

.status-progress-track.is-primary .status-progress-fill { background: #409eff; }
.status-progress-track.is-warning .status-progress-fill { background: linear-gradient(90deg, #f5c260 0%, #e6a23c 100%); }
.status-progress-track.is-success .status-progress-fill { background: linear-gradient(90deg, #85ce61 0%, #67c23a 100%); }
.status-progress-track.is-danger .status-progress-fill { background: linear-gradient(90deg, #f89898 0%, #f56c6c 100%); }
.status-progress-track.is-pending .status-progress-fill { background: #909399; }
.status-progress-track.is-muted .status-progress-fill { background: #c0c4cc; }

.status-progress-track.is-exception .status-progress-rail {
  background: repeating-linear-gradient(
    135deg,
    #f4f4f5 0,
    #f4f4f5 6px,
    #ebeef5 6px,
    #ebeef5 12px
  );
}

.batch-operations {
  margin-bottom: 16px;
  background-color: #f0f9ff;
  border: 1px solid #0ea5e9;
}

.batch-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.batch-actions {
  display: flex;
  gap: 8px;
}

.form-hint {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.4;
  color: #909399;
}

.expansion-lld-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  background: #fafafa;
}

.expansion-lld-main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.expansion-lld-title {
  max-width: 420px;
  color: #303133;
  font-size: 13px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.expansion-preview {
  margin-top: 10px;
}

.expansion-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.expansion-dialog-panel {
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  background: #f7f8fa;
}

.expansion-dialog-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.expansion-dialog-preview {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.expansion-preview-meta {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  color: #606266;
  font-size: 12px;
}

.expansion-dialog-empty {
  padding: 18px 0 8px;
}

.expansion-cell-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

@media (max-width: 640px) {
  .expansion-lld-card {
    align-items: flex-start;
    flex-direction: column;
  }

  .expansion-lld-title {
    max-width: 100%;
  }
}
</style>
