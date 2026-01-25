<template>
  <div class="page">
    <div class="page-header">
      <h1>移动端配置</h1>
      <div class="header-actions">
        <el-button @click="loadConfig" :loading="loading">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
        <el-button
          type="primary"
          @click="save"
          :loading="saving"
          :disabled="!canEdit"
        >
          <el-icon><Document /></el-icon>保存
        </el-button>
      </div>
    </div>

    <el-alert
      v-if="!canEdit"
      type="warning"
      title="当前用户仅可查看配置，修改需要管理员或项目经理权限"
      :closable="false"
      show-icon
      class="mb16"
    />

    <!-- 卡片 1：移动端定位模式 -->
    <el-card class="mb16" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>移动端定位模式</span>
        </div>
      </template>

      <el-form :model="form" label-width="140px" :disabled="!canEdit">
        <!-- 全局默认：定位模式 -->
        <el-form-item label="全局默认模式">
          <el-radio-group v-model="form.location_mode.default">
            <el-radio label="baidu">在线逆地理（国内Baidu/海外Google，默认）</el-radio>
            <el-radio label="native">原生插件模式（仅使用原生定位插件）</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="当前生效说明">
          <ul class="hint-list">
            <li>
              <strong>在线逆地理：</strong>
              手机 App 使用 <code>uni.getLocation(wgs84)</code> 获取坐标，
              再通过后端代理调用逆地理接口获取地址信息（国内优先 Baidu，海外走 Google；后端按约 30m 网格缓存，提高命中率并减少第三方调用）。
            </li>
            <li>
              <strong>原生插件模式：</strong>
              手机 App 使用原生定位插件获取坐标和地址，不依赖百度服务。
            </li>
            <li>
              所有拍照、水印、工单上传等定位场景都会使用当前配置的模式。
            </li>
          </ul>
        </el-form-item>
      </el-form>

      <!-- 高级覆盖配置：定位模式（使用折叠面板，默认收起以减少占用面积） -->
      <el-collapse v-model="activeAdvancedLocation" class="mt8">
        <el-collapse-item name="role">
          <template #title>
            <span>按角色覆盖（定位模式）</span>
          </template>
          <el-table
            :data="roleRows"
            size="small"
            border
            style="width: 100%"
          >
            <el-table-column prop="label" label="角色" width="140" />
            <el-table-column label="定位模式" width="210">
              <template #default="{ row }">
                <el-select
                  v-model="form.location_mode.per_role[row.key]"
                  placeholder="跟随全局"
                  style="width: 180px"
                  :disabled="!canEdit"
                  clearable
                >
                  <el-option label="跟随全局" :value="''" />
                  <el-option label="在线逆地理" value="baidu" />
                  <el-option label="原生插件模式" value="native" />
                </el-select>
              </template>
            </el-table-column>
          </el-table>
          <p class="hint mt8">
            留空表示该角色使用“全局默认模式”。当同一用户同时满足多个角色时，APP 端会按后端解析的优先级使用配置。
          </p>
        </el-collapse-item>

        <el-collapse-item name="user">
          <template #title>
            <span>按用户覆盖（定位模式）</span>
          </template>
          <div class="user-rules">
            <div class="user-rule-form">
              <el-select
                v-model="newLocationUserRule.user_id"
                filterable
                remote
                reserve-keyword
                placeholder="搜索用户名/姓名/邮箱"
                :remote-method="searchUsers"
                :loading="userSelectLoading"
                style="width: 260px"
                :disabled="!canEdit"
              >
                <el-option
                  v-for="opt in userOptions"
                  :key="opt.id"
                  :label="opt.label"
                  :value="String(opt.id)"
                />
              </el-select>
              <el-select
                v-model="newLocationUserRule.mode"
                placeholder="定位模式"
                style="width: 160px; margin-left: 8px"
                :disabled="!canEdit"
              >
                <el-option label="在线逆地理" value="baidu" />
                <el-option label="原生插件模式" value="native" />
              </el-select>
              <el-button
                type="primary"
                size="small"
                style="margin-left: 8px"
                :disabled="!canEdit"
                @click="addLocationUserRule"
              >
                添加
              </el-button>
            </div>

            <el-table
              v-if="form.location_mode.per_user.length"
              :data="form.location_mode.per_user"
              size="small"
              border
              style="width: 100%; margin-top: 8px"
            >
              <el-table-column prop="user_id" label="用户ID" width="120" />
              <el-table-column prop="mode" label="定位模式" width="140">
                <template #default="{ row }">
                  <span v-if="row.mode === 'baidu'">在线逆地理</span>
                  <span v-else-if="row.mode === 'native'">原生插件模式</span>
                  <span v-else>（无效）</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80">
                <template #default="{ $index }">
                  <el-button
                    type="danger"
                    text
                    size="small"
                    :disabled="!canEdit"
                    @click="removeLocationUserRule($index)"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
            <p class="hint mt8">
              按用户配置的优先级最高，会覆盖全局与角色配置。
            </p>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <!-- 卡片 2：检查详情本地上传 -->
    <el-card class="mb16" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>检查详情本地上传</span>
        </div>
      </template>

      <el-form :model="form" label-width="160px" :disabled="!canEdit">
        <!-- 全局默认：检查详情是否允许本地上传图片 -->
        <el-form-item label="全局默认策略">
          <el-radio-group v-model="form.allow_local_photo_upload.default">
            <el-radio :label="true">允许从本地/相册上传图片</el-radio>
            <el-radio :label="false">只允许拍照，不允许本地上传</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="说明">
          <ul class="hint-list">
            <li>该开关仅影响检查详情中拍照/上传图片时是否允许从本地/相册选择。</li>
            <li>禁用后，App 端只会展示“拍照”选项，不再展示“从相册选择”。</li>
          </ul>
        </el-form-item>
      </el-form>

      <!-- 高级覆盖配置：检查详情本地上传 -->
      <el-collapse v-model="activeAdvancedUpload" class="mt8">
        <el-collapse-item name="role-upload">
          <template #title>
            <span>按角色覆盖（本地上传）</span>
          </template>
          <el-table
            :data="roleRows"
            size="small"
            border
            style="width: 100%"
          >
            <el-table-column prop="label" label="角色" width="140" />
            <el-table-column label="本地上传策略">
              <template #default="{ row }">
                <el-select
                  v-model="form.allow_local_photo_upload.per_role[row.key]"
                  placeholder="跟随全局"
                  style="width: 220px"
                  :disabled="!canEdit"
                  clearable
                >
                  <el-option label="跟随全局" :value="''" />
                  <el-option label="允许本地上传" value="allow" />
                  <el-option label="禁止本地上传" value="deny" />
                </el-select>
              </template>
            </el-table-column>
          </el-table>
          <p class="hint mt8">
            留空表示该角色使用“全局默认策略”。当同一用户同时满足多个角色时，APP 端会按后端解析的优先级使用配置。
          </p>
        </el-collapse-item>

        <el-collapse-item name="user-upload">
          <template #title>
            <span>按用户覆盖（本地上传）</span>
          </template>
          <div class="user-rules">
            <div class="user-rule-form">
              <el-select
                v-model="newUploadUserRule.user_id"
                filterable
                remote
                reserve-keyword
                placeholder="搜索用户名/姓名/邮箱"
                :remote-method="searchUsers"
                :loading="userSelectLoading"
                style="width: 260px"
                :disabled="!canEdit"
              >
                <el-option
                  v-for="opt in userOptions"
                  :key="opt.id"
                  :label="opt.label"
                  :value="String(opt.id)"
                />
              </el-select>
              <el-select
                v-model="newUploadUserRule.flag"
                placeholder="本地上传策略"
                style="width: 200px; margin-left: 8px"
                :disabled="!canEdit"
              >
                <el-option label="允许本地上传" value="allow" />
                <el-option label="禁止本地上传" value="deny" />
              </el-select>
              <el-button
                type="primary"
                size="small"
                style="margin-left: 8px"
                :disabled="!canEdit"
                @click="addUploadUserRule"
              >
                添加
              </el-button>
            </div>

            <el-table
              v-if="form.allow_local_photo_upload.per_user.length"
              :data="form.allow_local_photo_upload.per_user"
              size="small"
              border
              style="width: 100%; margin-top: 8px"
            >
              <el-table-column prop="user_id" label="用户ID" width="120" />
              <el-table-column prop="flag" label="本地上传策略" width="180">
                <template #default="{ row }">
                  <span v-if="row.flag === 'allow'">允许本地上传</span>
                  <span v-else-if="row.flag === 'deny'">禁止本地上传</span>
                  <span v-else>（未知）</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80">
                <template #default="{ $index }">
                  <el-button
                    type="danger"
                    text
                    size="small"
                    :disabled="!canEdit"
                    @click="removeUploadUserRule($index)"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
            <p class="hint mt8">
              按用户配置的优先级最高，会覆盖全局与角色配置。
            </p>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <!-- 卡片 3：检查详情本地上传水印定位信息 -->
    <el-card class="mb16" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>检查详情本地上传水印</span>
        </div>
      </template>

      <el-form :model="form" label-width="200px" :disabled="!canEdit">
        <!-- 全局默认：本地上传水印是否携带经纬度和地址 -->
        <el-form-item label="全局默认开关">
          <el-switch
            v-model="form.local_upload_watermark_with_geo.default"
            active-text="携带经纬度和地址"
            inactive-text="不携带"
          />
        </el-form-item>

        <el-form-item label="说明">
          <ul class="hint-list">
            <li>仅影响检查详情中“从本地/相册上传”的照片水印。</li>
            <li>
              关闭后：App 不再调用定位与地址解析接口，水印中将以“本图片为本地上传照片”替换经纬度/地址信息（其他水印内容不变）。
            </li>
            <li>开启后：保持现状，水印携带经纬度与地址信息。</li>
          </ul>
        </el-form-item>
      </el-form>

      <!-- 高级覆盖配置：检查详情本地上传水印 -->
      <el-collapse v-model="activeAdvancedLocalUploadWatermark" class="mt8">
        <el-collapse-item name="role-watermark">
          <template #title>
            <span>按角色覆盖（本地上传水印）</span>
          </template>
          <el-table
            :data="roleRows"
            size="small"
            border
            style="width: 100%"
          >
            <el-table-column prop="label" label="角色" width="140" />
            <el-table-column label="水印定位信息">
              <template #default="{ row }">
                <el-select
                  v-model="form.local_upload_watermark_with_geo.per_role[row.key]"
                  placeholder="跟随全局"
                  style="width: 220px"
                  :disabled="!canEdit"
                  clearable
                >
                  <el-option label="跟随全局" :value="''" />
                  <el-option label="携带经纬度和地址" value="allow" />
                  <el-option label="不携带（标注本地上传）" value="deny" />
                </el-select>
              </template>
            </el-table-column>
          </el-table>
          <p class="hint mt8">
            留空表示该角色使用“全局默认开关”。当同一用户同时满足多个角色时，APP 端会按后端解析的优先级使用配置。
          </p>
        </el-collapse-item>

        <el-collapse-item name="user-watermark">
          <template #title>
            <span>按用户覆盖（本地上传水印）</span>
          </template>
          <div class="user-rules">
            <div class="user-rule-form">
              <el-select
                v-model="newLocalUploadWatermarkUserRule.user_id"
                filterable
                remote
                reserve-keyword
                placeholder="搜索用户名/姓名/邮箱"
                :remote-method="searchUsers"
                :loading="userSelectLoading"
                style="width: 260px"
                :disabled="!canEdit"
              >
                <el-option
                  v-for="opt in userOptions"
                  :key="opt.id"
                  :label="opt.label"
                  :value="String(opt.id)"
                />
              </el-select>
              <el-select
                v-model="newLocalUploadWatermarkUserRule.flag"
                placeholder="水印定位信息"
                style="width: 220px; margin-left: 8px"
                :disabled="!canEdit"
              >
                <el-option label="携带经纬度和地址" value="allow" />
                <el-option label="不携带（标注本地上传）" value="deny" />
              </el-select>
              <el-button
                type="primary"
                size="small"
                style="margin-left: 8px"
                :disabled="!canEdit"
                @click="addLocalUploadWatermarkUserRule"
              >
                添加
              </el-button>
            </div>

            <el-table
              v-if="form.local_upload_watermark_with_geo.per_user.length"
              :data="form.local_upload_watermark_with_geo.per_user"
              size="small"
              border
              style="width: 100%; margin-top: 8px"
            >
              <el-table-column prop="user_id" label="用户ID" width="120" />
              <el-table-column prop="flag" label="水印定位信息" width="220">
                <template #default="{ row }">
                  <span v-if="row.flag === 'allow'">携带经纬度和地址</span>
                  <span v-else-if="row.flag === 'deny'">不携带（标注本地上传）</span>
                  <span v-else>（未知）</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80">
                <template #default="{ $index }">
                  <el-button
                    type="danger"
                    text
                    size="small"
                    :disabled="!canEdit"
                    @click="removeLocalUploadWatermarkUserRule($index)"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
            <p class="hint mt8">
              按用户配置的优先级最高，会覆盖全局与角色配置。
            </p>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <!-- 卡片 4：旧流程扫码领货（我的设备） -->
    <el-card class="mb16" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>旧流程扫码领货（我的设备）</span>
        </div>
      </template>

      <el-form :model="form" label-width="200px" :disabled="!canEdit">
        <el-form-item label="全局默认开关">
          <el-switch
            v-model="form.enable_legacy_scan_pickup.default"
            active-text="开启旧流程扫码"
            inactive-text="关闭旧流程扫码"
          />
        </el-form-item>

        <el-form-item label="说明">
          <ul class="hint-list">
            <li>该开关仅影响移动端“我的设备”页面内的“扫码领货/扫码出库”（旧流程）。</li>
            <li>关闭后：移动端仍可查看领用台账、退库、解绑，但不可扫码出库；后端会拒绝 /api/stock/scan-checkout。</li>
            <li>建议：为避免流程混淆，生产环境默认关闭，统一走“物料申请→领料单→仓库确认出库”。</li>
          </ul>
        </el-form-item>
      </el-form>

      <el-collapse v-model="activeAdvancedLegacyScanPickup" class="mt8">
        <el-collapse-item name="role-legacy-scan">
          <template #title>
            <span>按角色覆盖（旧流程扫码领货）</span>
          </template>
          <el-table
            :data="roleRows"
            size="small"
            border
            style="width: 100%"
          >
            <el-table-column prop="label" label="角色" width="140" />
            <el-table-column label="旧流程扫码领货">
              <template #default="{ row }">
                <el-select
                  v-model="form.enable_legacy_scan_pickup.per_role[row.key]"
                  placeholder="跟随全局"
                  style="width: 220px"
                  :disabled="!canEdit"
                  clearable
                >
                  <el-option label="跟随全局" :value="''" />
                  <el-option label="允许旧流程扫码" value="allow" />
                  <el-option label="禁止旧流程扫码" value="deny" />
                </el-select>
              </template>
            </el-table-column>
          </el-table>
          <p class="hint mt8">
            留空表示该角色使用“全局默认开关”。当同一用户同时满足多个角色时，APP 端会按后端解析的优先级使用配置。
          </p>
        </el-collapse-item>

        <el-collapse-item name="user-legacy-scan">
          <template #title>
            <span>按用户覆盖（旧流程扫码领货）</span>
          </template>
          <div class="user-rules">
            <div class="user-rule-form">
              <el-select
                v-model="newLegacyScanPickupUserRule.user_id"
                filterable
                remote
                reserve-keyword
                placeholder="搜索用户名/姓名/邮箱"
                :remote-method="searchUsers"
                :loading="userSelectLoading"
                style="width: 260px"
                :disabled="!canEdit"
              >
                <el-option
                  v-for="opt in userOptions"
                  :key="opt.id"
                  :label="opt.label"
                  :value="String(opt.id)"
                />
              </el-select>
              <el-select
                v-model="newLegacyScanPickupUserRule.flag"
                placeholder="旧流程扫码策略"
                style="width: 220px; margin-left: 8px"
                :disabled="!canEdit"
              >
                <el-option label="允许旧流程扫码" value="allow" />
                <el-option label="禁止旧流程扫码" value="deny" />
              </el-select>
              <el-button
                type="primary"
                size="small"
                style="margin-left: 8px"
                :disabled="!canEdit"
                @click="addLegacyScanPickupUserRule"
              >
                添加
              </el-button>
            </div>

            <el-table
              v-if="form.enable_legacy_scan_pickup.per_user.length"
              :data="form.enable_legacy_scan_pickup.per_user"
              size="small"
              border
              style="width: 100%; margin-top: 8px"
            >
              <el-table-column prop="user_id" label="用户ID" width="120" />
              <el-table-column prop="flag" label="旧流程扫码策略" width="200">
                <template #default="{ row }">
                  <span v-if="row.flag === 'allow'">允许旧流程扫码</span>
                  <span v-else-if="row.flag === 'deny'">禁止旧流程扫码</span>
                  <span v-else>（未知）</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80">
                <template #default="{ $index }">
                  <el-button
                    type="danger"
                    text
                    size="small"
                    :disabled="!canEdit"
                    @click="removeLegacyScanPickupUserRule($index)"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
            <p class="hint mt8">
              按用户配置的优先级最高，会覆盖全局与角色配置。
            </p>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <el-card>
      <template #header>
        <div class="card-header">
          <span>其他移动端配置（预留）</span>
        </div>
      </template>
      <p class="placeholder-text">
        此区域预留给未来更多移动端行为开关和选项（例如：是否强制 GPS、水印样式模板选择、离线缓存策略等），当前版本暂未启用。
      </p>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Document } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { mobileSettingsApi } from '@/api/system'
import { userAPI } from '@/api/user'

const userStore = useUserStore()

const loading = ref(false)
const saving = ref(false)

const form = ref({
  location_mode: {
    default: 'baidu',
    per_role: {
      admin: '',
      manager: '',
      inspector: '',
      surveyor: '',
      user: '',
    },
    per_user: [],
  },
  allow_local_photo_upload: {
    default: true,
    per_role: {
      admin: '',
      manager: '',
      inspector: '',
      surveyor: '',
      user: '',
    },
    per_user: [],
  },
  local_upload_watermark_with_geo: {
    default: true,
    per_role: {
      admin: '',
      manager: '',
      inspector: '',
      surveyor: '',
      user: '',
    },
    per_user: [],
  },
  enable_legacy_scan_pickup: {
    default: false,
    per_role: {
      admin: '',
      manager: '',
      inspector: '',
      surveyor: '',
      user: '',
    },
    per_user: [],
  },
})

const newLocationUserRule = ref({
  user_id: '',
  mode: 'baidu',
})

const newUploadUserRule = ref({
  user_id: '',
  flag: 'allow',
})

const newLocalUploadWatermarkUserRule = ref({
  user_id: '',
  flag: 'allow',
})

const newLegacyScanPickupUserRule = ref({
  user_id: '',
  flag: 'deny',
})

// 高级配置折叠面板（默认全部收起，减少页面占用）
const activeAdvancedLocation = ref([])
const activeAdvancedUpload = ref([])
const activeAdvancedLocalUploadWatermark = ref([])
const activeAdvancedLegacyScanPickup = ref([])

// 用户搜索下拉选项
const userOptions = ref([])
const userSelectLoading = ref(false)

const canEdit = computed(() => {
  const role = userStore.user?.role
  return role === 'admin' || role === 'manager'
})

const roleRows = [
  { key: 'admin', label: '管理员 (admin)' },
  { key: 'manager', label: '项目经理 (manager)' },
  { key: 'inspector', label: '检查员 (inspector)' },
  { key: 'surveyor', label: '勘察员 (surveyor)' },
  { key: 'user', label: '普通用户 (user)' },
]

const roleKeys = roleRows.map(r => r.key)

// 通用布尔规则：后端 -> 表单
const fillBoolRuleToForm = (formRule, serverRule, roles, defaultValue = true) => {
  const safeRule = serverRule || {}
  const perRole = safeRule.per_role || {}
  const perUser = safeRule.per_user || {}

  // default
  formRule.default =
    typeof safeRule.default === 'boolean' ? safeRule.default : defaultValue

  // per_role: 布尔 -> 'allow' / 'deny' / ''
  const mappedPerRole = {}
  roles.forEach((role) => {
    if (Object.prototype.hasOwnProperty.call(perRole, role)) {
      mappedPerRole[role] = perRole[role] ? 'allow' : 'deny'
    } else {
      mappedPerRole[role] = ''
    }
  })
  formRule.per_role = mappedPerRole

  // per_user: { id: bool } -> [{ user_id, flag }]
  formRule.per_user = Object.entries(perUser).map(([id, flag]) => ({
    user_id: id,
    flag: flag ? 'allow' : 'deny',
  }))
}

// 通用布尔规则：表单 -> 后端 payload
const buildBoolRulePayload = (formRule) => {
  const payload = {
    default: formRule.default,
    per_role: {},
    per_user: {},
  }

  Object.entries(formRule.per_role || {}).forEach(([role, flag]) => {
    if (flag === 'allow') {
      payload.per_role[role] = true
    } else if (flag === 'deny') {
      payload.per_role[role] = false
    }
  })

  ;(formRule.per_user || []).forEach((rule) => {
    const id = String(rule.user_id || '').trim()
    if (!id) return
    if (rule.flag === 'allow') {
      payload.per_user[id] = true
    } else if (rule.flag === 'deny') {
      payload.per_user[id] = false
    }
  })

  return payload
}

const loadConfig = async () => {
  try {
    loading.value = true
    const res = await mobileSettingsApi.getMobileSettings()
    const raw = res || {}
    const lm = raw.location_mode || {}
    const perRole = lm.per_role || {}
    const perUser = lm.per_user || {}
    const uploadRule = raw.allow_local_photo_upload || {}
    const localUploadWatermarkRule = raw.local_upload_watermark_with_geo || {}
    const legacyScanPickupRule = raw.enable_legacy_scan_pickup || {}

    form.value.location_mode.default =
      (lm.default && lm.default.toLowerCase()) === 'native' ? 'native' : 'baidu'
    form.value.location_mode.per_role = {
      admin: perRole.admin || '',
      manager: perRole.manager || '',
      inspector: perRole.inspector || '',
      surveyor: perRole.surveyor || '',
      user: perRole.user || '',
    }
    form.value.location_mode.per_user = Object.entries(perUser).map(([id, mode]) => ({
      user_id: id,
      mode: (mode || '').toLowerCase() === 'native' ? 'native' : 'baidu',
    }))

    // allow_local_photo_upload：使用通用布尔规则映射
    fillBoolRuleToForm(
      form.value.allow_local_photo_upload,
      uploadRule,
      roleKeys,
      true,
    )

    // local_upload_watermark_with_geo：使用通用布尔规则映射（true=携带经纬度地址）
    fillBoolRuleToForm(
      form.value.local_upload_watermark_with_geo,
      localUploadWatermarkRule,
      roleKeys,
      true,
    )

    // enable_legacy_scan_pickup：默认关闭（false）
    fillBoolRuleToForm(
      form.value.enable_legacy_scan_pickup,
      legacyScanPickupRule,
      roleKeys,
      false,
    )

  } catch (e) {
    console.error(e)
    const detail = e?.response?.data?.detail
    ElMessage.error(detail || '加载移动端配置失败')
  } finally {
    loading.value = false
  }
}

const save = async () => {
  if (!canEdit.value) {
    ElMessage.error('只有管理员或项目经理可以保存配置')
    return
  }
  try {
    saving.value = true
    const payload = {
      location_mode: {
        default: form.value.location_mode.default,
        per_role: {},
        per_user: {},
      },
      allow_local_photo_upload: {},
      local_upload_watermark_with_geo: {},
      enable_legacy_scan_pickup: {},
    }

    // 构建 per_role：仅提交明确选择的模式
    Object.entries(form.value.location_mode.per_role || {}).forEach(([role, mode]) => {
      const val = (mode || '').toLowerCase()
      if (val === 'baidu' || val === 'native') {
        payload.location_mode.per_role[role] = val
      }
    })

    // 构建 per_user：按 user_id -> mode 映射
    ;(form.value.location_mode.per_user || []).forEach((rule) => {
      const id = String(rule.user_id || '').trim()
      const val = (rule.mode || '').toLowerCase()
      if (!id) return
      if (val !== 'baidu' && val !== 'native') return
      payload.location_mode.per_user[id] = val
    })

    // 构建 allow_local_photo_upload：使用通用布尔规则映射
    payload.allow_local_photo_upload = buildBoolRulePayload(
      form.value.allow_local_photo_upload,
    )

    payload.local_upload_watermark_with_geo = buildBoolRulePayload(
      form.value.local_upload_watermark_with_geo,
    )

    payload.enable_legacy_scan_pickup = buildBoolRulePayload(
      form.value.enable_legacy_scan_pickup,
    )

    await mobileSettingsApi.updateMobileSettings(payload)

    ElMessage.success('保存成功')
  } catch (e) {
    console.error(e)
    const detail = e?.response?.data?.detail
    let msg = '保存失败'
    if (typeof detail === 'string') {
      msg = detail
    } else if (Array.isArray(detail)) {
      msg = detail.map(d => d.msg || JSON.stringify(d)).join('；')
    }
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadConfig()
})

const addUserRule = () => {
  const id = String(newLocationUserRule.value.user_id || '').trim()
  const mode = (newLocationUserRule.value.mode || '').toLowerCase()
  if (!id) {
    ElMessage.warning('请选择用户')
    return
  }
  if (mode !== 'baidu' && mode !== 'native') {
    ElMessage.warning('请选择有效的模式')
    return
  }
  const exists = form.value.location_mode.per_user.some((r) => String(r.user_id) === id)
  if (exists) {
    ElMessage.warning('该用户已存在覆盖配置')
    return
  }
  form.value.location_mode.per_user.push({
    user_id: id,
    mode,
  })
  newLocationUserRule.value.user_id = ''
  newLocationUserRule.value.mode = 'baidu'
}

const removeUserRule = (index) => {
  form.value.location_mode.per_user.splice(index, 1)
}

const addLocationUserRule = addUserRule
const removeLocationUserRule = removeUserRule

const addUploadUserRule = () => {
  const id = String(newUploadUserRule.value.user_id || '').trim()
  const flag = newUploadUserRule.value.flag
  if (!id) {
    ElMessage.warning('请选择用户')
    return
  }
  if (flag !== 'allow' && flag !== 'deny') {
    ElMessage.warning('请选择本地上传策略')
    return
  }
  const exists = form.value.allow_local_photo_upload.per_user.some(
    (r) => String(r.user_id) === id,
  )
  if (exists) {
    ElMessage.warning('该用户已存在本地上传策略')
    return
  }
  form.value.allow_local_photo_upload.per_user.push({
    user_id: id,
    flag,
  })
  newUploadUserRule.value.user_id = ''
  newUploadUserRule.value.flag = 'allow'
}

const removeUploadUserRule = (index) => {
  form.value.allow_local_photo_upload.per_user.splice(index, 1)
}

const addLocalUploadWatermarkUserRule = () => {
  const id = String(newLocalUploadWatermarkUserRule.value.user_id || '').trim()
  const flag = newLocalUploadWatermarkUserRule.value.flag
  if (!id) {
    ElMessage.warning('请选择用户')
    return
  }
  if (flag !== 'allow' && flag !== 'deny') {
    ElMessage.warning('请选择水印定位信息策略')
    return
  }
  const exists = form.value.local_upload_watermark_with_geo.per_user.some(
    (r) => String(r.user_id) === id,
  )
  if (exists) {
    ElMessage.warning('该用户已存在水印定位信息策略')
    return
  }
  form.value.local_upload_watermark_with_geo.per_user.push({
    user_id: id,
    flag,
  })
  newLocalUploadWatermarkUserRule.value.user_id = ''
  newLocalUploadWatermarkUserRule.value.flag = 'allow'
}

const removeLocalUploadWatermarkUserRule = (index) => {
  form.value.local_upload_watermark_with_geo.per_user.splice(index, 1)
}

const addLegacyScanPickupUserRule = () => {
  const id = String(newLegacyScanPickupUserRule.value.user_id || '').trim()
  const flag = newLegacyScanPickupUserRule.value.flag
  if (!id) {
    ElMessage.warning('请选择用户')
    return
  }
  if (flag !== 'allow' && flag !== 'deny') {
    ElMessage.warning('请选择旧流程扫码策略')
    return
  }
  const exists = form.value.enable_legacy_scan_pickup.per_user.some(
    (r) => String(r.user_id) === id,
  )
  if (exists) {
    ElMessage.warning('该用户已存在旧流程扫码策略')
    return
  }
  form.value.enable_legacy_scan_pickup.per_user.push({
    user_id: id,
    flag,
  })
  newLegacyScanPickupUserRule.value.user_id = ''
  newLegacyScanPickupUserRule.value.flag = 'deny'
}

const removeLegacyScanPickupUserRule = (index) => {
  form.value.enable_legacy_scan_pickup.per_user.splice(index, 1)
}

// 远程搜索用户（用于按用户覆盖的选择器）
const searchUsers = async (query) => {
  const keyword = (query || '').trim()
  if (!keyword) {
    userOptions.value = []
    return
  }
  try {
    userSelectLoading.value = true
    const res = await userAPI.searchUsers({
      keyword,
      limit: 20,
    })
    const items = res?.users || res?.data?.users || []
    userOptions.value = items.map((u) => ({
      id: u.id,
      label: `${u.username}${u.full_name ? '（' + u.full_name + '）' : ''} [${u.role}]`,
    }))
  } catch (e) {
    console.error('搜索用户失败:', e)
    userOptions.value = []
  } finally {
    userSelectLoading.value = false
  }
}
</script>

<style scoped>
.page {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.mb16 {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.hint-list {
  margin: 0;
  padding-left: 18px;
  color: #606266;
  font-size: 13px;
  line-height: 1.6;
}

.hint-list li + li {
  margin-top: 4px;
}

.hint-list code {
  font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
  font-size: 12px;
  background-color: #f5f7fa;
  padding: 2px 4px;
  border-radius: 3px;
}

.placeholder-text {
  font-size: 13px;
  color: #909399;
  margin: 0;
}

.hint {
  font-size: 12px;
  color: #909399;
}

.mt8 {
  margin-top: 8px;
}

.user-rules {
  width: 100%;
}

.user-rule-form {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
}
</style>
