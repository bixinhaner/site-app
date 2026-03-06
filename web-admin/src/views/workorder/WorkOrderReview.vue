<template>
  <div class="page">
    <div class="page-header">
      <h1>工单审核台</h1>
      <div>
        <el-button @click="refresh"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>
    <el-card v-loading="loading">
      <template v-if="order">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="标题">{{ order.title }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ typeText(order.type) }}</el-descriptions-item>
          <el-descriptions-item label="站点">{{ order.site_name || order.site_id }}</el-descriptions-item>
          <el-descriptions-item label="分配给">{{ order.assignee_name }}</el-descriptions-item>
          <el-descriptions-item label="优先级">{{ priorityText(order.priority) }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(order.status)">{{ statusText(order.status, order.type) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="分配时间">{{ formatDateTime(order.assigned_at) }}</el-descriptions-item>
          <el-descriptions-item label="提交时间">{{ formatDateTime(order.submitted_at) }}</el-descriptions-item>
          <el-descriptions-item v-if="order.voided_at" label="作废时间">{{ formatDateTime(order.voided_at) }}</el-descriptions-item>
          <el-descriptions-item v-if="order.voided_at" label="作废原因">{{ order.void_reason || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-alert
          v-if="order.status === 'VOIDED'"
          class="mb16"
          type="warning"
          :closable="false"
          show-icon
          :title="`该工单已作废${order.voided_by_name ? `（${order.voided_by_name}）` : ''}`"
          :description="'工单、检查记录和勘察草稿均已冻结为只读，不可继续审核或修改。'"
        />

        <el-alert
          v-if="duplicatePhotoSummary.total > 0"
          class="mb16"
          type="warning"
          :closable="false"
          show-icon
          :title="`检测到重复图片：共 ${duplicatePhotoSummary.total} 张，涉及 ${duplicatePhotoSummary.items} 个检查项`"
          :description="'列表页已标注，建议进入检查项详情逐张核验来源信息。'"
        />

        <el-alert
          v-if="similarPhotoSummary.total > 0"
          class="mb16"
          type="error"
          :closable="false"
          show-icon
          :title="`检测到极度相似图片：共 ${similarPhotoSummary.total} 张，涉及 ${similarPhotoSummary.items} 个检查项`"
          :description="'建议重点核验是否存在历史照片复用风险。'"
        />

        <el-divider />

        <!-- 设备更换工单信息 -->
        <el-card v-if="order.type === 'equipment_replacement'" style="margin-bottom: 16px;">
          <template #header>
            <div class="card-header">
              <span>设备更换信息</span>
            </div>
          </template>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="更换设备位">
              <el-space wrap>
                <el-tag
                  v-for="t in replacementTargets"
                  :key="`${t.sector_id}__${t.band}`"
                  size="small"
                >
                  S{{ t.sector_id }}/{{ t.band }}
                </el-tag>
                <span v-if="!replacementTargets.length" class="muted">-</span>
              </el-space>
            </el-descriptions-item>
            <el-descriptions-item label="发起人ID">
              <span>{{ replacementInitiatorId || '-' }}</span>
            </el-descriptions-item>
          </el-descriptions>

          <el-divider />

          <div class="replacement-block">
            <div class="replacement-title">旧设备（预填）</div>
            <el-empty v-if="!replacementOldDevices.length" description="暂无预填旧设备" />
            <el-table v-else :data="replacementOldDevices" size="small" stripe>
              <el-table-column label="设备位" width="160">
                <template #default="{ row }">S{{ row.sector_id }}/{{ row.band }}</template>
              </el-table-column>
              <el-table-column prop="old_sn" label="旧设备SN" min-width="180">
                <template #default="{ row }">
                  <span>{{ row.old_sn || '-' }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <el-divider />

          <div class="replacement-block">
            <div class="replacement-title">更换记录</div>
            <el-empty v-if="!replacementHistory.length" description="暂无更换记录" />
            <el-table v-else :data="replacementHistory" size="small" stripe>
              <el-table-column label="时间" width="180">
                <template #default="{ row }">{{ formatDateTime(row.replaced_at) }}</template>
              </el-table-column>
              <el-table-column label="设备位" width="160">
                <template #default="{ row }">S{{ row.sector_id }}/{{ row.band }}</template>
              </el-table-column>
              <el-table-column prop="old_sn" label="旧SN" min-width="160" />
              <el-table-column prop="new_sn" label="新SN" min-width="160" />
              <el-table-column prop="operator_id" label="操作人" width="120" />
            </el-table>
          </div>

          <el-divider />

          <div class="replacement-block">
            <div class="replacement-title">旧设备退库（可选）</div>
            <el-empty v-if="!replacementReturnCandidates.length" description="暂无可退库的旧设备" />
            <template v-else>
              <el-checkbox-group v-model="selectedReturnSns">
                <el-checkbox v-for="sn in replacementReturnCandidates" :key="sn" :label="sn">
                  {{ sn }}
                </el-checkbox>
              </el-checkbox-group>
              <div style="margin-top: 12px;">
                <el-button
                  type="primary"
                  size="small"
                  :disabled="selectedReturnSns.length === 0 || returnSubmitting"
                  :loading="returnSubmitting"
                  @click="createReturnByActual"
                >
                  发起退库申请
                </el-button>
              </div>
            </template>
          </div>
        </el-card>

        <!-- 开站/设备更换工单：设备在线/激活状态 -->
        <el-card
          v-if="order.type === 'opening_inspection' || order.type === 'equipment_replacement'"
          class="mb16"
          v-loading="deviceStatusLoading"
        >
          <template #header>
            <div class="card-header">
              <span>{{ order.type === 'opening_inspection' ? '开站设备在线 / 激活状态' : '换机设备在线 / 激活状态' }}</span>
              <div>
	                <span v-if="deviceStatusCheckedAt" style="margin-right: 12px; color: #909399;">
	                  最近检查时间：{{ formatDateTime(deviceStatusCheckedAt) }}
	                </span>
	                <el-button
	                  size="small"
	                  type="primary"
	                  :disabled="deviceRefreshCooldown > 0"
	                  @click="loadDeviceStatus(true)"
                >
                  <span v-if="deviceRefreshCooldown > 0">
                    刷新状态 ({{ deviceRefreshCooldown }}s)
                  </span>
                  <span v-else>
                    刷新状态
                  </span>
                </el-button>
              </div>
            </div>
          </template>
          <el-empty v-if="!devices.length && !deviceStatusLoading" description="暂无绑定设备记录" />
          <el-table v-else :data="devices" size="small" stripe>
            <el-table-column prop="sn" label="设备 SN" min-width="180" />
            <el-table-column prop="equipment_type" label="设备类型" width="120" />
            <el-table-column prop="equipment_model" label="设备型号" min-width="160" />
            <el-table-column label="扇区信息" min-width="160">
              <template #default="{ row }">
                扇区 {{ row.sector_id || '-' }} / Band {{ row.band || '-' }} / Cell {{ row.cell_id || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="在线状态" width="200">
              <template #default="{ row }">
                <div class="status-cell">
                  <el-tag :type="onlineRealtimeTagType(row.online)" size="small" class="mr4">
                    {{ onlineRealtimeText(row.online) }}
                  </el-tag>
                  <el-tag :type="everOnlineTagType(row.ever_online)" size="small">
                    {{ everOnlineText(row.ever_online) }}
                  </el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="激活状态" width="220">
              <template #default="{ row }">
                <div class="status-cell">
                  <el-tag :type="activeRealtimeTagType(row.activated)" size="small" class="mr4">
                    {{ activeRealtimeText(row.activated) }}
                  </el-tag>
                  <el-tag :type="everActiveTagType(row.ever_activated)" size="small">
                    {{ everActiveText(row.ever_activated) }}
                  </el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="安装人" width="140">
              <template #default="{ row }">
                {{ row.installer_name || row.installer_id || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="bound_at" label="绑定时间" width="180">
              <template #default="{ row }">
                {{ formatDateTime(row.bound_at) }}
              </template>
            </el-table-column>
            <el-table-column v-if="canShowManualConfirm" label="手工确认" width="220">
              <template #default="{ row }">
                <el-space>
                  <el-button
                    size="small"
                    type="success"
                    plain
                    :disabled="isVoided || manualConfirmSubmitting || row.ever_online"
                    @click="manualConfirm(row, 'online')"
                  >
                    确认上线
                  </el-button>
                  <el-button
                    size="small"
                    type="warning"
                    plain
                    :disabled="isVoided || manualConfirmSubmitting || row.ever_activated"
                    @click="manualConfirm(row, 'activated')"
                  >
                    确认激活
                  </el-button>
                </el-space>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
	        <div class="section-header">
	          <div class="section-title">
	            <h3>检查项审核</h3>
	            <el-radio-group v-model="reviewListMode" size="small">
	              <el-radio-button label="全部" />
	              <el-radio-button label="仅看需复审" />
	            </el-radio-group>
	            <el-radio-group v-model="scopeFilter" size="small">
	              <el-radio-button label="全部范围" />
	              <el-radio-button label="站点" />
	              <el-radio-button label="扇区" />
	              <el-radio-button label="小区" />
	              <el-radio-button label="设备" />
	            </el-radio-group>
	            <el-radio-group v-model="distanceFilter" size="small">
	              <el-radio-button label="全部距离" />
	              <el-radio-button label="仅超距" />
	            </el-radio-group>
	            <el-dropdown
	              style="margin-left: 12px;"
	              trigger="click"
	              @command="runAiCheckBatch"
	            >
		              <el-button size="small" type="primary" :disabled="isVoided || itemsLoading || aiCheckProgress.running">
	                <el-icon><MagicStick /></el-icon>一键AI检查
	                <el-icon class="el-icon--right"><ArrowDown /></el-icon>
	              </el-button>
	              <template #dropdown>
	                <el-dropdown-menu>
	                  <el-dropdown-item command="missing">仅未生成</el-dropdown-item>
	                  <el-dropdown-item command="all">全部</el-dropdown-item>
	                </el-dropdown-menu>
	              </template>
	            </el-dropdown>
	          </div>
	          <div v-if="summary" class="review-summary">
	            <div class="review-summary__counts">
	              <el-tag type="success" effect="plain" round size="small" class="review-summary__count-tag">
	                通过 {{ summary.pass_count }}
	              </el-tag>
	              <el-tag type="warning" effect="plain" round size="small" class="review-summary__count-tag">
	                警告 {{ summary.warning_count }}
	              </el-tag>
	              <el-tag type="danger" effect="plain" round size="small" class="review-summary__count-tag">
	                不合格 {{ summary.fail_count }}
	              </el-tag>
	              <el-tag effect="plain" round size="small" class="review-summary__count-tag">
	                待审 {{ summary.pending_count }}
	              </el-tag>
	            </div>

	            <el-tooltip
	              v-if="reviewHeaderHint.tooltip"
	              :content="reviewHeaderHint.tooltip"
	              placement="top"
	            >
	              <el-tag
	                :type="reviewHeaderHint.type"
	                effect="plain"
	                round
	                size="small"
	                class="review-summary__hint"
	              >
	                <el-icon class="review-summary__hint-icon">
	                  <component :is="reviewHeaderHint.icon" />
	                </el-icon>
	                {{ reviewHeaderHint.text }}
	              </el-tag>
	            </el-tooltip>
	          </div>
        </div>
        <el-table :data="displayedItems" size="small" stripe v-loading="itemsLoading">
          <el-table-column prop="item_name" label="检查项" min-width="220" />
          <el-table-column label="范围" min-width="180">
            <template #default="{ row }">
              <div
                class="scope-cell"
                :class="{ 'scope-cell--multiline': getItemScopeLevel(row) === '设备' && row.equipment_sn }"
              >
                <el-tag :type="scopeTagType(row)" size="small" class="mr4">
                  {{ getItemScopeLevel(row) }}
                </el-tag>
                <template v-if="getItemScopeLevel(row) === '设备' && row.equipment_sn">
                  <div class="scope-sn">
                    <el-tooltip :content="row.equipment_sn" placement="top">
                      <span class="scope-text scope-text--multiline">{{ row.equipment_sn }}</span>
                    </el-tooltip>
                  </div>
                  <el-button
                    link
                    type="primary"
                    size="small"
                    class="scope-copy-btn"
                    @click="copyToClipboard(row.equipment_sn)"
                  >
                    <el-icon><CopyDocument /></el-icon>
                  </el-button>
                </template>
                <template v-else-if="getItemScopeLevel(row) === '小区'">
                  <el-tooltip
                    :content="`扇区 ${row.sector_id || '-'} / Band ${row.band || '-'} / Cell ${row.cell_id || '-'}`"
                    placement="top"
                  >
                    <span class="scope-text">
                      S{{ row.sector_id || '-' }}/{{ row.band || '-' }}/{{ row.cell_id || '-' }}
                    </span>
                  </el-tooltip>
                </template>
                <template v-else-if="getItemScopeLevel(row) === '扇区'">
                  <el-tooltip :content="`扇区 ${row.sector_id || '-'}`" placement="top">
                    <span class="scope-text">S{{ row.sector_id || '-' }}</span>
                  </el-tooltip>
                </template>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="required_type" label="类型" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.required_type === 'photo'" type="info" size="small">照片</el-tag>
              <el-tag v-else-if="row.required_type === 'data'" type="warning" size="small">数据</el-tag>
              <el-tag v-else-if="row.required_type === 'both'" type="primary" size="small">数据+照片</el-tag>
              <span v-else>{{ row.required_type }}</span>
            </template>
          </el-table-column>
          <el-table-column label="内容" width="120">
            <template #default="{ row }">
              <div>
                <div v-if="row.data_value && row.data_value.length > 0" style="margin-bottom: 4px;">
                  <el-tag size="small" type="success">数据: {{ row.data_value.length }}项</el-tag>
                </div>
                <div v-if="row.photos && row.photos.length > 0">
                  <el-tag size="small" type="info">照片: {{ row.photos.length }}张</el-tag>
                </div>
                <div v-if="(!row.data_value || row.data_value.length === 0) && (!row.photos || row.photos.length === 0)">
                  <el-tag size="small" type="warning">无内容</el-tag>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="重复图" width="130">
            <template #default="{ row }">
              <template v-if="getItemDuplicateStats(row).count > 0">
                <el-popover placement="top" width="420" trigger="hover">
                  <template #reference>
                    <el-tag type="warning" size="small">重复 {{ getItemDuplicateStats(row).count }} 张</el-tag>
                  </template>
                  <div
                    v-for="(line, idx) in getItemDuplicateHintLines(row)"
                    :key="`${row.id}-dup-${idx}`"
                    class="duplicate-hint-line"
                  >
                    {{ line }}
                  </div>
                </el-popover>
              </template>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="相似图" width="130">
            <template #default="{ row }">
              <template v-if="getItemSimilarStats(row).count > 0">
                <el-popover placement="top" width="420" trigger="hover">
                  <template #reference>
                    <el-tag type="danger" size="small">相似 {{ getItemSimilarStats(row).count }} 张</el-tag>
                  </template>
                  <div
                    v-for="(line, idx) in getItemSimilarHintLines(row)"
                    :key="`${row.id}-sim-${idx}`"
                    class="duplicate-hint-line"
                  >
                    {{ line }}
                  </div>
                </el-popover>
              </template>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="位置比对" width="180">
            <template #default="{ row }">
              <template v-if="getItemLocationCompareStats(row).comparedCount > 0">
                <el-tag
                  :type="getItemLocationCompareStats(row).exceededCount > 0 ? 'danger' : 'success'"
                  size="small"
                >
                  {{
                    getItemLocationCompareStats(row).exceededCount > 0
                      ? `超距 ${getItemLocationCompareStats(row).exceededCount} 张`
                      : '正常'
                  }}
                </el-tag>
                <el-tag
                  v-if="getItemLocationCompareStats(row).missingPlanCount > 0"
                  type="warning"
                  size="small"
                  style="margin-left: 4px;"
                >
                  缺规划 {{ getItemLocationCompareStats(row).missingPlanCount }} 张
                </el-tag>
              </template>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="提交状态" width="120">
            <template #default="{ row }">
              <el-tag :type="checkItemStatusTagType(row.status)" size="small">
                {{ checkItemStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
	          <el-table-column prop="review_status" label="审核结果" width="120">
	            <template #default="{ row }">
	              <el-tag v-if="row.review_status === 'pass'" type="success">通过</el-tag>
	              <el-tag v-else-if="row.review_status === 'warning'" type="warning">警告</el-tag>
	              <el-tag v-else-if="row.review_status === 'fail'" type="danger">不合格</el-tag>
	              <span v-else>-</span>
	            </template>
	          </el-table-column>
	          <el-table-column label="AI建议" width="140">
	            <template #default="{ row }">
	              <el-tag v-if="row.ai_status === 'running'" type="info" size="small">生成中</el-tag>
	              <el-tooltip v-else-if="row.ai_status === 'failed'" :content="row.ai_error || 'AI检查失败'" placement="top">
	                <el-tag type="danger" size="small">失败</el-tag>
	              </el-tooltip>
	              <template v-else-if="row.ai_status === 'done' && row.ai_result">
	                <el-tag :type="aiSuggestedTagType(row.ai_result?.suggested_review_status)" size="small">
	                  {{ aiSuggestedStatusText(row.ai_result?.suggested_review_status) }}
	                </el-tag>
	              </template>
	              <span v-else>-</span>
	            </template>
	          </el-table-column>
	          <el-table-column prop="review_comments" label="审核意见" min-width="200" show-overflow-tooltip />
	          <el-table-column prop="notes" label="现场备注" min-width="200" show-overflow-tooltip />
	          <el-table-column label="操作" width="220" fixed="right">
	            <template #default="{ row }">
	              <div class="action-cell">
	                <el-button link type="primary" size="small" @click="viewItemDetail(row)">详情</el-button>
	                <el-dropdown trigger="click" @command="(cmd) => handleAiAction(cmd, row)">
	                  <el-button link type="primary" size="small">
	                    AI <el-icon class="el-icon--right"><ArrowDown /></el-icon>
	                  </el-button>
	                  <template #dropdown>
	                    <el-dropdown-menu>
		                      <el-dropdown-item :disabled="isVoided || aiCheckProgress.running" command="check">AI检查</el-dropdown-item>
	                      <el-dropdown-item :disabled="!canApplyAi(row)" command="apply">采纳AI</el-dropdown-item>
	                    </el-dropdown-menu>
	                  </template>
	                </el-dropdown>

	                <el-dropdown
	                  trigger="click"
	                  :disabled="!canReviewCheckItem(row)"
	                  @command="(cmd) => handleReviewAction(cmd, row)"
	                >
	                  <el-button link type="primary" size="small" :disabled="!canReviewCheckItem(row)">
	                    审核 <el-icon class="el-icon--right"><ArrowDown /></el-icon>
	                  </el-button>
	                  <template #dropdown>
	                    <el-dropdown-menu>
	                      <el-dropdown-item command="pass">通过</el-dropdown-item>
	                      <el-dropdown-item command="warning">警告</el-dropdown-item>
	                      <el-dropdown-item command="fail">不合格</el-dropdown-item>
	                    </el-dropdown-menu>
	                  </template>
	                </el-dropdown>
	              </div>
	              <el-tooltip v-if="!canReviewCheckItem(row)" :content="checkItemReviewDisabledReason(row)" placement="top">
	                <span class="help-tip">?</span>
	              </el-tooltip>
	            </template>
	          </el-table-column>
        </el-table>


        <el-divider />
        <el-form label-width="100px">
          <el-form-item label="审核意见">
            <div class="i18n-inline">
              <el-input
                v-model="comments"
                class="i18n-inline__input"
                type="textarea"
                :rows="3"
                placeholder="请输入审核意见"
              />
              <el-button-group class="i18n-actions">
                <el-tooltip content="多语言" placement="top">
                  <el-button
                    size="small"
                    circle
                    :icon="ChatDotRound"
                    @click="openI18nEditorForFinalReview()"
                  />
                </el-tooltip>
                <el-tooltip content="AI翻译" placement="top">
                  <el-button
                    size="small"
                    circle
                    :icon="MagicStick"
                    @click="aiFillFinalReviewI18n()"
                  />
                </el-tooltip>
              </el-button-group>
            </div>
          </el-form-item>
          <el-form-item>
            <el-space>
              <el-button type="primary" :disabled="!canStartReview" @click="startReview">认领审核</el-button>
              <el-button type="success" :disabled="!canApprove" @click="finalReview('approve')">
                {{ hasFailedItems ? '存在不合格检查项，无法通过' : '通过' }}
              </el-button>
              <el-button type="danger" :disabled="!canReject" @click="finalReview('reject')">驳回</el-button>
              <el-button v-if="canVoidCurrentOrder" type="warning" @click="voidCurrentWorkOrder">作废工单</el-button>
              <el-button type="info" @click="showAuditHistory">
                <el-icon><Clock /></el-icon>查看审核历史
              </el-button>
              <el-button type="warning" :disabled="aiReviewI18nLoading" @click="openAiReviewI18n">
                <el-icon><MagicStick /></el-icon>AI国际化
              </el-button>
            </el-space>
          </el-form-item>
        </el-form>
      </template>
      <div v-else>请选择一条工单或从列表进入。</div>
    </el-card>

    <!-- 检查项详情弹窗 -->
    <el-dialog v-model="itemDetailVisible" title="检查项详情" width="800px">
      <div v-if="selectedItem">
	        <el-descriptions :column="2" border>
	          <el-descriptions-item label="检查项名称">{{ selectedItem.item_name }}</el-descriptions-item>
	          <el-descriptions-item label="类型">
	            <el-tag v-if="selectedItem.required_type === 'photo'" type="info" size="small">照片</el-tag>
            <el-tag v-else-if="selectedItem.required_type === 'data'" type="warning" size="small">数据</el-tag>
            <el-tag v-else-if="selectedItem.required_type === 'both'" type="primary" size="small">数据+照片</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="checkItemStatusTagType(selectedItem.status)" size="small">
              {{ checkItemStatusText(selectedItem.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ formatDateTime(selectedItem.checked_at) }}</el-descriptions-item>
          <el-descriptions-item label="审核状态">
            <el-tag v-if="selectedItem.review_status === 'pass'" type="success">通过</el-tag>
            <el-tag v-else-if="selectedItem.review_status === 'warning'" type="warning">警告</el-tag>
            <el-tag v-else-if="selectedItem.review_status === 'fail'" type="danger">不合格</el-tag>
            <span v-else>待审核</span>
          </el-descriptions-item>
	          <el-descriptions-item label="审核意见">{{ selectedItem.review_comments || '-' }}</el-descriptions-item>
	          <el-descriptions-item label="现场备注">{{ selectedItem.notes || '-' }}</el-descriptions-item>
	        </el-descriptions>

	        <!-- AI 建议 -->
	        <div style="margin-top: 16px;">
	          <div style="display: flex; align-items: center; justify-content: space-between;">
	            <h4 style="margin: 0;">AI 建议（需人工确认后采纳）</h4>
	            <el-space>
		              <el-button size="small" type="primary" :disabled="isVoided || aiCheckProgress.running" @click="aiCheckSingle(selectedItem)">
	                <el-icon><MagicStick /></el-icon>AI检查
	              </el-button>
	              <el-button size="small" type="success" :disabled="!canApplyAi(selectedItem)" @click="applyAiSuggestion(selectedItem)">
	                采纳AI
	              </el-button>
	            </el-space>
	          </div>

	          <div style="margin-top: 8px;">
	            <el-tag v-if="selectedItem.ai_status === 'running'" type="info" size="small">生成中</el-tag>
	            <el-tooltip v-else-if="selectedItem.ai_status === 'failed'" :content="selectedItem.ai_error || 'AI检查失败'" placement="top">
	              <el-tag type="danger" size="small">失败</el-tag>
	            </el-tooltip>
	            <el-tag v-else-if="selectedItem.ai_status === 'done'" type="success" size="small">已生成</el-tag>
	            <el-tag v-else size="small">未生成</el-tag>
	          </div>

	          <div v-if="selectedItem.ai_status === 'done' && selectedItem.ai_result" style="margin-top: 10px;">
	            <el-descriptions :column="3" size="small" border>
	              <el-descriptions-item label="建议结论">
	                <el-tag :type="aiSuggestedTagType(selectedItem.ai_result?.suggested_review_status)" size="small">
	                  {{ aiSuggestedStatusText(selectedItem.ai_result?.suggested_review_status) }}
	                </el-tag>
	              </el-descriptions-item>
	              <el-descriptions-item label="建议分数">
	                {{ (selectedItem.ai_result?.suggested_score ?? '-') }}
	              </el-descriptions-item>
	              <el-descriptions-item label="置信度">
	                {{ (selectedItem.ai_result?.confidence ?? '-') }}
	              </el-descriptions-item>
	            </el-descriptions>

	            <el-alert
	              v-if="selectedItem.ai_result?.summary"
	              type="info"
	              :closable="false"
	              show-icon
	              style="margin-top: 10px;"
	              :title="selectedItem.ai_result.summary"
	            />

	            <div v-if="Array.isArray(selectedItem.ai_result?.analysis) && selectedItem.ai_result.analysis.length" style="margin-top: 10px;">
	              <div style="font-weight: 600; margin-bottom: 6px;">分析要点</div>
	              <ul style="margin: 0; padding-left: 18px;">
	                <li v-for="(it, idx) in selectedItem.ai_result.analysis" :key="idx">{{ it }}</li>
	              </ul>
	            </div>

	            <div v-if="Array.isArray(selectedItem.ai_result?.missing_evidence) && selectedItem.ai_result.missing_evidence.length" style="margin-top: 10px;">
	              <div style="font-weight: 600; margin-bottom: 6px;">缺材料/需补充</div>
	              <el-space wrap>
	                <el-tag v-for="(it, idx) in selectedItem.ai_result.missing_evidence" :key="idx" type="warning" size="small">
	                  {{ it }}
	                </el-tag>
	              </el-space>
	            </div>
	          </div>
	        </div>

	        <!-- 数据内容 -->
	        <div v-if="itemDetailFieldRows.length > 0" style="margin-top: 20px;">
	          <h4>字段数据 & 字段照片</h4>
	          <el-table :data="itemDetailFieldRows" size="small" border>
	            <el-table-column label="字段名称" min-width="260">
	              <template #default="{ row }">
	                <div class="field-name-cell">
	                  <span>{{ row.label }}</span>
                  <span v-if="row.required" class="field-required-mark">*</span>
                  <el-popover
                    v-if="row.help_text"
                    placement="top-start"
                    trigger="click"
                    width="360"
                    :title="`${row.label} 描述/注意事项`"
                  >
                    <template #reference>
                      <el-icon class="field-help-icon" :title="`${row.label} 描述/注意事项`">
                        <QuestionFilled />
                      </el-icon>
                    </template>
                    <div class="field-help-text">{{ row.help_text }}</div>
                  </el-popover>
                </div>
	              </template>
	            </el-table-column>
	            <el-table-column prop="display_value" label="填写值" min-width="180" show-overflow-tooltip />
	            <el-table-column prop="unit" label="单位" width="120">
	              <template #default="{ row }">{{ row.unit || '-' }}</template>
	            </el-table-column>
	            <el-table-column label="照片" min-width="260">
	              <template #default="{ row }">
	                <div v-if="row.photos && row.photos.length" class="field-photo-strip">
	                  <ProgressImage
	                    v-for="(p, idx) in row.photos.slice(0, 4)"
	                    :key="p.id || idx"
	                    :src="getImageUrl(p.file_path)"
	                    class="field-photo-img"
	                    fit="cover"
	                    @click.stop="viewPhotoDetail(p)"
	                  />
	                  <el-tag
	                    v-if="row.photos.length > 4"
	                    size="small"
	                    effect="plain"
	                    type="info"
	                    class="field-photo-more"
	                  >
	                    +{{ row.photos.length - 4 }}
	                  </el-tag>
	                </div>
	              </template>
	            </el-table-column>
	          </el-table>

	          <div v-if="itemDetailExtraPhotos.length" style="margin-top: 12px;">
	            <el-divider />
	            <el-row :gutter="10">
	              <el-col v-for="p in itemDetailExtraPhotos" :key="p.id" :span="8">
	                <div class="photo-card">
	                  <ProgressImage
	                    :src="getImageUrl(p.file_path)"
	                    style="width: 100%; height: 120px; cursor: pointer;"
	                    fit="cover"
	                    @click="viewPhotoDetail(p)"
	                  />
                  <div class="photo-info">
                    <div class="photo-name">{{ p.original_name }}</div>
                    <div class="photo-time">{{ formatDateTime(p.taken_at) }}</div>
                    <div v-if="p.is_duplicate_global" class="duplicate-photo-tip">
                      {{ getPhotoDuplicateBrief(p) }}
                    </div>
                    <div v-if="p.is_similar_risk" class="similar-photo-tip">
                      {{ getPhotoSimilarBrief(p) }}
                    </div>
                  </div>
                </div>
              </el-col>
	            </el-row>
	          </div>
	        </div>

	        <!-- 照片内容 -->
	        <div v-if="itemDetailFieldRows.length === 0 && selectedItem.photos && selectedItem.photos.length > 0" style="margin-top: 20px;">
	          <h4>相关照片 ({{ selectedItem.photos.length }}张)</h4>
	          <el-row :gutter="10">
	            <el-col v-for="photo in selectedItem.photos" :key="photo.id" :span="8">
	              <div class="photo-card">
                <ProgressImage 
                  :src="getImageUrl(photo.file_path)" 
                  style="width: 100%; height: 120px; cursor: pointer;"
                  fit="cover"
                  @click="viewPhotoDetail(photo)"
                />
                <div class="photo-info">
                  <div class="photo-name">{{ photo.original_name }}</div>
                  <div class="photo-time">{{ formatDateTime(photo.taken_at) }}</div>
                  <div v-if="photo.is_duplicate_global" class="duplicate-photo-tip">
                    {{ getPhotoDuplicateBrief(photo) }}
                  </div>
                  <div v-if="photo.is_similar_risk" class="similar-photo-tip">
                    {{ getPhotoSimilarBrief(photo) }}
                  </div>
                  <div v-if="photo.latitude && photo.longitude" class="photo-location">
                    {{ photo.latitude.toFixed(6) }}, {{ photo.longitude.toFixed(6) }}
                  </div>
                  <div class="photo-actions" style="margin-top: 4px;">
                    <el-button type="primary" size="small" @click="viewPhotoDetail(photo)">详情</el-button>
                  </div>
                </div>
              </div>
            </el-col>
          </el-row>
        </div>

        <!-- 如果没有内容 -->
        <div v-if="(!selectedItem.photos || selectedItem.photos.length === 0) && itemDetailFieldRows.length === 0" style="margin-top: 20px;">
          <el-empty description="该检查项暂无提交内容" />
        </div>
      </div>
      <template #footer>
        <el-button @click="itemDetailVisible = false">关闭</el-button>
        <template v-if="selectedItem && (!selectedItem.review_status || selectedItem.review_status === 'pending')">
          <el-button type="success" :disabled="!canReviewCheckItem(selectedItem)" @click="reviewItem(selectedItem, 'pass')">通过</el-button>
          <el-button type="warning" :disabled="!canReviewCheckItem(selectedItem)" @click="reviewItem(selectedItem, 'warning')">警告</el-button>
          <el-button type="danger" :disabled="!canReviewCheckItem(selectedItem)" @click="reviewItem(selectedItem, 'fail')">不合格</el-button>
          <el-tooltip v-if="!canReviewCheckItem(selectedItem)" :content="checkItemReviewDisabledReason(selectedItem)" placement="top">
            <span class="help-tip">?</span>
          </el-tooltip>
        </template>
      </template>
    </el-dialog>

    <!-- 照片详情弹窗 -->
    <el-dialog v-model="photoDetailVisible" title="照片详情" width="1200px" :fullscreen="isFullscreen">
      <div v-if="selectedPhoto">
        <el-row :gutter="20">
          <el-col :span="isFullscreen ? 18 : 16">
            <div class="photo-container">
              <div class="photo-toolbar">
                <el-button-group>
                  <el-button size="small" @click="zoomIn"><el-icon><ZoomIn /></el-icon></el-button>
                  <el-button size="small" @click="zoomOut"><el-icon><ZoomOut /></el-icon></el-button>
                  <el-button size="small" @click="resetZoom">重置</el-button>
                  <el-button size="small" @click="toggleFullscreen">
                    <el-icon v-if="!isFullscreen"><FullScreen /></el-icon>
                    <el-icon v-else><Aim /></el-icon>
                  </el-button>
                  <el-button size="small" type="primary" @click="downloadPhoto">
                    <el-icon><Download /></el-icon>下载
                  </el-button>
                </el-button-group>
                <span class="zoom-info">{{ Math.round(zoomLevel * 100) }}%</span>
              </div>
              <div class="photo-viewer" @wheel="handleWheel" @mousedown="handleMouseDown" @mousemove="handleMouseMove" @mouseup="handleMouseUp" @mouseleave="handleMouseUp">
                <div
                  v-if="photoViewerStatus !== 'loaded'"
                  class="photo-viewer-overlay"
                  :class="photoViewerStatus === 'error' ? 'photo-viewer-overlay--error' : ''"
                  @click.stop="photoViewerStatus === 'error' ? loadSelectedPhotoForViewer() : undefined"
                >
                  <template v-if="photoViewerStatus === 'loading'">
                    <div class="photo-viewer-overlay__percent">{{ photoViewerProgress }}%</div>
                    <div class="photo-viewer-overlay__bar">
                      <div class="photo-viewer-overlay__bar-fill" :style="{ width: photoViewerProgress + '%' }"></div>
                    </div>
                  </template>
                  <template v-else-if="photoViewerStatus === 'error'">
                    <div class="photo-viewer-overlay__error-text">加载失败</div>
                    <div class="photo-viewer-overlay__error-sub">点击重试</div>
                  </template>
                </div>
                <img 
                  v-if="photoViewerStatus === 'loaded'"
                  ref="photoImage"
                  :src="photoViewerSrc" 
                  :style="{
                    transform: `scale(${zoomLevel}) translate(${translateX}px, ${translateY}px)`,
                    cursor: isDragging ? 'grabbing' : 'grab',
                    maxWidth: 'none',
                    maxHeight: 'none'
                  }"
                  @dragstart.prevent
                />
              </div>
            </div>
          </el-col>
          <el-col :span="isFullscreen ? 6 : 8">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="文件名">{{ selectedPhoto.original_name }}</el-descriptions-item>
              <el-descriptions-item label="拍摄时间">{{ formatDateTime(selectedPhoto.taken_at) }}</el-descriptions-item>
              <el-descriptions-item label="文件大小">{{ formatFileSize(selectedPhoto.file_size) }}</el-descriptions-item>
              <el-descriptions-item label="纬度">{{ selectedPhoto.latitude || '-' }}</el-descriptions-item>
              <el-descriptions-item label="经度">{{ selectedPhoto.longitude || '-' }}</el-descriptions-item>
              <el-descriptions-item label="GPS精度">{{ selectedPhoto.gps_accuracy || '-' }}</el-descriptions-item>
              <el-descriptions-item label="地址">{{ selectedPhoto.address || '-' }}</el-descriptions-item>
              <el-descriptions-item label="规划坐标">
                {{
                  selectedPhotoLocationCompare?.plannedCoordinatesText
                    || (selectedPhotoLocationCompare?.planCoordinateMissing ? '规划坐标缺失' : '-')
                }}
              </el-descriptions-item>
              <el-descriptions-item label="距规划距离">
                {{
                  Number.isFinite(selectedPhotoLocationCompare?.distanceToPlanM)
                    ? `${selectedPhotoLocationCompare.distanceToPlanM.toFixed(1)} m`
                    : '-'
                }}
              </el-descriptions-item>
              <el-descriptions-item label="位置结论">
                <template v-if="selectedPhotoLocationCompare">
                  <el-tag
                    :type="selectedPhotoLocationCompare.exceeded ? 'danger' : 'success'"
                    size="small"
                  >
                    {{ selectedPhotoLocationCompare.exceeded ? '超阈值' : '正常' }}
                  </el-tag>
                  <span
                    v-if="Number.isFinite(selectedPhotoLocationCompare.thresholdM)"
                    style="margin-left: 6px;"
                  >
                    (阈值 {{ selectedPhotoLocationCompare.thresholdM }}m)
                  </span>
                </template>
                <span v-else>-</span>
              </el-descriptions-item>
              <el-descriptions-item label="水印">{{ selectedPhoto.has_watermark ? '是' : '否' }}</el-descriptions-item>
              <el-descriptions-item label="重复图片">
                <template v-if="selectedPhoto.is_duplicate_global">
                  <el-tag type="warning" size="small">是</el-tag>
                  <div class="duplicate-detail-block">
                    <div>{{ getPhotoDuplicateBrief(selectedPhoto) }}</div>
                    <div>{{ getPhotoDuplicateSourceLine(selectedPhoto) }}</div>
                  </div>
                </template>
                <span v-else>否</span>
              </el-descriptions-item>
              <el-descriptions-item label="相似图片">
                <template v-if="selectedPhoto.is_similar_risk">
                  <el-tag type="danger" size="small">是</el-tag>
                  <div class="similar-detail-block">
                    <div>{{ getPhotoSimilarBrief(selectedPhoto) }}</div>
                    <div>{{ getPhotoSimilarSourceLine(selectedPhoto) }}</div>
                  </div>
                </template>
                <span v-else>否</span>
              </el-descriptions-item>
              <el-descriptions-item label="相似度详情">
                <el-button size="small" type="primary" plain @click="openPhotoSimilarityDetail">
                  查看详情
                </el-button>
              </el-descriptions-item>
            </el-descriptions>
          </el-col>
        </el-row>
      </div>
      <template #footer>
        <el-button @click="photoDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="photoSimilarityDetailVisible"
      title="相似度详情"
      width="820px"
      :close-on-click-modal="false"
    >
      <el-alert
        :type="selectedPhotoSimilarityRiskTagType"
        :title="selectedPhotoSimilarityConclusionText"
        show-icon
        :closable="false"
        style="margin-bottom: 12px;"
      />

      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="判定结论">
          {{ selectedPhotoSimilarityDecisionText }}
        </el-descriptions-item>
        <el-descriptions-item label="校验范围">
          {{ selectedPhotoSimilarityWindowText }}
        </el-descriptions-item>
        <el-descriptions-item label="提醒阈值">
          {{ selectedPhotoSimilarityThresholdText }}
        </el-descriptions-item>
        <el-descriptions-item label="候选筛选过程">
          {{ selectedPhotoSimilarityCandidateText }}
        </el-descriptions-item>
        <el-descriptions-item label="最接近的历史照片">
          {{ selectedPhotoSimilarityBestMatchText }}
        </el-descriptions-item>
        <el-descriptions-item label="处理建议">
          {{ selectedPhotoSimilarityAdviceText }}
        </el-descriptions-item>
      </el-descriptions>

      <div class="similarity-human-lines" v-if="selectedPhotoSimilarityHumanLines.length > 0">
        <div class="similarity-human-lines__title">说明</div>
        <div
          v-for="(line, idx) in selectedPhotoSimilarityHumanLines"
          :key="`similarity-line-${idx}`"
          class="similarity-human-lines__item"
        >
          {{ line }}
        </div>
      </div>

      <el-divider>后台校验原始数据</el-divider>
      <pre class="similarity-debug-json">{{ selectedPhotoSimilarityDebugJson }}</pre>

      <template #footer>
        <el-button @click="photoSimilarityDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 审核历史弹窗 -->
    <el-dialog v-model="auditHistoryVisible" title="工单详情历史" width="900px">
      <el-timeline v-if="timelineLogs.length > 0">
        <el-timeline-item
          v-for="log in timelineLogs"
          :key="log.id"
          :timestamp="formatDateTime(log.created_at)"
          placement="top"
          :type="getTimelineLogType(log)"
        >
          <el-card>
            <template #header>
              <div class="card-header">
                <div class="card-header-left">
                  <span>
                    <strong>{{ log.operator_name }}</strong>
                    <span v-if="log.operator_username">({{ log.operator_username }})</span>
                  </span>
                  <el-tag :type="getSourceTagType(log.source)" size="small" class="ml8">
                    {{ log.source_label || sourceText(log.source) }}
                  </el-tag>
                </div>
                <el-tag :type="getTimelineActionTagType(log)" size="small">{{ getActionText(log.action, log.source) }}</el-tag>
              </div>
            </template>

            <div v-if="log.from_status || log.to_status">
              状态变更：
              <el-tag v-if="log.from_status" size="small">{{ formatTimelineStatus(log.from_status) }}</el-tag>
              <el-icon><Right /></el-icon>
              <el-tag v-if="log.to_status" size="small" :type="getTimelineStatusTagType(log.to_status)">
                {{ formatTimelineStatus(log.to_status) }}
              </el-tag>
            </div>

            <div v-if="log.source === 'binding'" style="margin-top: 8px;">
              <div>
                设备：
                <el-tag size="small">{{ log.details?.equipment_sn || '-' }}</el-tag>
                <template v-if="log.action === 'rebind' && log.details?.previous_equipment_sn">
                  <el-icon><Right /></el-icon>
                  <el-tag size="small" type="success">{{ log.details.previous_equipment_sn }}</el-tag>
                </template>
              </div>
              <div style="margin-top: 4px;">
                小区：扇区 {{ log.details?.sector_id || '-' }} / Band {{ log.details?.band || '-' }} / Cell {{ log.details?.cell_id || '-' }}
              </div>
            </div>

            <div v-if="isAssigneeChange(log)" style="margin-top: 8px;">
              指派变更：
              <el-tag size="small">
                {{ log.details?.old_assignee_name || log.details?.old_assignee_id || '-' }}
              </el-tag>
              <el-icon><Right /></el-icon>
              <el-tag size="small" type="success">
                {{ log.details?.new_assignee_name || log.details?.new_assignee_id || log.details?.new_assignee || '-' }}
              </el-tag>
            </div>

            <div v-if="log.comments" style="margin-top: 8px;">
              <strong>意见：</strong>{{ log.comments }}
            </div>

            <div v-if="hasLogDetails(log)" style="margin-top: 8px; color: #909399; font-size: 12px;">
              <el-button link size="small" @click="toggleLogDetails(log.id)">
                {{ isLogDetailsExpanded(log.id) ? '收起详情' : '查看详情' }}
              </el-button>
              <pre v-if="isLogDetailsExpanded(log.id)" style="margin: 8px 0 0;">{{ JSON.stringify(log.details, null, 2) }}</pre>
            </div>
          </el-card>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无操作历史" />

      <template #footer>
        <el-button @click="auditHistoryVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 检查项审核意见弹窗（替代 prompt，支持多语言/AI） -->
    <el-dialog
      v-model="itemReviewVisible"
      title="检查项审核"
      width="600px"
      :close-on-click-modal="false"
    >
      <div v-if="itemReviewRow" class="item-review-body">
        <div class="item-review-meta">
          <div class="item-review-name">
            <span style="font-weight: 600;">检查项：</span>{{ itemReviewRow.item_name }}
          </div>
          <el-tag v-if="itemReviewAction === 'pass'" type="success" size="small">通过</el-tag>
          <el-tag v-else-if="itemReviewAction === 'warning'" type="warning" size="small">警告</el-tag>
          <el-tag v-else-if="itemReviewAction === 'fail'" type="danger" size="small">不合格</el-tag>
        </div>

        <div class="i18n-inline">
          <el-input
            v-model="itemReviewComments"
            class="i18n-inline__input"
            type="textarea"
            :rows="4"
            :placeholder="itemReviewAction === 'pass' ? '请输入审核意见（可选）' : '请输入审核意见（必填）'"
          />
          <el-button-group class="i18n-actions">
            <el-tooltip content="多语言" placement="top">
              <el-button
                size="small"
                circle
                :icon="ChatDotRound"
                @click="openI18nEditorForItemReview()"
              />
            </el-tooltip>
            <el-tooltip content="AI翻译" placement="top">
              <el-button
                size="small"
                circle
                :icon="MagicStick"
                @click="aiFillItemReviewI18n()"
              />
            </el-tooltip>
          </el-button-group>
        </div>
      </div>
      <template #footer>
        <el-button @click="itemReviewVisible = false" :disabled="itemReviewSubmitting">取消</el-button>
        <el-button type="primary" @click="submitItemReview" :loading="itemReviewSubmitting">提交</el-button>
      </template>
    </el-dialog>

    <!-- 多语言编辑弹窗（en / id） -->
    <el-dialog
      v-model="i18nEditorVisible"
      :title="i18nEditorTitle"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form label-width="80px">
        <el-form-item label="原文">
          <el-input v-model="i18nEditorSourceText" type="textarea" :rows="3" disabled />
        </el-form-item>
        <el-form-item label="en">
          <el-input v-model="i18nEditorValues.en" type="textarea" :rows="3" placeholder="English" />
        </el-form-item>
        <el-form-item label="id">
          <el-input v-model="i18nEditorValues.id" type="textarea" :rows="3" placeholder="Bahasa Indonesia" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="i18nEditorVisible = false" :disabled="i18nEditorLoading">取消</el-button>
        <el-button @click="aiFillI18nInDialog" :loading="i18nEditorLoading">
          <el-icon><MagicStick /></el-icon>
          AI翻译
        </el-button>
        <el-button type="primary" @click="saveI18nEditor" :disabled="i18nEditorLoading">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="aiReviewI18nVisible" title="AI国际化（生成 en / id）" width="520px">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 12px;"
        title="AI 生成的翻译建议人工检查后再保存。"
      />
      <el-form label-width="140px">
        <el-form-item label="覆盖已有翻译">
          <el-switch v-model="aiReviewI18nOverwrite" />
        </el-form-item>
        <el-form-item label="生成后自动保存">
          <el-switch v-model="aiReviewI18nAutoSave" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="aiReviewI18nVisible = false">取消</el-button>
        <el-button type="primary" :loading="aiReviewI18nLoading" @click="runAiReviewI18n">开始生成</el-button>
      </template>
    </el-dialog>

	    <el-dialog
	      v-model="aiReviewI18nProgressVisible"
	      title="AI翻译进度"
      width="520px"
      :show-close="false"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
      <div class="ai-progress">
        <el-progress :percentage="aiReviewI18nProgressPercent" :status="aiReviewI18nProgressBarStatus" />
        <div class="ai-progress-meta">
          <div class="ai-progress-main">
            已完成 {{ aiReviewI18nProgress.done }}/{{ aiReviewI18nProgress.total }}
            <span v-if="aiReviewI18nProgress.batchTotal" class="ai-progress-batch">
              （第 {{ aiReviewI18nProgress.batchIndex }}/{{ aiReviewI18nProgress.batchTotal }} 批）
            </span>
          </div>
          <div class="ai-progress-time" v-if="aiReviewI18nProgress.elapsedSeconds">
            用时 {{ formatDuration(aiReviewI18nProgress.elapsedSeconds) }}
          </div>
        </div>
        <div class="ai-progress-status">{{ aiReviewI18nProgress.message }}</div>
        <el-alert
          v-if="aiReviewI18nProgress.error"
          type="error"
          :closable="false"
          show-icon
          style="margin-top: 12px;"
          :title="aiReviewI18nProgress.error"
        />
      </div>
      <template #footer>
        <el-button v-if="!aiReviewI18nProgress.running" type="primary" @click="closeAiReviewI18nProgress">
          关闭
        </el-button>
      </template>
	    </el-dialog>

	    <el-dialog
	      v-model="aiCheckProgressVisible"
	      title="AI检查进度"
	      width="520px"
	      :show-close="false"
	      :close-on-click-modal="false"
	      :close-on-press-escape="false"
	    >
	      <div class="ai-progress">
	        <el-progress :percentage="aiCheckProgressPercent" :status="aiCheckProgressBarStatus" />
	        <div class="ai-progress-meta">
	          <div class="ai-progress-main">
	            已完成 {{ aiCheckProgress.done }}/{{ aiCheckProgress.total }}
	          </div>
	          <div class="ai-progress-time" v-if="aiCheckProgress.elapsedSeconds">
	            用时 {{ formatDuration(aiCheckProgress.elapsedSeconds) }}
	          </div>
	        </div>
	        <div class="ai-progress-status">{{ aiCheckProgress.message }}</div>
	        <el-alert
	          v-if="aiCheckProgress.error"
	          type="error"
	          :closable="false"
	          show-icon
	          style="margin-top: 12px;"
	          :title="aiCheckProgress.error"
	        />
	      </div>
	      <template #footer>
	        <el-button v-if="!aiCheckProgress.running" type="primary" @click="closeAiCheckProgress">
	          关闭
	        </el-button>
	      </template>
	    </el-dialog>
	  </div>
	</template>

<script setup>
	import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue'
	import { useRoute } from 'vue-router'
	import request from '@/utils/request'
	import { copyTextToClipboard } from '@/utils/clipboard'
	import { ElMessage, ElMessageBox, ElLoading } from 'element-plus'
	import { aiAPI } from '@/api/ai'
		import { ZoomIn, ZoomOut, FullScreen, Aim, Download, Clock, Right, QuestionFilled, ChatDotRound, MagicStick, ArrowDown, CopyDocument, CircleCheckFilled, CircleCloseFilled, WarningFilled } from '@element-plus/icons-vue'
	import { useUserStore } from '@/stores/user'
	import ProgressImage from '@/components/common/ProgressImage.vue'
	import { createObjectUrl, loadImageBlob, revokeObjectUrl, resolveImageUrl } from '@/utils/imageLoader'

const route = useRoute()
const userStore = useUserStore()
const loading = ref(false)
const order = ref(null)
const items = ref([])
const itemsLoading = ref(false)
const summary = ref(null)
const comments = ref('')
const commentsI18n = reactive({ en: '', id: '' })
const reviewListMode = ref('全部')
const scopeFilter = ref('全部范围')
const distanceFilter = ref('全部距离')
const photoDetailVisible = ref(false)
const photoSimilarityDetailVisible = ref(false)
const selectedPhoto = ref(null)
const itemDetailVisible = ref(false)
const selectedItem = ref(null)
const isFullscreen = ref(false)
const zoomLevel = ref(1)
const translateX = ref(0)
const translateY = ref(0)
	const isDragging = ref(false)
	const dragStart = ref({ x: 0, y: 0 })
	const photoImage = ref(null)

	// 照片查看器（大图）加载状态
	const photoViewerStatus = ref('idle') // idle | loading | loaded | error
	const photoViewerProgress = ref(0)
	const photoViewerObjectUrl = ref('')
	const photoViewerLoadToken = ref(0)
	const photoViewerSrc = computed(() => photoViewerObjectUrl.value || '')

	const cleanupPhotoViewerObjectUrl = () => {
	  if (photoViewerObjectUrl.value) revokeObjectUrl(photoViewerObjectUrl.value)
	  photoViewerObjectUrl.value = ''
	}

	const auditHistoryVisible = ref(false)
	const timelineLogs = ref([])
	const expandedLogDetails = ref({})

// 设备状态
const deviceStatusLoading = ref(false)
const devices = ref([])
const deviceStatusCheckedAt = ref(null)
const manualConfirmEnabled = ref(false)
const manualConfirmSubmitting = ref(false)

// 设备更换工单信息（从 work_order.extra_data 中读取）
const replacementTargets = computed(() => {
  const list = order.value?.extra_data?.replacement_targets
  return Array.isArray(list) ? list : []
})

const replacementOldDevices = computed(() => {
  const list = order.value?.extra_data?.replacement_old_devices
  return Array.isArray(list) ? list : []
})

const replacementHistory = computed(() => {
  const list = order.value?.extra_data?.replacement_history
  return Array.isArray(list) ? list : []
})

const replacementInitiatorId = computed(() => {
  const v = order.value?.extra_data?.initiator_id
  return v != null ? String(v) : ''
})

const replacementReturnCandidates = computed(() => {
  const sns = []
  for (const row of replacementHistory.value || []) {
    const sn = String(row?.old_sn || '').trim()
    if (sn) sns.push(sn)
  }
  for (const row of replacementOldDevices.value || []) {
    const sn = String(row?.old_sn || '').trim()
    if (sn) sns.push(sn)
  }
  return Array.from(new Set(sns))
})

const selectedReturnSns = ref([])
const returnSubmitting = ref(false)

watch(
  () => order.value?.id,
  () => {
    selectedReturnSns.value = []
  }
)

const createReturnByActual = async () => {
  const id = order.value?.id
  const sns = Array.isArray(selectedReturnSns.value) ? selectedReturnSns.value : []
  const picked = Array.from(new Set(sns.map(s => String(s || '').trim()).filter(Boolean)))
  if (!picked.length) return
  if (!id) return

  try {
    returnSubmitting.value = true
    const res = await request.post('/api/stock/returns/by-actual', {
      main_sns: picked,
      work_order_id: id,
      notes: '设备更换退库申请',
    })
    const mainCnt = Number(res?.summary?.main_device_count || picked.length)
    const splitCnt = Number(res?.created_count || 0)
    ElMessage.success(`已发起退库申请（主设备 ${mainCnt} 台，拆分 ${splitCnt || 1} 单）`)
    selectedReturnSns.value = []
  } catch (e) {
    console.error(e)
    const detail = e?.response?.data?.detail
    const msg = typeof detail === 'string'
      ? detail
      : detail?.reason || detail?.message || detail?.detail || '发起退库失败'
    ElMessage.error(msg)
  } finally {
    returnSubmitting.value = false
  }
}

// 检查项逐条审核（自定义弹窗）
const itemReviewVisible = ref(false)
const itemReviewRow = ref(null)
const itemReviewAction = ref('pass')
const itemReviewComments = ref('')
const itemReviewCommentsI18n = reactive({ en: '', id: '' })
const itemReviewSubmitting = ref(false)

// 多语言编辑弹窗（复用）
const i18nEditorVisible = ref(false)
const i18nEditorTitle = ref('多语言')
const i18nEditorSourceText = ref('')
const i18nEditorValues = reactive({ en: '', id: '' })
const i18nEditorLoading = ref(false)
const i18nEditorTargetMap = ref(null)

// 一键 AI 国际化（审核意见）
const aiReviewI18nVisible = ref(false)
const aiReviewI18nOverwrite = ref(false)
const aiReviewI18nAutoSave = ref(true)
const aiReviewI18nLoading = ref(false)
const aiReviewI18nProgressVisible = ref(false)
const aiReviewI18nProgress = reactive({
  total: 0,
  done: 0,
  batchIndex: 0,
  batchTotal: 0,
  message: '',
  error: '',
  running: false,
  elapsedSeconds: 0,
})

let aiReviewI18nProgressTimer = null
let aiReviewI18nProgressStartedAt = 0

const aiReviewI18nProgressPercent = computed(() => {
  if (!aiReviewI18nProgress.total) return 0
  const v = Math.floor((aiReviewI18nProgress.done / aiReviewI18nProgress.total) * 100)
  return Math.min(100, Math.max(0, v))
})

const aiReviewI18nProgressBarStatus = computed(() => {
  if (aiReviewI18nProgress.error) return 'exception'
  if (!aiReviewI18nProgress.running && aiReviewI18nProgress.total > 0 && aiReviewI18nProgress.done >= aiReviewI18nProgress.total) return 'success'
  return ''
})

const startAiReviewI18nProgressTimer = () => {
  if (aiReviewI18nProgressTimer) {
    clearInterval(aiReviewI18nProgressTimer)
    aiReviewI18nProgressTimer = null
  }
  aiReviewI18nProgressStartedAt = Date.now()
  aiReviewI18nProgress.elapsedSeconds = 0
  aiReviewI18nProgressTimer = setInterval(() => {
    aiReviewI18nProgress.elapsedSeconds = Math.max(
      0,
      Math.floor((Date.now() - aiReviewI18nProgressStartedAt) / 1000),
    )
  }, 1000)
}

const stopAiReviewI18nProgressTimer = () => {
  if (!aiReviewI18nProgressTimer) return
  clearInterval(aiReviewI18nProgressTimer)
  aiReviewI18nProgressTimer = null
}

const closeAiReviewI18nProgress = () => {
  if (aiReviewI18nProgress.running) return
  aiReviewI18nProgressVisible.value = false
  aiReviewI18nProgress.message = ''
  aiReviewI18nProgress.error = ''
}

	const formatDuration = (seconds) => {
	  const s = Math.max(0, Number(seconds || 0))
	  const m = Math.floor(s / 60)
	  const r = s % 60
	  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`
	}

	// 一键 AI 检查（检查项）
	const aiCheckProgressVisible = ref(false)
	const aiCheckProgress = reactive({
	  total: 0,
	  done: 0,
	  message: '',
	  error: '',
	  running: false,
	  elapsedSeconds: 0,
	})

	let aiCheckProgressTimer = null
	let aiCheckProgressStartedAt = 0

	const aiCheckProgressPercent = computed(() => {
	  if (!aiCheckProgress.total) return 0
	  const v = Math.floor((aiCheckProgress.done / aiCheckProgress.total) * 100)
	  return Math.min(100, Math.max(0, v))
	})

	const aiCheckProgressBarStatus = computed(() => {
	  if (aiCheckProgress.error) return 'exception'
	  if (!aiCheckProgress.running && aiCheckProgress.total > 0 && aiCheckProgress.done >= aiCheckProgress.total) return 'success'
	  return ''
	})

	const startAiCheckProgressTimer = () => {
	  if (aiCheckProgressTimer) {
	    clearInterval(aiCheckProgressTimer)
	    aiCheckProgressTimer = null
	  }
	  aiCheckProgressStartedAt = Date.now()
	  aiCheckProgress.elapsedSeconds = 0
	  aiCheckProgressTimer = setInterval(() => {
	    aiCheckProgress.elapsedSeconds = Math.max(
	      0,
	      Math.floor((Date.now() - aiCheckProgressStartedAt) / 1000),
	    )
	  }, 1000)
	}

	const stopAiCheckProgressTimer = () => {
	  if (!aiCheckProgressTimer) return
	  clearInterval(aiCheckProgressTimer)
	  aiCheckProgressTimer = null
	}

	const closeAiCheckProgress = () => {
	  if (aiCheckProgress.running) return
	  aiCheckProgressVisible.value = false
	  aiCheckProgress.message = ''
	  aiCheckProgress.error = ''
	}

const statuses = [
  { label: '待分配', value: 'PENDING' },
  { label: '已分配', value: 'ACTIVE' },
  { label: '已提交', value: 'SUBMITTED' },
  { label: '审核中', value: 'UNDER_REVIEW' },
  { label: '已通过/待上线', value: 'APPROVED' },
  { label: '已开通(上线阶段)', value: 'ACTIVATED' },
  { label: '已驳回', value: 'REJECTED' },
  { label: '已完成', value: 'COMPLETED' },
  { label: '已作废', value: 'VOIDED' },
]
const VOIDABLE_STATUSES = ['PENDING', 'ACTIVE', 'SUBMITTED', 'UNDER_REVIEW', 'REJECTED']
const types = [
  { label: '新站点设备安装', value: 'opening_inspection' },
  { label: '设备更换', value: 'equipment_replacement' },
  { label: '维护检查', value: 'maintenance' },
  { label: '断电问题', value: 'power_issue' },
  { label: '传输问题', value: 'transmission_issue' },
  { label: 'GPS问题', value: 'gps_issue' },
  { label: '信号问题', value: 'signal_issue' },
  { label: '站点勘察', value: 'site_survey' },
  { label: 'SSV 验收', value: 'ssv' },
]

const isVoided = computed(() => order.value?.status === 'VOIDED')
const canStartReview = computed(() => order.value && order.value.status === 'SUBMITTED')
const canFinalReview = computed(() => order.value && ['SUBMITTED','UNDER_REVIEW'].includes(order.value.status))
const canVoidCurrentOrder = computed(() => {
  return !!order.value && userStore.hasPermission('workorder:void:write') && VOIDABLE_STATUSES.includes(order.value.status)
})

const checkItemStatusText = (status) => {
  const value = (status ?? '').toString()
  const mapping = {
    pending: '待处理',
    in_progress: '进行中',
    completed: '已完成',
    failed: '失败',
    skipped: '跳过',
  }
  return mapping[value] || (value || '-')
}

	const checkItemStatusTagType = (status) => {
	  const value = (status ?? '').toString()
	  const mapping = {
	    pending: 'info',
	    in_progress: 'warning',
	    completed: 'success',
	    failed: 'danger',
	    skipped: 'info',
	  }
	  return mapping[value] || 'info'
	}

	const aiSuggestedStatusText = (status) => {
	  const v = String(status || '').trim()
	  const mapping = {
	    pass: '通过',
	    warning: '警告',
	    fail: '不合格',
	  }
	  return mapping[v] || (v || '-')
	}

	const aiSuggestedTagType = (status) => {
	  const v = String(status || '').trim()
	  const mapping = {
	    pass: 'success',
	    warning: 'warning',
	    fail: 'danger',
	  }
	  return mapping[v] || 'info'
	}

	const canApplyAi = (row) => {
	  if (isVoided.value) return false
	  if (!row) return false
	  if (row.review_status === 'pass' || row.review_status === 'warning' || row.review_status === 'fail') return false
	  const status = String(row.status || '').trim()
	  if (status !== 'completed') return false
	  if (String(row.ai_status || '') !== 'done') return false
	  const suggested = row.ai_result?.suggested_review_status
	  return ['pass', 'warning', 'fail'].includes(String(suggested || '').trim())
	}

const canReviewCheckItem = (item) => {
  if (isVoided.value) return false
  const status = (item?.status ?? '').toString()
  return status === 'completed'
}

const toBool = (value) => {
  if (value === true || value === false) return value
  if (typeof value === 'number') return value === 1
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase()
    return normalized === 'true' || normalized === '1' || normalized === 'yes'
  }
  return false
}

const getPhotoLocationCompare = (photo) => {
  if (!photo || typeof photo !== 'object') return null
  const rawCompare = photo?.watermark_data?.location_compare || photo?.location_compare
  if (!rawCompare || typeof rawCompare !== 'object') return null

  const distanceToPlanRaw = Number(rawCompare.distance_to_plan_m)
  const thresholdRaw = Number(rawCompare.distance_threshold_m)
  const hasDistance = Number.isFinite(distanceToPlanRaw) && distanceToPlanRaw >= 0
  const hasThreshold = Number.isFinite(thresholdRaw) && thresholdRaw > 0
  const exceeded = toBool(rawCompare.distance_exceeded)
  const planCoordinateMissing = toBool(rawCompare.plan_coordinate_missing)

  const plannedCoordinatesText = (() => {
    const text = String(rawCompare.planned_coordinates || '').trim()
    if (text) return text
    const lat = Number(rawCompare.planned_latitude)
    const lon = Number(rawCompare.planned_longitude)
    if (Number.isFinite(lat) && Number.isFinite(lon)) {
      return `${lat.toFixed(6)}, ${lon.toFixed(6)}`
    }
    return ''
  })()

  return {
    distanceToPlanM: hasDistance ? distanceToPlanRaw : null,
    thresholdM: hasThreshold ? thresholdRaw : null,
    exceeded,
    planCoordinateMissing,
    plannedCoordinatesText,
    compared: hasDistance || planCoordinateMissing || plannedCoordinatesText !== '',
  }
}

const getItemLocationCompareStats = (item) => {
  const photos = Array.isArray(item?.photos) ? item.photos : []
  const stats = {
    comparedCount: 0,
    exceededCount: 0,
    missingPlanCount: 0,
    maxDistanceM: null,
  }

  photos.forEach((photo) => {
    const compare = getPhotoLocationCompare(photo)
    if (!compare || compare.compared !== true) return
    stats.comparedCount += 1
    if (compare.exceeded === true) {
      stats.exceededCount += 1
    }
    if (compare.planCoordinateMissing === true) {
      stats.missingPlanCount += 1
    }
    if (Number.isFinite(compare.distanceToPlanM)) {
      const v = Number(compare.distanceToPlanM)
      stats.maxDistanceM = stats.maxDistanceM === null ? v : Math.max(stats.maxDistanceM, v)
    }
  })

  return stats
}

const checkItemReviewDisabledReason = (item) => {
  if (isVoided.value) return '工单已作废，不能继续审核检查项'
  const statusText = checkItemStatusText(item?.status)
  return `该检查项未完成提交（当前：${statusText}），无法审核`
}

// 检查是否有不合格的检查项
const hasFailedItems = computed(() => {
  return items.value.some(item => item.review_status === 'fail')
})

const getItemScopeLevel = (item) => {
  if (!item) return '站点'
  const equipmentSn = String(item?.equipment_sn || '').trim()
  if (equipmentSn) return '设备'
  const cellId = String(item?.cell_id || '').trim()
  if (cellId) return '小区'
  const sectorId = String(item?.sector_id || '').trim()
  if (sectorId) return '扇区'
  const band = String(item?.band || '').trim()
  if (band) return '小区'
  return '站点'
}

const scopeTagType = (item) => {
  const level = getItemScopeLevel(item)
  if (level === '设备') return 'success'
  if (level === '小区') return 'primary'
  if (level === '扇区') return 'warning'
  return 'info'
}

const copyToClipboard = async (text) => {
  const v = String(text || '').trim()
  if (!v) return
  const ok = await copyTextToClipboard(v)
  if (ok) {
    ElMessage.success('SN已复制到剪贴板')
    return
  }
  ElMessage.error('复制失败')
}

const handleAiAction = (command, row) => {
  const cmd = String(command || '').trim()
  if (!row) return
  if (cmd === 'check') {
    aiCheckSingle(row)
    return
  }
  if (cmd === 'apply') {
    applyAiSuggestion(row)
  }
}

const handleReviewAction = (command, row) => {
  const cmd = String(command || '').trim()
  if (!row) return
  if (!['pass', 'warning', 'fail'].includes(cmd)) return
  reviewItem(row, cmd)
}

const displayedItems = computed(() => {
  let list = items.value
  if (reviewListMode.value === '仅看需复审') {
    list = list.filter(item => !item.review_status || item.review_status === 'pending')
  }
  if (scopeFilter.value && scopeFilter.value !== '全部范围') {
    list = list.filter(item => getItemScopeLevel(item) === scopeFilter.value)
  }
  if (distanceFilter.value === '仅超距') {
    list = list.filter((item) => getItemLocationCompareStats(item).exceededCount > 0)
  }
  return list
})

const selectedPhotoLocationCompare = computed(() => {
  return getPhotoLocationCompare(selectedPhoto.value)
})

const getPhotoDuplicateInfo = (photo) => {
  const info = photo?.duplicate_info
  return info && typeof info === 'object' ? info : null
}

const getPhotoDuplicateBrief = (photo) => {
  const info = getPhotoDuplicateInfo(photo)
  if (!photo?.is_duplicate_global || !info) return ''
  const site = info.site_display || info.site_name || (info.site_id ? `站点ID:${info.site_id}` : '未知站点')
  const uploader = info.uploader_display || info.uploader_name || (info.uploader_id ? `用户ID:${info.uploader_id}` : '未知用户')
  const time = info.uploaded_at || '-'
  return `重复来源：${site} / ${uploader} / ${time}`
}

const getPhotoDuplicateSourceLine = (photo) => {
  const info = getPhotoDuplicateInfo(photo)
  if (!photo?.is_duplicate_global || !info) return ''
  const source = info.source_type_label || info.source_type || '未知来源'
  const sourceId = info.source_id || '-'
  return `来源：${source}（ID: ${sourceId}）`
}

const getItemDuplicateStats = (item) => {
  const photos = Array.isArray(item?.photos) ? item.photos : []
  const duplicatePhotos = photos.filter((p) => p?.is_duplicate_global)
  return {
    count: duplicatePhotos.length,
    duplicatePhotos,
  }
}

const getItemDuplicateHintLines = (item) => {
  const stats = getItemDuplicateStats(item)
  return stats.duplicatePhotos.slice(0, 3).map((photo, idx) => {
    const name = photo?.original_name || `图片${idx + 1}`
    const brief = getPhotoDuplicateBrief(photo)
    return brief ? `${name}: ${brief}` : `${name}: 检测到重复来源`
  })
}

const duplicatePhotoSummary = computed(() => {
  let total = 0
  let itemsWithDup = 0
  ;(items.value || []).forEach((item) => {
    const count = getItemDuplicateStats(item).count
    if (count > 0) {
      itemsWithDup += 1
      total += count
    }
  })
  return { total, items: itemsWithDup }
})

const getPhotoSimilarInfo = (photo) => {
  const info = photo?.similar_info
  return info && typeof info === 'object' ? info : null
}

const getPhotoSimilarityEvaluation = (photo) => {
  const info = getPhotoSimilarInfo(photo)
  const evaluation = info?.evaluation
  return evaluation && typeof evaluation === 'object' ? evaluation : null
}

const SIMILARITY_REASON_TEXT_MAP = {
  POLICY_DISABLED: '当前未启用相似度校验，本次仅保存图片，不做相似风险判断。',
  MISSING_QUERY_PHASH: '当前图片特征提取不完整，无法完成相似度比较。',
  MISSING_QUERY_VECTOR: '当前图片精细特征提取失败，无法完成相似度比较。',
  NO_CANDIDATES: '在配置的时间窗口内，没有可比较的历史照片。',
  NO_PHASH_MATCH: '历史照片存在，但基础外观差异较大，未进入高风险候选。',
  NO_VECTOR_MATCH: '存在外观接近的历史照片，但未达到高风险提醒标准。',
  NO_MATCH: '本次未发现需要提醒的高相似风险。',
  MATCHED: '检测到高相似风险，建议结合站点与工单信息重点复核。',
}

const formatSimilarityCandidateLine = (candidate) => {
  if (!candidate || typeof candidate !== 'object') return '未找到可说明的历史候选'
  const site = candidate.site_display || candidate.site_name || (candidate.site_id ? `站点ID:${candidate.site_id}` : '未知站点')
  const uploader = candidate.uploader_display || candidate.uploader_name || (candidate.uploader_id ? `用户ID:${candidate.uploader_id}` : '未知用户')
  const time = candidate.uploaded_at || '-'
  const percent = Number(candidate.similarity_percent)
  const percentText = Number.isFinite(percent) ? ` / 相似度${percent.toFixed(2)}%` : ''
  const distance = Number(candidate.phash_distance)
  const distanceText = Number.isFinite(distance) ? ` / 粗筛差异值${distance}` : ''
  return `${site} / ${uploader} / ${time}${percentText}${distanceText}`
}

const pickBestSimilarityCandidate = (photo) => {
  const info = getPhotoSimilarInfo(photo)
  const evaluation = getPhotoSimilarityEvaluation(photo)
  if (evaluation?.matched_candidate) return evaluation.matched_candidate
  if (evaluation?.best_similarity_candidate) return evaluation.best_similarity_candidate
  if (evaluation?.closest_phash_candidate) return evaluation.closest_phash_candidate

  if (info?.matched_photo_id || info?.site_display || info?.site_name || info?.uploader_display || info?.uploader_name) {
    return {
      photo_id: info.matched_photo_id || null,
      site_id: info.site_id || null,
      site_name: info.site_name || null,
      site_display: info.site_display || null,
      uploader_id: info.uploader_id || null,
      uploader_name: info.uploader_name || null,
      uploader_display: info.uploader_display || null,
      uploaded_at: info.uploaded_at || null,
      similarity_percent: info.similarity_percent,
      phash_distance: info.phash_distance,
    }
  }
  return null
}

const getPhotoSimilarBrief = (photo) => {
  const info = getPhotoSimilarInfo(photo)
  if (!photo?.is_similar_risk || !info) return ''
  const site = info.site_display || info.site_name || (info.site_id ? `站点ID:${info.site_id}` : '未知站点')
  const uploader = info.uploader_display || info.uploader_name || (info.uploader_id ? `用户ID:${info.uploader_id}` : '未知用户')
  const time = info.uploaded_at || '-'
  const percent = Number(info.similarity_percent)
  const percentText = Number.isFinite(percent) ? ` / 相似度:${percent.toFixed(2)}%` : ''
  return `相似来源：${site} / ${uploader} / ${time}${percentText}`
}

const getPhotoSimilarSourceLine = (photo) => {
  const info = getPhotoSimilarInfo(photo)
  if (!photo?.is_similar_risk || !info) return ''
  const source = info.source_type_label || info.source_type || '未知来源'
  const matchedPhotoId = info.matched_photo_id || '-'
  const phashDistance = Number(info.phash_distance)
  const distanceText = Number.isFinite(phashDistance) ? `，pHash距离: ${phashDistance}` : ''
  return `来源：${source}（匹配照片ID: ${matchedPhotoId}${distanceText}）`
}

const getItemSimilarStats = (item) => {
  const photos = Array.isArray(item?.photos) ? item.photos : []
  const similarPhotos = photos.filter((p) => p?.is_similar_risk)
  return {
    count: similarPhotos.length,
    similarPhotos,
  }
}

const getItemSimilarHintLines = (item) => {
  const stats = getItemSimilarStats(item)
  return stats.similarPhotos.slice(0, 3).map((photo, idx) => {
    const name = photo?.original_name || `图片${idx + 1}`
    const brief = getPhotoSimilarBrief(photo)
    return brief ? `${name}: ${brief}` : `${name}: 检测到高相似来源`
  })
}

const similarPhotoSummary = computed(() => {
  let total = 0
  let itemsWithRisk = 0
  ;(items.value || []).forEach((item) => {
    const count = getItemSimilarStats(item).count
    if (count > 0) {
      itemsWithRisk += 1
      total += count
    }
  })
  return { total, items: itemsWithRisk }
})

const selectedPhotoSimilarityEvaluation = computed(() => getPhotoSimilarityEvaluation(selectedPhoto.value))

const selectedPhotoSimilarityReasonCode = computed(() => {
  const evaluation = selectedPhotoSimilarityEvaluation.value
  if (evaluation?.reason_code) return String(evaluation.reason_code)
  return selectedPhoto.value?.is_similar_risk ? 'MATCHED' : 'NO_MATCH'
})

const selectedPhotoSimilarityDecisionText = computed(() => {
  const isRisk = selectedPhoto.value?.is_similar_risk === true
  if (isRisk) return '检测到高相似风险（建议复核）'
  const reasonCode = selectedPhotoSimilarityReasonCode.value
  return SIMILARITY_REASON_TEXT_MAP[reasonCode] || '未触发高相似风险提醒'
})

const selectedPhotoSimilarityWindowText = computed(() => {
  const evaluation = selectedPhotoSimilarityEvaluation.value
  const days = Number(evaluation?.window_days)
  if (Number.isFinite(days) && days > 0) return `仅比较最近 ${days} 天内上传的检查项照片`
  return '未记录时间窗口（可能为历史数据）'
})

const selectedPhotoSimilarityThresholdText = computed(() => {
  const evaluation = selectedPhotoSimilarityEvaluation.value
  const phashThreshold = Number(evaluation?.phash_threshold)
  const vectorThreshold = Number(evaluation?.vector_threshold)
  const phashText = Number.isFinite(phashThreshold) ? `快速筛选阈值 ${phashThreshold}` : '快速筛选阈值 -'
  const vectorText = Number.isFinite(vectorThreshold) ? `精细比对阈值 ${(vectorThreshold * 100).toFixed(2)}%` : '精细比对阈值 -'
  return `${phashText} / ${vectorText}`
})

const selectedPhotoSimilarityCandidateText = computed(() => {
  const evaluation = selectedPhotoSimilarityEvaluation.value
  if (!evaluation) return '暂无候选筛选数据（可能为历史数据）'
  const total = Number(evaluation.candidate_total)
  const phashPass = Number(evaluation.candidate_phash_pass)
  const vectorPass = Number(evaluation.candidate_vector_pass)
  const totalText = Number.isFinite(total) ? `${total}` : '-'
  const phashPassText = Number.isFinite(phashPass) ? `${phashPass}` : '-'
  const vectorPassText = Number.isFinite(vectorPass) ? `${vectorPass}` : '-'
  return `共扫描 ${totalText} 张历史照片；快速筛选通过 ${phashPassText} 张；精细比对通过 ${vectorPassText} 张`
})

const selectedPhotoSimilarityBestMatchText = computed(() => {
  const bestCandidate = pickBestSimilarityCandidate(selectedPhoto.value)
  return formatSimilarityCandidateLine(bestCandidate)
})

const selectedPhotoSimilarityAdviceText = computed(() => {
  if (selectedPhoto.value?.is_similar_risk) {
    return '建议到详情页核对站点、上传人、上传时间，并结合现场情况判断是否复用历史照片。'
  }
  return '当前未命中高风险提醒。如对结果有疑问，可适度放宽阈值后再次测试。'
})

const selectedPhotoSimilarityConclusionText = computed(() => {
  if (selectedPhoto.value?.is_similar_risk) {
    return '已命中高相似风险：建议重点复核该照片是否复用历史素材。'
  }
  return '未命中高相似风险：系统未发现需要预警的历史复用迹象。'
})

const selectedPhotoSimilarityRiskTagType = computed(() => {
  return selectedPhoto.value?.is_similar_risk ? 'error' : 'success'
})

const selectedPhotoSimilarityHumanLines = computed(() => {
  const lines = []
  const reasonCode = selectedPhotoSimilarityReasonCode.value
  const reasonText = SIMILARITY_REASON_TEXT_MAP[reasonCode]
  if (reasonText) lines.push(reasonText)
  lines.push(selectedPhotoSimilarityCandidateText.value)
  lines.push(`最接近历史照片：${selectedPhotoSimilarityBestMatchText.value}`)
  return lines
})

const selectedPhotoSimilarityDebugData = computed(() => {
  const photo = selectedPhoto.value || {}
  return {
    raw_photo_payload: photo,
    similar_validation: {
      is_similar_risk: !!photo?.is_similar_risk,
      similar_info: getPhotoSimilarInfo(photo),
      evaluation: selectedPhotoSimilarityEvaluation.value,
      reason_code: selectedPhotoSimilarityReasonCode.value,
    },
    duplicate_validation: {
      is_duplicate_global: !!photo?.is_duplicate_global,
      duplicate_info: getPhotoDuplicateInfo(photo),
    },
    feature_fields: {
      content_hash: photo?.content_hash ?? null,
      original_content_hash: photo?.original_content_hash ?? null,
      content_phash: photo?.content_phash ?? null,
      content_vector_backend: photo?.content_vector_backend ?? null,
      hash_value: photo?.hash_value ?? null,
    },
  }
})

const selectedPhotoSimilarityDebugJson = computed(() => {
  return JSON.stringify(selectedPhotoSimilarityDebugData.value, null, 2)
})

// 检查是否有未审核的检查项
const hasPendingItems = computed(() => {
  return items.value.some(item => !item.review_status || item.review_status === 'pending')
})

// 获取未审核检查项的数量
const pendingItemsCount = computed(() => {
  return items.value.filter(item => !item.review_status || item.review_status === 'pending').length
})

const reviewHeaderHint = computed(() => {
  if (isVoided.value) {
    return {
      type: 'warning',
      text: '工单已作废',
      tooltip: '该工单已作废，审核与编辑操作均已冻结。',
      icon: WarningFilled,
    }
  }
  if (hasPendingItems.value) {
    const count = pendingItemsCount.value
    return {
      type: 'warning',
      text: `未审核 ${count} 项`,
      tooltip: `还有 ${count} 项检查项未完成审核，请先完成所有检查项的审核，再进行最终审核。`,
      icon: WarningFilled,
    }
  }
  if (hasFailedItems.value) {
    return {
      type: 'danger',
      text: '存在不合格',
      tooltip: '存在不合格检查项，工单无法通过审核。',
      icon: CircleCloseFilled,
    }
  }
  return {
    type: 'success',
    text: '可最终审核',
    tooltip: '所有检查项已审核完成，可以进行最终审核。',
    icon: CircleCheckFilled,
  }
})

// 只有在没有不合格检查项时才能通过
const canApprove = computed(() => {
  return canFinalReview.value && !hasFailedItems.value && !hasPendingItems.value
})

// 允许直接驳回（即使存在未完成/未审核项）
const canReject = computed(() => {
  return canFinalReview.value
})

const statusTagType = (status) => {
  if (status === 'VOIDED') return 'info'
  if (status === 'REJECTED') return 'danger'
  if (['SUBMITTED', 'UNDER_REVIEW'].includes(status)) return 'warning'
  if (['APPROVED', 'ACTIVATED', 'COMPLETED'].includes(status)) return 'success'
  if (status === 'ACTIVE') return 'primary'
  return ''
}

const refresh = async () => {
  const id = route.query.id
  if (!id) return
  try {
    loading.value = true
    // 先加载工单信息
    order.value = await request.get(`/api/work-orders/${id}`)
    // 回填审核意见（含多语言）
    comments.value = order.value?.review_comments || ''
    commentsI18n.en = order.value?.review_comments_i18n?.en || ''
    commentsI18n.id = order.value?.review_comments_i18n?.id || ''
    // 然后基于工单信息加载相关数据
    await Promise.all([loadItems(), loadSummary(), loadDeviceStatus(false)])
  } catch (e) {
    console.error(e)
    ElMessage.error('加载工单失败')
  } finally {
    loading.value = false
  }
}

const loadItems = async () => {
  const id = route.query.id
  if (!id) return
  try {
    itemsLoading.value = true
    // 如果工单有关联的检查，优先加载检查的检查项
    if (order.value && order.value.inspection_id) {
      items.value = await request.get(`/api/inspections/detail/${order.value.inspection_id}/items`)
    } else {
      // 否则加载工单自己的检查项
      items.value = await request.get(`/api/work-orders/${id}/items`)
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('加载检查项失败')
  } finally {
    itemsLoading.value = false
  }
}


const loadSummary = async () => {
  const id = route.query.id
  if (!id) return
  try {
    summary.value = await request.get(`/api/work-orders/${id}/review-summary`)
  } catch (e) {
    // ignore
  }
}

// ===== 多语言与 AI（审核意见）=====
const normalizeI18nPayload = (map) => {
  if (!map || typeof map !== 'object') return undefined
  const en = String(map.en || '').trim()
  const id = String(map.id || '').trim()
  if (!en && !id) return undefined
  return { en, id }
}

const openI18nEditor = ({ title, sourceText, targetMap }) => {
  i18nEditorTitle.value = title || '多语言'
  i18nEditorSourceText.value = String(sourceText || '')
  i18nEditorTargetMap.value = targetMap
  i18nEditorValues.en = String(targetMap?.en || '')
  i18nEditorValues.id = String(targetMap?.id || '')
  i18nEditorVisible.value = true
}

const saveI18nEditor = () => {
  const targetMap = i18nEditorTargetMap.value
  if (targetMap && typeof targetMap === 'object') {
    targetMap.en = i18nEditorValues.en || ''
    targetMap.id = i18nEditorValues.id || ''
  }
  i18nEditorVisible.value = false
}

const aiFillI18n = async (sourceText, targetMap) => {
  const text = String(sourceText || '').trim()
  if (!text) {
    ElMessage.warning('原文为空，无法生成翻译')
    return
  }
  if (!targetMap || typeof targetMap !== 'object') return

  const loadingInstance = ElLoading.service({ text: 'AI 翻译中...' })
  try {
    const res = await aiAPI.translateBatch({
      items: [
        { key: 'comments:en', text, target_locale: 'en' },
        { key: 'comments:id', text, target_locale: 'id' },
      ],
    })
    const items = res?.items || []
    targetMap.en = items?.[0]?.translation ?? ''
    targetMap.id = items?.[1]?.translation ?? ''
    ElMessage.success('AI 翻译已生成')
  } catch (error) {
    console.error('AI 翻译失败:', error)
    ElMessage.error(error?.response?.data?.detail || 'AI 翻译失败')
  } finally {
    loadingInstance.close()
  }
}

const aiFillI18nInDialog = async () => {
  const text = String(i18nEditorSourceText.value || '').trim()
  if (!text) {
    ElMessage.warning('原文为空，无法生成翻译')
    return
  }
  i18nEditorLoading.value = true
  try {
    const res = await aiAPI.translateBatch({
      items: [
        { key: 'comments:en', text, target_locale: 'en' },
        { key: 'comments:id', text, target_locale: 'id' },
      ],
    })
    const items = res?.items || []
    i18nEditorValues.en = items?.[0]?.translation ?? ''
    i18nEditorValues.id = items?.[1]?.translation ?? ''
    ElMessage.success('AI 翻译已生成')
  } catch (error) {
    console.error('AI 翻译失败:', error)
    ElMessage.error(error?.response?.data?.detail || 'AI 翻译失败')
  } finally {
    i18nEditorLoading.value = false
  }
}

const openI18nEditorForFinalReview = () => {
  openI18nEditor({ title: '审核意见', sourceText: comments.value, targetMap: commentsI18n })
}

const aiFillFinalReviewI18n = async () => {
  await aiFillI18n(comments.value, commentsI18n)
}

const openI18nEditorForItemReview = () => {
  openI18nEditor({ title: '检查项审核意见', sourceText: itemReviewComments.value, targetMap: itemReviewCommentsI18n })
}

const aiFillItemReviewI18n = async () => {
  await aiFillI18n(itemReviewComments.value, itemReviewCommentsI18n)
}

const ensureI18nMap = (targetObj, i18nKey) => {
  if (!targetObj) return null
  const cur = targetObj[i18nKey]
  if (!cur || typeof cur !== 'object' || Array.isArray(cur)) {
    targetObj[i18nKey] = {}
  }
  return targetObj[i18nKey]
}

const openAiReviewI18n = () => {
  aiReviewI18nOverwrite.value = false
  aiReviewI18nAutoSave.value = true
  aiReviewI18nVisible.value = true
}

const runAiReviewI18n = async () => {
  const overwrite = aiReviewI18nOverwrite.value === true
  const autoSave = aiReviewI18nAutoSave.value === true

  const tasks = []
  const appliers = []
  const dirtyItemIds = new Set()
  let dirtyWorkOrder = false

  const push = (targetMap, sourceText, locale, keyPrefix, markDirty) => {
    const text = String(sourceText || '').trim()
    if (!text) return
    const existing = targetMap?.[locale]
    if (!overwrite && existing && String(existing).trim()) return
    const key = `${keyPrefix || 'comments'}:${locale}`
    tasks.push({ key, text, target_locale: locale })
    appliers.push((translation) => {
      targetMap[locale] = translation ?? ''
    })
    if (typeof markDirty === 'function') markDirty()
  }

  // 最终审核意见（本地生成；是否落库取决于是否已提交/是否一致）
  push(commentsI18n, comments.value, 'en', 'wo:final', () => { dirtyWorkOrder = true })
  push(commentsI18n, comments.value, 'id', 'wo:final', () => { dirtyWorkOrder = true })

  // 检查项审核意见（全部）
  items.value.forEach((it, idx) => {
    const base = String(it?.review_comments || '').trim()
    if (!base) return
    const map = ensureI18nMap(it, 'review_comments_i18n')
    if (!map) return
    const keyBase = `item:${idx}:${it.id || ''}`
    const markDirty = () => dirtyItemIds.add(it.id)
    push(map, base, 'en', keyBase, markDirty)
    push(map, base, 'id', keyBase, markDirty)
  })

  if (!tasks.length) {
    ElMessage.info('没有需要 AI 生成的多语言内容')
    aiReviewI18nVisible.value = false
    return
  }

  aiReviewI18nLoading.value = true
  aiReviewI18nVisible.value = false
  aiReviewI18nProgressVisible.value = true
  aiReviewI18nProgress.total = tasks.length
  aiReviewI18nProgress.done = 0
  aiReviewI18nProgress.batchIndex = 0
  aiReviewI18nProgress.batchTotal = 0
  aiReviewI18nProgress.message = '准备开始...'
  aiReviewI18nProgress.error = ''
  aiReviewI18nProgress.running = true
  startAiReviewI18nProgressTimer()

  try {
    const slowWarnSeconds = 60
    const warnedOnce = { value: false }
    const getBatchSize = (total) => {
      if (total <= 20) return 5
      if (total <= 60) return 10
      if (total <= 120) return 20
      return Math.min(200, 20 + 10 * Math.ceil((total - 120) / 100))
    }
    const batchSize = getBatchSize(tasks.length)
    const batchTotal = Math.max(1, Math.ceil(tasks.length / batchSize))
    aiReviewI18nProgress.batchTotal = batchTotal

    const yieldEvery = tasks.length <= 100 ? 1 : tasks.length <= 300 ? 5 : 10
    let batchIndex = 0
    for (let i = 0; i < tasks.length; i += batchSize) {
      batchIndex += 1
      aiReviewI18nProgress.batchIndex = batchIndex
      const sliceTasks = tasks.slice(i, i + batchSize)
      const sliceAppliers = appliers.slice(i, i + batchSize)
      aiReviewI18nProgress.message = `请求翻译中...（第 ${batchIndex}/${batchTotal} 批，${sliceTasks.length} 条）`

      const slowTimer = setTimeout(() => {
        aiReviewI18nProgress.message = `本批次请求耗时较长（已等待超过 ${slowWarnSeconds} 秒），请继续等待...（第 ${batchIndex}/${batchTotal} 批）`
        if (!warnedOnce.value) {
          warnedOnce.value = true
          ElMessage.warning('AI 翻译耗时较长，请耐心等待...')
        }
      }, slowWarnSeconds * 1000)

      let res
      try {
        res = await aiAPI.translateBatch({ items: sliceTasks })
      } finally {
        clearTimeout(slowTimer)
      }

      const respItems = res?.items || []
      aiReviewI18nProgress.message = `写入翻译结果...（第 ${batchIndex}/${batchTotal} 批）`
      for (let j = 0; j < sliceAppliers.length; j += 1) {
        const translation = respItems?.[j]?.translation ?? ''
        sliceAppliers[j](translation)
        aiReviewI18nProgress.done += 1
        if (yieldEvery === 1 || aiReviewI18nProgress.done % yieldEvery === 0) {
          await nextTick()
        }
      }
    }

    if (autoSave) {
      const id = route.query.id
      if (!id) {
        ElMessage.warning('缺少工单ID，无法自动保存')
      } else {
        const payload = {}

        // 最终审核意见：若已提交且当前输入未被修改，才自动落库（避免翻译与原文不一致）
        if (dirtyWorkOrder) {
          const serverText = normalizeText(order.value?.review_comments)
          const currentText = normalizeText(comments.value)
          if (serverText && serverText === currentText) {
            payload.comments_i18n = normalizeI18nPayload(commentsI18n)
          } else if (currentText) {
            ElMessage.info('最终审核意见翻译已生成，待点击通过/驳回提交时将一并保存')
          }
        }

        if (dirtyItemIds.size) {
          payload.items = Array.from(dirtyItemIds)
            .map((itemId) => {
              const row = items.value.find(x => x?.id === itemId)
              return {
                item_id: itemId,
                comments_i18n: normalizeI18nPayload(row?.review_comments_i18n),
              }
            })
            .filter(x => x && x.item_id && x.comments_i18n)
        }

        if (payload.comments_i18n || (payload.items && payload.items.length)) {
          aiReviewI18nProgress.message = '保存到服务器...'
          await request.post(`/api/work-orders/${id}/review/comments-i18n`, payload)
        }
      }
    }

    aiReviewI18nProgress.message = '已完成'
    aiReviewI18nProgress.running = false
    ElMessage.success(autoSave ? '审核意见多语言已生成并已保存' : '审核意见多语言已生成')
  } catch (error) {
    console.error('AI 翻译失败:', error)
    const detail = error?.response?.data?.detail || error?.message || 'AI 翻译失败'
    aiReviewI18nProgress.error = detail
    aiReviewI18nProgress.message = '已中止'
    aiReviewI18nProgress.running = false
    ElMessage.error(detail)
	} finally {
	  aiReviewI18nLoading.value = false
	  aiReviewI18nProgress.running = false
	  stopAiReviewI18nProgressTimer()
	}
}

const applyAiAnalyzeResultToRow = (row, res) => {
  if (!row || !res) return
  row.ai_status = res.ai_status
  row.ai_mode = res.ai_mode
  row.ai_model = res.ai_model
  row.ai_input_hash = res.ai_input_hash
  row.ai_result = res.ai_result
  row.ai_error = res.ai_error
  row.ai_checked_by = res.ai_checked_by
  row.ai_checked_at = res.ai_checked_at
}

const aiCheckSingle = async (row) => {
  if (!row?.id) return
  const loadingInstance = ElLoading.service({ text: 'AI 检查中...' })
  try {
    const res = await aiAPI.analyzeCheckItem(row.id, {
      mode: 'auto',
      force: false,
      max_images: 5,
      image_detail: 'low',
    })
    applyAiAnalyzeResultToRow(row, res)
    ElMessage.success('AI 建议已生成')
  } catch (error) {
    console.error('AI 检查失败:', error)
    ElMessage.error(error?.response?.data?.detail || error?.message || 'AI 检查失败')
  } finally {
    loadingInstance.close()
  }
}

const runAiCheckBatch = async (command) => {
  const cmd = String(command || '').trim()
  if (aiCheckProgress.running) return

  const list = Array.isArray(items.value) ? items.value : []
  const targets = cmd === 'all'
    ? list
    : list.filter((row) => String(row?.ai_status || '') !== 'done' || !row?.ai_result)

  if (!targets.length) {
    ElMessage.info('没有需要 AI 检查的检查项')
    return
  }

  aiCheckProgressVisible.value = true
  aiCheckProgress.total = targets.length
  aiCheckProgress.done = 0
  aiCheckProgress.message = '准备开始...'
  aiCheckProgress.error = ''
  aiCheckProgress.running = true
  startAiCheckProgressTimer()

  try {
    for (let i = 0; i < targets.length; i += 1) {
      const row = targets[i]
      const name = row?.item_name || row?.item_id || row?.id
      aiCheckProgress.message = `检查中（${i + 1}/${targets.length}）：${name}`
      const res = await aiAPI.analyzeCheckItem(row.id, {
        mode: 'auto',
        force: false,
        max_images: 5,
        image_detail: 'low',
      })
      applyAiAnalyzeResultToRow(row, res)
      aiCheckProgress.done = i + 1
      await nextTick()
    }

    aiCheckProgress.message = '已完成'
    ElMessage.success('AI 检查已完成')
  } catch (error) {
    console.error('AI 检查失败:', error)
    const detail = error?.response?.data?.detail || error?.message || 'AI 检查失败'
    aiCheckProgress.error = detail
    aiCheckProgress.message = '已中止'
    ElMessage.error(detail)
  } finally {
    aiCheckProgress.running = false
    stopAiCheckProgressTimer()
  }
}

const applyAiSuggestion = async (row) => {
  if (!row?.id) return
  if (!canApplyAi(row)) {
    ElMessage.warning('当前检查项不满足采纳条件')
    return
  }

  try {
    await ElMessageBox.confirm(
      `将 AI 建议写入“审核结果/审核意见”？\n检查项：${row.item_name || row.item_id || row.id}`,
      '采纳 AI 建议',
      { type: 'warning', confirmButtonText: '采纳', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  const loadingInstance = ElLoading.service({ text: '采纳中...' })
  try {
    const res = await aiAPI.applyCheckItem(row.id)
    row.review_status = res?.review_status
    row.review_comments = res?.review_comments
    row.reviewed_at = res?.reviewed_at
    ElMessage.success('已采纳 AI 建议')
    await loadSummary()
  } catch (error) {
    console.error('采纳 AI 失败:', error)
    ElMessage.error(error?.response?.data?.detail || error?.message || '采纳失败')
  } finally {
    loadingInstance.close()
  }
}

		const startReview = async () => {
		  const id = route.query.id
		  try {
		    await request.post(`/api/work-orders/${id}/review/start`)
	    ElMessage.success('已进入审核中')
	    await refresh()
	  } catch (e) {
	    console.error(e)
	    ElMessage.error(e?.response?.data?.detail || '认领失败')
	  }
	}

const reviewItem = async (row, action) => {
  itemReviewRow.value = row
  itemReviewAction.value = action
  itemReviewComments.value = row?.review_comments || ''
  itemReviewCommentsI18n.en = row?.review_comments_i18n?.en || ''
  itemReviewCommentsI18n.id = row?.review_comments_i18n?.id || ''
  itemReviewVisible.value = true
}

const submitItemReview = async () => {
  const id = route.query.id
  if (!id || !itemReviewRow.value) return

  const action = itemReviewAction.value
  const baseText = String(itemReviewComments.value || '')
  if (action !== 'pass' && baseText.trim() === '') {
    ElMessage.warning('请输入审核意见')
    return
  }

  const payload = {
    action,
    comments: baseText.trim() ? baseText : undefined,
    comments_i18n: baseText.trim() ? normalizeI18nPayload(itemReviewCommentsI18n) : undefined,
  }

  try {
    itemReviewSubmitting.value = true
    // 如果工单有关联的检查，调用检查项审核API
    if (order.value && order.value.inspection_id) {
      await request.post(
        `/api/inspections/detail/${order.value.inspection_id}/items/${itemReviewRow.value.id}/review`,
        payload
      )
    } else {
      // 否则调用工单项审核API
      await request.post(`/api/work-orders/${id}/items/${itemReviewRow.value.id}/review`, payload)
    }
    ElMessage.success('已提交')
    itemReviewVisible.value = false
    // 审核成功后自动关闭“检查项详情”弹窗（不切换下一条）
    itemDetailVisible.value = false
    await Promise.all([loadItems(), loadSummary()])
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '提交失败')
  } finally {
    itemReviewSubmitting.value = false
  }
}

const finalReview = async (action) => {
  const id = route.query.id
  try {
    const baseText = String(comments.value || '')
    await request.post(`/api/work-orders/${id}/review`, {
      action,
      comments: baseText.trim() ? baseText : undefined,
      comments_i18n: baseText.trim() ? normalizeI18nPayload(commentsI18n) : undefined,
    })
    ElMessage.success('审核已提交')
    await refresh()
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '审核失败')
  }
}

const promptVoidReason = async () => {
  const result = await ElMessageBox.prompt(
    '作废后工单与检查记录会保留，但会被冻结为只读。若仍有设备级 SN 绑定，系统会拒绝作废。请输入作废原因：',
    '确认作废工单',
    {
      confirmButtonText: '确认作废',
      cancelButtonText: '取消',
      type: 'warning',
      inputType: 'textarea',
      inputPlaceholder: '请填写至少 5 个字的作废原因',
      closeOnClickModal: false,
      inputValidator: (value) => {
        const text = String(value || '').trim()
        if (text.length < 5) return '作废原因至少需要 5 个字符'
        if (text.length > 200) return '作废原因不能超过 200 个字符'
        return true
      },
    },
  )
  return String(result.value || '').trim()
}

const voidCurrentWorkOrder = async () => {
  const id = route.query.id
  if (!id || !order.value) return
  try {
    const reason = await promptVoidReason()
    await request.post(`/api/work-orders/${id}/void`, { reason })
    ElMessage.success('工单已作废')
    await refresh()
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '作废失败')
  }
}


const getImageUrl = (filePath) => {
  return resolveImageUrl(filePath)
}

const normalizeText = (val) => String(val ?? '').trim()

const formatFieldValueForReview = (val) => {
  if (val === null || val === undefined || val === '') return '-'
  if (typeof val === 'boolean') return val ? '是' : '否'
  if (Array.isArray(val)) {
    if (val.length === 0) return '-'
    return val.map((x) => {
      if (x === null || x === undefined || x === '') return '-'
      if (typeof x === 'boolean') return x ? '是' : '否'
      if (typeof x === 'object') return JSON.stringify(x)
      return String(x)
    }).join(', ')
  }
  if (typeof val === 'object') return JSON.stringify(val)
  return String(val)
}

	const buildItemDetailFieldRows = (item) => {
	  if (!item) return []
	  const defs = Array.isArray(item.fields) ? item.fields : []
	  const dataList = Array.isArray(item.data_value) ? item.data_value : []
	  const photos = Array.isArray(item.photos) ? item.photos : []
	
	  const photoMap = new Map()
	  photos.forEach((p) => {
	    const fid = normalizeText(p?.field_id)
	    if (!fid) return
	    if (!photoMap.has(fid)) photoMap.set(fid, [])
	    photoMap.get(fid).push(p)
	  })

	  const dvByName = new Map()
	  dataList.forEach((dv) => {
	    const key = normalizeText(dv?.field_name)
	    if (!key) return
    if (!dvByName.has(key)) dvByName.set(key, dv)
  })

  const usedFieldNames = new Set()
  const rows = []

  const pickDataValue = (def) => {
    const fid = normalizeText(def?.field_id)
    if (fid && dvByName.has(fid)) return dvByName.get(fid)
    const lbl = normalizeText(def?.label)
    if (lbl && dvByName.has(lbl)) return dvByName.get(lbl)
    return null
  }

	  defs.forEach((def) => {
	    const label = normalizeText(def?.label) || normalizeText(def?.field_id)
	    if (!label) return
	    const dv = pickDataValue(def)
	    if (dv) usedFieldNames.add(normalizeText(dv.field_name))
	    const helpText = normalizeText(def?.help_text)
	    const fid = normalizeText(def?.field_id)

	    rows.push({
	      key: normalizeText(def?.field_id) || label,
	      field_id: fid || null,
	      label,
	      required: def?.required === true,
	      help_text: helpText,
	      display_value: formatFieldValueForReview(dv ? dv.value : null),
	      unit: normalizeText(dv?.unit) || '',
	      is_defined: true,
	      photos: fid ? (photoMap.get(fid) || []) : [],
	    })
	  })

	  // 追加未在字段定义中出现的数据（兼容历史/异常数据）
	  dataList.forEach((dv) => {
    const fieldName = normalizeText(dv?.field_name)
    if (!fieldName) return
    if (usedFieldNames.has(fieldName)) return
    const matched = defs.some((def) => normalizeText(def?.field_id) === fieldName || normalizeText(def?.label) === fieldName)
    if (matched) return

	    rows.push({
	      key: `__extra__${fieldName}`,
	      field_id: null,
	      label: fieldName,
	      required: false,
	      help_text: '',
	      display_value: formatFieldValueForReview(dv?.value),
	      unit: normalizeText(dv?.unit) || '',
	      is_defined: false,
	      photos: [],
	    })
	  })

	  return rows
	}

	const itemDetailFieldRows = computed(() => buildItemDetailFieldRows(selectedItem.value))
	
	const itemDetailExtraPhotos = computed(() => {
	  const item = selectedItem.value
	  if (!item) return []
	  const defs = Array.isArray(item.fields) ? item.fields : []
	  const known = new Set(defs.map(d => normalizeText(d?.field_id)).filter(Boolean))
	  const photos = Array.isArray(item.photos) ? item.photos : []
	  return photos.filter((p) => {
	    const fid = normalizeText(p?.field_id)
	    return !fid || !known.has(fid)
	  })
	})

const viewItemDetail = (item) => {
  selectedItem.value = item
  itemDetailVisible.value = true
}

const viewPhotoDetail = (photo) => {
  console.log('viewPhotoDetail called with photo:', photo)
  selectedPhoto.value = photo
  photoSimilarityDetailVisible.value = false
  photoDetailVisible.value = true
  console.log('photoDetailVisible set to:', photoDetailVisible.value)
  // 重置查看器状态
  resetZoom()
  isFullscreen.value = false
  loadSelectedPhotoForViewer()
}

const openPhotoSimilarityDetail = () => {
  if (!selectedPhoto.value) {
    ElMessage.warning('请先选择照片')
    return
  }
  photoSimilarityDetailVisible.value = true
}

const loadSelectedPhotoForViewer = async () => {
  cleanupPhotoViewerObjectUrl()
  const photo = selectedPhoto.value
  if (!photo) {
    photoViewerStatus.value = 'idle'
    photoViewerProgress.value = 0
    return
  }

  const url = getImageUrl(photo.file_path)
  if (!url) {
    photoViewerStatus.value = 'error'
    photoViewerProgress.value = 0
    return
  }

  photoViewerStatus.value = 'loading'
  photoViewerProgress.value = 0
  const token = ++photoViewerLoadToken.value

  const res = await loadImageBlob({
    url,
    onProgress: (p) => {
      if (token !== photoViewerLoadToken.value) return
      photoViewerProgress.value = p
    },
  })

  if (token !== photoViewerLoadToken.value) return

  if (res?.ok && res.blob) {
    photoViewerProgress.value = 100
    photoViewerObjectUrl.value = createObjectUrl(res.blob) || ''
    photoViewerStatus.value = photoViewerObjectUrl.value ? 'loaded' : 'error'
    return
  }

  photoViewerStatus.value = 'error'
}

const zoomIn = () => {
  zoomLevel.value = Math.min(zoomLevel.value * 1.5, 5)
}

const zoomOut = () => {
  zoomLevel.value = Math.max(zoomLevel.value / 1.5, 0.1)
}

const resetZoom = () => {
  zoomLevel.value = 1
  translateX.value = 0
  translateY.value = 0
}

const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value
}

const downloadPhoto = async () => {
  if (!selectedPhoto.value) return
  
  try {
    // 获取图片URL
    const imageUrl = photoViewerObjectUrl.value || getImageUrl(selectedPhoto.value.file_path)
    
    // 创建一个临时的a标签进行下载
    const link = document.createElement('a')
    link.href = imageUrl
    
    // 生成文件名：原始文件名 + GPS坐标 + 时间戳
    const timestamp = selectedPhoto.value.taken_at ? 
      new Date(selectedPhoto.value.taken_at).toISOString().replace(/[:.]/g, '-').substring(0, 19) : 
      'unknown-time'
    
    const gpsInfo = selectedPhoto.value.latitude && selectedPhoto.value.longitude ? 
      `_GPS-${selectedPhoto.value.latitude.toFixed(6)}-${selectedPhoto.value.longitude.toFixed(6)}` : 
      ''
    
    const originalName = selectedPhoto.value.original_name || 'photo'
    const extension = originalName.split('.').pop() || 'jpg'
    const baseName = originalName.replace(/\.[^/.]+$/, "")
    
    link.download = `${baseName}_${timestamp}${gpsInfo}.${extension}`
    
    // 触发下载
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    
    ElMessage.success('照片下载成功')
  } catch (error) {
    console.error('下载照片失败:', error)
    ElMessage.error('下载照片失败')
  }
}

watch(photoDetailVisible, (visible) => {
  if (!visible) {
    photoViewerLoadToken.value += 1
    photoViewerStatus.value = 'idle'
    photoViewerProgress.value = 0
    cleanupPhotoViewerObjectUrl()
  }
})

const handleWheel = (e) => {
  e.preventDefault()
  const delta = e.deltaY > 0 ? -1 : 1
  if (delta > 0) {
    zoomIn()
  } else {
    zoomOut()
  }
}

const handleMouseDown = (e) => {
  if (zoomLevel.value > 1) {
    isDragging.value = true
    dragStart.value = { x: e.clientX - translateX.value, y: e.clientY - translateY.value }
  }
}

const handleMouseMove = (e) => {
  if (isDragging.value && zoomLevel.value > 1) {
    translateX.value = e.clientX - dragStart.value.x
    translateY.value = e.clientY - dragStart.value.y
  }
}

const handleMouseUp = () => {
  isDragging.value = false
}

const formatFileSize = (size) => {
  if (!size) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)} KB`
  return `${(size / (1024 * 1024)).toFixed(2)} MB`
}

const statusText = (status, type) => {
  if (type === 'opening_inspection' || type === 'equipment_replacement') {
    if (status === 'APPROVED') return '待上线 (80%)'
    if (status === 'ACTIVATED') return '已上线待激活 (90%)'
    if (status === 'COMPLETED') return '已激活 (100%)'
  }
  return statuses.find(s => s.value === status)?.label || status
}
const typeText = (v) => (types.find(t => t.value === v)?.label || v)
const priorityText = (v) => ({ low: '低', normal: '普通', high: '高', urgent: '紧急' }[v] || v)
const formatDateTime = (val) => (val ? new Date(val).toLocaleString() : '-')

const onlineRealtimeText = (val) => {
  if (val === true) return '当前在线'
  if (val === false) return '当前离线'
  return '待检测'
}
const onlineRealtimeTagType = (val) => {
  if (val === true) return 'success'
  if (val === false) return 'danger'
  return 'info'
}
const everOnlineTagType = (val) => (val ? 'success' : 'info')
const everOnlineText = (val) => (val ? '曾上线' : '未曾上线')

const activeRealtimeText = (val) => {
  if (val === true) return '当前已激活'
  if (val === false) return '当前未激活'
  return '待检测'
}
const activeRealtimeTagType = (val) => {
  if (val === true) return 'success'
  if (val === false) return 'warning'
  return 'info'
}
const everActiveTagType = (val) => (val ? 'success' : 'info')
const everActiveText = (val) => (val ? '曾激活' : '未曾激活')

const deviceRefreshCooldown = ref(0)
let deviceCooldownTimer = null

const canShowManualConfirm = computed(() => {
  return !isVoided.value && manualConfirmEnabled.value && userStore.hasPermission('workorder:review:write')
})

const manualConfirm = async (row, action) => {
  const id = route.query.id
  const sn = (row?.sn || '').toString().trim()
  if (!id || !sn) return
  if (!canShowManualConfirm.value) {
    ElMessage.error('当前未开启手工确认功能或无权限操作')
    return
  }
  if (manualConfirmSubmitting.value) return

  const isActivate = action === 'activated'
  const title = isActivate ? '确认已激活' : '确认已上线'
  const msg = isActivate
    ? `确认设备 SN ${sn} 已激活？该操作不可撤销，将同时确认“已上线”，并可能触发工单状态推进。`
    : `确认设备 SN ${sn} 已上线？该操作不可撤销，且可能触发工单状态推进。`

  try {
    await ElMessageBox.confirm(msg, title, {
      type: 'warning',
      confirmButtonText: '确认',
      cancelButtonText: '取消',
    })
  } catch (e) {
    return
  }

  try {
    manualConfirmSubmitting.value = true
    await request.post(`/api/work-orders/${id}/omc/manual-confirm`, {
      sn,
      confirm_online: !isActivate,
      confirm_activated: isActivate,
    })
    ElMessage.success('手工确认成功')
    await refresh()
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '手工确认失败')
  } finally {
    manualConfirmSubmitting.value = false
  }
}

const loadDeviceStatus = async (refresh = false) => {
  if (refresh && deviceRefreshCooldown.value > 0) {
    ElMessage.warning(`请等待 ${deviceRefreshCooldown.value}s 后再刷新设备状态`)
    return
  }
  // 仅开站/设备更换工单需要设备状态
  if (!order.value || !['opening_inspection', 'equipment_replacement'].includes(order.value.type)) {
    devices.value = []
    deviceStatusCheckedAt.value = null
    manualConfirmEnabled.value = false
    return
  }
  try {
    deviceStatusLoading.value = true
    const res = await request.get(`/api/sites/${order.value.site_id}/omc/devices`, {
      params: { refresh: refresh ? 1 : 0 }
    })
    devices.value = Array.isArray(res.devices) ? res.devices : []
    deviceStatusCheckedAt.value = res.checked_at || null
    manualConfirmEnabled.value = !!res.manual_confirm_enabled

    if (refresh) {
      startDeviceCooldown()
    }
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '加载设备状态失败')
    manualConfirmEnabled.value = false
  } finally {
    deviceStatusLoading.value = false
  }
}

// 审核历史相关方法
const showAuditHistory = async () => {
  if (!route.query.id) {
    ElMessage.warning('请先选择工单')
    return
  }
  
  try {
    // request 的响应拦截器已经返回了 response.data，所以直接使用
    const data = await request.get(`/api/work-orders/${route.query.id}/audit-logs`)
    timelineLogs.value = data.timeline || []
    expandedLogDetails.value = {}
    auditHistoryVisible.value = true
  } catch (error) {
    console.error('获取审核历史失败:', error)
    ElMessage.error('获取审核历史失败：' + (error.response?.data?.detail || error.message))
  }
}

const getActionText = (action, source) => {
  const actionMap = {
    'create': '创建',
    'assign': '分配',
    'change_assignee': '重新分配',
    'batch_assignee_change': '重新分配(批量)',
    'accept': '接受',
    'submit': '提交',
    'resubmit': '重新提交',
    'start_review': '开始审核',
    'final_review': '最终审核',
    'approve': '通过',
    'reject': '驳回',
    'void': '作废',
    'batch_void': '批量作废',
    'update_status': '更新状态',
    'update': '更新',
    'delete': '删除',
    'mark_completed': '标记完成',
    'activate': '激活',
    // 检查相关
    'item_review': '检查项审核',
    'photo_review': '照片审核',
    'delete_photo': '删除照片',
    'replace_photo': '替换照片',
    'batch_photo_operations': '批量照片操作',
    'cleanup_duplicate_photos': '清理重复照片',
    // 绑定相关
    'bind': '绑定设备',
    'unbind': '解绑设备',
    'rebind': '重新绑定设备',
    'omc_manual_confirm': '手工确认设备状态',
  }
  return actionMap[action] || action
}

const isAssigneeChange = (log) => {
  const action = log?.action
  if (!action) return false
  return ['change_assignee', 'batch_assignee_change'].includes(action)
}

const sourceText = (source) => {
  const map = { work_order: '工单', inspection: '检查', binding: '绑定' }
  return map[source] || source || '-'
}

const getSourceTagType = (source) => {
  if (source === 'work_order') return 'primary'
  if (source === 'inspection') return 'warning'
  if (source === 'binding') return 'info'
  return 'info'
}

const getTimelineActionTagType = (log) => {
  const action = log?.action
  const source = log?.source
  if (source === 'binding') return 'info'
  if (['approve', 'accept'].includes(action)) return 'success'
  if (['reject', 'delete', 'void', 'batch_void'].includes(action)) return 'danger'
  if (['submit', 'resubmit', 'start_review'].includes(action)) return 'warning'
  if (['item_review', 'photo_review'].includes(action)) return 'primary'
  if (['delete_photo', 'replace_photo', 'batch_photo_operations', 'cleanup_duplicate_photos'].includes(action)) return 'warning'
  return 'info'
}

const getTimelineLogType = (log) => {
  const action = log?.action
  const source = log?.source
  if (source === 'binding') return 'info'
  if (['approve', 'accept', 'mark_completed'].includes(action)) return 'success'
  if (['reject', 'delete', 'void', 'batch_void'].includes(action)) return 'danger'
  if (['submit', 'resubmit'].includes(action)) return 'primary'
  return 'info'
}

const getTimelineStatusTagType = (status) => {
  const v = (status ?? '').toString()
  if (['APPROVED', 'COMPLETED', 'approved', 'completed'].includes(v)) return 'success'
  if (['REJECTED', 'rejected'].includes(v)) return 'danger'
  if (['SUBMITTED', 'UNDER_REVIEW', 'submitted', 'under_review'].includes(v)) return 'warning'
  return 'info'
}

const formatTimelineStatus = (status) => {
  const v = (status ?? '').toString()
  const woText = statuses.find(s => s.value === v)?.label
  if (woText) return woText
  const inspectionMap = {
    draft: '草稿',
    in_progress: '进行中',
    submitted: '已提交',
    under_review: '审核中',
    approved: '已通过',
    rejected: '已驳回',
    completed: '已完成',
    voided: '已作废',
  }
  return inspectionMap[v] || v
}

const hasLogDetails = (log) => {
  const d = log?.details
  if (!d) return false
  if (typeof d !== 'object') return true
  return Object.keys(d).length > 0
}

const toggleLogDetails = (id) => {
  expandedLogDetails.value[id] = !expandedLogDetails.value[id]
}

const isLogDetailsExpanded = (id) => {
  return !!expandedLogDetails.value[id]
}

const startDeviceCooldown = () => {
  deviceRefreshCooldown.value = 10
  if (deviceCooldownTimer) return
  deviceCooldownTimer = setInterval(() => {
    if (deviceRefreshCooldown.value > 0) {
      deviceRefreshCooldown.value -= 1
    }
    if (deviceRefreshCooldown.value <= 0) {
      clearInterval(deviceCooldownTimer)
      deviceCooldownTimer = null
    }
  }, 1000)
}

onMounted(refresh)
</script>

<style scoped>
.i18n-inline {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  width: 100%;
}

.i18n-inline__input {
  flex: 1;
}

.i18n-actions {
  flex: none;
}

.ai-progress {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ai-progress-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.ai-progress-main {
  font-size: 14px;
  color: #333;
}

.ai-progress-batch {
  color: #666;
  font-size: 12px;
  margin-left: 6px;
}

.ai-progress-time {
  color: #666;
  font-size: 12px;
  white-space: nowrap;
}

.ai-progress-status {
  font-size: 12px;
  color: #666;
}

.item-review-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  gap: 12px;
}

.item-review-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.section-header { display:flex; justify-content: space-between; align-items:center; margin: 8px 0; }
.section-title { display:flex; align-items:center; gap: 12px; flex-wrap: wrap; }

.review-summary {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.review-summary__counts {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.review-summary__count-tag {
  font-weight: 600;
  letter-spacing: 0.2px;
}

.review-summary__hint {
  font-weight: 600;
  letter-spacing: 0.2px;
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.02);
}

.review-summary__hint.el-tag--success {
  background-color: var(--el-color-success-light-9);
}
.review-summary__hint.el-tag--warning {
  background-color: var(--el-color-warning-light-9);
}
.review-summary__hint.el-tag--danger {
  background-color: var(--el-color-danger-light-9);
}

.review-summary__hint-icon {
  margin-right: 4px;
}

.status-cell {
  display: flex;
  align-items: center;
  gap: 4px;
}
.mr4 {
  margin-right: 4px;
}

.scope-cell {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.scope-cell--multiline {
  align-items: flex-start;
}

.scope-sn {
  flex: 1;
  min-width: 0;
}

.scope-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #606266;
}

.scope-text--multiline {
  white-space: normal;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  overflow-wrap: anywhere;
  word-break: break-all;
}

.scope-copy-btn {
  align-self: flex-start;
}

.action-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.help-tip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  margin-left: 4px;
  border: 1px solid #dcdfe6;
  border-radius: 50%;
  color: #909399;
  font-size: 12px;
  line-height: 1;
  cursor: help;
}

.field-name-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.field-required-mark {
  color: #f56c6c;
  font-weight: 700;
  margin-left: 2px;
}

.field-help-icon {
  cursor: pointer;
  color: #909399;
  font-size: 14px;
}

.field-help-text {
  white-space: pre-line;
  line-height: 1.6;
}

.muted {
  color: #909399;
  font-weight: normal;
}

.replacement-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.replacement-title {
  font-weight: 600;
  color: #303133;
}

.field-photo-strip {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.field-photo-img {
  width: 52px;
  height: 52px;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #ebeef5;
  cursor: pointer;
  background: #fff;
}

.field-photo-more {
  margin-left: 2px;
}

/* 审核历史样式 */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-header-left {
  display: flex;
  align-items: center;
}
.ml8 {
  margin-left: 8px;
}

/* 照片查看器样式 */
.photo-container {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f7fa;
}

.photo-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #fff;
  border-bottom: 1px solid #dcdfe6;
}

.zoom-info {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
}

.photo-viewer {
  height: 600px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
  position: relative;
  user-select: none;
}

.photo-viewer-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  z-index: 2;
}

.photo-viewer-overlay__percent {
  font-size: 22px;
  font-weight: 700;
}

.photo-viewer-overlay__bar {
  width: min(420px, 72%);
  height: 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.18);
  overflow: hidden;
}

.photo-viewer-overlay__bar-fill {
  height: 100%;
  background: #409eff;
  width: 0;
}

.photo-viewer-overlay--error {
  cursor: pointer;
}

.photo-viewer-overlay__error-text {
  font-size: 16px;
  font-weight: 700;
  color: #ffd1d1;
}

.photo-viewer-overlay__error-sub {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.82);
}

.photo-viewer img {
  display: block;
  transition: transform 0.2s ease;
  transform-origin: center center;
}

/* 全屏模式下的样式调整 */
:deep(.el-dialog.is-fullscreen) .photo-viewer {
  height: calc(100vh - 200px);
}

:deep(.el-dialog.is-fullscreen) .el-descriptions {
  height: calc(100vh - 200px);
  overflow-y: auto;
}

/* 检查项详情弹窗样式 */
.photo-card {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 10px;
  background: #fff;
}

.photo-info {
  padding: 8px;
  background: #f5f7fa;
}

.photo-name {
  font-size: 12px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.photo-time {
  font-size: 11px;
  color: #909399;
  margin-bottom: 2px;
}

.photo-location {
  font-size: 11px;
  color: #606266;
  font-family: monospace;
}

.duplicate-hint-line {
  font-size: 12px;
  line-height: 1.5;
  color: #8a6d3b;
  margin-bottom: 6px;
}

.duplicate-hint-line:last-child {
  margin-bottom: 0;
}

.duplicate-photo-tip {
  margin-top: 4px;
  font-size: 11px;
  color: #8a6d3b;
  line-height: 1.4;
}

.duplicate-detail-block {
  margin-top: 8px;
  color: #8a6d3b;
  line-height: 1.5;
  font-size: 12px;
}

.similar-photo-tip {
  margin-top: 4px;
  font-size: 11px;
  color: #b91c1c;
  line-height: 1.4;
}

.similar-detail-block {
  margin-top: 8px;
  color: #b91c1c;
  line-height: 1.5;
  font-size: 12px;
}

.similarity-human-lines {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 6px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
}

.similarity-human-lines__title {
  font-size: 13px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 8px;
}

.similarity-human-lines__item {
  font-size: 12px;
  color: #374151;
  line-height: 1.6;
  margin-bottom: 4px;
}

.similarity-human-lines__item:last-child {
  margin-bottom: 0;
}

.similarity-debug-json {
  margin: 0;
  padding: 12px;
  max-height: 280px;
  overflow: auto;
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.5;
}
</style>
