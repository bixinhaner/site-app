<template>
  <el-dialog
    v-model="dialogVisible"
    title="模板解析测试"
    width="80%"
    top="5vh"
  >
    <div class="resolver-test-panel">
      <el-row :gutter="20">
        <!-- 左侧：测试输入 -->
        <el-col :span="12">
          <div class="test-input">
            <h4>解析上下文</h4>
            <el-form :model="testContext" label-width="100px">
              <el-form-item label="站点ID">
                <el-input-number 
                  v-model="testContext.site_id" 
                  placeholder="输入站点ID"
                  :min="1"
                  controls-position="right"
                  style="width: 100%"
                />
              </el-form-item>
              
              <el-form-item label="站点类型">
                <el-select 
                  v-model="testContext.site_type" 
                  placeholder="选择站点类型"
                  clearable
                  style="width: 100%"
                >
                  <el-option
                    v-for="(label, value) in SITE_TYPE_LABELS"
                    :key="value"
                    :label="label"
                    :value="value"
                  />
                </el-select>
              </el-form-item>
              
              <el-form-item label="任务类型">
                <el-select 
                  v-model="testContext.task_type" 
                  placeholder="选择任务类型"
                  clearable
                  style="width: 100%"
                >
                  <el-option
                    v-for="(label, value) in TASK_TYPE_LABELS"
                    :key="value"
                    :label="label"
                    :value="value"
                  />
                </el-select>
              </el-form-item>
              
              <el-form-item label="任务ID">
                <el-input 
                  v-model="testContext.task_id" 
                  placeholder="输入任务ID"
                />
              </el-form-item>
              
              <el-form-item label="区域">
                <el-input 
                  v-model="testContext.region" 
                  placeholder="输入区域"
                />
              </el-form-item>
              
              <el-form-item label="客户">
                <el-input 
                  v-model="testContext.customer" 
                  placeholder="输入客户"
                />
              </el-form-item>
              
              <el-form-item label="标签">
                <el-input 
                  v-model="testContext.tagsInput" 
                  placeholder="多个标签用逗号分隔"
                />
              </el-form-item>
              
              <el-form-item>
                <el-button 
                  type="primary" 
                  @click="runTest" 
                  :loading="testing"
                  style="width: 100%;"
                >
                  <el-icon><Search /></el-icon>
                  执行解析测试
                </el-button>
              </el-form-item>
              
              <el-form-item>
                <el-checkbox v-model="showAllResults">
                  显示所有匹配结果
                </el-checkbox>
              </el-form-item>
            </el-form>
          </div>
        </el-col>
        
        <!-- 右侧：测试结果 -->
        <el-col :span="12">
          <div class="test-results">
            <h4>解析结果</h4>
            
            <div v-if="!testResult && !testing" class="no-result">
              <el-empty description="请输入测试条件并执行测试" />
            </div>
            
            <div v-else-if="testing" class="testing">
              <el-skeleton :rows="6" animated />
            </div>
            
            <div v-else-if="testResult" class="result-content">
              <div v-if="testResult.success" class="success-result">
                <!-- 最佳匹配结果 -->
                <div v-if="testResult.result" class="best-match">
                  <div class="result-header">
                    <el-tag type="success" size="large">
                      最佳匹配
                    </el-tag>
                    <el-tag type="info" size="small">
                      匹配度: {{ testResult.result.match_score.toFixed(1) }}
                    </el-tag>
                  </div>
                  
                  <div class="match-details">
                    <div class="template-info">
                      <strong>{{ testResult.result.template_name }}</strong>
                      <div class="template-id">ID: {{ testResult.result.template_id }}</div>
                    </div>
                    
                    <div class="binding-info">
                      <div class="binding-conditions">
                        <el-tag 
                          v-if="testResult.result.binding_details.site_id" 
                          type="warning" 
                          size="small"
                        >
                          站点: {{ testResult.result.binding_details.site_id }}
                        </el-tag>
                        <el-tag 
                          v-if="testResult.result.binding_details.site_type" 
                          type="info" 
                          size="small"
                        >
                          类型: {{ SITE_TYPE_LABELS[testResult.result.binding_details.site_type] }}
                        </el-tag>
                        <el-tag 
                          v-if="testResult.result.binding_details.task_type" 
                          type="success" 
                          size="small"
                        >
                          任务: {{ TASK_TYPE_LABELS[testResult.result.binding_details.task_type] }}
                        </el-tag>
                        <el-tag 
                          v-if="testResult.result.binding_details.region" 
                          type="primary" 
                          size="small"
                        >
                          区域: {{ testResult.result.binding_details.region }}
                        </el-tag>
                      </div>
                      
                      <div class="explanation">
                        <strong>解释:</strong> {{ testResult.result.explain }}
                      </div>
                    </div>
                  </div>
                </div>
                
                <!-- 所有匹配结果 -->
                <div v-if="showAllResults && testResult.all_matches && testResult.all_matches.length > 1" class="all-matches">
                  <h5>所有匹配结果 ({{ testResult.all_matches.length }})</h5>
                  
                  <div 
                    v-for="(match, index) in testResult.all_matches" 
                    :key="match.binding_id"
                    class="match-item"
                    :class="{ 'best-match-highlight': index === 0 }"
                  >
                    <div class="match-header">
                      <span class="match-rank">#{{ index + 1 }}</span>
                      <span class="template-name">{{ match.template_name }}</span>
                      <el-tag size="small" :type="index === 0 ? 'success' : 'info'">
                        {{ match.match_score.toFixed(1) }}
                      </el-tag>
                    </div>
                    
                    <div class="match-explain">
                      {{ match.explain }}
                    </div>
                  </div>
                </div>
              </div>
              
              <div v-else class="no-match-result">
                <el-alert
                  title="无匹配结果"
                  :description="testResult.message"
                  type="warning"
                  show-icon
                />
              </div>
            </div>
          </div>
        </el-col>
      </el-row>
    </div>
    
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="closeDialog">关闭</el-button>
        <el-button @click="clearTest">清空测试</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { resolverAPI, TASK_TYPE_LABELS, SITE_TYPE_LABELS } from '../../../api/templates'

// Props & Emits
const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'test'])

// 响应式数据
const testing = ref(false)
const showAllResults = ref(true)
const testResult = ref(null)

const testContext = reactive({
  site_id: null,
  site_type: '',
  task_type: '',
  task_id: '',
  region: '',
  customer: '',
  tagsInput: ''
})

// 计算属性
const dialogVisible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

// 方法
const runTest = async () => {
  testing.value = true
  testResult.value = null
  
  try {
    // 构建测试上下文
    const context = {
      site_id: testContext.site_id || null,
      site_type: testContext.site_type || null,
      task_type: testContext.task_type || null,
      task_id: testContext.task_id || null,
      region: testContext.region || null,
      customer: testContext.customer || null,
      tags: testContext.tagsInput ? 
        testContext.tagsInput.split(',').map(t => t.trim()).filter(t => t) : 
        null
    }
    
    // 调用解析API
    const result = await resolverAPI.resolveTemplate(context, showAllResults.value)
    testResult.value = result
    
    if (result.success) {
      ElMessage.success('解析测试完成')
    } else {
      ElMessage.info('未找到匹配的模板')
    }
    
    emit('test', context)
  } catch (error) {
    console.error('解析测试失败:', error)
    ElMessage.error('解析测试失败')
    testResult.value = {
      success: false,
      message: error.message || '测试执行出错'
    }
  } finally {
    testing.value = false
  }
}

const clearTest = () => {
  testContext.site_id = null
  testContext.site_type = ''
  testContext.task_type = ''
  testContext.task_id = ''
  testContext.region = ''
  testContext.customer = ''
  testContext.tagsInput = ''
  testResult.value = null
}

const closeDialog = () => {
  dialogVisible.value = false
}

// 监听对话框打开，重置状态
watch(dialogVisible, (newVal) => {
  if (newVal) {
    clearTest()
  }
})
</script>

<style scoped>
.resolver-test-panel {
  min-height: 500px;
}

.test-input,
.test-results {
  height: 100%;
}

.test-input h4,
.test-results h4 {
  margin: 0 0 16px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid #eee;
  font-size: 16px;
  font-weight: 600;
}

.no-result {
  height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.testing {
  padding: 20px;
}

.result-content {
  max-height: 500px;
  overflow-y: auto;
}

.success-result {
  space-y: 20px;
}

.best-match {
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 20px;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.template-info {
  margin-bottom: 12px;
}

.template-info strong {
  font-size: 16px;
}

.template-id {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}

.binding-conditions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.explanation {
  font-size: 14px;
  color: #666;
  line-height: 1.5;
}

.all-matches {
  margin-top: 20px;
}

.all-matches h5 {
  margin: 0 0 16px 0;
  font-size: 14px;
  font-weight: 600;
  color: #666;
}

.match-item {
  background: #fafafa;
  border: 1px solid #e6e6e6;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 8px;
}

.best-match-highlight {
  background: #f0f9ff;
  border-color: #bae6fd;
}

.match-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.match-rank {
  font-size: 12px;
  font-weight: 600;
  color: #666;
  margin-right: 8px;
}

.template-name {
  flex: 1;
  font-weight: 500;
}

.match-explain {
  font-size: 12px;
  color: #666;
  line-height: 1.4;
}

.no-match-result {
  padding: 20px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>