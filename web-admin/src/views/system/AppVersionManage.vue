<template>
  <div class="app-version-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <h1>App版本管理</h1>
      <div class="header-actions">
        <el-button type="primary" @click="showPublishDialog = true">
          <el-icon><Upload /></el-icon>
          发布新版本
        </el-button>
        <el-button @click="loadVersionList" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <el-card class="stat-card">
        <div class="stat-content">
          <el-icon class="stat-icon" :size="32"><Box /></el-icon>
          <div class="stat-info">
            <span class="stat-value">{{ stats.total_versions || 0 }}</span>
            <span class="stat-label">总版本数</span>
          </div>
        </div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-content">
          <el-icon class="stat-icon success" :size="32"><CircleCheck /></el-icon>
          <div class="stat-info">
            <span class="stat-value">{{ stats.active_versions || 0 }}</span>
            <span class="stat-label">活跃版本</span>
          </div>
        </div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-content">
          <el-icon class="stat-icon primary" :size="32"><Download /></el-icon>
          <div class="stat-info">
            <span class="stat-value">{{ stats.total_downloads || 0 }}</span>
            <span class="stat-label">总下载量</span>
          </div>
        </div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-content">
          <el-icon class="stat-icon warning" :size="32"><Cpu /></el-icon>
          <div class="stat-info">
            <span class="stat-value">{{ stats.latest_version || '-' }}</span>
            <span class="stat-label">最新版本</span>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 版本列表 -->
    <el-card class="table-card">
      <el-table :data="versionList" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="version_name" label="版本号" width="120">
          <template #default="{ row }">
            <span class="version-name">v{{ row.version_name }}</span>
            <el-tag v-if="row.is_latest" type="success" size="small" style="margin-left: 8px">最新</el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="version_code" label="版本码" width="100" />
        
        <el-table-column prop="update_type" label="更新类型" width="120">
          <template #default="{ row }">
            <el-tag :type="getUpdateTypeTag(row.update_type)">
              {{ getUpdateTypeLabel(row.update_type) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="gray_scale_percent" label="灰度比例" width="120">
          <template #default="{ row }">
            <el-progress 
              :percentage="row.gray_scale_percent" 
              :stroke-width="8"
              :format="() => row.gray_scale_percent + '%'"
            />
          </template>
        </el-table-column>
        
        <el-table-column prop="file_size" label="文件大小" width="120">
          <template #default="{ row }">
            {{ formatFileSize(row.file_size) }}
          </template>
        </el-table-column>
        
        <el-table-column prop="download_count" label="下载次数" width="100" />
        
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-switch 
              v-model="row.is_active" 
              @change="handleStatusChange(row)"
              :loading="row._switching"
            />
          </template>
        </el-table-column>
        
        <el-table-column prop="published_at" label="发布时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.published_at) }}
          </template>
        </el-table-column>
        
        <el-table-column prop="release_notes" label="更新说明" min-width="200">
          <template #default="{ row }">
            <el-tooltip :content="row.release_notes || '-'" placement="top" :show-after="500">
              <span class="ellipsis-text">{{ row.release_notes || '-' }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="editVersion(row)">
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            <el-button type="success" size="small" link @click="openReleaseNotesEditor(row)">
              <el-icon><Document /></el-icon>
              详情页
            </el-button>
            <el-button type="info" size="small" link @click="copyDownloadUrl(row)">
              <el-icon><Link /></el-icon>
              链接
            </el-button>
            <el-button type="danger" size="small" link @click="deleteVersion(row)">
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.size"
          :page-sizes="[10, 20, 50]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 发布新版本对话框 -->
    <el-dialog 
      v-model="showPublishDialog" 
      :title="editingVersion ? '编辑版本' : '发布新版本'" 
      width="700px"
      @close="resetForm"
    >
      <el-form 
        ref="formRef" 
        :model="versionForm" 
        :rules="formRules" 
        label-width="120px"
      >
        <!-- 步骤1：上传APK -->
        <el-form-item label="APK文件" prop="download_url" v-if="!editingVersion">
          <div class="upload-section">
            <el-upload
              ref="uploadRef"
              :auto-upload="false"
              :limit="1"
              accept=".apk"
              :on-change="handleFileChange"
              :on-remove="handleFileRemove"
              :file-list="fileList"
              drag
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                将 APK 文件拖到此处，或 <em>点击上传</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">只能上传 .apk 文件</div>
              </template>
            </el-upload>
            
            <!-- 上传进度 -->
            <div v-if="uploading" class="upload-progress">
              <el-progress :percentage="uploadProgress" :status="uploadProgress === 100 ? 'success' : ''" />
              <span class="progress-text">{{ uploadProgress === 100 ? '上传完成' : '上传中...' }}</span>
            </div>
            
            <!-- 已上传文件信息 -->
            <div v-if="uploadedFileInfo" class="uploaded-info">
              <el-descriptions :column="2" size="small" border>
                <el-descriptions-item label="文件名">{{ uploadedFileInfo.file_name }}</el-descriptions-item>
                <el-descriptions-item label="文件大小">{{ formatFileSize(uploadedFileInfo.file_size) }}</el-descriptions-item>
                <el-descriptions-item label="MD5">{{ uploadedFileInfo.file_md5 }}</el-descriptions-item>
              </el-descriptions>
            </div>
          </div>
        </el-form-item>

        <el-divider v-if="!editingVersion" />
        
        <!-- 版本信息 -->
        <el-form-item label="版本号" prop="version_name">
          <el-input 
            v-model="versionForm.version_name" 
            placeholder="例如：1.2.0"
            :disabled="!!editingVersion"
          >
            <template #prepend>v</template>
          </el-input>
        </el-form-item>
        
        <el-form-item label="版本码" prop="version_code">
          <el-input-number 
            v-model="versionForm.version_code" 
            :min="1"
            :disabled="!!editingVersion"
            placeholder="例如：10200"
          />
          <span class="form-tip">版本码应大于当前版本，通常格式：主版本*10000 + 次版本*100 + 修订版本</span>
        </el-form-item>
        
        <el-form-item label="更新类型" prop="update_type">
          <el-radio-group v-model="versionForm.update_type">
            <el-radio-button value="force">
              <el-icon><Warning /></el-icon>
              强制更新
            </el-radio-button>
            <el-radio-button value="recommend">
              <el-icon><InfoFilled /></el-icon>
              推荐更新
            </el-radio-button>
            <el-radio-button value="silent">
              <el-icon><Hide /></el-icon>
              静默更新
            </el-radio-button>
          </el-radio-group>
          <div class="update-type-tip">
            <span v-if="versionForm.update_type === 'force'">⚠️ 用户必须升级才能使用App</span>
            <span v-else-if="versionForm.update_type === 'recommend'">💡 弹窗提示用户，可选择跳过</span>
            <span v-else-if="versionForm.update_type === 'silent'">🔇 后台静默下载，下次启动安装</span>
          </div>
        </el-form-item>
        
        <el-form-item label="灰度比例" prop="gray_scale_percent">
          <el-slider 
            v-model="versionForm.gray_scale_percent" 
            :min="0" 
            :max="100"
            :marks="{ 0: '0%', 25: '25%', 50: '50%', 75: '75%', 100: '100%' }"
            show-input
          />
        </el-form-item>
        
        <el-form-item label="最低兼容版本" prop="min_version_code">
          <el-input-number 
            v-model="versionForm.min_version_code" 
            :min="0"
            placeholder="低于此版本强制更新"
          />
        </el-form-item>
        
        <el-form-item label="更新说明" prop="release_notes">
          <el-input 
            v-model="versionForm.release_notes" 
            type="textarea" 
            :rows="4"
            placeholder="请输入更新说明，每条一行&#10;• 新增xxx功能&#10;• 优化xxx体验&#10;• 修复已知问题"
          />
        </el-form-item>
        
        <el-form-item label="英文说明" prop="release_notes_en">
          <el-input 
            v-model="versionForm.release_notes_en" 
            type="textarea" 
            :rows="3"
            placeholder="可选，用于多语言支持"
          />
        </el-form-item>
        
        <el-form-item label="立即发布" prop="is_active">
          <el-switch v-model="versionForm.is_active" />
          <span class="form-tip">关闭则保存为草稿，不会推送给用户</span>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showPublishDialog = false">取消</el-button>
        <el-button 
          type="primary" 
          @click="handleSubmit" 
          :loading="submitting"
          :disabled="!editingVersion && !uploadedFileInfo"
        >
          {{ editingVersion ? '保存修改' : '发布版本' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- Release Notes 编辑器对话框 -->
    <el-dialog 
      v-model="showReleaseNotesDialog" 
      title="Release Notes 详情页编辑"
      width="900px"
      @close="resetReleaseNotesForm"
    >
      <div class="release-notes-editor">
        <!-- 已有Release Notes提示 -->
        <el-alert 
          v-if="releaseNotesForm.id" 
          type="success" 
          :closable="false"
          style="margin-bottom: 20px"
        >
          <template #title>
            <span>该版本已创建 Release Notes 页面</span>
            <el-button type="primary" link @click="previewReleaseNotes">
              <el-icon><View /></el-icon>
              预览页面
            </el-button>
          </template>
        </el-alert>

        <el-form :model="releaseNotesForm" label-width="100px">
          <!-- 启用开关 -->
          <el-form-item label="启用">
            <el-switch v-model="releaseNotesForm.is_enabled" />
            <span class="form-tip">关闭后用户将无法查看此 Release Notes 页面</span>
          </el-form-item>

          <el-divider />

          <!-- 标题区域 -->
          <el-form-item label="页面标题">
            <el-input v-model="releaseNotesForm.title" placeholder="例如：v1.2.0 重大更新" />
          </el-form-item>
          <el-form-item label="英文标题">
            <el-input v-model="releaseNotesForm.title_en" placeholder="例如：v1.2.0 Major Update" />
          </el-form-item>
          <el-form-item label="副标题">
            <el-input v-model="releaseNotesForm.subtitle" placeholder="例如：全新的用户体验" />
          </el-form-item>
          <el-form-item label="英文副标题">
            <el-input v-model="releaseNotesForm.subtitle_en" placeholder="例如：Brand New Experience" />
          </el-form-item>

          <el-divider />

          <!-- 更新项目列表 -->
          <el-form-item label="更新项目">
            <div class="items-list">
              <div 
                v-for="(item, index) in releaseNotesForm.items" 
                :key="index"
                class="item-card"
                :class="{ 'image-card': item.item_type === 'image' }"
              >
                <div class="item-header">
                  <span class="item-number">{{ index + 1 }}</span>
                  <el-tag :type="item.item_type === 'text' ? 'primary' : 'success'" size="small">
                    {{ item.item_type === 'text' ? '📝 文字' : '🖼️ 图片' }}
                  </el-tag>
                  <div class="item-actions">
                    <el-button 
                      type="primary" 
                      link 
                      size="small"
                      :disabled="index === 0"
                      @click="moveItem(index, -1)"
                    >
                      <el-icon><Top /></el-icon>
                    </el-button>
                    <el-button 
                      type="primary" 
                      link 
                      size="small"
                      :disabled="index === releaseNotesForm.items.length - 1"
                      @click="moveItem(index, 1)"
                    >
                      <el-icon><Bottom /></el-icon>
                    </el-button>
                    <el-button type="danger" link size="small" @click="removeItem(index)">
                      <el-icon><Delete /></el-icon>
                    </el-button>
                  </div>
                </div>

                <!-- 文字项目 -->
                <template v-if="item.item_type === 'text'">
                  <el-input 
                    v-model="item.content" 
                    type="textarea" 
                    :rows="2" 
                    placeholder="中文内容"
                    style="margin-bottom: 8px"
                  />
                  <el-input 
                    v-model="item.content_en" 
                    type="textarea" 
                    :rows="2" 
                    placeholder="英文内容（可选）"
                  />
                </template>

                <!-- 图片项目 -->
                <template v-else-if="item.item_type === 'image'">
                  <div class="image-upload-area">
                    <el-upload
                      v-if="!item.image_url"
                      :auto-upload="false"
                      :show-file-list="false"
                      accept=".jpg,.jpeg,.png,.gif,.webp"
                      @change="(file) => handleImageUpload(file, index)"
                    >
                      <el-button type="primary">
                        <el-icon><Upload /></el-icon>
                        选择图片
                      </el-button>
                      <template #tip>
                        <div class="upload-tip">支持 jpg/png/gif/webp，最大 5MB</div>
                      </template>
                    </el-upload>
                    <div v-else class="image-preview">
                      <img :src="getFullImageUrl(item.image_url)" @error="handleImageError" />
                      <el-button 
                        type="danger" 
                        size="small" 
                        class="remove-image-btn"
                        @click="item.image_url = ''"
                      >
                        移除图片
                      </el-button>
                    </div>
                  </div>
                  <el-input 
                    v-model="item.image_caption" 
                    placeholder="图片说明（中文）"
                    style="margin-top: 8px"
                  />
                  <el-input 
                    v-model="item.image_caption_en" 
                    placeholder="图片说明（英文，可选）"
                    style="margin-top: 8px"
                  />
                </template>
              </div>

              <!-- 添加按钮 -->
              <div class="add-buttons">
                <el-button @click="addItem('text')">
                  <el-icon><Plus /></el-icon>
                  添加文字项目
                </el-button>
                <el-button @click="addItem('image')">
                  <el-icon><Picture /></el-icon>
                  添加图片项目
                </el-button>
              </div>
            </div>
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <el-button @click="showReleaseNotesDialog = false">取消</el-button>
        <el-button 
          v-if="releaseNotesForm.id"
          type="danger" 
          @click="deleteReleaseNotes"
          :loading="releaseNotesSubmitting"
        >
          删除 Release Notes
        </el-button>
        <el-button 
          type="primary" 
          @click="saveReleaseNotes"
          :loading="releaseNotesSubmitting"
        >
          {{ releaseNotesForm.id ? '保存修改' : '创建 Release Notes' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Upload, Refresh, Box, CircleCheck, Download, Cpu, Edit, Delete, Link,
  UploadFilled, Warning, InfoFilled, Hide, Document, View, Top, Bottom, Plus, Picture
} from '@element-plus/icons-vue'
import { appVersionAPI } from '@/api/appVersion'
import config from '@/config/env.js'
import { useRouter } from 'vue-router'

const router = useRouter()

// 响应式数据
const loading = ref(false)
const versionList = ref([])
const stats = ref({})

// 分页
const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})

// 对话框相关
const showPublishDialog = ref(false)
const editingVersion = ref(null)
const formRef = ref()
const uploadRef = ref()

// 表单数据
const versionForm = reactive({
  version_name: '',
  version_code: null,
  update_type: 'recommend',
  download_url: '',
  file_size: 0,
  file_md5: '',
  file_name: '',
  release_notes: '',
  release_notes_en: '',
  min_version_code: 0,
  gray_scale_percent: 100,
  is_active: true
})

// 表单验证规则
const formRules = {
  version_name: [
    { required: true, message: '请输入版本号', trigger: 'blur' },
    { pattern: /^\d+\.\d+(\.\d+)?$/, message: '版本号格式应为 x.y 或 x.y.z', trigger: 'blur' }
  ],
  version_code: [
    { required: true, message: '请输入版本码', trigger: 'blur' }
  ],
  update_type: [
    { required: true, message: '请选择更新类型', trigger: 'change' }
  ]
}

// 上传相关
const fileList = ref([])
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadedFileInfo = ref(null)
const submitting = ref(false)

// 加载版本列表
const loadVersionList = async () => {
  loading.value = true
  try {
    const response = await appVersionAPI.getVersions({
      skip: (pagination.page - 1) * pagination.size,
      limit: pagination.size
    })
    versionList.value = response.versions || []
    pagination.total = response.total || 0
  } catch (error) {
    ElMessage.error('加载版本列表失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

// 加载统计数据
const loadStats = async () => {
  try {
    stats.value = await appVersionAPI.getStats()
  } catch (error) {
    console.error('加载统计失败:', error)
  }
}

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (!bytes) return '-'
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 格式化时间
const formatDateTime = (dateString) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('zh-CN')
}

// 更新类型标签
const getUpdateTypeTag = (type) => {
  const map = { force: 'danger', recommend: 'warning', silent: 'info' }
  return map[type] || 'info'
}

const getUpdateTypeLabel = (type) => {
  const map = { force: '强制更新', recommend: '推荐更新', silent: '静默更新' }
  return map[type] || type
}

// 处理文件选择
const handleFileChange = async (file) => {
  if (!file.raw.name.endsWith('.apk')) {
    ElMessage.error('请选择 APK 文件')
    fileList.value = []
    return
  }
  
  // 开始上传
  uploading.value = true
  uploadProgress.value = 0
  
  try {
    const result = await appVersionAPI.uploadApk(file.raw, (progress) => {
      uploadProgress.value = progress
    })
    
    uploadedFileInfo.value = result
    versionForm.download_url = result.download_url
    versionForm.file_size = result.file_size
    versionForm.file_md5 = result.file_md5
    versionForm.file_name = result.file_name
    
    ElMessage.success('APK 上传成功')
  } catch (error) {
    ElMessage.error('上传失败: ' + (error.response?.data?.detail || error.message))
    fileList.value = []
    uploadedFileInfo.value = null
  } finally {
    uploading.value = false
  }
}

const handleFileRemove = () => {
  uploadedFileInfo.value = null
  versionForm.download_url = ''
  versionForm.file_size = 0
  versionForm.file_md5 = ''
  versionForm.file_name = ''
}

// 编辑版本
const editVersion = (version) => {
  editingVersion.value = version
  Object.assign(versionForm, {
    version_name: version.version_name,
    version_code: version.version_code,
    update_type: version.update_type,
    download_url: version.download_url,
    file_size: version.file_size,
    file_md5: version.file_md5,
    file_name: version.file_name,
    release_notes: version.release_notes || '',
    release_notes_en: version.release_notes_en || '',
    min_version_code: version.min_version_code || 0,
    gray_scale_percent: version.gray_scale_percent,
    is_active: version.is_active
  })
  showPublishDialog.value = true
}

// 提交表单
const handleSubmit = async () => {
  try {
    await formRef.value?.validate()
    submitting.value = true
    
    if (editingVersion.value) {
      // 更新版本
      await appVersionAPI.updateVersion(editingVersion.value.id, {
        update_type: versionForm.update_type,
        release_notes: versionForm.release_notes,
        release_notes_en: versionForm.release_notes_en,
        min_version_code: versionForm.min_version_code,
        gray_scale_percent: versionForm.gray_scale_percent,
        is_active: versionForm.is_active
      })
      ElMessage.success('版本更新成功')
    } else {
      // 创建新版本
      await appVersionAPI.createVersion({
        version_name: versionForm.version_name,
        version_code: versionForm.version_code,
        update_type: versionForm.update_type,
        download_url: versionForm.download_url,
        file_size: versionForm.file_size,
        file_md5: versionForm.file_md5,
        file_name: versionForm.file_name,
        release_notes: versionForm.release_notes,
        release_notes_en: versionForm.release_notes_en,
        min_version_code: versionForm.min_version_code,
        gray_scale_percent: versionForm.gray_scale_percent,
        is_active: versionForm.is_active
      })
      ElMessage.success('版本发布成功')
    }
    
    showPublishDialog.value = false
    loadVersionList()
    loadStats()
  } catch (error) {
    if (error.response?.data?.detail) {
      ElMessage.error(error.response.data.detail)
    }
  } finally {
    submitting.value = false
  }
}

// 切换版本状态
const handleStatusChange = async (row) => {
  row._switching = true
  try {
    await appVersionAPI.updateVersion(row.id, { is_active: row.is_active })
    ElMessage.success(row.is_active ? '版本已启用' : '版本已禁用')
    loadStats()
  } catch (error) {
    row.is_active = !row.is_active
    ElMessage.error('操作失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    row._switching = false
  }
}

// 删除版本
const deleteVersion = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除版本 v${row.version_name} 吗？此操作不可恢复。`,
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    
    await appVersionAPI.deleteVersion(row.id)
    ElMessage.success('版本已删除')
    loadVersionList()
    loadStats()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败: ' + (error.response?.data?.detail || error.message))
    }
  }
}

// 复制下载链接
const copyDownloadUrl = async (row) => {
  const url = row.download_url.startsWith('http') 
    ? row.download_url 
    : config.API_BASE_URL + row.download_url
  
  try {
    await navigator.clipboard.writeText(url)
    ElMessage.success('下载链接已复制')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

// 重置表单
const resetForm = () => {
  editingVersion.value = null
  fileList.value = []
  uploadedFileInfo.value = null
  uploadProgress.value = 0
  Object.assign(versionForm, {
    version_name: '',
    version_code: null,
    update_type: 'recommend',
    download_url: '',
    file_size: 0,
    file_md5: '',
    file_name: '',
    release_notes: '',
    release_notes_en: '',
    min_version_code: 0,
    gray_scale_percent: 100,
    is_active: true
  })
}

// 分页处理
const handleSizeChange = (size) => {
  pagination.size = size
  pagination.page = 1
  loadVersionList()
}

const handleCurrentChange = (page) => {
  pagination.page = page
  loadVersionList()
}

// 页面初始化
onMounted(() => {
  loadVersionList()
  loadStats()
})

// ============ Release Notes 相关 ============

const showReleaseNotesDialog = ref(false)
const releaseNotesSubmitting = ref(false)
const currentVersionForReleaseNotes = ref(null)

const releaseNotesForm = reactive({
  id: null,
  version_id: null,
  title: '',
  title_en: '',
  subtitle: '',
  subtitle_en: '',
  is_enabled: true,
  items: []
})

// 打开 Release Notes 编辑器
const openReleaseNotesEditor = async (version) => {
  currentVersionForReleaseNotes.value = version
  releaseNotesForm.version_id = version.id
  
  // 尝试加载已有的 Release Notes
  try {
    const data = await appVersionAPI.getReleaseNote(version.id)
    Object.assign(releaseNotesForm, {
      id: data.id,
      title: data.title || '',
      title_en: data.title_en || '',
      subtitle: data.subtitle || '',
      subtitle_en: data.subtitle_en || '',
      is_enabled: data.is_enabled,
      items: data.items.map(item => ({
        sort_order: item.sort_order,
        item_type: item.item_type,
        content: item.content || '',
        content_en: item.content_en || '',
        image_url: item.image_url || '',
        image_caption: item.image_caption || '',
        image_caption_en: item.image_caption_en || ''
      }))
    })
  } catch (error) {
    // 404 表示不存在，初始化空表单
    if (error.response?.status === 404) {
      resetReleaseNotesForm()
      releaseNotesForm.version_id = version.id
      releaseNotesForm.title = `v${version.version_name} 更新说明`
      releaseNotesForm.title_en = `v${version.version_name} Release Notes`
    } else {
      ElMessage.error('加载 Release Notes 失败')
      return
    }
  }
  
  showReleaseNotesDialog.value = true
}

// 重置 Release Notes 表单
const resetReleaseNotesForm = () => {
  Object.assign(releaseNotesForm, {
    id: null,
    version_id: null,
    title: '',
    title_en: '',
    subtitle: '',
    subtitle_en: '',
    is_enabled: true,
    items: []
  })
}

// 添加项目
const addItem = (type) => {
  releaseNotesForm.items.push({
    sort_order: releaseNotesForm.items.length,
    item_type: type,
    content: '',
    content_en: '',
    image_url: '',
    image_caption: '',
    image_caption_en: ''
  })
}

// 移除项目
const removeItem = (index) => {
  releaseNotesForm.items.splice(index, 1)
  // 更新排序
  releaseNotesForm.items.forEach((item, i) => {
    item.sort_order = i
  })
}

// 移动项目
const moveItem = (index, direction) => {
  const newIndex = index + direction
  if (newIndex < 0 || newIndex >= releaseNotesForm.items.length) return
  
  const items = [...releaseNotesForm.items]
  const temp = items[index]
  items[index] = items[newIndex]
  items[newIndex] = temp
  
  // 更新排序
  items.forEach((item, i) => {
    item.sort_order = i
  })
  
  releaseNotesForm.items = items
}

// 上传图片
const handleImageUpload = async (file, index) => {
  try {
    const result = await appVersionAPI.uploadReleaseNoteImage(file.raw)
    releaseNotesForm.items[index].image_url = result.image_url
    ElMessage.success('图片上传成功')
  } catch (error) {
    ElMessage.error('图片上传失败: ' + (error.response?.data?.detail || error.message))
  }
}

// 获取完整图片URL
const getFullImageUrl = (url) => {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return config.API_BASE_URL + url
}

// 图片加载失败
const handleImageError = (e) => {
  e.target.style.display = 'none'
}

// 保存 Release Notes
const saveReleaseNotes = async () => {
  releaseNotesSubmitting.value = true
  
  try {
    const data = {
      version_id: releaseNotesForm.version_id,
      title: releaseNotesForm.title,
      title_en: releaseNotesForm.title_en,
      subtitle: releaseNotesForm.subtitle,
      subtitle_en: releaseNotesForm.subtitle_en,
      is_enabled: releaseNotesForm.is_enabled,
      items: releaseNotesForm.items.map((item, index) => ({
        sort_order: index,
        item_type: item.item_type,
        content: item.content || null,
        content_en: item.content_en || null,
        image_url: item.image_url || null,
        image_caption: item.image_caption || null,
        image_caption_en: item.image_caption_en || null
      }))
    }
    
    if (releaseNotesForm.id) {
      await appVersionAPI.updateReleaseNote(releaseNotesForm.id, data)
      ElMessage.success('Release Notes 已更新')
    } else {
      const result = await appVersionAPI.createReleaseNote(data)
      releaseNotesForm.id = result.id
      ElMessage.success('Release Notes 已创建')
    }
  } catch (error) {
    ElMessage.error('保存失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    releaseNotesSubmitting.value = false
  }
}

// 删除 Release Notes
const deleteReleaseNotes = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要删除此 Release Notes 页面吗？',
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    
    releaseNotesSubmitting.value = true
    await appVersionAPI.deleteReleaseNote(releaseNotesForm.id)
    ElMessage.success('Release Notes 已删除')
    showReleaseNotesDialog.value = false
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败: ' + (error.response?.data?.detail || error.message))
    }
  } finally {
    releaseNotesSubmitting.value = false
  }
}

// 预览 Release Notes
const previewReleaseNotes = () => {
  if (currentVersionForReleaseNotes.value) {
    router.push(`/settings/release-notes/${currentVersionForReleaseNotes.value.id}`)
  }
}
</script>

<style scoped>
.app-version-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  color: #303133;
}

.header-actions {
  display: flex;
  gap: 10px;
}

/* 统计卡片 */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 20px;
}

.stat-card {
  border-radius: 8px;
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  color: #909399;
}

.stat-icon.success {
  color: #67c23a;
}

.stat-icon.primary {
  color: #f97316;
}

.stat-icon.warning {
  color: #e6a23c;
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

/* 表格 */
.table-card {
  margin-bottom: 20px;
}

.version-name {
  font-weight: 600;
  color: #f97316;
}

.ellipsis-text {
  display: block;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

/* 上传区域 */
.upload-section {
  width: 100%;
}

.upload-progress {
  margin-top: 12px;
}

.progress-text {
  display: block;
  text-align: center;
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}

.uploaded-info {
  margin-top: 12px;
}

/* 表单提示 */
.form-tip {
  color: #909399;
  font-size: 12px;
  margin-left: 12px;
}

.update-type-tip {
  margin-top: 8px;
  font-size: 13px;
  color: #606266;
}

/* 响应式 */
@media (max-width: 1200px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .stats-row {
    grid-template-columns: 1fr;
  }
}

/* Release Notes 编辑器 */
.release-notes-editor {
  max-height: 70vh;
  overflow-y: auto;
}

.items-list {
  width: 100%;
}

.item-card {
  background: #f8f9fa;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.item-card.image-card {
  background: #f0f9eb;
  border-color: #c2e7b0;
}

.item-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.item-number {
  width: 28px;
  height: 28px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
}

.item-actions {
  margin-left: auto;
  display: flex;
  gap: 4px;
}

.image-upload-area {
  margin-top: 8px;
}

.upload-tip {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}

.image-preview {
  position: relative;
  display: inline-block;
}

.image-preview img {
  max-width: 300px;
  max-height: 200px;
  border-radius: 8px;
  border: 1px solid #e8e8e8;
}

.remove-image-btn {
  position: absolute;
  top: 8px;
  right: 8px;
}

.add-buttons {
  display: flex;
  gap: 12px;
  margin-top: 16px;
}
</style>
