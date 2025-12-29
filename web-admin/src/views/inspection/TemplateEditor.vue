<template>
  <div class="template-editor">
    <div class="editor-header">
      <div class="header-left">
        <el-button @click="goBack" size="small">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <div class="template-title">
          <h2>{{ isNewTemplate ? '新建检查模板' : template?.template_name || '加载中...' }}</h2>
          <p v-if="!isNewTemplate">编辑检查模板结构和内容</p>
        </div>
      </div>
      
      <div class="header-actions">
        <el-button @click="openAiTemplateI18n">
          <el-icon><MagicStick /></el-icon>
          AI国际化
        </el-button>
        <el-button @click="previewTemplate" v-if="!isNewTemplate">
          <el-icon><View /></el-icon>
          预览
        </el-button>
        <el-button 
          type="primary" 
          @click="saveTemplate"
          :loading="saving"
        >
          <el-icon><Check /></el-icon>
          {{ isNewTemplate ? '创建模板' : '保存更改' }}
        </el-button>
      </div>
    </div>

    <div class="editor-content">
      <!-- 使用情况提示 -->
      <el-alert
        v-if="!isNewTemplate && templateUsageInfo.is_used"
        type="warning"
        :closable="false"
        show-icon
        class="usage-warning"
      >
        <template #title>
          该检查模板已被 {{ templateUsageInfo.total_inspections }} 个工单使用
        </template>
        <div style="margin-top: 8px;">
          <p style="margin: 4px 0;">✅ 您可以修改：检查项名称、描述、字段标签、约束条件等</p>
          <p style="margin: 4px 0;">❌ 不可修改：检查分类结构、检查项类型、字段类型等</p>
          <p style="margin: 8px 0; font-weight: bold; color: #E6A23C;">💡 修改后将自动同步更新所有已使用该模板的工单</p>
        </div>
      </el-alert>
      
      <el-row :gutter="20">
        <!-- 左侧：模板编辑器 -->
        <el-col :span="16">
          <el-card class="editor-card">
            <template #header>
              <div class="card-header">
                <span>模板结构编辑</span>
                <el-button 
                  size="small" 
                  @click="addCategory"
                  :disabled="isOperationDisabled('add_category')"
                  :title="getDisabledReason('add_category')"
                >
                  <el-icon><Plus /></el-icon>
                  添加分类
                </el-button>
              </div>
            </template>
            
            <div v-if="loading" class="loading-container">
              <el-skeleton :rows="8" animated />
            </div>
            
            <div v-else class="categories-editor">
              <!-- 模板基本信息 -->
              <el-form :model="templateForm" label-width="120px" class="template-basic-form">
                <el-form-item label="模板名称" required>
                  <el-input 
                    v-model="templateForm.template_name" 
                    placeholder="请输入模板名称"
                  />
                </el-form-item>
                <el-form-item label="模板描述">
                  <el-input 
                    v-model="templateForm.description" 
                    type="textarea"
                    :rows="2"
                    placeholder="请输入模板描述"
                  />
                </el-form-item>
              </el-form>
              
              <!-- 检查分类列表 -->
              <div class="categories-list">
                <div 
                  v-for="(category, categoryIndex) in templateData.check_categories" 
                  :key="category.category_id"
                  class="category-item"
                >
                  <div class="category-header">
                    <div class="category-title">
                      <div class="i18n-inline">
                        <el-input 
                          v-model="category.category_name" 
                          placeholder="分类名称"
                          size="small"
                          :disabled="isFieldDisabled('category', 'category_name')"
                          :title="getFieldTooltip('category', 'category_name')"
                        />
                        <el-button-group class="i18n-actions">
                          <el-button
                            size="small"
                            circle
                            :icon="ChatDotRound"
                            title="多语言"
                            @click="openI18nEditor(category, 'category_name', 'category_name_i18n', '分类名称')"
                          />
                          <el-button
                            size="small"
                            circle
                            :icon="MagicStick"
                            title="AI翻译"
                            @click="aiFillI18n(category, 'category_name', 'category_name_i18n')"
                          />
                        </el-button-group>
                      </div>
                      <el-select
                        v-model="category.level_type"
                        placeholder="检查级别"
                        size="small"
                        style="margin-left: 12px; width: 120px;"
                        @change="onLevelTypeChange(category)"
                        :disabled="isFieldDisabled('category', 'level_type')"
                        :title="getFieldTooltip('category', 'level_type')"
                      >
                        <el-option label="站点级" value="site" />
                        <el-option label="扇区级" value="sector" />
                        <el-option label="设备级" value="device" />
                        <el-option label="小区级" value="cell_earfcn" />
                      </el-select>
                      
                      <el-tag 
                        :type="getLevelTagType(category)"
                        size="small"
                        style="margin-left: 8px;"
                      >
                        {{ getLevelLabel(category) }}
                      </el-tag>
                    </div>
                    
                    <div class="category-actions">
                      <el-button 
                        size="small" 
                        @click="addItem(categoryIndex)"
                        :disabled="isOperationDisabled('add_item')"
                        :title="getDisabledReason('add_item')"
                      >
                        <el-icon><Plus /></el-icon>
                        添加检查项
                      </el-button>
                      <el-button 
                        size="small" 
                        type="danger" 
                        @click="removeCategory(categoryIndex)"
                        :disabled="isOperationDisabled('delete_category')"
                        :title="getDisabledReason('delete_category')"
                      >
                        <el-icon><Delete /></el-icon>
                        删除分类
                      </el-button>
                    </div>
                  </div>
                  
                  <div class="category-description">
                    <div class="i18n-inline">
                      <el-input 
                        v-model="category.description" 
                        placeholder="分类描述（可选）"
                        size="small"
                        :disabled="isFieldDisabled('category', 'description')"
                        :title="getFieldTooltip('category', 'description')"
                      />
                      <el-button-group class="i18n-actions">
                        <el-button
                          size="small"
                          circle
                          :icon="ChatDotRound"
                          title="多语言"
                          @click="openI18nEditor(category, 'description', 'description_i18n', '分类描述')"
                        />
                        <el-button
                          size="small"
                          circle
                          :icon="MagicStick"
                          title="AI翻译"
                          @click="aiFillI18n(category, 'description', 'description_i18n')"
                        />
                      </el-button-group>
                    </div>
                  </div>
                  
                  <!-- 检查项列表 -->
                  <div class="items-list">
                    <div 
                      v-for="(item, itemIndex) in category.items" 
                      :key="item.item_id"
                      class="item-row"
                    >
                      <div class="item-basic">
                        <div class="i18n-inline i18n-inline--item">
                          <el-input 
                            v-model="item.item_name" 
                            placeholder="检查项名称"
                            size="small"
                            :disabled="isFieldDisabled('item', 'item_name')"
                            :title="getFieldTooltip('item', 'item_name')"
                          />
                          <el-button-group class="i18n-actions">
                            <el-button
                              size="small"
                              circle
                              :icon="ChatDotRound"
                              title="多语言"
                              @click="openI18nEditor(item, 'item_name', 'item_name_i18n', '检查项名称')"
                            />
                            <el-button
                              size="small"
                              circle
                              :icon="MagicStick"
                              title="AI翻译"
                              @click="aiFillI18n(item, 'item_name', 'item_name_i18n')"
                            />
                          </el-button-group>
                        </div>
                        
                        <el-select 
                          v-model="item.required_type" 
                          placeholder="要求类型"
                          size="small"
                          style="width: 120px; margin-left: 8px;"
                          :disabled="isFieldDisabled('item', 'required_type')"
                          :title="getFieldTooltip('item', 'required_type')"
                        >
                          <el-option label="仅拍照" value="photo" />
                          <el-option label="仅数据" value="data" />
                          <el-option label="拍照+数据" value="both" />
                        </el-select>
                        
                        <el-button 
                          size="small" 
                          type="danger" 
                          @click="removeItem(categoryIndex, itemIndex)"
                          style="margin-left: 8px;"
                          :disabled="isOperationDisabled('delete_item')"
                          :title="getDisabledReason('delete_item')"
                        >
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </div>
                      
                      <div class="item-description">
                        <div class="i18n-inline">
                          <el-input 
                            v-model="item.description" 
                            type="textarea"
                            :autosize="{ minRows: 2, maxRows: 6 }"
                            placeholder="检查项描述（可选）"
                            size="small"
                            :disabled="isFieldDisabled('item', 'description')"
                            :title="getFieldTooltip('item', 'description')"
                          />
                          <el-button-group class="i18n-actions">
                            <el-button
                              size="small"
                              circle
                              :icon="ChatDotRound"
                              title="多语言"
                              @click="openI18nEditor(item, 'description', 'description_i18n', '检查项描述')"
                            />
                            <el-button
                              size="small"
                              circle
                              :icon="MagicStick"
                              title="AI翻译"
                              @click="aiFillI18n(item, 'description', 'description_i18n')"
                            />
                          </el-button-group>
                        </div>
                      </div>

                      <!-- 字段配置（高级） -->
                      <el-card class="fields-card" shadow="never">
                        <template #header>
                          <div class="card-header">
                            <span>字段配置（可选）</span>
                            <el-button 
                              size="small" 
                              @click="addField(categoryIndex, itemIndex)"
                              :disabled="isOperationDisabled('add_field')"
                              :title="getDisabledReason('add_field')"
                            >
                              <el-icon><Plus /></el-icon> 添加字段
                            </el-button>
                          </div>
                        </template>
                        <div v-if="!item.fields || item.fields.length === 0" class="empty-fields">暂无字段，点击“添加字段”新增</div>
                        <div v-for="(field, fieldIndex) in (item.fields || (item.fields = []))" :key="field.field_id || fieldIndex" class="field-row">
                          <div class="field-line-labels">
                            <div class="field-label-with-help" style="width: 180px">
                              <span>字段ID（英文）</span>
                              <el-tooltip content="用于系统内部存储和匹配数据，请保持稳定，不要随意修改" placement="top">
                                <el-icon class="field-help-icon"><QuestionFilled /></el-icon>
                              </el-tooltip>
                            </div>
                            <div class="field-label-with-help" style="width: 180px; margin-left:8px;">
                              <span>显示名称</span>
                              <el-tooltip content="用于 App 和档案中的展示标题，可根据业务语言调整文案" placement="top">
                                <el-icon class="field-help-icon"><QuestionFilled /></el-icon>
                              </el-tooltip>
                            </div>
                            <div class="field-label-with-help" style="width: 160px; margin-left:8px;">
                              <span>类型</span>
                              <el-tooltip content="决定该字段在检查表单中的输入控件类型，例如文本、数字、单选、多选等" placement="top">
                                <el-icon class="field-help-icon"><QuestionFilled /></el-icon>
                              </el-tooltip>
                            </div>
                          </div>
                          <div class="field-line">
                            <el-input 
                              v-model="field.field_id" 
                              size="small" 
                              placeholder="字段ID（英文）" 
                              style="width: 180px"
                              :disabled="isFieldDisabled('field', 'field_id')"
                              :title="getFieldTooltip('field', 'field_id')"
                            />
                            <el-input 
                              v-model="field.label" 
                              size="small" 
                              placeholder="显示名称" 
                              style="width: 180px; margin-left:8px;"
                              :disabled="isFieldDisabled('field', 'label')"
                              :title="getFieldTooltip('field', 'label')"
                            />
                            <el-button-group class="i18n-actions i18n-actions--compact">
                              <el-button
                                size="small"
                                circle
                                :icon="ChatDotRound"
                                title="多语言"
                                @click="openI18nEditor(field, 'label', 'label_i18n', '字段显示名称')"
                              />
                              <el-button
                                size="small"
                                circle
                                :icon="MagicStick"
                                title="AI翻译"
                                @click="aiFillI18n(field, 'label', 'label_i18n')"
                              />
                            </el-button-group>
                            <el-select 
                              v-model="field.type" 
                              size="small" 
                              placeholder="类型" 
                              style="width: 160px; margin-left:8px;"
                              :disabled="isFieldDisabled('field', 'type')"
                              :title="getFieldTooltip('field', 'type')"
                            >
                              <el-option label="文本" value="text" />
                              <el-option label="数字" value="number" />
                              <el-option label="布尔" value="boolean" />
                              <el-option label="单选" value="select_single" />
                              <el-option label="多选" value="select_multi" />
                              <el-option label="日期" value="date" />
                              <el-option label="时间" value="time" />
                              <el-option label="日期时间" value="datetime" />
                              <el-option label="富文本" value="rich_text" />
                            </el-select>
                            <el-checkbox 
                              v-model="field.required" 
                              style="margin-left:12px;"
                              :disabled="isRequiredFieldDisabled(field)"
                              :title="getRequiredFieldTooltip(field)"
                            >
                              必填
                            </el-checkbox>
                            <el-checkbox
                              v-model="field.allow_photo"
                              style="margin-left:12px;"
                              :disabled="isFieldDisabled('field', 'allow_photo') || item.required_type !== 'both'"
                              :title="item.required_type !== 'both' ? '仅“数据+照片(both)”类型支持字段拍照' : getFieldTooltip('field', 'allow_photo')"
                              @change="(val) => { if (!val) field.photo_required = false }"
                            >
                              允许拍照
                            </el-checkbox>
                            <el-checkbox
                              v-model="field.photo_required"
                              style="margin-left:12px;"
                              :disabled="!field.allow_photo || isFieldDisabled('field', 'photo_required') || item.required_type !== 'both'"
                              :title="!field.allow_photo ? '需先开启“允许拍照”' : (item.required_type !== 'both' ? '仅“数据+照片(both)”类型支持字段拍照' : getFieldTooltip('field', 'photo_required'))"
                            >
                              必须拍照*
                            </el-checkbox>
                            <el-button 
                              size="small" 
                              type="danger" 
                              @click="removeField(categoryIndex, itemIndex, fieldIndex)" 
                              style="margin-left:8px;"
                              :disabled="isOperationDisabled('delete_field')"
                              :title="getDisabledReason('delete_field')"
                            >
                              <el-icon><Delete /></el-icon>
                            </el-button>
                          </div>
                          <div class="field-advanced">
                            <!-- 选项配置 -->
                            <div v-if="['select_single','select_multi'].includes(field.type)" class="options-line">
                              <el-tag type="info" size="small">选项</el-tag>
                              <el-input v-model="field._newOptionLabel" size="small" placeholder="标签" style="width: 160px; margin-left:8px;" />
                              <el-input v-model="field._newOptionValue" size="small" placeholder="值" style="width: 160px; margin-left:8px;" />
                              <el-button size="small" @click="addOption(field)">添加</el-button>
                              <div class="option-list" v-if="field.options && field.options.length">
                                <el-tag
                                  v-for="(opt, oi) in field.options"
                                  :key="oi"
                                  class="option-tag"
                                  closable
                                  @close="removeOption(field, oi)"
                                  @click="openOptionI18n(opt, $event)"
                                  style="margin:4px;"
                                >
                                  {{ opt.label || opt }} ({{ opt.value || opt }})
                                </el-tag>
                              </div>
                            </div>
                            <!-- 约束配置 -->
                            <div class="constraints">
                              <el-tag type="info" size="small">约束</el-tag>
                              <template v-if="field.type==='number'">
                                <el-input-number v-model="(field.constraints || (field.constraints={})).min" :step="1" size="small" placeholder="最小值" style="margin-left:8px;" />
                                <el-input-number v-model="(field.constraints || (field.constraints={})).max" :step="1" size="small" placeholder="最大值" style="margin-left:8px;" />
                              </template>
                              <template v-else-if="field.type==='text' || field.type==='rich_text'">
                                <el-input-number v-model="(field.constraints || (field.constraints={})).min_length" :step="1" size="small" placeholder="最短" style="margin-left:8px;" />
                                <el-input-number v-model="(field.constraints || (field.constraints={})).max_length" :step="1" size="small" placeholder="最长" style="margin-left:8px;" />
                                <el-input v-model="(field.constraints || (field.constraints={})).pattern" size="small" placeholder="正则表达式" style="width: 220px; margin-left:8px;" />
                              </template>
                            </div>
                            <!-- 占位符（字段级） -->
                            <div class="placeholder-line">
                              <el-tag type="info" size="small">占位符</el-tag>
                              <el-input
                                v-model="field.placeholder"
                                placeholder="占位符（可选）"
                                size="small"
                                style="width: 420px; margin-left:8px;"
                                :disabled="isFieldDisabled('field', 'placeholder')"
                                :title="getFieldTooltip('field', 'placeholder')"
                              />
                              <el-button-group class="i18n-actions">
                                <el-button
                                  size="small"
                                  circle
                                  :icon="ChatDotRound"
                                  title="多语言"
                                  @click="openI18nEditor(field, 'placeholder', 'placeholder_i18n', '字段占位符')"
                                />
                                <el-button
                                  size="small"
                                  circle
                                  :icon="MagicStick"
                                  title="AI翻译"
                                  @click="aiFillI18n(field, 'placeholder', 'placeholder_i18n')"
                                />
                              </el-button-group>
                            </div>
                            <!-- 描述/注意事项（字段级） -->
                            <div class="help-text">
                              <el-tag type="info" size="small">描述/注意事项</el-tag>
                              <el-input
                                v-model="field.help_text"
                                type="textarea"
                                :autosize="{ minRows: 2, maxRows: 6 }"
                                placeholder="描述/注意事项（可选）"
                                size="small"
                                style="width: 420px; margin-left:8px;"
                                :disabled="isFieldDisabled('field', 'help_text')"
                                :title="getFieldTooltip('field', 'help_text')"
                              />
                              <el-button-group class="i18n-actions">
                                <el-button
                                  size="small"
                                  circle
                                  :icon="ChatDotRound"
                                  title="多语言"
                                  @click="openI18nEditor(field, 'help_text', 'help_text_i18n', '字段描述/注意事项')"
                                />
                                <el-button
                                  size="small"
                                  circle
                                  :icon="MagicStick"
                                  title="AI翻译"
                                  @click="aiFillI18n(field, 'help_text', 'help_text_i18n')"
                                />
                              </el-button-group>
                            </div>
                          </div>
                        </div>
                      </el-card>
                    </div>
                    
                    <div v-if="category.items.length === 0" class="no-items">
                      暂无检查项，点击"添加检查项"按钮添加
                    </div>
                  </div>
                </div>
                
                <div v-if="templateData.check_categories.length === 0" class="no-categories">
                  暂无检查分类，点击"添加分类"按钮添加
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
        
        <!-- 右侧：属性面板和预览 -->
        <el-col :span="8">
          <el-card class="properties-card">
            <template #header>
              <span>模板统计</span>
            </template>
            
            <div class="template-stats">
              <div class="stat-item">
                <div class="stat-label">检查分类</div>
                <div class="stat-value">{{ templateData.check_categories.length }}</div>
              </div>
              
              <div class="stat-item">
                <div class="stat-label">检查项总数</div>
                <div class="stat-value">{{ getTotalItems() }}</div>
              </div>
              
              <div class="stat-item">
                <div class="stat-label">站点级检查项</div>
                <div class="stat-value">{{ getSiteLevelItems() }}</div>
              </div>
              
              <div class="stat-item">
                <div class="stat-label">扇区级检查项</div>
                <div class="stat-value">{{ getSectorLevelItems() }}</div>
              </div>
              
              <div class="stat-item">
                <div class="stat-label">设备级检查项</div>
                <div class="stat-value">{{ getDeviceLevelItems() }}</div>
              </div>

              <div class="stat-item">
                <div class="stat-label">小区级检查项</div>
                <div class="stat-value">{{ getCellLevelItems() }}</div>
              </div>
            </div>
          </el-card>
          
          <el-card class="help-card" style="margin-top: 20px;">
            <template #header>
              <span>检查级别说明</span>
            </template>
            
            <div class="help-content">
              <div class="help-item">
                <el-tag type="success" size="small">站点级</el-tag>
                <span>整个站点检查一次（如：供电、环境）</span>
              </div>
              
              <div class="help-item">
                <el-tag type="warning" size="small">扇区级</el-tag>
                <span>每个扇区独立检查（如：天线安装）</span>
              </div>
              
              <div class="help-item">
                <el-tag type="info" size="small">设备级</el-tag>
                <span>每个设备（扇区×频段）独立检查（如：功率测试）</span>
              </div>

              <div class="help-item">
                <el-tag type="danger" size="small">小区级</el-tag>
                <span>每个小区（扇区×频段×EARFCN）独立检查（如：频点相关参数）</span>
              </div>
            </div>
          </el-card>
          
          <el-card class="preview-card" style="margin-top: 20px;">
            <template #header>
              <div class="card-header">
                <span>模板预览</span>
                <el-button size="small" @click="previewTemplate">
                  <el-icon><View /></el-icon>
                  打开预览
                </el-button>
              </div>
            </template>
            <div class="preview-hint">点击“打开预览”查看拟真 App 端检查表单效果</div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>

  <TemplatePreviewDrawer
    v-model="previewVisible"
    :content="previewContent"
    :disabled="false"
    title="模板预览"
  />

  <el-dialog v-model="i18nEditorVisible" :title="i18nEditorTitle" width="680px">
    <div class="i18n-editor">
      <div class="i18n-editor-source">
        <div class="i18n-editor-source-title">原文</div>
        <el-input v-model="i18nEditorSourceText" type="textarea" :rows="4" readonly />
      </div>
      <el-divider />
      <el-form label-width="90px">
        <el-form-item label="英文(en)">
          <el-input v-model="i18nEditorValues.en" type="textarea" :autosize="{ minRows: 2, maxRows: 6 }" />
        </el-form-item>
        <el-form-item label="印尼语(id)">
          <el-input v-model="i18nEditorValues.id" type="textarea" :autosize="{ minRows: 2, maxRows: 6 }" />
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <el-button @click="i18nEditorVisible = false">取消</el-button>
      <el-button :loading="i18nEditorLoading" @click="aiFillI18nInDialog">AI生成</el-button>
      <el-button type="primary" @click="saveI18nEditor">保存</el-button>
    </template>
  </el-dialog>

	  <el-dialog v-model="aiTemplateVisible" title="AI国际化（生成 en / id）" width="520px">
	    <el-alert
	      type="warning"
	      :closable="false"
	      show-icon
      style="margin-bottom: 12px;"
      title="AI 生成的翻译建议人工检查后再保存。"
    />
    <el-form label-width="140px">
      <el-form-item label="覆盖已有翻译">
        <el-switch v-model="aiTemplateOverwrite" />
      </el-form-item>
    </el-form>
	    <template #footer>
	      <el-button @click="aiTemplateVisible = false">取消</el-button>
	      <el-button type="primary" :loading="aiTemplateLoading" @click="runAiTemplateI18n">开始生成</el-button>
	    </template>
	  </el-dialog>

	  <el-dialog
	    v-model="aiTemplateProgressVisible"
	    title="AI翻译进度"
	    width="520px"
	    :show-close="false"
	    :close-on-click-modal="false"
	    :close-on-press-escape="false"
	  >
	    <div class="ai-progress">
	      <el-progress
	        :percentage="aiTemplateProgressPercent"
	        :status="aiTemplateProgressBarStatus"
	      />
	      <div class="ai-progress-meta">
	        <div class="ai-progress-main">
	          已完成 {{ aiTemplateProgress.done }}/{{ aiTemplateProgress.total }}
	          <span v-if="aiTemplateProgress.batchTotal" class="ai-progress-batch">
	            （第 {{ aiTemplateProgress.batchIndex }}/{{ aiTemplateProgress.batchTotal }} 批）
	          </span>
	        </div>
	        <div class="ai-progress-time" v-if="aiTemplateProgress.elapsedSeconds">
	          用时 {{ formatDuration(aiTemplateProgress.elapsedSeconds) }}
	        </div>
	      </div>
	      <div class="ai-progress-status">{{ aiTemplateProgress.message }}</div>
	      <el-alert
	        v-if="aiTemplateProgress.error"
	        type="error"
	        :closable="false"
	        show-icon
	        style="margin-top: 12px;"
	        :title="aiTemplateProgress.error"
	      />
	    </div>
	    <template #footer>
	      <el-button v-if="!aiTemplateProgress.running" type="primary" @click="closeAiTemplateProgress">
	        关闭
	      </el-button>
	    </template>
	  </el-dialog>
	</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, ElLoading } from 'element-plus'
import { 
  ArrowLeft, Check, View, Plus, Delete, DocumentCopy, QuestionFilled, MagicStick, ChatDotRound
} from '@element-plus/icons-vue'
import { templateAPI } from '../../api/templates'
import { aiAPI } from '../../api/ai'
import {
  isStructuralField,
  getFieldDisabledReason,
  getOperationDisabledReason,
  canChangeRequired
} from '../../config/template-field-rules'
import TemplatePreviewDrawer from './components/TemplatePreviewDrawer.vue'

const route = useRoute()
const router = useRouter()

// 响应式数据
const loading = ref(false)
const saving = ref(false)
const template = ref(null)

const templateForm = reactive({
  template_name: '',
  description: ''
})

const templateData = reactive({
  check_categories: []
})

// ===== 多语言与 AI =====
const i18nEditorVisible = ref(false)
const i18nEditorTitle = ref('')
const i18nEditorSourceText = ref('')
const i18nEditorTarget = ref(null)
const i18nEditorI18nKey = ref('')
const i18nEditorValues = reactive({ en: '', id: '' })
const i18nEditorLoading = ref(false)

	const aiTemplateVisible = ref(false)
	const aiTemplateOverwrite = ref(false)
	const aiTemplateLoading = ref(false)
	const aiTemplateProgressVisible = ref(false)
	const aiTemplateProgress = reactive({
	  total: 0,
	  done: 0,
	  batchIndex: 0,
	  batchTotal: 0,
	  message: '',
	  error: '',
	  running: false,
	  elapsedSeconds: 0,
	})
	const aiTemplateProgressPercent = computed(() => {
	  if (!aiTemplateProgress.total) return 0
	  const percent = (aiTemplateProgress.done / aiTemplateProgress.total) * 100
	  return Math.max(0, Math.min(100, Math.round(percent)))
	})
	const aiTemplateProgressBarStatus = computed(() => {
	  if (aiTemplateProgress.error) return 'exception'
	  if (!aiTemplateProgress.running && aiTemplateProgress.total && aiTemplateProgress.done >= aiTemplateProgress.total) {
	    return 'success'
	  }
	  return ''
	})
	let aiTemplateProgressTimer = null
	let aiTemplateProgressStartedAt = 0

	const startAiTemplateProgressTimer = () => {
	  if (aiTemplateProgressTimer) {
	    clearInterval(aiTemplateProgressTimer)
	    aiTemplateProgressTimer = null
	  }
	  aiTemplateProgressStartedAt = Date.now()
	  aiTemplateProgress.elapsedSeconds = 0
	  aiTemplateProgressTimer = setInterval(() => {
	    aiTemplateProgress.elapsedSeconds = Math.max(
	      0,
	      Math.floor((Date.now() - aiTemplateProgressStartedAt) / 1000)
	    )
	  }, 1000)
	}

	const stopAiTemplateProgressTimer = () => {
	  if (!aiTemplateProgressTimer) return
	  clearInterval(aiTemplateProgressTimer)
	  aiTemplateProgressTimer = null
	}

	const closeAiTemplateProgress = () => {
	  if (aiTemplateProgress.running) return
	  aiTemplateProgressVisible.value = false
	  aiTemplateProgress.message = ''
	  aiTemplateProgress.error = ''
	}

	const formatDuration = (seconds) => {
	  const s = Math.max(0, Number(seconds || 0))
	  const m = Math.floor(s / 60)
	  const r = s % 60
	  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`
	}

// 模板使用情况
const templateUsageInfo = ref({
  is_used: false,
  total_inspections: 0,
  active_inspections: 0,
  completed_inspections: 0,
  inspection_details: []
})

// 原始模板数据（用于比对变更）
const originalTemplateData = ref(null)

// 计算属性
const isNewTemplate = computed(() => route.params.id === 'new')

const ensureI18nMap = (targetObj, i18nKey) => {
  if (!targetObj) return null
  const cur = targetObj[i18nKey]
  if (!cur || typeof cur !== 'object' || Array.isArray(cur)) {
    targetObj[i18nKey] = {}
  }
  return targetObj[i18nKey]
}

const openI18nEditor = (targetObj, sourceKey, i18nKey, title) => {
  if (!targetObj) return
  i18nEditorTitle.value = title || '多语言'
  i18nEditorSourceText.value = String(targetObj[sourceKey] || '')
  i18nEditorTarget.value = targetObj
  i18nEditorI18nKey.value = i18nKey

  const cur = targetObj[i18nKey]
  i18nEditorValues.en = (cur && typeof cur === 'object' && !Array.isArray(cur) ? cur.en : '') || ''
  i18nEditorValues.id = (cur && typeof cur === 'object' && !Array.isArray(cur) ? cur.id : '') || ''
  i18nEditorVisible.value = true
}

const openOptionI18n = (opt, evt) => {
  try {
    const target = evt?.target
    if (target?.classList?.contains('el-tag__close') || target?.closest?.('.el-tag__close')) {
      return
    }
  } catch (e) {
    // ignore
  }
  openI18nEditor(opt, 'label', 'label_i18n', '选项标签')
}

const saveI18nEditor = () => {
  const targetObj = i18nEditorTarget.value
  const i18nKey = i18nEditorI18nKey.value
  if (!targetObj || !i18nKey) {
    i18nEditorVisible.value = false
    return
  }
  const map = ensureI18nMap(targetObj, i18nKey)
  map.en = i18nEditorValues.en || ''
  map.id = i18nEditorValues.id || ''
  i18nEditorVisible.value = false
}

const aiFillI18n = async (targetObj, sourceKey, i18nKey) => {
  const text = String(targetObj?.[sourceKey] || '').trim()
  if (!text) {
    ElMessage.warning('原文为空，无法生成翻译')
    return
  }

  const loadingInstance = ElLoading.service({ text: 'AI 生成多语言中...' })
  try {
    const res = await aiAPI.translateBatch({
      items: [
        { key: `${i18nKey}:en`, text, target_locale: 'en' },
        { key: `${i18nKey}:id`, text, target_locale: 'id' },
      ],
    })
    const items = res?.items || []
    const en = items?.[0]?.translation ?? ''
    const id = items?.[1]?.translation ?? ''
    const map = ensureI18nMap(targetObj, i18nKey)
    map.en = en
    map.id = id
    ElMessage.success('AI 多语言已生成')
  } catch (error) {
    console.error('AI 翻译失败:', error)
    ElMessage.error(error?.response?.data?.detail || 'AI 翻译失败')
  } finally {
    loadingInstance.close()
  }
}

const aiFillI18nInDialog = async () => {
  const targetObj = i18nEditorTarget.value
  const i18nKey = i18nEditorI18nKey.value
  const text = String(i18nEditorSourceText.value || '').trim()
  if (!targetObj || !i18nKey) return
  if (!text) {
    ElMessage.warning('原文为空，无法生成翻译')
    return
  }
  i18nEditorLoading.value = true
  try {
    const res = await aiAPI.translateBatch({
      items: [
        { key: `${i18nKey}:en`, text, target_locale: 'en' },
        { key: `${i18nKey}:id`, text, target_locale: 'id' },
      ],
    })
    const items = res?.items || []
    i18nEditorValues.en = items?.[0]?.translation ?? ''
    i18nEditorValues.id = items?.[1]?.translation ?? ''
    ElMessage.success('AI 多语言已生成')
  } catch (error) {
    console.error('AI 翻译失败:', error)
    ElMessage.error(error?.response?.data?.detail || 'AI 翻译失败')
  } finally {
    i18nEditorLoading.value = false
  }
}

	const openAiTemplateI18n = () => {
	  aiTemplateOverwrite.value = false
	  aiTemplateVisible.value = true
	}

	const runAiTemplateI18n = async () => {
	  const tasks = []
	  const appliers = []
	  const overwrite = aiTemplateOverwrite.value === true

  const push = (targetObj, sourceKey, i18nKey, locale, keyPrefix) => {
    const text = String(targetObj?.[sourceKey] || '').trim()
    if (!text) return
    const existing = targetObj?.[i18nKey]?.[locale]
    if (!overwrite && existing && String(existing).trim()) return
    const key = `${keyPrefix || i18nKey}:${locale}`
    tasks.push({ key, text, target_locale: locale })
    appliers.push((translation) => {
      const map = ensureI18nMap(targetObj, i18nKey)
      map[locale] = translation ?? ''
    })
  }

  templateData.check_categories.forEach((cat, ci) => {
    push(cat, 'category_name', 'category_name_i18n', 'en', `cat:${ci}:name`)
    push(cat, 'category_name', 'category_name_i18n', 'id', `cat:${ci}:name`)
    push(cat, 'description', 'description_i18n', 'en', `cat:${ci}:desc`)
    push(cat, 'description', 'description_i18n', 'id', `cat:${ci}:desc`)

    ;(cat.items || []).forEach((item, ii) => {
      push(item, 'item_name', 'item_name_i18n', 'en', `item:${ci}:${ii}:name`)
      push(item, 'item_name', 'item_name_i18n', 'id', `item:${ci}:${ii}:name`)
      push(item, 'description', 'description_i18n', 'en', `item:${ci}:${ii}:desc`)
      push(item, 'description', 'description_i18n', 'id', `item:${ci}:${ii}:desc`)

      ;(item.fields || []).forEach((field, fi) => {
        push(field, 'label', 'label_i18n', 'en', `field:${ci}:${ii}:${fi}:label`)
        push(field, 'label', 'label_i18n', 'id', `field:${ci}:${ii}:${fi}:label`)
        push(field, 'placeholder', 'placeholder_i18n', 'en', `field:${ci}:${ii}:${fi}:ph`)
        push(field, 'placeholder', 'placeholder_i18n', 'id', `field:${ci}:${ii}:${fi}:ph`)
        push(field, 'help_text', 'help_text_i18n', 'en', `field:${ci}:${ii}:${fi}:help`)
        push(field, 'help_text', 'help_text_i18n', 'id', `field:${ci}:${ii}:${fi}:help`)

        ;(field.options || []).forEach((opt, oi) => {
          push(opt, 'label', 'label_i18n', 'en', `opt:${ci}:${ii}:${fi}:${oi}`)
          push(opt, 'label', 'label_i18n', 'id', `opt:${ci}:${ii}:${fi}:${oi}`)
        })
      })
    })
  })

	  if (!tasks.length) {
	    ElMessage.info('没有需要 AI 生成的多语言内容')
	    return
	  }

	  aiTemplateLoading.value = true
	  aiTemplateVisible.value = false
	  aiTemplateProgressVisible.value = true
	  aiTemplateProgress.total = tasks.length
	  aiTemplateProgress.done = 0
	  aiTemplateProgress.batchIndex = 0
	  aiTemplateProgress.batchTotal = 0
	  aiTemplateProgress.message = '准备开始...'
	  aiTemplateProgress.error = ''
	  aiTemplateProgress.running = true
	  startAiTemplateProgressTimer()
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
	    aiTemplateProgress.batchTotal = batchTotal

	    const yieldEvery = tasks.length <= 100 ? 1 : tasks.length <= 300 ? 5 : 10
	    let batchIndex = 0
	    for (let i = 0; i < tasks.length; i += batchSize) {
	      batchIndex += 1
	      aiTemplateProgress.batchIndex = batchIndex
	      const sliceTasks = tasks.slice(i, i + batchSize)
	      const sliceAppliers = appliers.slice(i, i + batchSize)
	      aiTemplateProgress.message = `请求翻译中...（第 ${batchIndex}/${batchTotal} 批，${sliceTasks.length} 条）`
	      const slowTimer = setTimeout(() => {
	        aiTemplateProgress.message = `本批次请求耗时较长（已等待超过 ${slowWarnSeconds} 秒），请继续等待...（第 ${batchIndex}/${batchTotal} 批）`
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
	      const items = res?.items || []
	      aiTemplateProgress.message = `写入翻译结果...（第 ${batchIndex}/${batchTotal} 批）`
	      for (let j = 0; j < sliceAppliers.length; j += 1) {
	        const translation = items?.[j]?.translation ?? ''
	        sliceAppliers[j](translation)
	        aiTemplateProgress.done += 1
	        if (yieldEvery === 1 || aiTemplateProgress.done % yieldEvery === 0) {
	          await nextTick()
	        }
	      }
	    }
	    aiTemplateProgress.message = '已完成'
	    aiTemplateProgress.running = false
	    ElMessage.success('模板多语言已生成，请检查后保存')
	  } catch (error) {
	    console.error('AI 模板翻译失败:', error)
	    const detail = error?.response?.data?.detail || error?.message || 'AI 模板翻译失败'
	    aiTemplateProgress.error = detail
	    aiTemplateProgress.message = '已中止'
	    aiTemplateProgress.running = false
	    ElMessage.error(detail)
	  } finally {
	    aiTemplateLoading.value = false
	    aiTemplateProgress.running = false
	    stopAiTemplateProgressTimer()
	  }
	}

// 方法
const loadTemplate = async () => {
  if (isNewTemplate.value) {
    // 新建模板，初始化空数据
    templateForm.template_name = '新检查模板'
    templateForm.description = ''
    templateData.check_categories = []
    templateUsageInfo.value.is_used = false
    return
  }
  
  loading.value = true
  try {
    // 并行加载模板详情和使用情况
    const [templateResponse, usageResponse] = await Promise.all([
      templateAPI.getTemplate(route.params.id),
      templateAPI.getTemplateUsage(route.params.id)
    ])
    
    template.value = templateResponse
    templateUsageInfo.value = usageResponse
    
    templateForm.template_name = templateResponse.template_name
    templateForm.description = templateResponse.template_data.description || ''
    
    // 深拷贝模板数据并处理 level_type
    templateData.check_categories = JSON.parse(
      JSON.stringify(templateResponse.template_data.check_categories || [])
    )
    
    // 保存原始数据用于比对变更
    originalTemplateData.value = JSON.parse(
      JSON.stringify(templateResponse.template_data)
    )
    
    // 为现有类别设置 level_type 和确保 fields 数组存在
    templateData.check_categories.forEach(category => {
      // 历史兼容：旧模板可能用 level_type='cell' 表示“扇区×频段”（本次统一显示为 device）
      if (category.level_type === 'cell') {
        category.level_type = 'device'
      }

      if (!category.level_type) {
        if (category.cell_specific) {
          category.level_type = 'device'
        } else if (category.sector_specific) {
          category.level_type = 'sector'
        } else {
          category.level_type = 'site'
        }
      }

      // 同步 booleans（用于兼容老数据与后端）
      onLevelTypeChange(category)
      
      // 确保每个检查项都有fields数组，避免旧模板没有fields字段
      if (category.items && Array.isArray(category.items)) {
        category.items.forEach(item => {
          if (!item.fields) {
            item.fields = []
          }
        })
      }
    })
  } catch (error) {
    console.error('加载模板失败:', error)
    ElMessage.error('加载模板失败')
    goBack()
  } finally {
    loading.value = false
  }
}

const saveTemplate = async () => {
  if (!templateForm.template_name.trim()) {
    ElMessage.error('请输入模板名称')
    return
  }
  
  if (templateData.check_categories.length === 0) {
    const confirmed = await ElMessageBox.confirm(
      '模板中没有检查分类，确认保存吗？',
      '确认保存',
      { type: 'warning' }
    ).catch(() => false)
    
    if (!confirmed) return
  }
  
  // 对于已使用的模板，显示变更提示
  if (!isNewTemplate.value && templateUsageInfo.value.is_used) {
    const changes = analyzeChanges()
    
    if (changes.total === 0) {
      ElMessage.warning('未检测到任何变更')
      return
    }
    
    // 构建确认消息
    let confirmMessage = '<div style="text-align: left;">'
    confirmMessage += `<p style="margin-bottom: 12px;"><strong>即将保存以下变更：</strong></p>`
    confirmMessage += `<ul style="margin: 8px 0; padding-left: 20px;">`
    
    if (changes.summary.modified_names > 0) {
      confirmMessage += `<li>修改了 ${changes.summary.modified_names} 个名称</li>`
    }
    if (changes.summary.modified_descriptions > 0) {
      confirmMessage += `<li>修改了 ${changes.summary.modified_descriptions} 个描述</li>`
    }
    if (changes.summary.modified_constraints > 0) {
      confirmMessage += `<li>修改了 ${changes.summary.modified_constraints} 个约束条件</li>`
    }
    if (changes.summary.modified_labels > 0) {
      confirmMessage += `<li>修改了 ${changes.summary.modified_labels} 个字段标签</li>`
    }
    
    confirmMessage += `</ul>`
    confirmMessage += `<div style="background: #FFF7E6; padding: 12px; border-radius: 4px; margin-top: 12px;">`
    confirmMessage += `<p style="color: #E6A23C; font-weight: bold; margin: 0 0 8px 0;">⚠️ 这些变更将自动同步到已使用该模板的 ${templateUsageInfo.value.total_inspections} 个工单</p>`
    confirmMessage += `<p style="color: #909399; font-size: 12px; margin: 0;">其中 ${templateUsageInfo.value.active_inspections} 个工单正在进行中</p>`
    confirmMessage += `</div>`
    confirmMessage += `</div>`
    
    try {
      await ElMessageBox.confirm(confirmMessage, '确认保存', {
        dangerouslyUseHTMLString: true,
        confirmButtonText: '确认保存',
        cancelButtonText: '取消',
        type: 'warning',
        customClass: 'save-confirm-dialog'
      })
    } catch {
      // 用户取消
      return
    }
  }
  
  saving.value = true
  const loadingInstance = ElLoading.service({ text: '保存中...' })
  
  try {
    const templatePayload = {
      template_name: templateForm.template_name,
      template_data: {
        description: templateForm.description,
        check_categories: templateData.check_categories
      }
    }
    
    if (isNewTemplate.value) {
      const newTemplate = await templateAPI.createTemplate(templatePayload)
      ElMessage.success('模板创建成功')
      
      // 跳转到编辑页面
      router.replace({ name: 'TemplateEditor', params: { id: newTemplate.id } })
    } else {
      const response = await templateAPI.updateTemplate(route.params.id, templatePayload)
      
      // 显示保存结果
      let successMessage = '模板保存成功'
      if (response.cascaded_updates_count > 0) {
        successMessage += `，已自动更新 ${response.cascaded_updates_count} 个检查项`
      }
      
      ElMessage.success(successMessage)
      
      // 重新加载模板数据
      await loadTemplate()
    }
  } catch (error) {
    console.error('保存模板失败:', error)
    
    // 处理后端返回的结构性变更错误
    if (error.response && error.response.data && error.response.data.detail) {
      const detail = error.response.data.detail
      if (detail.error === '检测到禁止的结构性变更') {
        ElMessageBox.alert(
          `<div style="text-align: left;">
            <p><strong>${detail.message}</strong></p>
            <p style="margin-top: 12px; color: #909399;">禁止的变更：</p>
            <ul style="margin: 8px 0; padding-left: 20px; color: #F56C6C;">
              ${detail.violations.map(v => `<li>${v}</li>`).join('')}
            </ul>
          </div>`,
          '保存失败',
          {
            dangerouslyUseHTMLString: true,
            type: 'error'
          }
        )
      } else {
        ElMessage.error(typeof detail === 'string' ? detail : '保存模板失败')
      }
    } else {
      ElMessage.error('保存模板失败')
    }
  } finally {
    saving.value = false
    loadingInstance.close()
  }
}

// 分析变更（前端简单比对）
const analyzeChanges = () => {
  const changes = {
    total: 0,
    summary: {
      modified_names: 0,
      modified_descriptions: 0,
      modified_constraints: 0,
      modified_labels: 0
    }
  }
  
  if (!originalTemplateData.value) {
    return changes
  }
  
  // 简单的 JSON 字符串比对
  const oldJson = JSON.stringify(originalTemplateData.value)
  const newJson = JSON.stringify({
    description: templateForm.description,
    check_categories: templateData.check_categories
  })
  
  if (oldJson !== newJson) {
    // 这里简化处理，实际可以做更详细的对比
    // 后端会做准确的变更分析
    changes.total = 1
    changes.summary.modified_names = 1 // 示例值
  }
  
  return changes
}

const addCategory = () => {
  const newCategory = {
    category_id: `category_${Date.now()}`,
    category_name: '新检查分类',
    description: '',
    sector_specific: false,
    cell_specific: false,
    level_type: 'site', // 默认为站点级
    items: []
  }
  
  templateData.check_categories.push(newCategory)
}

// 处理检查级别变更
const onLevelTypeChange = (category) => {
  switch (category.level_type) {
    case 'site':
      category.sector_specific = false
      category.cell_specific = false
      break
    case 'sector':
      category.sector_specific = true
      category.cell_specific = false
      break
    case 'device':
    case 'cell': // 历史兼容
    case 'cell_earfcn':
      category.sector_specific = false
      category.cell_specific = true
      break
  }
}

const normalizeLevelType = (category) => {
  const lt = category?.level_type
  if (lt === 'cell') return 'device'
  if (!lt) {
    if (category?.cell_specific) return 'device'
    if (category?.sector_specific) return 'sector'
    return 'site'
  }
  return lt
}

const getLevelLabel = (category) => {
  const lt = normalizeLevelType(category)
  switch (lt) {
    case 'site':
      return '站点级'
    case 'sector':
      return '扇区级'
    case 'device':
      return '设备级'
    case 'cell_earfcn':
      return '小区级'
    default:
      return '站点级'
  }
}

const getLevelTagType = (category) => {
  const lt = normalizeLevelType(category)
  switch (lt) {
    case 'site':
      return 'success'
    case 'sector':
      return 'warning'
    case 'device':
      return 'info'
    case 'cell_earfcn':
      return 'danger'
    default:
      return 'success'
  }
}

const removeCategory = async (categoryIndex) => {
  try {
    await ElMessageBox.confirm(
      '确认删除这个检查分类吗？',
      '删除确认',
      { type: 'warning' }
    )
    
    templateData.check_categories.splice(categoryIndex, 1)
    ElMessage.success('分类已删除')
  } catch (error) {
    // 用户取消
  }
}

const addItem = (categoryIndex) => {
  const newItem = {
    item_id: `item_${Date.now()}`,
    item_name: '新检查项',
    description: '',
    required_type: 'photo',
    assigned_role: 'inspector',
    status: 'pending',
    fields: []  // 初始化fields数组，确保字段配置能被正确保存
  }
  
  templateData.check_categories[categoryIndex].items.push(newItem)
}

const removeItem = async (categoryIndex, itemIndex) => {
  try {
    await ElMessageBox.confirm(
      '确认删除这个检查项吗？',
      '删除确认',
      { type: 'warning' }
    )
    
    templateData.check_categories[categoryIndex].items.splice(itemIndex, 1)
    ElMessage.success('检查项已删除')
  } catch (error) {
    // 用户取消
  }
}

// 字段编辑方法
const addField = (categoryIndex, itemIndex) => {
  const item = templateData.check_categories[categoryIndex].items[itemIndex]
  if (!item.fields) item.fields = []
  item.fields.push({
    field_id: `field_${Date.now()}`,
    label: '新字段',
    type: 'text',
    required: false,
    help_text: '',
    allow_photo: false,
    photo_required: false,
    options: [],
    constraints: {},
  })
}

const removeField = (categoryIndex, itemIndex, fieldIndex) => {
  const item = templateData.check_categories[categoryIndex].items[itemIndex]
  if (!item.fields) return
  item.fields.splice(fieldIndex, 1)
}

const addOption = (field) => {
  if (!field._newOptionLabel && !field._newOptionValue) return
  if (!field.options) field.options = []
  field.options.push({ label: field._newOptionLabel || String(field._newOptionValue || ''), value: field._newOptionValue || field._newOptionLabel })
  field._newOptionLabel = ''
  field._newOptionValue = ''
}

const removeOption = (field, index) => {
  field.options.splice(index, 1)
}

const previewVisible = ref(false)
const previewContent = computed(() => ({
  meta: {
    template: { name: templateForm.template_name, version: template.value?.template_data?.template_version }
  },
  check_categories: templateData.check_categories
}))

const previewTemplate = () => {
  if (!templateData.check_categories.length) {
    ElMessage.warning('请先添加检查项再预览')
    return
  }
  previewVisible.value = true
}

const copyJson = async () => {
  try {
    await navigator.clipboard.writeText(JSON.stringify(templateData, null, 2))
    ElMessage.success('JSON 已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败')
  }
}

const goBack = () => {
  router.push({ name: 'InspectionTemplates' })
}

// 统计方法
const getTotalItems = () => {
  return templateData.check_categories.reduce((total, category) => {
    return total + category.items.length
  }, 0)
}

const getSiteLevelItems = () => {
  return templateData.check_categories.reduce((total, category) => {
    return total + (normalizeLevelType(category) === 'site' ? category.items.length : 0)
  }, 0)
}

const getSectorLevelItems = () => {
  return templateData.check_categories.reduce((total, category) => {
    return total + (normalizeLevelType(category) === 'sector' ? category.items.length : 0)
  }, 0)
}

const getDeviceLevelItems = () => {
  return templateData.check_categories.reduce((total, category) => {
    return total + (normalizeLevelType(category) === 'device' ? category.items.length : 0)
  }, 0)
}

const getCellLevelItems = () => {
  return templateData.check_categories.reduce((total, category) => {
    return total + (normalizeLevelType(category) === 'cell_earfcn' ? category.items.length : 0)
  }, 0)
}

// 字段禁用控制函数
const isFieldDisabled = (level, fieldName) => {
  if (!templateUsageInfo.value.is_used) {
    return false // 未使用，都不禁用
  }
  return isStructuralField(level, fieldName)
}

const getFieldTooltip = (level, fieldName) => {
  if (!templateUsageInfo.value.is_used) {
    return ''
  }
  return getFieldDisabledReason(level, fieldName, true) || ''
}

const isOperationDisabled = (operation) => {
  if (!templateUsageInfo.value.is_used) {
    return false
  }
  return true // 已使用，禁用所有结构性操作
}

const getDisabledReason = (operation) => {
  return getOperationDisabledReason(operation, templateUsageInfo.value.is_used)
}

// 特殊处理：required 字段
const isRequiredFieldDisabled = (field) => {
  if (!templateUsageInfo.value.is_used) {
    return false
  }
  
  // 如果当前是 true，允许改为 false（放宽限制）
  if (field.required) {
    return false
  }
  
  // 如果当前是 false，不能在模板已使用时改为 true
  // 这里不能直接禁用，因为会影响交互，而是在点击时阻止
  // 但为了用户体验，我们还是禁用
  return true
}

const getRequiredFieldTooltip = (field) => {
  if (!templateUsageInfo.value.is_used) {
    return ''
  }
  
  if (!field.required) {
    return '该检查模板已有工单使用，不允许将字段从非必填改为必填'
  }
  
  return ''
}

// 生命周期
onMounted(() => {
  loadTemplate()
})
</script>

<style scoped>
.template-editor {
  padding: 20px;
  min-height: calc(100vh - 140px);
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e6e6e6;
}

.header-left {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.template-title h2 {
  margin: 0 0 4px 0;
  font-size: 24px;
  font-weight: 600;
}

.template-title p {
  margin: 0;
  color: #666;
  font-size: 14px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.i18n-inline {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.i18n-inline--item {
  flex: 1;
}

.i18n-inline .el-input,
.i18n-inline .el-textarea {
  flex: 1;
}

.i18n-actions {
  margin-left: 0;
}

.i18n-actions--compact {
  margin-left: 8px;
}

.option-tag {
  cursor: pointer;
}

.i18n-editor-source-title {
  font-size: 12px;
  color: #666;
  margin-bottom: 6px;
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

.editor-content {
  min-height: 600px;
}

.usage-warning {
  margin-bottom: 20px;
}

.usage-warning p {
  line-height: 1.6;
}

.editor-card,
.properties-card,
.json-preview-card {
  border: 1px solid #e6e6e6;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.loading-container {
  padding: 20px;
}

.template-basic-form {
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f0f0f0;
}

.categories-list {
  space-y: 20px;
}

.category-item {
  background: #fafafa;
  border: 1px solid #e6e6e6;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.category-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.category-title {
  flex: 1;
  display: flex;
  align-items: center;
}

.category-description {
  margin-bottom: 16px;
}

.items-list {
  space-y: 8px;
}

.item-row {
  background: white;
  border: 1px solid #e6e6e6;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 8px;
}

.fields-card {
  margin-top: 8px;
}
.field-line-labels {
  display: flex;
  margin-bottom: 4px;
}
.field-label-with-help {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #666;
}
.field-help-icon {
  cursor: pointer;
  font-size: 14px;
}
.field-row { border-top: 1px dashed #eee; padding-top: 8px; margin-top: 8px; }
.field-line { display:flex; align-items:center; }
.field-advanced { padding-left: 0; margin-top: 8px; }
.constraints { margin-top: 6px; display:flex; align-items:center; gap:8px; }
.options-line { margin-top: 6px; display:flex; align-items:center; flex-wrap: wrap; }
.help-text { margin-top: 6px; display:flex; align-items:flex-start; gap:8px; flex-wrap: wrap; }
.placeholder-line { margin-top: 6px; display:flex; align-items:center; gap:8px; flex-wrap: wrap; }
.empty-fields { color:#999; padding: 8px 0; }

.item-basic {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.item-basic .el-input {
  flex: 1;
}

.no-categories,
.no-items {
  text-align: center;
  color: #999;
  padding: 40px 20px;
  background: #f9f9f9;
  border-radius: 6px;
  border: 1px dashed #ddd;
}

.template-stats {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f9f9f9;
  border-radius: 6px;
}

.stat-label {
  font-size: 14px;
  color: #666;
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: #409eff;
}

.json-content {
  font-size: 12px;
  line-height: 1.5;
  max-height: 300px;
  overflow-y: auto;
  background: #f9f9f9;
  padding: 12px;
  border-radius: 4px;
  margin: 0;
}

.help-content {
  background: #f0f9ff;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 16px;
}

.help-item {
  margin-bottom: 12px;
  padding: 8px 12px;
  background: #ffffff;
  border-radius: 4px;
  border-left: 3px solid #3b82f6;
}

.help-item:last-child {
  margin-bottom: 0;
}

.help-item strong {
  color: #1e40af;
  font-weight: 600;
}
</style>

<style>
.json-preview-dialog .el-message-box__message {
  font-family: 'Courier New', monospace;
  white-space: pre-wrap;
  max-height: 400px;
  overflow-y: auto;
  background: #f5f5f5;
  padding: 12px;
  border-radius: 4px;
}
</style>
