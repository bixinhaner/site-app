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

    <!-- 卡片 3：检查项重复图片阻断 -->
    <el-card class="mb16" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>检查项重复图片阻断</span>
        </div>
      </template>

      <el-form :model="form" label-width="200px" :disabled="!canEdit">
        <el-form-item label="全局默认开关">
          <el-switch
            v-model="form.block_duplicate_check_item_photo_upload.default"
            active-text="阻断重复图片上传"
            inactive-text="不阻断"
          />
        </el-form-item>

        <el-form-item label="说明">
          <ul class="hint-list">
            <li>仅影响“检查项”相关的图片上传。</li>
            <li>开启后：全局范围内（跨站点、跨用户）命中重复图片会被阻断。</li>
            <li>关闭后：不阻断上传，但仍会提示重复来源并记录重复标记。</li>
            <li>线下票据/单据照片上传不受此开关影响。</li>
          </ul>
        </el-form-item>
      </el-form>

      <el-collapse v-model="activeAdvancedDuplicatePhotoBlock" class="mt8">
        <el-collapse-item name="role-duplicate-photo-block">
          <template #title>
            <span>按角色覆盖（重复图片阻断）</span>
          </template>
          <el-table :data="roleRows" size="small" border style="width: 100%">
            <el-table-column prop="label" label="角色" width="140" />
            <el-table-column label="重复图片策略">
              <template #default="{ row }">
                <el-select
                  v-model="form.block_duplicate_check_item_photo_upload.per_role[row.key]"
                  placeholder="跟随全局"
                  style="width: 220px"
                  :disabled="!canEdit"
                  clearable
                >
                  <el-option label="跟随全局" :value="''" />
                  <el-option label="阻断重复上传" value="allow" />
                  <el-option label="允许重复上传" value="deny" />
                </el-select>
              </template>
            </el-table-column>
          </el-table>
          <p class="hint mt8">
            留空表示该角色使用“全局默认开关”。当同一用户同时满足多个角色时，APP 端会按后端解析的优先级使用配置。
          </p>
        </el-collapse-item>

        <el-collapse-item name="user-duplicate-photo-block">
          <template #title>
            <span>按用户覆盖（重复图片阻断）</span>
          </template>
          <div class="user-rules">
            <div class="user-rule-form">
              <el-select
                v-model="newDuplicatePhotoBlockUserRule.user_id"
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
                v-model="newDuplicatePhotoBlockUserRule.flag"
                placeholder="重复图片策略"
                style="width: 220px; margin-left: 8px"
                :disabled="!canEdit"
              >
                <el-option label="阻断重复上传" value="allow" />
                <el-option label="允许重复上传" value="deny" />
              </el-select>
              <el-button
                type="primary"
                size="small"
                style="margin-left: 8px"
                :disabled="!canEdit"
                @click="addDuplicatePhotoBlockUserRule"
              >
                添加
              </el-button>
            </div>

            <el-table
              v-if="form.block_duplicate_check_item_photo_upload.per_user.length"
              :data="form.block_duplicate_check_item_photo_upload.per_user"
              size="small"
              border
              style="width: 100%; margin-top: 8px"
            >
              <el-table-column prop="user_id" label="用户ID" width="120" />
              <el-table-column prop="flag" label="重复图片策略" width="200">
                <template #default="{ row }">
                  <span v-if="row.flag === 'allow'">阻断重复上传</span>
                  <span v-else-if="row.flag === 'deny'">允许重复上传</span>
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
                    @click="removeDuplicatePhotoBlockUserRule($index)"
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

    <!-- 卡片 4：检查项照片相似度提醒 -->
    <el-card class="mb16" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>检查项照片相似度提醒</span>
          <el-button type="primary" link @click="openSimilarityThresholdGuide">
            调参建议
          </el-button>
        </div>
      </template>

      <el-form :model="form" label-width="200px" :disabled="!canEdit">
        <el-form-item label="全局默认开关">
          <el-switch
            v-model="form.enable_check_item_photo_similarity_alert.default"
            active-text="开启相似度提醒"
            inactive-text="关闭提醒"
          />
        </el-form-item>

        <el-form-item label="匹配窗口（天）">
          <el-input-number
            v-model="form.check_item_photo_similarity_window_days.default"
            :min="1"
            :max="3650"
            :step="1"
            step-strictly
            controls-position="right"
            style="width: 220px"
          />
          <span class="hint" style="margin-left: 8px;">仅匹配最近N天内的历史检查项照片</span>
        </el-form-item>

        <el-form-item label="相似度粗筛阈值">
          <el-input-number
            v-model="form.check_item_photo_similarity_phash_threshold.default"
            :min="0"
            :max="64"
            :step="1"
            step-strictly
            controls-position="right"
            style="width: 220px"
          />
          <span class="hint" style="margin-left: 8px;">值越大越宽松，更容易触发“相似提醒”</span>
        </el-form-item>

        <el-form-item label="相似度精筛阈值">
          <el-input-number
            v-model="form.check_item_photo_similarity_vector_threshold.default"
            :min="0"
            :max="1"
            :step="0.001"
            :precision="3"
            controls-position="right"
            style="width: 220px"
          />
          <span class="hint" style="margin-left: 8px;">值越大越严格，更不容易误报</span>
        </el-form-item>

        <el-form-item label="说明">
          <ul class="hint-list">
            <li>仅影响“检查项”照片（不含线下票据/单据照片）。</li>
            <li>系统会先做快速筛选，再做精细比对；两步都通过才会提示“高相似风险”。</li>
            <li>提醒场景：APP上传后提示 + 工单审核台列表/详情提醒。</li>
          </ul>
        </el-form-item>
      </el-form>
    </el-card>

    <el-dialog
      v-model="similarityGuideDialogVisible"
      title="相似度阈值调参建议（检查项照片）"
      width="980px"
      destroy-on-close
    >
      <div class="similarity-guide">
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="这张表是实战调参参考，不是死规则。建议先看“当前值”，再按你们现场误报/漏报情况微调。"
        />

        <el-descriptions class="mt12" :column="2" border size="small">
          <el-descriptions-item label="当前粗筛阈值（phash）">
            {{ formatSimilarityPhashValue(form.check_item_photo_similarity_phash_threshold.default) }}
          </el-descriptions-item>
          <el-descriptions-item label="当前精筛阈值（向量）">
            {{ formatSimilarityVectorValue(form.check_item_photo_similarity_vector_threshold.default) }}
          </el-descriptions-item>
        </el-descriptions>

        <el-table
          class="mt12"
          :data="similarityThresholdSuggestionRows"
          size="small"
          border
          style="width: 100%"
        >
          <el-table-column prop="level" label="档位" width="140" />
          <el-table-column prop="phash" label="粗筛阈值" width="120" />
          <el-table-column prop="vector" label="精筛阈值" width="130" />
          <el-table-column prop="scenario" label="适用场景" min-width="220" />
          <el-table-column prop="result" label="效果（说人话）" min-width="300" />
        </el-table>

        <div class="similarity-guide__human mt12">
          <div class="similarity-guide__title">怎么调（说人话）</div>
          <ul class="hint-list">
            <li>现场反馈“提醒太少，担心漏掉复用照片”：先把粗筛阈值加 1~2（例如 8→9/10），观察 2~3 天。</li>
            <li>现场反馈“提醒太多，审核压力大”：先把精筛阈值加 0.005~0.01（例如 0.975→0.980/0.985）。</li>
            <li>优先单参数微调，不建议两项同时大幅改，避免不知道是哪一项导致变化。</li>
            <li>默认推荐：`粗筛=8` + `精筛=0.975`，适合大多数场景作为起点。</li>
          </ul>
        </div>
      </div>
      <template #footer>
        <el-button @click="similarityGuideDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 卡片 5：检查详情本地上传水印定位信息 -->
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

    <!-- 卡片 6：拍照规划坐标比对 -->
    <el-card class="mb16" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>拍照规划坐标比对</span>
        </div>
      </template>

      <el-form :model="form" label-width="200px" :disabled="!canEdit">
        <el-form-item label="全局比对开关">
          <el-switch
            v-model="form.enable_photo_location_distance_check.default"
            active-text="开启比对"
            inactive-text="关闭比对"
          />
        </el-form-item>

        <el-form-item label="全局阈值（米）">
          <el-input-number
            v-model="form.photo_location_distance_threshold_m.default"
            :min="1"
            :max="10000"
            :step="1"
            controls-position="right"
          />
        </el-form-item>

        <el-form-item label="超限上传策略">
          <el-switch
            v-model="form.distance_exceed_block_upload.default"
            active-text="超限阻断上传"
            inactive-text="超限仅提醒不阻断"
          />
        </el-form-item>

        <el-form-item label="说明">
          <ul class="hint-list">
            <li>开启后：移动端拍照会将“实拍坐标 vs 规划坐标”的距离写入水印与上传元数据。</li>
            <li>阈值默认 100 米，可按角色和用户覆盖。</li>
            <li>超限阻断关闭时：保存前仅提示可继续上传；开启时：超限会阻断上传。</li>
            <li>当站点没有规划坐标时，水印会显示“规划坐标缺失”。</li>
          </ul>
        </el-form-item>
      </el-form>

      <el-collapse v-model="activeAdvancedLocationDistanceCheck" class="mt8">
        <el-collapse-item name="role-distance-check">
          <template #title>
            <span>按角色覆盖（距离比对开关）</span>
          </template>
          <el-table :data="roleRows" size="small" border style="width: 100%">
            <el-table-column prop="label" label="角色" width="140" />
            <el-table-column label="距离比对开关">
              <template #default="{ row }">
                <el-select
                  v-model="form.enable_photo_location_distance_check.per_role[row.key]"
                  placeholder="跟随全局"
                  style="width: 220px"
                  :disabled="!canEdit"
                  clearable
                >
                  <el-option label="跟随全局" :value="''" />
                  <el-option label="开启比对" value="allow" />
                  <el-option label="关闭比对" value="deny" />
                </el-select>
              </template>
            </el-table-column>
          </el-table>
        </el-collapse-item>

        <el-collapse-item name="user-distance-check">
          <template #title>
            <span>按用户覆盖（距离比对开关）</span>
          </template>
          <div class="user-rules">
            <div class="user-rule-form">
              <el-select
                v-model="newLocationDistanceCheckUserRule.user_id"
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
                v-model="newLocationDistanceCheckUserRule.flag"
                placeholder="距离比对开关"
                style="width: 180px; margin-left: 8px"
                :disabled="!canEdit"
              >
                <el-option label="开启比对" value="allow" />
                <el-option label="关闭比对" value="deny" />
              </el-select>
              <el-button
                type="primary"
                size="small"
                style="margin-left: 8px"
                :disabled="!canEdit"
                @click="addLocationDistanceCheckUserRule"
              >
                添加
              </el-button>
            </div>

            <el-table
              v-if="form.enable_photo_location_distance_check.per_user.length"
              :data="form.enable_photo_location_distance_check.per_user"
              size="small"
              border
              style="width: 100%; margin-top: 8px"
            >
              <el-table-column prop="user_id" label="用户ID" width="120" />
              <el-table-column prop="flag" label="距离比对开关" width="180">
                <template #default="{ row }">
                  <span v-if="row.flag === 'allow'">开启比对</span>
                  <span v-else-if="row.flag === 'deny'">关闭比对</span>
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
                    @click="removeLocationDistanceCheckUserRule($index)"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-collapse-item>
      </el-collapse>

      <el-collapse v-model="activeAdvancedDistanceBlockUpload" class="mt8">
        <el-collapse-item name="role-distance-block">
          <template #title>
            <span>按角色覆盖（超限阻断上传）</span>
          </template>
          <el-table :data="roleRows" size="small" border style="width: 100%">
            <el-table-column prop="label" label="角色" width="140" />
            <el-table-column label="超限上传策略">
              <template #default="{ row }">
                <el-select
                  v-model="form.distance_exceed_block_upload.per_role[row.key]"
                  placeholder="跟随全局"
                  style="width: 220px"
                  :disabled="!canEdit"
                  clearable
                >
                  <el-option label="跟随全局" :value="''" />
                  <el-option label="超限阻断上传" value="allow" />
                  <el-option label="超限仅提醒不阻断" value="deny" />
                </el-select>
              </template>
            </el-table-column>
          </el-table>
        </el-collapse-item>

        <el-collapse-item name="user-distance-block">
          <template #title>
            <span>按用户覆盖（超限阻断上传）</span>
          </template>
          <div class="user-rules">
            <div class="user-rule-form">
              <el-select
                v-model="newDistanceBlockUploadUserRule.user_id"
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
                v-model="newDistanceBlockUploadUserRule.flag"
                placeholder="超限上传策略"
                style="width: 220px; margin-left: 8px"
                :disabled="!canEdit"
              >
                <el-option label="超限阻断上传" value="allow" />
                <el-option label="超限仅提醒不阻断" value="deny" />
              </el-select>
              <el-button
                type="primary"
                size="small"
                style="margin-left: 8px"
                :disabled="!canEdit"
                @click="addDistanceBlockUploadUserRule"
              >
                添加
              </el-button>
            </div>

            <el-table
              v-if="form.distance_exceed_block_upload.per_user.length"
              :data="form.distance_exceed_block_upload.per_user"
              size="small"
              border
              style="width: 100%; margin-top: 8px"
            >
              <el-table-column prop="user_id" label="用户ID" width="120" />
              <el-table-column prop="flag" label="超限上传策略" width="220">
                <template #default="{ row }">
                  <span v-if="row.flag === 'allow'">超限阻断上传</span>
                  <span v-else-if="row.flag === 'deny'">超限仅提醒不阻断</span>
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
                    @click="removeDistanceBlockUploadUserRule($index)"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-collapse-item>
      </el-collapse>

      <el-collapse v-model="activeAdvancedDistanceThreshold" class="mt8">
        <el-collapse-item name="role-distance-threshold">
          <template #title>
            <span>按角色覆盖（超限阈值米数）</span>
          </template>
          <el-table :data="roleRows" size="small" border style="width: 100%">
            <el-table-column prop="label" label="角色" width="140" />
            <el-table-column label="阈值（米）">
              <template #default="{ row }">
                <div style="display: flex; align-items: center; gap: 8px;">
                  <el-input-number
                    v-model="form.photo_location_distance_threshold_m.per_role[row.key]"
                    :min="1"
                    :max="10000"
                    :step="1"
                    controls-position="right"
                    :disabled="!canEdit"
                    style="width: 180px"
                  />
                  <el-button
                    size="small"
                    text
                    :disabled="!canEdit"
                    @click="form.photo_location_distance_threshold_m.per_role[row.key] = null"
                  >
                    跟随全局
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-collapse-item>

        <el-collapse-item name="user-distance-threshold">
          <template #title>
            <span>按用户覆盖（超限阈值米数）</span>
          </template>
          <div class="user-rules">
            <div class="user-rule-form">
              <el-select
                v-model="newDistanceThresholdUserRule.user_id"
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
              <el-input-number
                v-model="newDistanceThresholdUserRule.value"
                :min="1"
                :max="10000"
                :step="1"
                controls-position="right"
                style="width: 180px; margin-left: 8px"
                :disabled="!canEdit"
              />
              <el-button
                type="primary"
                size="small"
                style="margin-left: 8px"
                :disabled="!canEdit"
                @click="addDistanceThresholdUserRule"
              >
                添加
              </el-button>
            </div>

            <el-table
              v-if="form.photo_location_distance_threshold_m.per_user.length"
              :data="form.photo_location_distance_threshold_m.per_user"
              size="small"
              border
              style="width: 100%; margin-top: 8px"
            >
              <el-table-column prop="user_id" label="用户ID" width="120" />
              <el-table-column prop="value" label="阈值（米）" width="160" />
              <el-table-column label="操作" width="80">
                <template #default="{ $index }">
                  <el-button
                    type="danger"
                    text
                    size="small"
                    :disabled="!canEdit"
                    @click="removeDistanceThresholdUserRule($index)"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <!-- 卡片 7：旧流程扫码领货（我的设备） -->
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

    <!-- 卡片 8：照片水印模板 -->
    <el-card class="mb16" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>照片水印模板</span>
        </div>
      </template>

      <el-form :model="form" label-width="200px" :disabled="!canEdit">
        <el-form-item label="场景策略">
          <div class="watermark-scene-policy">
            <el-switch
              v-model="form.photo_watermark_scene_policy.apply_for_camera"
              active-text="拍照场景启用模板"
              inactive-text="拍照场景不启用模板"
            />
            <el-switch
              v-model="form.photo_watermark_scene_policy.apply_for_album"
              active-text="相册场景启用模板"
              inactive-text="相册场景不启用模板"
            />
            <el-switch
              v-model="form.photo_watermark_scene_policy.force_local_upload_note_when_geo_disabled"
              active-text="本地上传无定位时强制本地标注"
              inactive-text="本地上传无定位时不强制本地标注"
            />
          </div>
        </el-form-item>
      </el-form>

      <div class="watermark-template-toolbar">
        <el-button type="primary" size="small" :disabled="!canEdit" @click="addWatermarkTemplate">
          新增模板
        </el-button>
        <el-button size="small" :disabled="!canEdit || !currentWatermarkTemplate" @click="copyCurrentWatermarkTemplate">
          复制当前模板
        </el-button>
        <el-button
          size="small"
          type="danger"
          :disabled="!canEdit || !currentWatermarkTemplate || form.photo_watermark_templates.length <= 1"
          @click="removeCurrentWatermarkTemplate"
        >
          删除当前模板
        </el-button>
      </div>

      <el-table :data="form.photo_watermark_templates" size="small" border style="width: 100%; margin-top: 8px">
        <el-table-column label="模板ID" width="180">
          <template #default="{ row }">
            <code>{{ row.id }}</code>
          </template>
        </el-table-column>
        <el-table-column label="模板名称" min-width="180">
          <template #default="{ row }">
            <span>{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="版本" width="90">
          <template #default="{ row }">
            <span>{{ row.version }}</span>
          </template>
        </el-table-column>
        <el-table-column label="默认模板" width="120">
          <template #default="{ row }">
            <el-tag v-if="form.photo_watermark_template_rule.default === row.id" size="small" type="success">
              默认
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button type="primary" link size="small" :disabled="!canEdit" @click="selectWatermarkTemplate(row.id)">
              编辑
            </el-button>
            <el-button
              type="success"
              link
              size="small"
              :disabled="!canEdit || form.photo_watermark_template_rule.default === row.id"
              @click="setDefaultWatermarkTemplate(row.id)"
            >
              设为默认
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="currentWatermarkTemplate" class="watermark-template-detail mt12">
        <el-form :model="currentWatermarkTemplate" label-width="180px" :disabled="!canEdit">
          <el-form-item label="当前编辑模板ID">
            <code>{{ currentWatermarkTemplate.id }}</code>
          </el-form-item>
          <el-form-item label="模板名称">
            <el-input
              v-model="currentWatermarkTemplate.name"
              maxlength="40"
              show-word-limit
              placeholder="例如：施工现场标准模板"
              style="max-width: 420px"
            />
          </el-form-item>
          <el-form-item label="模板版本">
            <el-input-number
              v-model="currentWatermarkTemplate.version"
              :min="1"
              :max="999999"
              :step="1"
              controls-position="right"
            />
          </el-form-item>

          <el-divider content-position="left">样式</el-divider>
          <el-form-item label="水印位置">
            <el-select v-model="currentWatermarkTemplate.style.position" style="width: 220px">
              <el-option label="左上角" value="topLeft" />
              <el-option label="右上角" value="topRight" />
              <el-option label="左下角" value="bottomLeft" />
              <el-option label="右下角" value="bottomRight" />
              <el-option label="居中" value="center" />
            </el-select>
          </el-form-item>
          <el-form-item label="文字颜色">
            <el-color-picker v-model="currentWatermarkTemplate.style.text_color" />
          </el-form-item>
          <el-form-item label="背景颜色">
            <el-color-picker v-model="currentWatermarkTemplate.style.background_color" />
          </el-form-item>
          <el-form-item label="背景透明度">
            <el-slider
              v-model="currentWatermarkTemplate.style.background_opacity"
              :min="0"
              :max="1"
              :step="0.05"
              style="max-width: 360px"
            />
          </el-form-item>
          <el-form-item label="字体大小">
            <el-input-number
              v-model="currentWatermarkTemplate.style.font_size"
              :min="12"
              :max="96"
              :step="1"
              controls-position="right"
            />
          </el-form-item>
          <el-form-item label="行高">
            <el-input-number
              v-model="currentWatermarkTemplate.style.line_height"
              :min="16"
              :max="140"
              :step="1"
              controls-position="right"
            />
          </el-form-item>
          <el-form-item label="内边距">
            <el-input-number
              v-model="currentWatermarkTemplate.style.padding"
              :min="0"
              :max="120"
              :step="1"
              controls-position="right"
            />
          </el-form-item>
          <el-form-item label="外边距">
            <el-input-number
              v-model="currentWatermarkTemplate.style.margin"
              :min="0"
              :max="120"
              :step="1"
              controls-position="right"
            />
          </el-form-item>
          <el-form-item label="圆角">
            <el-input-number
              v-model="currentWatermarkTemplate.style.border_radius"
              :min="0"
              :max="80"
              :step="1"
              controls-position="right"
            />
          </el-form-item>
          <el-form-item label="最大宽度比例">
            <el-slider
              v-model="currentWatermarkTemplate.style.max_width_ratio"
              :min="0.3"
              :max="1"
              :step="0.01"
              style="max-width: 360px"
            />
          </el-form-item>
          <el-form-item label="水印区域占比">
            <el-slider
              v-model="currentWatermarkTemplate.style.area_ratio"
              :min="0.01"
              :max="0.4"
              :step="0.005"
              style="max-width: 360px"
            />
            <span class="hint" style="margin-left: 10px">
              {{ (currentWatermarkTemplate.style.area_ratio * 100).toFixed(1) }}%
            </span>
          </el-form-item>

          <el-divider content-position="left">内容</el-divider>
          <el-form-item label="显示项">
            <div class="watermark-content-switches">
              <el-switch v-model="currentWatermarkTemplate.content.show_icon" active-text="图标" />
              <el-switch v-model="currentWatermarkTemplate.content.show_local_upload_note" active-text="本地上传标注" />
              <el-switch v-model="currentWatermarkTemplate.content.show_gps" active-text="GPS坐标" />
              <el-switch v-model="currentWatermarkTemplate.content.show_accuracy" active-text="定位精度" />
              <el-switch v-model="currentWatermarkTemplate.content.show_address" active-text="地址" />
              <el-switch v-model="currentWatermarkTemplate.content.show_timestamp" active-text="时间" />
              <el-switch v-model="currentWatermarkTemplate.content.show_inspector" active-text="检查员" />
              <el-switch v-model="currentWatermarkTemplate.content.show_check_item" active-text="检查项" />
              <el-switch v-model="currentWatermarkTemplate.content.show_site_name" active-text="站点名" />
            </div>
          </el-form-item>
          <el-form-item label="坐标精度">
            <el-input-number
              v-model="currentWatermarkTemplate.content.coordinate_precision"
              :min="2"
              :max="8"
              :step="1"
              controls-position="right"
            />
          </el-form-item>
          <el-form-item label="前缀文本">
            <el-input
              v-model="currentWatermarkTemplate.content.custom_prefix"
              maxlength="80"
              show-word-limit
              placeholder="可选，例如：现场作业留痕"
              style="max-width: 420px"
            />
          </el-form-item>
          <el-form-item label="后缀文本">
            <el-input
              v-model="currentWatermarkTemplate.content.custom_suffix"
              maxlength="80"
              show-word-limit
              placeholder="可选，例如：未经许可不得传播"
              style="max-width: 420px"
            />
          </el-form-item>
        </el-form>

        <div class="watermark-preview">
          <div class="watermark-preview__title">实时预览</div>
          <el-tabs v-model="activeWatermarkPreviewTab" class="watermark-preview-tabs">
            <el-tab-pane
              v-for="preview in watermarkPreviewPanels"
              :key="preview.key"
              :label="preview.tabLabel"
              :name="preview.key"
            >
              <div class="watermark-preview__actions">
                <el-button size="small" :disabled="!currentWatermarkTemplate" @click="openWatermarkPreviewDialog(preview.key)">
                  查看原始分辨率效果
                </el-button>
                <span class="hint">
                  缩略预览比例：{{ (preview.previewScale * 100).toFixed(1) }}%
                </span>
              </div>
              <div class="watermark-preview__panel">
                <div class="watermark-preview__panel-title">{{ preview.label }}</div>
                <div class="watermark-preview__canvas" :style="preview.canvasStyle">
                  <div class="watermark-preview__box" :style="preview.boxStyle">
                    <div v-for="(line, idx) in preview.lines" :key="`${preview.key}-${idx}`">{{ line }}</div>
                  </div>
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </div>

      <el-divider content-position="left">模板分配规则</el-divider>
      <el-form :model="form" label-width="200px" :disabled="!canEdit">
        <el-form-item label="全局默认模板">
          <el-select v-model="form.photo_watermark_template_rule.default" style="width: 260px" :disabled="!canEdit">
            <el-option
              v-for="opt in watermarkTemplateOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
      </el-form>

      <el-collapse class="mt8">
        <el-collapse-item name="role-watermark-template">
          <template #title>
            <span>按角色覆盖（水印模板）</span>
          </template>
          <el-table :data="roleRows" size="small" border style="width: 100%">
            <el-table-column prop="label" label="角色" width="140" />
            <el-table-column label="模板">
              <template #default="{ row }">
                <el-select
                  v-model="form.photo_watermark_template_rule.per_role[row.key]"
                  placeholder="跟随全局默认模板"
                  clearable
                  style="width: 320px"
                  :disabled="!canEdit"
                >
                  <el-option label="跟随全局默认模板" :value="''" />
                  <el-option
                    v-for="opt in watermarkTemplateOptions"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
              </template>
            </el-table-column>
          </el-table>
        </el-collapse-item>

        <el-collapse-item name="user-watermark-template">
          <template #title>
            <span>按用户覆盖（水印模板）</span>
          </template>
          <div class="user-rules">
            <div class="user-rule-form">
              <el-select
                v-model="newWatermarkTemplateUserRule.user_id"
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
                v-model="newWatermarkTemplateUserRule.template_id"
                placeholder="模板"
                style="width: 280px; margin-left: 8px"
                :disabled="!canEdit"
              >
                <el-option
                  v-for="opt in watermarkTemplateOptions"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
              <el-button
                type="primary"
                size="small"
                style="margin-left: 8px"
                :disabled="!canEdit"
                @click="addWatermarkTemplateUserRule"
              >
                添加
              </el-button>
            </div>

            <el-table
              v-if="form.photo_watermark_template_rule.per_user.length"
              :data="form.photo_watermark_template_rule.per_user"
              size="small"
              border
              style="width: 100%; margin-top: 8px"
            >
              <el-table-column prop="user_id" label="用户ID" width="120" />
              <el-table-column prop="template_id" label="模板ID" width="160" />
              <el-table-column label="模板名称" min-width="180">
                <template #default="{ row }">
                  <span>
                    {{
                      (form.photo_watermark_templates.find(t => t.id === row.template_id)?.name || '未知模板')
                    }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80">
                <template #default="{ $index }">
                  <el-button
                    type="danger"
                    text
                    size="small"
                    :disabled="!canEdit"
                    @click="removeWatermarkTemplateUserRule($index)"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
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

    <el-dialog
      v-model="watermarkPreviewDialogVisible"
      :title="watermarkPreviewDialogTitle"
      width="92%"
      top="4vh"
      destroy-on-close
    >
      <div v-if="watermarkPreviewDialogPanel" class="watermark-preview-dialog">
        <div class="watermark-preview-dialog__toolbar">
          <div class="watermark-preview-dialog__zoom">
            <span class="hint">缩放：</span>
            <el-radio-group v-model="watermarkPreviewDialogZoom" size="small">
              <el-radio-button
                v-for="zoom in watermarkPreviewDialogZoomOptions"
                :key="zoom"
                :label="zoom"
              >
                {{ zoom === 'fit' ? '自适应' : `${zoom}%` }}
              </el-radio-button>
            </el-radio-group>
          </div>
          <span class="hint">
            原始分辨率：{{ watermarkPreviewDialogPanel.width }} x {{ watermarkPreviewDialogPanel.height }}
          </span>
        </div>
        <div class="watermark-preview-dialog__viewport">
          <div class="watermark-preview__canvas watermark-preview-dialog__canvas" :style="watermarkPreviewDialogPanel.canvasStyle">
            <div class="watermark-preview__box" :style="watermarkPreviewDialogPanel.boxStyle">
              <div
                v-for="(line, idx) in watermarkPreviewDialogPanel.lines"
                :key="`dialog-${watermarkPreviewDialogPanel.key}-${idx}`"
              >
                {{ line }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Document } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { mobileSettingsApi } from '@/api/system'
import { userAPI } from '@/api/user'

const userStore = useUserStore()

const loading = ref(false)
const saving = ref(false)
const similarityGuideDialogVisible = ref(false)
const similarityThresholdSuggestionRows = [
  {
    level: '1档（极严）',
    phash: 4,
    vector: '0.990',
    scenario: '项目初期、先稳住误报，审核人力紧张',
    result: '只有非常接近的历史照片才会提醒，误报最低，但可能漏掉部分“轻微改图”复用。',
  },
  {
    level: '2档（偏严）',
    phash: 6,
    vector: '0.985',
    scenario: '站点拍摄环境差异较大，不想被频繁打扰',
    result: '提醒频次偏低，适合先跑一段时间摸底。',
  },
  {
    level: '3档（推荐）',
    phash: 8,
    vector: '0.975',
    scenario: '大多数项目默认起步档',
    result: '在误报与漏报之间比较平衡，建议先从这一档开始。',
  },
  {
    level: '4档（偏松）',
    phash: 10,
    vector: '0.970',
    scenario: '历史照片复用风险高，希望更敏感',
    result: '会抓到更多“改曝光/改水印”类复用，但提醒数量会明显增多。',
  },
  {
    level: '5档（高敏）',
    phash: 12,
    vector: '0.965',
    scenario: '专项治理期，需要尽量多发现可疑照片',
    result: '提醒最多，审核压力最大，建议短期使用并配合人工复核。',
  },
]

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
  block_duplicate_check_item_photo_upload: {
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
  enable_check_item_photo_similarity_alert: {
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
  check_item_photo_similarity_window_days: {
    default: 180,
    per_role: {
      admin: null,
      manager: null,
      inspector: null,
      surveyor: null,
      user: null,
    },
    per_user: [],
  },
  check_item_photo_similarity_phash_threshold: {
    default: 8,
    per_role: {
      admin: null,
      manager: null,
      inspector: null,
      surveyor: null,
      user: null,
    },
    per_user: [],
  },
  check_item_photo_similarity_vector_threshold: {
    default: 0.975,
    per_role: {
      admin: null,
      manager: null,
      inspector: null,
      surveyor: null,
      user: null,
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
  enable_photo_location_distance_check: {
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
  distance_exceed_block_upload: {
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
  photo_location_distance_threshold_m: {
    default: 100,
    per_role: {
      admin: null,
      manager: null,
      inspector: null,
      surveyor: null,
      user: null,
    },
    per_user: [],
  },
  photo_watermark_templates: [
    {
      id: 'default',
      name: '默认模板',
      version: 1,
      style: {
        position: 'bottomLeft',
        text_color: '#FF6600',
        background_color: '#000000',
        background_opacity: 0.7,
        font_size: 28,
        padding: 15,
        margin: 20,
        line_height: 35,
        border_radius: 8,
        max_width_ratio: 0.9,
        area_ratio: 0.08,
      },
      content: {
        show_icon: true,
        show_local_upload_note: true,
        show_gps: true,
        show_accuracy: true,
        show_address: true,
        show_timestamp: true,
        show_inspector: true,
        show_check_item: true,
        show_site_name: true,
        coordinate_precision: 6,
        custom_prefix: '',
        custom_suffix: '',
      },
    },
  ],
  photo_watermark_template_rule: {
    default: 'default',
    per_role: {
      admin: '',
      manager: '',
      inspector: '',
      surveyor: '',
      user: '',
    },
    per_user: [],
  },
  photo_watermark_scene_policy: {
    apply_for_camera: true,
    apply_for_album: true,
    force_local_upload_note_when_geo_disabled: true,
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

const newDuplicatePhotoBlockUserRule = ref({
  user_id: '',
  flag: 'allow',
})

const newLegacyScanPickupUserRule = ref({
  user_id: '',
  flag: 'deny',
})

const newLocationDistanceCheckUserRule = ref({
  user_id: '',
  flag: 'allow',
})

const newDistanceBlockUploadUserRule = ref({
  user_id: '',
  flag: 'deny',
})

const newDistanceThresholdUserRule = ref({
  user_id: '',
  value: 100,
})

const newWatermarkTemplateUserRule = ref({
  user_id: '',
  template_id: 'default',
})

const selectedWatermarkTemplateId = ref('default')
const activeWatermarkPreviewTab = ref('720')
const watermarkPreviewDialogVisible = ref(false)
const watermarkPreviewDialogResolutionKey = ref('720')
const watermarkPreviewDialogZoom = ref('fit')
const watermarkPreviewDialogZoomOptions = ['fit', 25, 50, 100, 200]
const watermarkPreviewViewport = ref({
  width: typeof window !== 'undefined' ? window.innerWidth : 1440,
  height: typeof window !== 'undefined' ? window.innerHeight : 900,
})

// 高级配置折叠面板（默认全部收起，减少页面占用）
const activeAdvancedLocation = ref([])
const activeAdvancedUpload = ref([])
const activeAdvancedLocalUploadWatermark = ref([])
const activeAdvancedDuplicatePhotoBlock = ref([])
const activeAdvancedLegacyScanPickup = ref([])
const activeAdvancedLocationDistanceCheck = ref([])
const activeAdvancedDistanceBlockUpload = ref([])
const activeAdvancedDistanceThreshold = ref([])

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

const createWatermarkTemplate = (id = 'default') => ({
  id,
  name: id === 'default' ? '默认模板' : `模板-${id}`,
  version: 1,
  style: {
    position: 'bottomLeft',
    text_color: '#FF6600',
    background_color: '#000000',
    background_opacity: 0.7,
    font_size: 28,
    padding: 15,
    margin: 20,
    line_height: 35,
    border_radius: 8,
    max_width_ratio: 0.9,
    area_ratio: 0.08,
  },
  content: {
    show_icon: true,
    show_local_upload_note: true,
    show_gps: true,
    show_accuracy: true,
    show_address: true,
    show_timestamp: true,
    show_inspector: true,
    show_check_item: true,
    show_site_name: true,
    coordinate_precision: 6,
    custom_prefix: '',
    custom_suffix: '',
  },
})

const normalizeTemplateId = (value) => {
  const cleaned = String(value || '').trim().replace(/[^A-Za-z0-9_-]/g, '_').slice(0, 64)
  return cleaned || 'tpl'
}

const toRgba = (hex, opacity = 1) => {
  const text = String(hex || '').trim()
  const matched = /^#([0-9a-fA-F]{6})$/.exec(text)
  const alpha = clampFloat(opacity, 0, 1, 3, 1)
  if (!matched) {
    return `rgba(0, 0, 0, ${alpha})`
  }
  const color = matched[1]
  const r = parseInt(color.slice(0, 2), 16)
  const g = parseInt(color.slice(2, 4), 16)
  const b = parseInt(color.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

const normalizeWatermarkTemplateForForm = (id, rawTemplate = {}) => {
  const template = rawTemplate || {}
  const style = template.style || {}
  const content = template.content || {}
  return {
    id: normalizeTemplateId(id),
    name: String(template.name || '').trim() || '未命名模板',
    version: clampInt(template.version, 1, 999999, 1),
    style: {
      position: ['topLeft', 'topRight', 'bottomLeft', 'bottomRight', 'center'].includes(style.position)
        ? style.position
        : 'bottomLeft',
      text_color: /^#([0-9a-fA-F]{6})$/.test(String(style.text_color || '').trim())
        ? String(style.text_color || '').trim()
        : '#FF6600',
      background_color: /^#([0-9a-fA-F]{6})$/.test(String(style.background_color || '').trim())
        ? String(style.background_color || '').trim()
        : '#000000',
      background_opacity: clampFloat(style.background_opacity, 0, 1, 3, 0.7),
      font_size: clampInt(style.font_size, 12, 96, 28),
      padding: clampInt(style.padding, 0, 120, 15),
      margin: clampInt(style.margin, 0, 120, 20),
      line_height: clampInt(style.line_height, 16, 140, 35),
      border_radius: clampInt(style.border_radius, 0, 80, 8),
      max_width_ratio: clampFloat(style.max_width_ratio, 0.3, 1, 3, 0.9),
      area_ratio: clampFloat(style.area_ratio, 0.01, 0.4, 3, 0.08),
    },
    content: {
      show_icon: content.show_icon !== false,
      show_local_upload_note: content.show_local_upload_note !== false,
      show_gps: content.show_gps !== false,
      show_accuracy: content.show_accuracy !== false,
      show_address: content.show_address !== false,
      show_timestamp: content.show_timestamp !== false,
      show_inspector: content.show_inspector !== false,
      show_check_item: content.show_check_item !== false,
      show_site_name: content.show_site_name !== false,
      coordinate_precision: clampInt(content.coordinate_precision, 2, 8, 6),
      custom_prefix: String(content.custom_prefix || '').slice(0, 80),
      custom_suffix: String(content.custom_suffix || '').slice(0, 80),
    },
  }
}

const ensureWatermarkTemplateRuleIntegrity = () => {
  const templates = form.value.photo_watermark_templates || []
  if (!templates.length) {
    form.value.photo_watermark_templates = [createWatermarkTemplate('default')]
  }
  const existingIds = new Set((form.value.photo_watermark_templates || []).map(t => String(t.id)))

  let defaultId = String(form.value.photo_watermark_template_rule.default || '').trim()
  if (!defaultId || !existingIds.has(defaultId)) {
    defaultId = existingIds.has('default')
      ? 'default'
      : String(form.value.photo_watermark_templates[0]?.id || 'default')
  }
  form.value.photo_watermark_template_rule.default = defaultId

  const safePerRole = {}
  roleKeys.forEach((role) => {
    const current = String(form.value.photo_watermark_template_rule.per_role?.[role] || '').trim()
    safePerRole[role] = current && existingIds.has(current) ? current : ''
  })
  form.value.photo_watermark_template_rule.per_role = safePerRole

  form.value.photo_watermark_template_rule.per_user =
    (form.value.photo_watermark_template_rule.per_user || []).filter((rule) => {
      const uid = String(rule.user_id || '').trim()
      const tid = String(rule.template_id || '').trim()
      return uid && tid && existingIds.has(tid)
    })

  if (!existingIds.has(selectedWatermarkTemplateId.value)) {
    selectedWatermarkTemplateId.value = defaultId
  }
}

const currentWatermarkTemplate = computed(() => {
  const currentId = String(selectedWatermarkTemplateId.value || '').trim()
  return (form.value.photo_watermark_templates || []).find(t => String(t.id) === currentId) || null
})

const watermarkTemplateOptions = computed(() =>
  (form.value.photo_watermark_templates || []).map(t => ({
    label: `${t.name} (${t.id})`,
    value: t.id,
  })),
)

const watermarkPreviewResolutions = [
  { key: '720', tabLabel: '720p', label: '720p (1280 x 720)', width: 1280, height: 720 },
  { key: '1080', tabLabel: '1080p', label: '1080p (1920 x 1080)', width: 1920, height: 1080 },
  { key: '2k', tabLabel: '2k', label: '2k (2560 x 1440)', width: 2560, height: 1440 },
  { key: '4k', tabLabel: '4k', label: '4k (3840 x 2160)', width: 3840, height: 2160 },
]
const WATERMARK_PREVIEW_THUMB_SCALE = 0.16

const buildPreviewLine = (icon, text, showIcon) => {
  const raw = String(text || '').trim()
  if (!raw) return ''
  return showIcon ? `${icon} ${raw}` : raw
}

const buildWatermarkPreviewLines = (content) => {
  const c = content || {}
  const showIcon = c.show_icon !== false
  const lines = []
  if (c.custom_prefix) lines.push(String(c.custom_prefix))
  if (c.show_local_upload_note) lines.push('本图片为本地上传照片')
  if (c.show_gps) lines.push(buildPreviewLine('📍', '31.245678, 121.473701', showIcon))
  if (c.show_accuracy) lines.push(buildPreviewLine('📊', '4.5m', showIcon))
  if (c.show_address) lines.push(buildPreviewLine('🏠', '上海市浦东新区张江路', showIcon))
  if (c.show_timestamp) lines.push(buildPreviewLine('🕐', '2026-02-28 10:30:15', showIcon))
  if (c.show_inspector) lines.push(buildPreviewLine('👤', 'demo_user', showIcon))
  if (c.show_check_item) lines.push(buildPreviewLine('📋', '站点围栏检查', showIcon))
  if (c.show_site_name) lines.push(buildPreviewLine('🏗️', 'SITE-DEMO-001', showIcon))
  if (c.custom_suffix) lines.push(String(c.custom_suffix))
  const filtered = lines.map(line => String(line || '').trim()).filter(Boolean)
  if (!filtered.length) {
    filtered.push(buildPreviewLine('🕐', '2026-02-28 10:30:15', showIcon))
  }
  return filtered
}

const estimatePreviewTextWidth = (text, fontSize) => {
  const chars = Array.from(String(text || ''))
  let weight = 0
  chars.forEach((ch) => {
    weight += /[^\x00-\xff]/.test(ch) ? 1 : 0.56
  })
  return Math.max(0, weight * fontSize)
}

const computePreviewBoxMetrics = (lines, fontSize, lineHeight, padding, maxWidthPx) => {
  let maxTextWidth = 0
  ;(lines || []).forEach((line) => {
    maxTextWidth = Math.max(maxTextWidth, estimatePreviewTextWidth(line, fontSize))
  })
  const width = Math.min(maxWidthPx, Math.max(120, Math.ceil(maxTextWidth + padding * 2)))
  const height = Math.max(48, Math.ceil((lines || []).length * lineHeight + padding * 2))
  return { width, height }
}

const resolveWatermarkBoxPosition = (position, canvasWidth, canvasHeight, boxWidth, boxHeight, margin) => {
  let x = margin
  let y = Math.max(margin, canvasHeight - boxHeight - margin)

  if (position === 'topLeft') {
    x = margin
    y = margin
  } else if (position === 'topRight') {
    x = Math.max(margin, canvasWidth - boxWidth - margin)
    y = margin
  } else if (position === 'bottomRight') {
    x = Math.max(margin, canvasWidth - boxWidth - margin)
    y = Math.max(margin, canvasHeight - boxHeight - margin)
  } else if (position === 'center') {
    x = Math.max(margin, Math.round((canvasWidth - boxWidth) / 2))
    y = Math.max(margin, Math.round((canvasHeight - boxHeight) / 2))
  }

  const maxX = Math.max(0, canvasWidth - boxWidth)
  const maxY = Math.max(0, canvasHeight - boxHeight)
  return {
    x: Math.max(0, Math.min(maxX, x)),
    y: Math.max(0, Math.min(maxY, y)),
  }
}

const buildWatermarkLayoutAtOriginal = (template, resolution) => {
  const tpl = template || {}
  const styleSource = tpl.style || {}
  const contentSource = tpl.content || {}
  const imageWidth = Number(resolution.width || 0)
  const imageHeight = Number(resolution.height || 0)
  if (!Number.isFinite(imageWidth) || !Number.isFinite(imageHeight) || imageWidth <= 0 || imageHeight <= 0) {
    return null
  }

  const lines = buildWatermarkPreviewLines(contentSource)
  const position = ['topLeft', 'topRight', 'bottomLeft', 'bottomRight', 'center'].includes(styleSource.position)
    ? styleSource.position
    : 'bottomLeft'
  const maxWidthRatio = clampFloat(styleSource.max_width_ratio, 0.3, 1, 3, 0.9)
  const areaRatio = clampFloat(styleSource.area_ratio, 0.01, 0.4, 3, 0.08)
  const textColor = /^#([0-9a-fA-F]{6})$/.test(String(styleSource.text_color || '').trim())
    ? String(styleSource.text_color).toUpperCase()
    : '#FF6600'
  const backgroundColor = /^#([0-9a-fA-F]{6})$/.test(String(styleSource.background_color || '').trim())
    ? String(styleSource.background_color).toUpperCase()
    : '#000000'
  const backgroundOpacity = clampFloat(styleSource.background_opacity, 0, 1, 3, 0.7)

  const baseFontSize = clampInt(styleSource.font_size, 12, 96, 28)
  const basePadding = clampInt(styleSource.padding, 0, 120, 15)
  const baseMargin = clampInt(styleSource.margin, 0, 120, 20)
  const baseLineHeight = clampInt(styleSource.line_height, 16, 140, 35)
  const baseBorderRadius = clampInt(styleSource.border_radius, 0, 80, 8)

  const shortEdge = Math.min(imageWidth, imageHeight)
  let initialScale = baseFontSize > 0 ? ((shortEdge * 0.025) / baseFontSize) : 1
  if (!Number.isFinite(initialScale) || initialScale <= 0) initialScale = 1
  initialScale = Math.max(0.8, Math.min(3, initialScale))

  const styleState = {
    fontSize: baseFontSize * initialScale,
    padding: basePadding * initialScale,
    margin: baseMargin * initialScale,
    lineHeight: baseLineHeight * initialScale,
    borderRadius: baseBorderRadius * initialScale,
  }

  const maxWidthPx = Math.max(120, Math.floor(imageWidth * maxWidthRatio))
  const computeMetrics = (inputStyle) => {
    const fontSize = Math.max(10, inputStyle.fontSize)
    const lineHeight = Math.max(fontSize + 2, inputStyle.lineHeight)
    const padding = Math.max(0, inputStyle.padding)
    return computePreviewBoxMetrics(lines, fontSize, lineHeight, padding, maxWidthPx)
  }

  let metrics = computeMetrics(styleState)
  const imageArea = imageWidth * imageHeight
  const currentArea = metrics.width * metrics.height
  const targetArea = imageArea * areaRatio
  if (Number.isFinite(imageArea) && imageArea > 0 && Number.isFinite(currentArea) && currentArea > 0 && Number.isFinite(targetArea) && targetArea > 0) {
    let areaScale = Math.sqrt(targetArea / currentArea)
    if (Number.isFinite(areaScale) && areaScale > 0) {
      areaScale = Math.max(0.35, Math.min(4, areaScale))
      styleState.fontSize = Math.max(12, styleState.fontSize * areaScale)
      styleState.padding = Math.max(0, styleState.padding * areaScale)
      styleState.lineHeight = Math.max(16, styleState.lineHeight * areaScale)
      styleState.borderRadius = Math.max(0, styleState.borderRadius * areaScale)
      metrics = computeMetrics(styleState)
    }
  }

  const margin = Math.max(0, styleState.margin)
  const boxPosition = resolveWatermarkBoxPosition(
    position,
    imageWidth,
    imageHeight,
    metrics.width,
    metrics.height,
    margin,
  )

  return {
    ...resolution,
    lines,
    imageWidth,
    imageHeight,
    textColor,
    backgroundColor,
    backgroundOpacity,
    box: {
      x: boxPosition.x,
      y: boxPosition.y,
      width: metrics.width,
      height: metrics.height,
      fontSize: styleState.fontSize,
      lineHeight: Math.max(styleState.fontSize + 2, styleState.lineHeight),
      padding: styleState.padding,
      borderRadius: styleState.borderRadius,
    },
  }
}

const getWatermarkPreviewFitScale = (resolution) => {
  const viewportWidth = Math.max(320, Number(watermarkPreviewViewport.value.width || 0))
  const viewportHeight = Math.max(260, Number(watermarkPreviewViewport.value.height || 0))
  const maxWidth = Math.max(260, viewportWidth * 0.82)
  const maxHeight = Math.max(220, viewportHeight * 0.62)
  const scaleX = maxWidth / Number(resolution.width || 1)
  const scaleY = maxHeight / Number(resolution.height || 1)
  const scale = Math.min(scaleX, scaleY, 1)
  if (!Number.isFinite(scale) || scale <= 0) return 1
  return scale
}

const resolveWatermarkPreviewScale = (resolution, options = {}) => {
  const mode = options.mode === 'original' ? 'original' : 'thumb'
  if (mode === 'thumb') return WATERMARK_PREVIEW_THUMB_SCALE

  if (options.zoom === 'fit') {
    return getWatermarkPreviewFitScale(resolution)
  }
  const zoomPercent = clampInt(options.zoom, 25, 200, 100)
  return zoomPercent / 100
}

const buildWatermarkPreviewPanel = (template, resolution, options = {}) => {
  const layout = buildWatermarkLayoutAtOriginal(template, resolution)
  if (!layout) return null
  const previewScale = resolveWatermarkPreviewScale(resolution, options)
  const imageWidth = Math.max(1, Math.round(layout.imageWidth * previewScale))
  const imageHeight = Math.max(1, Math.round(layout.imageHeight * previewScale))

  const scaledX = Math.round(layout.box.x * previewScale)
  const scaledY = Math.round(layout.box.y * previewScale)
  const scaledWidth = Math.max(1, Math.round(layout.box.width * previewScale))
  const scaledHeight = Math.max(1, Math.round(layout.box.height * previewScale))

  const boxStyle = {
    color: layout.textColor,
    backgroundColor: toRgba(layout.backgroundColor, layout.backgroundOpacity),
    borderRadius: `${Math.max(1, Math.round(layout.box.borderRadius * previewScale))}px`,
    padding: `${Math.max(1, Math.round(layout.box.padding * previewScale))}px`,
    lineHeight: `${Math.max(1, Math.round(layout.box.lineHeight * previewScale))}px`,
    fontSize: `${Math.max(1, Math.round(layout.box.fontSize * previewScale))}px`,
    width: `${scaledWidth}px`,
    minHeight: `${scaledHeight}px`,
    position: 'absolute',
    boxSizing: 'border-box',
    wordBreak: 'break-word',
    top: `${scaledY}px`,
    left: `${scaledX}px`,
  }

  return {
    ...layout,
    previewScale,
    lines: layout.lines,
    tabLabel: resolution.tabLabel || resolution.key,
    canvasStyle: {
      width: `${imageWidth}px`,
      height: `${imageHeight}px`,
    },
    boxStyle,
  }
}

const watermarkPreviewPanels = computed(() => {
  const tpl = currentWatermarkTemplate.value
  if (!tpl) return []
  return watermarkPreviewResolutions
    .map((resolution) => buildWatermarkPreviewPanel(tpl, resolution, { mode: 'thumb' }))
    .filter(Boolean)
})

const watermarkPreviewDialogPanel = computed(() => {
  const tpl = currentWatermarkTemplate.value
  if (!tpl) return null
  const resolution = watermarkPreviewResolutions.find(
    item => item.key === watermarkPreviewDialogResolutionKey.value,
  ) || watermarkPreviewResolutions[0]
  return buildWatermarkPreviewPanel(tpl, resolution, {
    mode: 'original',
    zoom: watermarkPreviewDialogZoom.value,
  })
})

const watermarkPreviewDialogTitle = computed(() => {
  if (!watermarkPreviewDialogPanel.value) return '水印原始分辨率预览'
  return `水印原始分辨率预览 - ${watermarkPreviewDialogPanel.value.label}`
})

const openWatermarkPreviewDialog = (resolutionKey) => {
  const key = String(resolutionKey || '').trim()
  watermarkPreviewDialogResolutionKey.value = key || activeWatermarkPreviewTab.value || '720'
  watermarkPreviewDialogZoom.value = 'fit'
  watermarkPreviewDialogVisible.value = true
}

watch(
  watermarkPreviewPanels,
  (panels) => {
    if (!panels.length) return
    const exists = panels.some(item => item.key === activeWatermarkPreviewTab.value)
    if (!exists) {
      activeWatermarkPreviewTab.value = panels[0].key
    }
  },
  { immediate: true },
)

const syncWatermarkPreviewViewport = () => {
  if (typeof window === 'undefined') return
  watermarkPreviewViewport.value = {
    width: window.innerWidth,
    height: window.innerHeight,
  }
}

const pickNextTemplateId = (seed = 'tpl') => {
  const base = normalizeTemplateId(seed)
  const existing = new Set((form.value.photo_watermark_templates || []).map(t => String(t.id)))
  if (!existing.has(base)) return base
  for (let i = 1; i <= 9999; i += 1) {
    const candidate = normalizeTemplateId(`${base}_${i}`)
    if (!existing.has(candidate)) return candidate
  }
  return normalizeTemplateId(`tpl_${Date.now()}`)
}

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

function clampInt(value, minValue, maxValue, fallbackValue) {
  const num = Number(value)
  if (!Number.isFinite(num)) return fallbackValue
  return Math.max(minValue, Math.min(maxValue, Math.round(num)))
}

function clampFloat(value, minValue, maxValue, precision, fallbackValue) {
  const num = Number(value)
  if (!Number.isFinite(num)) return fallbackValue
  const clamped = Math.max(minValue, Math.min(maxValue, num))
  if (!Number.isFinite(clamped)) return fallbackValue
  return Number(clamped.toFixed(precision))
}

const formatSimilarityPhashValue = (value) => clampInt(value, 0, 64, 8)

const formatSimilarityVectorValue = (value) => {
  const val = clampFloat(value, 0, 1, 3, 0.975)
  return Number(val).toFixed(3)
}

const openSimilarityThresholdGuide = () => {
  similarityGuideDialogVisible.value = true
}

// 通用整型规则：后端 -> 表单
const fillIntRuleToForm = (formRule, serverRule, roles, defaultValue = 100, minValue = 1, maxValue = 10000) => {
  const safeRule = serverRule || {}
  const perRole = safeRule.per_role || {}
  const perUser = safeRule.per_user || {}
  formRule.default = clampInt(safeRule.default, minValue, maxValue, defaultValue)

  const mappedPerRole = {}
  roles.forEach((role) => {
    if (Object.prototype.hasOwnProperty.call(perRole, role)) {
      mappedPerRole[role] = clampInt(perRole[role], minValue, maxValue, null)
    } else {
      mappedPerRole[role] = null
    }
  })
  formRule.per_role = mappedPerRole

  formRule.per_user = Object.entries(perUser).map(([id, val]) => {
    return {
      user_id: id,
      value: clampInt(val, minValue, maxValue, defaultValue),
    }
  })
}

// 通用整型规则：表单 -> 后端 payload
const buildIntRulePayload = (formRule, fallbackDefault = 100, minValue = 1, maxValue = 10000) => {
  const defaultNum = clampInt(formRule.default, minValue, maxValue, fallbackDefault)

  const payload = {
    default: defaultNum,
    per_role: {},
    per_user: {},
  }

  Object.entries(formRule.per_role || {}).forEach(([role, value]) => {
    if (value === null || value === undefined || value === '') return
    const clamped = clampInt(value, minValue, maxValue, null)
    if (clamped === null) return
    payload.per_role[role] = clamped
  })

  ;(formRule.per_user || []).forEach((rule) => {
    const id = String(rule.user_id || '').trim()
    if (!id) return
    const clamped = clampInt(rule.value, minValue, maxValue, null)
    if (clamped === null) return
    payload.per_user[id] = clamped
  })

  return payload
}

const fillFloatRuleToForm = (
  formRule,
  serverRule,
  roles,
  defaultValue = 0.975,
  minValue = 0,
  maxValue = 1,
  precision = 3,
) => {
  const safeRule = serverRule || {}
  const perRole = safeRule.per_role || {}
  const perUser = safeRule.per_user || {}
  formRule.default = clampFloat(safeRule.default, minValue, maxValue, precision, defaultValue)

  const mappedPerRole = {}
  roles.forEach((role) => {
    if (Object.prototype.hasOwnProperty.call(perRole, role)) {
      mappedPerRole[role] = clampFloat(perRole[role], minValue, maxValue, precision, null)
    } else {
      mappedPerRole[role] = null
    }
  })
  formRule.per_role = mappedPerRole

  formRule.per_user = Object.entries(perUser).map(([id, val]) => ({
    user_id: id,
    value: clampFloat(val, minValue, maxValue, precision, defaultValue),
  }))
}

const buildFloatRulePayload = (
  formRule,
  fallbackDefault = 0.975,
  minValue = 0,
  maxValue = 1,
  precision = 3,
) => {
  const defaultNum = clampFloat(formRule.default, minValue, maxValue, precision, fallbackDefault)

  const payload = {
    default: defaultNum,
    per_role: {},
    per_user: {},
  }

  Object.entries(formRule.per_role || {}).forEach(([role, value]) => {
    if (value === null || value === undefined || value === '') return
    const clamped = clampFloat(value, minValue, maxValue, precision, null)
    if (clamped === null) return
    payload.per_role[role] = clamped
  })

  ;(formRule.per_user || []).forEach((rule) => {
    const id = String(rule.user_id || '').trim()
    if (!id) return
    const clamped = clampFloat(rule.value, minValue, maxValue, precision, null)
    if (clamped === null) return
    payload.per_user[id] = clamped
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
    const duplicatePhotoBlockRule = raw.block_duplicate_check_item_photo_upload || {}
    const similarityAlertRule = raw.enable_check_item_photo_similarity_alert || {}
    const similarityWindowDaysRule = raw.check_item_photo_similarity_window_days || {}
    const similarityPhashThresholdRule = raw.check_item_photo_similarity_phash_threshold || {}
    const similarityVectorThresholdRule = raw.check_item_photo_similarity_vector_threshold || {}
    const legacyScanPickupRule = raw.enable_legacy_scan_pickup || {}
    const locationDistanceCheckRule = raw.enable_photo_location_distance_check || {}
    const distanceBlockUploadRule = raw.distance_exceed_block_upload || {}
    const distanceThresholdRule = raw.photo_location_distance_threshold_m || {}
    const watermarkTemplatesRaw = raw.photo_watermark_templates || {}
    const watermarkTemplateRuleRaw = raw.photo_watermark_template_rule || {}
    const watermarkScenePolicyRaw = raw.photo_watermark_scene_policy || {}

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

    fillBoolRuleToForm(
      form.value.block_duplicate_check_item_photo_upload,
      duplicatePhotoBlockRule,
      roleKeys,
      true,
    )

    fillBoolRuleToForm(
      form.value.enable_check_item_photo_similarity_alert,
      similarityAlertRule,
      roleKeys,
      true,
    )

    fillIntRuleToForm(
      form.value.check_item_photo_similarity_window_days,
      similarityWindowDaysRule,
      roleKeys,
      180,
      1,
      3650,
    )

    fillIntRuleToForm(
      form.value.check_item_photo_similarity_phash_threshold,
      similarityPhashThresholdRule,
      roleKeys,
      8,
      0,
      64,
    )

    fillFloatRuleToForm(
      form.value.check_item_photo_similarity_vector_threshold,
      similarityVectorThresholdRule,
      roleKeys,
      0.975,
      0,
      1,
      3,
    )

    // enable_legacy_scan_pickup：默认关闭（false）
    fillBoolRuleToForm(
      form.value.enable_legacy_scan_pickup,
      legacyScanPickupRule,
      roleKeys,
      false,
    )

    fillBoolRuleToForm(
      form.value.enable_photo_location_distance_check,
      locationDistanceCheckRule,
      roleKeys,
      true,
    )

    fillBoolRuleToForm(
      form.value.distance_exceed_block_upload,
      distanceBlockUploadRule,
      roleKeys,
      false,
    )

    fillIntRuleToForm(
      form.value.photo_location_distance_threshold_m,
      distanceThresholdRule,
      roleKeys,
      100,
      1,
      10000,
    )

    const templateEntries = Object.entries(watermarkTemplatesRaw || {})
    form.value.photo_watermark_templates = templateEntries.length
      ? templateEntries.map(([id, tpl]) => normalizeWatermarkTemplateForForm(id, tpl))
      : [createWatermarkTemplate('default')]

    const templateIdSet = new Set((form.value.photo_watermark_templates || []).map(t => String(t.id)))
    const defaultTemplateIdRaw = String(watermarkTemplateRuleRaw.default || '').trim()
    form.value.photo_watermark_template_rule.default = templateIdSet.has(defaultTemplateIdRaw)
      ? defaultTemplateIdRaw
      : (templateIdSet.has('default')
        ? 'default'
        : String(form.value.photo_watermark_templates[0]?.id || 'default'))

    const templatePerRoleRaw = watermarkTemplateRuleRaw.per_role || {}
    form.value.photo_watermark_template_rule.per_role = roleKeys.reduce((acc, role) => {
      const val = String(templatePerRoleRaw[role] || '').trim()
      acc[role] = val && templateIdSet.has(val) ? val : ''
      return acc
    }, {})

    form.value.photo_watermark_template_rule.per_user = Object.entries(
      watermarkTemplateRuleRaw.per_user || {},
    )
      .map(([uid, templateId]) => ({
        user_id: String(uid || '').trim(),
        template_id: String(templateId || '').trim(),
      }))
      .filter(rule => rule.user_id && templateIdSet.has(rule.template_id))

    form.value.photo_watermark_scene_policy = {
      apply_for_camera: watermarkScenePolicyRaw.apply_for_camera !== false,
      apply_for_album: watermarkScenePolicyRaw.apply_for_album !== false,
      force_local_upload_note_when_geo_disabled:
        watermarkScenePolicyRaw.force_local_upload_note_when_geo_disabled !== false,
    }

    ensureWatermarkTemplateRuleIntegrity()
    selectedWatermarkTemplateId.value = form.value.photo_watermark_template_rule.default

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
      block_duplicate_check_item_photo_upload: {},
      enable_check_item_photo_similarity_alert: {},
      check_item_photo_similarity_window_days: {},
      check_item_photo_similarity_phash_threshold: {},
      check_item_photo_similarity_vector_threshold: {},
      enable_legacy_scan_pickup: {},
      enable_photo_location_distance_check: {},
      distance_exceed_block_upload: {},
      photo_location_distance_threshold_m: {},
      photo_watermark_templates: {},
      photo_watermark_template_rule: {},
      photo_watermark_scene_policy: {},
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

    payload.block_duplicate_check_item_photo_upload = buildBoolRulePayload(
      form.value.block_duplicate_check_item_photo_upload,
    )

    payload.enable_check_item_photo_similarity_alert = buildBoolRulePayload(
      form.value.enable_check_item_photo_similarity_alert,
    )

    payload.check_item_photo_similarity_window_days = buildIntRulePayload(
      form.value.check_item_photo_similarity_window_days,
      180,
      1,
      3650,
    )

    payload.check_item_photo_similarity_phash_threshold = buildIntRulePayload(
      form.value.check_item_photo_similarity_phash_threshold,
      8,
      0,
      64,
    )

    payload.check_item_photo_similarity_vector_threshold = buildFloatRulePayload(
      form.value.check_item_photo_similarity_vector_threshold,
      0.975,
      0,
      1,
      3,
    )

    payload.enable_legacy_scan_pickup = buildBoolRulePayload(
      form.value.enable_legacy_scan_pickup,
    )

    payload.enable_photo_location_distance_check = buildBoolRulePayload(
      form.value.enable_photo_location_distance_check,
    )

    payload.distance_exceed_block_upload = buildBoolRulePayload(
      form.value.distance_exceed_block_upload,
    )

    payload.photo_location_distance_threshold_m = buildIntRulePayload(
      form.value.photo_location_distance_threshold_m,
      100,
      1,
      10000,
    )

    ensureWatermarkTemplateRuleIntegrity()
    const templates = form.value.photo_watermark_templates || []
    const templateMap = {}
    templates.forEach((tpl) => {
      const id = normalizeTemplateId(tpl.id)
      if (!id) return
      templateMap[id] = {
        name: String(tpl.name || '').trim() || '未命名模板',
        version: clampInt(tpl.version, 1, 999999, 1),
        style: {
          position: ['topLeft', 'topRight', 'bottomLeft', 'bottomRight', 'center'].includes(tpl.style?.position)
            ? tpl.style.position
            : 'bottomLeft',
          text_color: /^#([0-9a-fA-F]{6})$/.test(String(tpl.style?.text_color || '').trim())
            ? String(tpl.style.text_color).toUpperCase()
            : '#FF6600',
          background_color: /^#([0-9a-fA-F]{6})$/.test(String(tpl.style?.background_color || '').trim())
            ? String(tpl.style.background_color).toUpperCase()
            : '#000000',
          background_opacity: clampFloat(tpl.style?.background_opacity, 0, 1, 3, 0.7),
          font_size: clampInt(tpl.style?.font_size, 12, 96, 28),
          padding: clampInt(tpl.style?.padding, 0, 120, 15),
          margin: clampInt(tpl.style?.margin, 0, 120, 20),
          line_height: clampInt(tpl.style?.line_height, 16, 140, 35),
          border_radius: clampInt(tpl.style?.border_radius, 0, 80, 8),
          max_width_ratio: clampFloat(tpl.style?.max_width_ratio, 0.3, 1, 3, 0.9),
          area_ratio: clampFloat(tpl.style?.area_ratio, 0.01, 0.4, 3, 0.08),
        },
        content: {
          show_icon: tpl.content?.show_icon !== false,
          show_local_upload_note: tpl.content?.show_local_upload_note !== false,
          show_gps: tpl.content?.show_gps !== false,
          show_accuracy: tpl.content?.show_accuracy !== false,
          show_address: tpl.content?.show_address !== false,
          show_timestamp: tpl.content?.show_timestamp !== false,
          show_inspector: tpl.content?.show_inspector !== false,
          show_check_item: tpl.content?.show_check_item !== false,
          show_site_name: tpl.content?.show_site_name !== false,
          coordinate_precision: clampInt(tpl.content?.coordinate_precision, 2, 8, 6),
          custom_prefix: String(tpl.content?.custom_prefix || '').slice(0, 80),
          custom_suffix: String(tpl.content?.custom_suffix || '').slice(0, 80),
        },
      }
    })

    if (!Object.keys(templateMap).length) {
      const fallback = createWatermarkTemplate('default')
      templateMap.default = {
        name: fallback.name,
        version: fallback.version,
        style: fallback.style,
        content: fallback.content,
      }
    }

    if (!templateMap.default) {
      const firstId = Object.keys(templateMap)[0]
      templateMap.default = {
        ...templateMap[firstId],
        name: templateMap[firstId]?.name || '默认模板',
      }
    }
    payload.photo_watermark_templates = templateMap

    const availableTemplateIds = new Set(Object.keys(templateMap))
    const defaultTemplateId = availableTemplateIds.has(form.value.photo_watermark_template_rule.default)
      ? form.value.photo_watermark_template_rule.default
      : (availableTemplateIds.has('default') ? 'default' : Object.keys(templateMap)[0])
    const templateRulePayload = {
      default: defaultTemplateId,
      per_role: {},
      per_user: {},
    }

    Object.entries(form.value.photo_watermark_template_rule.per_role || {}).forEach(([role, templateId]) => {
      const tid = String(templateId || '').trim()
      if (tid && availableTemplateIds.has(tid)) {
        templateRulePayload.per_role[role] = tid
      }
    })

    ;(form.value.photo_watermark_template_rule.per_user || []).forEach((rule) => {
      const uid = String(rule.user_id || '').trim()
      const tid = String(rule.template_id || '').trim()
      if (!uid || !tid) return
      if (!availableTemplateIds.has(tid)) return
      templateRulePayload.per_user[uid] = tid
    })
    payload.photo_watermark_template_rule = templateRulePayload

    payload.photo_watermark_scene_policy = {
      apply_for_camera: form.value.photo_watermark_scene_policy.apply_for_camera !== false,
      apply_for_album: form.value.photo_watermark_scene_policy.apply_for_album !== false,
      force_local_upload_note_when_geo_disabled:
        form.value.photo_watermark_scene_policy.force_local_upload_note_when_geo_disabled !== false,
    }

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
  syncWatermarkPreviewViewport()
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', syncWatermarkPreviewViewport)
  }
  loadConfig()
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', syncWatermarkPreviewViewport)
  }
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

const addDuplicatePhotoBlockUserRule = () => {
  const id = String(newDuplicatePhotoBlockUserRule.value.user_id || '').trim()
  const flag = newDuplicatePhotoBlockUserRule.value.flag
  if (!id) {
    ElMessage.warning('请选择用户')
    return
  }
  if (flag !== 'allow' && flag !== 'deny') {
    ElMessage.warning('请选择重复图片策略')
    return
  }
  const exists = form.value.block_duplicate_check_item_photo_upload.per_user.some(
    (r) => String(r.user_id) === id,
  )
  if (exists) {
    ElMessage.warning('该用户已存在重复图片策略')
    return
  }
  form.value.block_duplicate_check_item_photo_upload.per_user.push({
    user_id: id,
    flag,
  })
  newDuplicatePhotoBlockUserRule.value.user_id = ''
  newDuplicatePhotoBlockUserRule.value.flag = 'allow'
}

const removeDuplicatePhotoBlockUserRule = (index) => {
  form.value.block_duplicate_check_item_photo_upload.per_user.splice(index, 1)
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

const addLocationDistanceCheckUserRule = () => {
  const id = String(newLocationDistanceCheckUserRule.value.user_id || '').trim()
  const flag = newLocationDistanceCheckUserRule.value.flag
  if (!id) {
    ElMessage.warning('请选择用户')
    return
  }
  if (flag !== 'allow' && flag !== 'deny') {
    ElMessage.warning('请选择比对开关策略')
    return
  }
  const exists = form.value.enable_photo_location_distance_check.per_user.some(
    (r) => String(r.user_id) === id,
  )
  if (exists) {
    ElMessage.warning('该用户已存在距离比对策略')
    return
  }
  form.value.enable_photo_location_distance_check.per_user.push({
    user_id: id,
    flag,
  })
  newLocationDistanceCheckUserRule.value.user_id = ''
  newLocationDistanceCheckUserRule.value.flag = 'allow'
}

const removeLocationDistanceCheckUserRule = (index) => {
  form.value.enable_photo_location_distance_check.per_user.splice(index, 1)
}

const addDistanceBlockUploadUserRule = () => {
  const id = String(newDistanceBlockUploadUserRule.value.user_id || '').trim()
  const flag = newDistanceBlockUploadUserRule.value.flag
  if (!id) {
    ElMessage.warning('请选择用户')
    return
  }
  if (flag !== 'allow' && flag !== 'deny') {
    ElMessage.warning('请选择超限阻断策略')
    return
  }
  const exists = form.value.distance_exceed_block_upload.per_user.some(
    (r) => String(r.user_id) === id,
  )
  if (exists) {
    ElMessage.warning('该用户已存在超限阻断策略')
    return
  }
  form.value.distance_exceed_block_upload.per_user.push({
    user_id: id,
    flag,
  })
  newDistanceBlockUploadUserRule.value.user_id = ''
  newDistanceBlockUploadUserRule.value.flag = 'deny'
}

const removeDistanceBlockUploadUserRule = (index) => {
  form.value.distance_exceed_block_upload.per_user.splice(index, 1)
}

const addDistanceThresholdUserRule = () => {
  const id = String(newDistanceThresholdUserRule.value.user_id || '').trim()
  const value = Number(newDistanceThresholdUserRule.value.value)
  if (!id) {
    ElMessage.warning('请选择用户')
    return
  }
  if (!Number.isFinite(value) || value < 1 || value > 10000) {
    ElMessage.warning('请输入 1-10000 之间的米数阈值')
    return
  }
  const exists = form.value.photo_location_distance_threshold_m.per_user.some(
    (r) => String(r.user_id) === id,
  )
  if (exists) {
    ElMessage.warning('该用户已存在阈值策略')
    return
  }
  form.value.photo_location_distance_threshold_m.per_user.push({
    user_id: id,
    value: Math.round(value),
  })
  newDistanceThresholdUserRule.value.user_id = ''
  newDistanceThresholdUserRule.value.value = 100
}

const removeDistanceThresholdUserRule = (index) => {
  form.value.photo_location_distance_threshold_m.per_user.splice(index, 1)
}

const selectWatermarkTemplate = (templateId) => {
  selectedWatermarkTemplateId.value = String(templateId || '').trim()
}

const addWatermarkTemplate = () => {
  const id = pickNextTemplateId('tpl')
  form.value.photo_watermark_templates.push(createWatermarkTemplate(id))
  selectedWatermarkTemplateId.value = id
  ensureWatermarkTemplateRuleIntegrity()
}

const copyCurrentWatermarkTemplate = () => {
  const current = currentWatermarkTemplate.value
  if (!current) {
    ElMessage.warning('请先选择一个模板')
    return
  }
  const id = pickNextTemplateId(`${current.id}_copy`)
  const copied = normalizeWatermarkTemplateForForm(id, {
    ...current,
    name: `${current.name}-副本`,
  })
  form.value.photo_watermark_templates.push(copied)
  selectedWatermarkTemplateId.value = id
  ensureWatermarkTemplateRuleIntegrity()
}

const removeCurrentWatermarkTemplate = () => {
  const current = currentWatermarkTemplate.value
  if (!current) {
    ElMessage.warning('请先选择一个模板')
    return
  }
  if ((form.value.photo_watermark_templates || []).length <= 1) {
    ElMessage.warning('至少保留一个模板')
    return
  }
  form.value.photo_watermark_templates = (form.value.photo_watermark_templates || []).filter(
    (tpl) => String(tpl.id) !== String(current.id),
  )
  ensureWatermarkTemplateRuleIntegrity()
}

const setDefaultWatermarkTemplate = (templateId) => {
  const id = String(templateId || '').trim()
  if (!id) return
  form.value.photo_watermark_template_rule.default = id
  ensureWatermarkTemplateRuleIntegrity()
}

const addWatermarkTemplateUserRule = () => {
  const id = String(newWatermarkTemplateUserRule.value.user_id || '').trim()
  const templateId = String(newWatermarkTemplateUserRule.value.template_id || '').trim()
  if (!id) {
    ElMessage.warning('请选择用户')
    return
  }
  if (!templateId) {
    ElMessage.warning('请选择模板')
    return
  }
  const exists = (form.value.photo_watermark_template_rule.per_user || []).some(
    (r) => String(r.user_id) === id,
  )
  if (exists) {
    ElMessage.warning('该用户已存在模板覆盖规则')
    return
  }
  form.value.photo_watermark_template_rule.per_user.push({
    user_id: id,
    template_id: templateId,
  })
  newWatermarkTemplateUserRule.value.user_id = ''
  newWatermarkTemplateUserRule.value.template_id = form.value.photo_watermark_template_rule.default || 'default'
}

const removeWatermarkTemplateUserRule = (index) => {
  form.value.photo_watermark_template_rule.per_user.splice(index, 1)
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

.mt12 {
  margin-top: 12px;
}

.user-rules {
  width: 100%;
}

.user-rule-form {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
}

.similarity-guide__human {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 12px 14px;
  background: #fcfcfd;
}

.similarity-guide__title {
  font-weight: 600;
  color: #303133;
  margin-bottom: 6px;
}

.watermark-scene-policy {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
}

.watermark-template-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
}

.watermark-template-detail {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 16px;
  align-items: start;
}

.watermark-content-switches {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
}

.watermark-preview {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 10px;
  background: #fff;
}

.watermark-preview__title {
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
}

.watermark-preview-tabs :deep(.el-tabs__header) {
  margin-bottom: 8px;
}

.watermark-preview-tabs :deep(.el-tabs__nav) {
  width: 100%;
}

.watermark-preview-tabs :deep(.el-tabs__item) {
  flex: 1 1 0;
  min-width: 0;
  padding: 0 8px;
  text-align: center;
}

.watermark-preview__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.watermark-preview__panel {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 8px;
  background: #fafbfd;
  display: inline-block;
}

.watermark-preview__panel-title {
  font-size: 12px;
  color: #606266;
  margin-bottom: 6px;
}

.watermark-preview__canvas {
  position: relative;
  border-radius: 8px;
  background: linear-gradient(135deg, #f7f8fb 0%, #e9edf5 100%);
  overflow: hidden;
}

.watermark-preview__box {
  box-sizing: border-box;
  word-break: break-word;
}

.watermark-preview-dialog__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.watermark-preview-dialog__zoom {
  display: flex;
  align-items: center;
  gap: 8px;
}

.watermark-preview-dialog__viewport {
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  max-height: 70vh;
  overflow: auto;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 10px;
  background: #f5f7fa;
}

.watermark-preview-dialog__canvas {
  flex-shrink: 0;
  margin: 0;
  border: 1px solid #d4d7de;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

@media (max-width: 1200px) {
  .watermark-template-detail {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 860px) {
  .watermark-preview__actions {
    flex-direction: column;
    align-items: flex-start;
  }
  .watermark-preview-dialog__toolbar {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
