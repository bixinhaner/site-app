<template>
  <div class="page">
    <div class="page-header">
      <h1>站点规划（LLD）</h1>
      <div class="header-actions">
        <el-tooltip
          v-if="planning"
          :content="editPolicyReason"
          placement="top"
          :disabled="canEdit"
        >
          <span>
            <el-button
              :disabled="!canEdit"
              @click="toggleEditMode"
              :type="editMode ? 'warning' : (editPolicyMode === 'limited' ? 'info' : 'primary')"
            >
              <el-icon><Edit v-if="!editMode" /><Check v-else /></el-icon>
              {{ editMode ? '退出编辑' : (editPolicyMode === 'limited' ? '手动编辑（受限）' : '手动编辑') }}
            </el-button>
          </span>
        </el-tooltip>
        <el-button v-if="editMode && hasChanges" @click="saveChanges" type="success" :loading="saving">
          <el-icon><DocumentCopy /></el-icon>保存更改
        </el-button>
        <el-button v-if="editMode" @click="cancelEdit" type="info">
          <el-icon><Close /></el-icon>取消编辑
        </el-button>
        <el-button @click="goBack"><el-icon><Back /></el-icon>返回</el-button>
      </div>
    </div>

    <el-card class="mb16" v-loading="loading">
      <div class="meta-row">
        <el-tag type="info">Site ID: {{ siteId }}</el-tag>
        <el-tag v-if="site" type="success">站点: {{ site.site_code }} / {{ site.site_name }}</el-tag>
        <el-tag v-if="planning" type="warning">当前版本: v{{ planning.version }}</el-tag>
        <el-tooltip
          v-if="editPolicy"
          :content="editPolicy.reason || ''"
          placement="top"
          :disabled="!editPolicy.reason"
        >
          <el-tag :type="editPolicyMode === 'full' ? 'success' : editPolicyMode === 'limited' ? 'warning' : 'info'">
            {{ editPolicyMode === 'full' ? '可编辑' : editPolicyMode === 'limited' ? '受限编辑' : '只读' }}
          </el-tag>
        </el-tooltip>
      </div>
      <div class="meta-row" v-if="summary">
        <el-tag type="info">Bands: {{ summary.bands && summary.bands.length ? summary.bands.join(', ') : '-' }}</el-tag>
        <el-tag type="success">扇区数: {{ summary.sector_count }}</el-tag>
        <el-tag type="primary">4G Cells: {{ summary.lte_cell_count }}</el-tag>
        <el-tag type="primary">5G Cells: {{ summary.nr_cell_count }}</el-tag>
      </div>
      <div class="meta-row" v-if="summary">
        <span>机械下倾范围: {{
          summary.mechanical_downtilt_min !== null && summary.mechanical_downtilt_min !== undefined
            ? `${summary.mechanical_downtilt_min}° ~ ${summary.mechanical_downtilt_max}°`
            : '-'
        }}</span>
        <span>电子下倾范围: {{
          summary.electrical_downtilt_min !== null && summary.electrical_downtilt_min !== undefined
            ? `${summary.electrical_downtilt_min}° ~ ${summary.electrical_downtilt_max}°`
            : '-'
        }}</span>
      </div>
    </el-card>

    <el-card class="mb16">
      <div class="import-row">
        <el-button @click="downloadLldTemplate">
          <el-icon><Download /></el-icon>下载 LLD 模板
        </el-button>
        <el-switch v-model="dryRun" active-text="试运行(dry run)" :disabled="!canImport" />
        <el-upload
          :show-file-list="false"
          :before-upload="onBeforeUpload"
          :http-request="onUploadLld"
        >
          <el-button type="success" :loading="importing" :disabled="!canImport">
            <el-icon><Upload /></el-icon>{{ dryRun ? '试运行导入' : '导入并保存' }}
          </el-button>
        </el-upload>
        <span v-if="importInfo" class="import-info">{{ importInfo }}</span>
      </div>
    </el-card>

    <el-card>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="概要" name="overview">
          <el-descriptions title="规划概要" :column="2" border v-if="planning && summary">
            <el-descriptions-item label="Bands">
              {{ summary.bands && summary.bands.length ? summary.bands.join(', ') : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="扇区数">
              {{ summary.sector_count }}
            </el-descriptions-item>
            <el-descriptions-item label="4G Cell 数量">
              {{ summary.lte_cell_count }}
            </el-descriptions-item>
            <el-descriptions-item label="5G Cell 数量">
              {{ summary.nr_cell_count }}
            </el-descriptions-item>
            <el-descriptions-item label="机械下倾范围">
              {{
                summary.mechanical_downtilt_min !== null && summary.mechanical_downtilt_min !== undefined
                  ? `${summary.mechanical_downtilt_min}° ~ ${summary.mechanical_downtilt_max}°`
                  : '-'
              }}
            </el-descriptions-item>
            <el-descriptions-item label="电子下倾范围">
              {{
                summary.electrical_downtilt_min !== null && summary.electrical_downtilt_min !== undefined
                  ? `${summary.electrical_downtilt_min}° ~ ${summary.electrical_downtilt_max}°`
                  : '-'
              }}
            </el-descriptions-item>
          </el-descriptions>
          <el-empty v-else description="尚未导入 LLD 规划" />
        </el-tab-pane>

        <el-tab-pane label="4G Cell 列表" name="lte">
          <div class="filter-row">
            <el-select v-model="lteBandFilter" clearable placeholder="按 Band 过滤" style="width: 180px">
              <el-option v-for="b in bandOptions" :key="b" :label="b" :value="b" />
            </el-select>
            <el-input
              v-model="ltePciFilter"
              placeholder="按 PCI 过滤"
              style="width: 160px"
              clearable
            />
            <el-input
              v-model="lteKeyword"
              placeholder="按 TOWER ID / CELL NAME 搜索"
              style="width: 260px"
              clearable
            />
          </div>
          <el-table :data="filteredLteCells" border size="small" height="520">
            <el-table-column type="expand">
              <template #default="{ row }">
                <div class="expand-groups">
                  <div class="expand-group">
                    <div class="group-title">基本信息</div>
                    <div class="group-grid">
                      <div class="field-item"><span class="field-label">RAT</span><span class="field-value">{{ row.rat || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">BandCode</span><span class="field-value">{{ row.band_code || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Sheet</span><span class="field-value">{{ row.sheet_name || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">TOWER ID</span><span class="field-value">{{ row.tower_id || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">SiteCode</span><span class="field-value">{{ row.site_information || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">SITE NAME</span><span class="field-value">{{ row.site_name || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">TOWER NAME</span><span class="field-value">{{ row.tower_name || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Town</span><span class="field-value">{{ row.town || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Region</span><span class="field-value">{{ row.region || '-' }}</span></div>
                    </div>
                  </div>
                  <div class="expand-group">
                    <div class="group-title">小区标识</div>
                    <div class="group-grid">
                      <div class="field-item"><span class="field-label">LOCAL CELL ID</span><span class="field-value">{{ row.local_cell_id ?? '-' }}</span></div>
                      <div class="field-item"><span class="field-label">CELL NAME</span><span class="field-value">{{ row.cell_name || '-' }}</span></div>
                    </div>
                  </div>
                  <div class="expand-group">
                    <div class="group-title">无线参数</div>
                    <div class="group-grid">
                      <div class="field-item"><span class="field-label">PLMN</span><span class="field-value">{{ row.plmn || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">TAC</span><span class="field-value">{{ row.tac || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">PCI</span><span class="field-value">{{ row.pci ?? '-' }}</span></div>
                      <div class="field-item"><span class="field-label">ZC Root Index</span><span class="field-value">{{ row.zc_root_index ?? '-' }}</span></div>
                      <div class="field-item"><span class="field-label">功率(dBm)</span><span class="field-value">{{ row.power_dbm ?? '-' }}</span></div>
                      <div class="field-item"><span class="field-label">PA</span><span class="field-value">{{ row.pa || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">PB</span><span class="field-value">{{ row.pb || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">BAND(原始)</span><span class="field-value">{{ row.band_in_file || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">EARFCN</span><span class="field-value">{{ row.frequency ?? '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Bandwidth</span><span class="field-value">{{ row.bandwidth || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">机械下倾</span><span class="field-value">{{ row.mechanical_downtilt_deg ?? '-' }}</span></div>
                      <div class="field-item"><span class="field-label">电子下倾</span><span class="field-value">{{ row.electrical_downtilt_deg ?? '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Azimuth</span><span class="field-value">{{ row.azimuth_deg ?? '-' }}</span></div>
                      <div class="field-item"><span class="field-label">经度</span><span class="field-value">{{ row.longitude ?? '-' }}</span></div>
                      <div class="field-item"><span class="field-label">纬度</span><span class="field-value">{{ row.latitude ?? '-' }}</span></div>
                      <div class="field-item"><span class="field-label">塔高</span><span class="field-value">{{ row.tower_height ?? '-' }}</span></div>
                      <div class="field-item"><span class="field-label">天线高</span><span class="field-value">{{ row.antenna_height ?? '-' }}</span></div>
                      <div class="field-item"><span class="field-label">塔商</span><span class="field-value">{{ row.tower_merchants || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Band Combination</span><span class="field-value">{{ row.band_combination || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">天线端口</span><span class="field-value">{{ row.antenna_ports ?? '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Cell Allocation</span><span class="field-value">{{ row.cell_allocation || '-' }}</span></div>
                    </div>
                  </div>
                  <div class="expand-group">
                    <div class="group-title">覆盖与评估</div>
                    <div class="group-grid">
                      <div class="field-item"><span class="field-label">Cover Type</span><span class="field-value">{{ row.cover_type || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">覆盖区域</span><span class="field-value">{{ row.coverage_area || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">区域权重</span><span class="field-value">{{ row.coverage_weight || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">覆盖场景</span><span class="field-value">{{ row.scenario || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">场景权重</span><span class="field-value">{{ row.scenario_weight || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">综合权重</span><span class="field-value">{{ row.weight || '-' }}</span></div>
                    </div>
                  </div>
                      <div class="expand-group">
                        <div class="group-title">5G 核心网（NR 时有意义）</div>
                        <div class="group-grid">
                      <div class="field-item"><span class="field-label">gNB ID</span><span class="field-value">{{ row.gnb_id ?? '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Gnb length</span><span class="field-value">{{ row.gnb_length ?? '-' }}</span></div>
                      <div class="field-item"><span class="field-label">NCI</span><span class="field-value">{{ row.nci ?? '-' }}</span></div>
                      <div class="field-item"><span class="field-label">gNB WAN IP</span><span class="field-value">{{ row.gnb_wan_ip || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">MASTER 5GC IP1</span><span class="field-value">{{ row.master_5gc_ip1 || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">MASTER 5GC IP2</span><span class="field-value">{{ row.master_5gc_ip2 || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">MASTER 5GC IP3</span><span class="field-value">{{ row.master_5gc_ip3 || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">BACKUP 5GC IP1</span><span class="field-value">{{ row.backup_5gc_ip1 || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">BACKUP 5GC IP2</span><span class="field-value">{{ row.backup_5gc_ip2 || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">BACKUP 5GC IP3</span><span class="field-value">{{ row.backup_5gc_ip3 || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">MASTER OMC IP</span><span class="field-value">{{ row.master_omc_ip || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">BACKUP OMC IP</span><span class="field-value">{{ row.backup_omc_ip || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">NTP IP1</span><span class="field-value">{{ row.ntp_ip1 || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">NTP IP2</span><span class="field-value">{{ row.ntp_ip2 || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Kssb</span><span class="field-value">{{ row.kssb ?? '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Offset to PointA</span><span class="field-value">{{ row.offset_to_point_a || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Slot config</span><span class="field-value">{{ row.slot_config || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Slot DL/UL</span><span class="field-value">{{ row.slot_config_dl_ul || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Symbol DL/UL</span><span class="field-value">{{ row.symbol_config_dl_ul || '-' }}</span></div>
                    </div>
                  </div>
                  <div class="expand-group">
                    <div class="group-title">LLD 模板扩展字段</div>
                    <div class="group-grid">
                      <div class="field-item"><span class="field-label">Index</span><span class="field-value">{{ row.excel_index || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Province Region</span><span class="field-value">{{ row.province_region || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Province</span><span class="field-value">{{ row.province || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">City</span><span class="field-value">{{ row.city || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">County</span><span class="field-value">{{ row.county || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Address</span><span class="field-value">{{ row.address || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Cluster</span><span class="field-value">{{ row.cluster || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">SN</span><span class="field-value">{{ row.sn || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Work Mode</span><span class="field-value">{{ row.work_mode || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Duplex Mode</span><span class="field-value">{{ row.duplex_mode || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">MIMO</span><span class="field-value">{{ row.mimo || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Cell ID</span><span class="field-value">{{ row.cell_id_in_file || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">SA</span><span class="field-value">{{ row.sa || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">SSP</span><span class="field-value">{{ row.ssp || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Total Tilt</span><span class="field-value">{{ row.total_tilt || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Antenna Model</span><span class="field-value">{{ row.antenna_model || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Antenna Gain</span><span class="field-value">{{ row.antenna_gain || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">RET</span><span class="field-value">{{ row.ret || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Transmission Port</span><span class="field-value">{{ row.transmission_port || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Type</span><span class="field-value">{{ row.lld_type || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">DL Bandwidth</span><span class="field-value">{{ row.dl_bandwidth || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">UL Bandwidth</span><span class="field-value">{{ row.ul_bandwidth || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">SSB Absolute Freq</span><span class="field-value">{{ row.ssb_absolute_freq || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">DL SubCarrierSpacing</span><span class="field-value">{{ row.dl_subcarrier_spacing || '-' }}</span></div>
                    </div>
                  </div>
                  <div class="expand-group">
                    <div class="group-title">OAM / Control / User Plane</div>
                    <div class="group-grid">
                      <div class="field-item"><span class="field-label">OAM IP Type</span><span class="field-value">{{ row.oam_ip_type || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">OAM IP Address</span><span class="field-value">{{ row.oam_ip_address || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">OAM IP Submask</span><span class="field-value">{{ row.oam_ip_submask || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">OAM IP Gateway</span><span class="field-value">{{ row.oam_ip_gateway || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">OAM IP VLAN</span><span class="field-value">{{ row.oam_ip_vlan || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">OAM IP DNS</span><span class="field-value">{{ row.oam_ip_dns || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">OAM Binding Port</span><span class="field-value">{{ row.oam_binding_port || '-' }}</span></div>

                      <div class="field-item"><span class="field-label">Control Plane IP Type</span><span class="field-value">{{ row.control_plane_ip_type || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Control Plane Address</span><span class="field-value">{{ row.control_plane_address || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Control Plane Submask</span><span class="field-value">{{ row.control_plane_submask || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Control Plane Gateway</span><span class="field-value">{{ row.control_plane_gateway || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Control Plane VLAN</span><span class="field-value">{{ row.control_plane_vlan || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Control Plane DNS</span><span class="field-value">{{ row.control_plane_dns || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">Control Plane Binding Port</span><span class="field-value">{{ row.control_plane_binding_port || '-' }}</span></div>

                      <div class="field-item"><span class="field-label">User Plane IP Type</span><span class="field-value">{{ row.user_plane_ip_type || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">User Plane Address</span><span class="field-value">{{ row.user_plane_address || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">User Plane Submask</span><span class="field-value">{{ row.user_plane_submask || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">User Plane Gateway</span><span class="field-value">{{ row.user_plane_gateway || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">User Plane VLAN</span><span class="field-value">{{ row.user_plane_vlan || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">User Plane DNS</span><span class="field-value">{{ row.user_plane_dns || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">User Plane Binding Port</span><span class="field-value">{{ row.user_plane_binding_port || '-' }}</span></div>
                    </div>
                  </div>
                  <div class="expand-group">
                    <div class="group-title">X2 / MME（LTE 时有意义）</div>
                    <div class="group-grid">
                      <div class="field-item"><span class="field-label">X2 IP Type</span><span class="field-value">{{ row.x2_ip_type || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">X2 Address</span><span class="field-value">{{ row.x2_address || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">X2 Submask</span><span class="field-value">{{ row.x2_submask || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">X2 Gateway</span><span class="field-value">{{ row.x2_gateway || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">X2 VLAN</span><span class="field-value">{{ row.x2_vlan || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">X2 DNS</span><span class="field-value">{{ row.x2_dns || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">X2 Binding Port</span><span class="field-value">{{ row.x2_binding_port || '-' }}</span></div>

                      <div class="field-item"><span class="field-label">MME IP 1</span><span class="field-value">{{ row.mme_ip_1 || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">MME IP 2</span><span class="field-value">{{ row.mme_ip_2 || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">MME IP 3</span><span class="field-value">{{ row.mme_ip_3 || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">MME IP 4</span><span class="field-value">{{ row.mme_ip_4 || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">MME IP 5</span><span class="field-value">{{ row.mme_ip_5 || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">MME IP 6</span><span class="field-value">{{ row.mme_ip_6 || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">MME IP 7</span><span class="field-value">{{ row.mme_ip_7 || '-' }}</span></div>
                      <div class="field-item"><span class="field-label">MME IP 8</span><span class="field-value">{{ row.mme_ip_8 || '-' }}</span></div>
                    </div>
                  </div>
                  <div class="expand-group">
                    <div class="group-title">其它</div>
                    <div class="group-grid">
                      <div class="field-item"><span class="field-label">备注</span><span class="field-value">{{ row.remark || '-' }}</span></div>
                    </div>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="tower_id" label="TOWER ID" width="160" />
            <el-table-column prop="local_cell_id" label="LOCAL CELL ID" width="120" />
            <el-table-column prop="cell_name" label="CELL NAME" min-width="220" />
            <el-table-column prop="band_code" label="Band" width="80" />
            <el-table-column prop="enb_id" label="ENB ID" width="100" />
            <el-table-column prop="eci" label="ECI" width="140" />
            <el-table-column prop="pci" label="PCI" width="80" />
            <el-table-column prop="frequency" label="EARFCN" width="100" />
            <el-table-column prop="bandwidth" label="Bandwidth" width="110" />
            <el-table-column prop="mechanical_downtilt_deg" label="机械下倾(°)" width="110" />
            <el-table-column prop="electrical_downtilt_deg" label="电子下倾(°)" width="110" />
            <el-table-column prop="azimuth_deg" label="Azimuth(°)" width="110" />
            <el-table-column prop="longitude" label="经度" width="120" />
            <el-table-column prop="latitude" label="纬度" width="120" />
            <el-table-column prop="tower_height" label="塔高" width="80" />
            <el-table-column prop="antenna_height" label="天线高" width="80" />
            <el-table-column prop="cover_type" label="Cover Type" width="140" />
            <el-table-column prop="region" label="Region" width="120" />
            <el-table-column prop="scenario" label="场景" width="120" />
            <el-table-column v-if="editMode" label="操作" width="180" fixed="right">
              <template #default="{ row, $index }">
                <el-button size="small" @click="editCell(row)">编辑</el-button>
                <template v-if="canDeleteCell">
                  <el-button size="small" type="danger" @click="deleteCell(row)">删除</el-button>
                </template>
                <template v-else>
                  <el-tooltip content="受限编辑：禁止删除 Cell" placement="top">
                    <span>
                      <el-button size="small" type="danger" disabled>删除</el-button>
                    </span>
                  </el-tooltip>
                </template>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="5G Cell 列表" name="nr">
          <div class="filter-row">
            <el-select v-model="nrBandFilter" clearable placeholder="按 Band 过滤" style="width: 180px">
              <el-option v-for="b in bandOptions" :key="b" :label="b" :value="b" />
            </el-select>
            <el-input
              v-model="nrNciFilter"
              placeholder="按 NCI 过滤"
              style="width: 180px"
              clearable
            />
            <el-input
              v-model="nrKeyword"
              placeholder="按 TOWER ID / CELL NAME 搜索"
              style="width: 260px"
              clearable
            />
          </div>
          <el-tabs v-model="nrViewMode" class="inner-tabs">
            <el-tab-pane label="简表" name="basic">
              <el-table :data="filteredNrCells" border size="small" height="520">
                <el-table-column type="expand">
                  <template #default="{ row }">
                    <div class="expand-groups">
                      <div class="expand-group">
                        <div class="group-title">基本信息</div>
                        <div class="group-grid">
                          <div class="field-item"><span class="field-label">RAT</span><span class="field-value">{{ row.rat || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">BandCode</span><span class="field-value">{{ row.band_code || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Sheet</span><span class="field-value">{{ row.sheet_name || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">TOWER ID</span><span class="field-value">{{ row.tower_id || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">SiteCode</span><span class="field-value">{{ row.site_information || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">SITE NAME</span><span class="field-value">{{ row.site_name || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">TOWER NAME</span><span class="field-value">{{ row.tower_name || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Town</span><span class="field-value">{{ row.town || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Region</span><span class="field-value">{{ row.region || '-' }}</span></div>
                        </div>
                      </div>
                      <div class="expand-group">
                        <div class="group-title">小区标识</div>
                        <div class="group-grid">
                          <div class="field-item"><span class="field-label">LOCAL CELL ID</span><span class="field-value">{{ row.local_cell_id ?? '-' }}</span></div>
                          <div class="field-item"><span class="field-label">CELL NAME</span><span class="field-value">{{ row.cell_name || '-' }}</span></div>
                        </div>
                      </div>
                      <div class="expand-group">
                        <div class="group-title">无线参数</div>
                        <div class="group-grid">
                          <div class="field-item"><span class="field-label">PLMN</span><span class="field-value">{{ row.plmn || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">TAC</span><span class="field-value">{{ row.tac || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">PCI</span><span class="field-value">{{ row.pci ?? '-' }}</span></div>
                          <div class="field-item"><span class="field-label">ZC Root Index</span><span class="field-value">{{ row.zc_root_index ?? '-' }}</span></div>
                          <div class="field-item"><span class="field-label">功率(dBm)</span><span class="field-value">{{ row.power_dbm ?? '-' }}</span></div>
                          <div class="field-item"><span class="field-label">PA</span><span class="field-value">{{ row.pa || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">PB</span><span class="field-value">{{ row.pb || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">BAND(原始)</span><span class="field-value">{{ row.band_in_file || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">EARFCN</span><span class="field-value">{{ row.frequency ?? '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Bandwidth</span><span class="field-value">{{ row.bandwidth || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">机械下倾</span><span class="field-value">{{ row.mechanical_downtilt_deg ?? '-' }}</span></div>
                          <div class="field-item"><span class="field-label">电子下倾</span><span class="field-value">{{ row.electrical_downtilt_deg ?? '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Azimuth</span><span class="field-value">{{ row.azimuth_deg ?? '-' }}</span></div>
                          <div class="field-item"><span class="field-label">经度</span><span class="field-value">{{ row.longitude ?? '-' }}</span></div>
                          <div class="field-item"><span class="field-label">纬度</span><span class="field-value">{{ row.latitude ?? '-' }}</span></div>
                          <div class="field-item"><span class="field-label">塔高</span><span class="field-value">{{ row.tower_height ?? '-' }}</span></div>
                          <div class="field-item"><span class="field-label">天线高</span><span class="field-value">{{ row.antenna_height ?? '-' }}</span></div>
                          <div class="field-item"><span class="field-label">塔商</span><span class="field-value">{{ row.tower_merchants || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Band Combination</span><span class="field-value">{{ row.band_combination || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">天线端口</span><span class="field-value">{{ row.antenna_ports ?? '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Cell Allocation</span><span class="field-value">{{ row.cell_allocation || '-' }}</span></div>
                        </div>
                      </div>
                      <div class="expand-group">
                        <div class="group-title">覆盖与评估</div>
                        <div class="group-grid">
                          <div class="field-item"><span class="field-label">Cover Type</span><span class="field-value">{{ row.cover_type || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">覆盖区域</span><span class="field-value">{{ row.coverage_area || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">区域权重</span><span class="field-value">{{ row.coverage_weight || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">覆盖场景</span><span class="field-value">{{ row.scenario || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">场景权重</span><span class="field-value">{{ row.scenario_weight || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">综合权重</span><span class="field-value">{{ row.weight || '-' }}</span></div>
                        </div>
                      </div>
                      <div class="expand-group">
                        <div class="group-title">5G 核心网</div>
                        <div class="group-grid">
                          <div class="field-item"><span class="field-label">gNB ID</span><span class="field-value">{{ row.gnb_id ?? '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Gnb length</span><span class="field-value">{{ row.gnb_length ?? '-' }}</span></div>
                          <div class="field-item"><span class="field-label">NCI</span><span class="field-value">{{ row.nci ?? '-' }}</span></div>
                          <div class="field-item"><span class="field-label">gNB WAN IP</span><span class="field-value">{{ row.gnb_wan_ip || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">MASTER 5GC IP1</span><span class="field-value">{{ row.master_5gc_ip1 || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">MASTER 5GC IP2</span><span class="field-value">{{ row.master_5gc_ip2 || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">MASTER 5GC IP3</span><span class="field-value">{{ row.master_5gc_ip3 || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">BACKUP 5GC IP1</span><span class="field-value">{{ row.backup_5gc_ip1 || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">BACKUP 5GC IP2</span><span class="field-value">{{ row.backup_5gc_ip2 || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">BACKUP 5GC IP3</span><span class="field-value">{{ row.backup_5gc_ip3 || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">MASTER OMC IP</span><span class="field-value">{{ row.master_omc_ip || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">BACKUP OMC IP</span><span class="field-value">{{ row.backup_omc_ip || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">NTP IP1</span><span class="field-value">{{ row.ntp_ip1 || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">NTP IP2</span><span class="field-value">{{ row.ntp_ip2 || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Kssb</span><span class="field-value">{{ row.kssb ?? '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Offset to PointA</span><span class="field-value">{{ row.offset_to_point_a || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Slot config</span><span class="field-value">{{ row.slot_config || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Slot DL/UL</span><span class="field-value">{{ row.slot_config_dl_ul || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Symbol DL/UL</span><span class="field-value">{{ row.symbol_config_dl_ul || '-' }}</span></div>
                        </div>
                      </div>
                      <div class="expand-group">
                        <div class="group-title">LLD 模板扩展字段</div>
                        <div class="group-grid">
                          <div class="field-item"><span class="field-label">Index</span><span class="field-value">{{ row.excel_index || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Province Region</span><span class="field-value">{{ row.province_region || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Province</span><span class="field-value">{{ row.province || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">City</span><span class="field-value">{{ row.city || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">County</span><span class="field-value">{{ row.county || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Address</span><span class="field-value">{{ row.address || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Cluster</span><span class="field-value">{{ row.cluster || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">SN</span><span class="field-value">{{ row.sn || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Work Mode</span><span class="field-value">{{ row.work_mode || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Duplex Mode</span><span class="field-value">{{ row.duplex_mode || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">MIMO</span><span class="field-value">{{ row.mimo || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Cell ID</span><span class="field-value">{{ row.cell_id_in_file || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">SA</span><span class="field-value">{{ row.sa || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">SSP</span><span class="field-value">{{ row.ssp || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Total Tilt</span><span class="field-value">{{ row.total_tilt || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Antenna Model</span><span class="field-value">{{ row.antenna_model || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Antenna Gain</span><span class="field-value">{{ row.antenna_gain || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">RET</span><span class="field-value">{{ row.ret || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Transmission Port</span><span class="field-value">{{ row.transmission_port || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Type</span><span class="field-value">{{ row.lld_type || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">DL Bandwidth</span><span class="field-value">{{ row.dl_bandwidth || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">UL Bandwidth</span><span class="field-value">{{ row.ul_bandwidth || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">SSB Absolute Freq</span><span class="field-value">{{ row.ssb_absolute_freq || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">DL SubCarrierSpacing</span><span class="field-value">{{ row.dl_subcarrier_spacing || '-' }}</span></div>
                        </div>
                      </div>
                      <div class="expand-group">
                        <div class="group-title">OAM / Control / User Plane</div>
                        <div class="group-grid">
                          <div class="field-item"><span class="field-label">OAM IP Type</span><span class="field-value">{{ row.oam_ip_type || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">OAM IP Address</span><span class="field-value">{{ row.oam_ip_address || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">OAM IP Submask</span><span class="field-value">{{ row.oam_ip_submask || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">OAM IP Gateway</span><span class="field-value">{{ row.oam_ip_gateway || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">OAM IP VLAN</span><span class="field-value">{{ row.oam_ip_vlan || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">OAM IP DNS</span><span class="field-value">{{ row.oam_ip_dns || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">OAM Binding Port</span><span class="field-value">{{ row.oam_binding_port || '-' }}</span></div>

                          <div class="field-item"><span class="field-label">Control Plane IP Type</span><span class="field-value">{{ row.control_plane_ip_type || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Control Plane Address</span><span class="field-value">{{ row.control_plane_address || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Control Plane Submask</span><span class="field-value">{{ row.control_plane_submask || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Control Plane Gateway</span><span class="field-value">{{ row.control_plane_gateway || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Control Plane VLAN</span><span class="field-value">{{ row.control_plane_vlan || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Control Plane DNS</span><span class="field-value">{{ row.control_plane_dns || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">Control Plane Binding Port</span><span class="field-value">{{ row.control_plane_binding_port || '-' }}</span></div>

                          <div class="field-item"><span class="field-label">User Plane IP Type</span><span class="field-value">{{ row.user_plane_ip_type || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">User Plane Address</span><span class="field-value">{{ row.user_plane_address || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">User Plane Submask</span><span class="field-value">{{ row.user_plane_submask || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">User Plane Gateway</span><span class="field-value">{{ row.user_plane_gateway || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">User Plane VLAN</span><span class="field-value">{{ row.user_plane_vlan || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">User Plane DNS</span><span class="field-value">{{ row.user_plane_dns || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">User Plane Binding Port</span><span class="field-value">{{ row.user_plane_binding_port || '-' }}</span></div>
                        </div>
                      </div>
                      <div class="expand-group">
                        <div class="group-title">XN（NR 时有意义）</div>
                        <div class="group-grid">
                          <div class="field-item"><span class="field-label">XN IP Type</span><span class="field-value">{{ row.xn_ip_type || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">XN Address</span><span class="field-value">{{ row.xn_address || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">XN Submask</span><span class="field-value">{{ row.xn_submask || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">XN Gateway</span><span class="field-value">{{ row.xn_gateway || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">XN VLAN</span><span class="field-value">{{ row.xn_vlan || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">XN DNS</span><span class="field-value">{{ row.xn_dns || '-' }}</span></div>
                          <div class="field-item"><span class="field-label">XN Binding Port</span><span class="field-value">{{ row.xn_binding_port || '-' }}</span></div>
                        </div>
                      </div>
                      <div class="expand-group">
                        <div class="group-title">其它</div>
                        <div class="group-grid">
                          <div class="field-item"><span class="field-label">备注</span><span class="field-value">{{ row.remark || '-' }}</span></div>
                        </div>
                      </div>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column prop="tower_id" label="TOWER ID" width="160" />
                <el-table-column prop="local_cell_id" label="LOCAL CELL ID" width="120" />
                <el-table-column prop="cell_name" label="CELL NAME" min-width="220" />
                <el-table-column prop="band_code" label="Band" width="80" />
                <el-table-column prop="gnb_id" label="gNB ID" width="100" />
                <el-table-column prop="nci" label="NCI" width="160" />
                <el-table-column prop="pci" label="PCI" width="80" />
                <el-table-column prop="frequency" label="EARFCN" width="100" />
                <el-table-column prop="bandwidth" label="Bandwidth" width="110" />
                <el-table-column prop="slot_config" label="Slot config" width="120" />
                <el-table-column prop="slot_config_dl_ul" label="Slot DL/UL" width="120" />
                <el-table-column prop="symbol_config_dl_ul" label="Symbol DL/UL" width="130" />
                <el-table-column prop="mechanical_downtilt_deg" label="机械下倾(°)" width="110" />
                <el-table-column prop="electrical_downtilt_deg" label="电子下倾(°)" width="110" />
                <el-table-column prop="azimuth_deg" label="Azimuth(°)" width="110" />
                <el-table-column prop="gnb_wan_ip" label="gNB WAN IP" width="150" />
                <el-table-column v-if="editMode" label="操作" width="180" fixed="right">
                  <template #default="{ row, $index }">
                    <el-button size="small" @click="editCell(row)">编辑</el-button>
                    <template v-if="canDeleteCell">
                      <el-button size="small" type="danger" @click="deleteCell(row)">删除</el-button>
                    </template>
                    <template v-else>
                      <el-tooltip content="受限编辑：禁止删除 Cell" placement="top">
                        <span>
                          <el-button size="small" type="danger" disabled>删除</el-button>
                        </span>
                      </el-tooltip>
                    </template>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
            <el-tab-pane label="核心网字段视图" name="core">
              <el-table :data="filteredNrCells" border size="small" height="520">
                <el-table-column prop="tower_id" label="TOWER ID" width="160" />
                <el-table-column prop="local_cell_id" label="LOCAL CELL ID" width="120" />
                <el-table-column prop="cell_name" label="CELL NAME" min-width="220" />
                <el-table-column prop="band_code" label="Band" width="80" />
                <el-table-column prop="gnb_id" label="gNB ID" width="100" />
                <el-table-column prop="gnb_length" label="Gnb length" width="120" />
                <el-table-column prop="nci" label="NCI" width="160" />
                <el-table-column prop="gnb_wan_ip" label="gNB WAN IP" width="150" />
                <el-table-column prop="master_5gc_ip1" label="MASTER 5GC IP1" width="150" />
                <el-table-column prop="master_5gc_ip2" label="MASTER 5GC IP2" width="150" />
                <el-table-column prop="master_5gc_ip3" label="MASTER 5GC IP3" width="150" />
                <el-table-column prop="backup_5gc_ip1" label="BACKUP 5GC IP1" width="150" />
                <el-table-column prop="backup_5gc_ip2" label="BACKUP 5GC IP2" width="150" />
                <el-table-column prop="backup_5gc_ip3" label="BACKUP 5GC IP3" width="150" />
                <el-table-column prop="master_omc_ip" label="MASTER OMC IP" width="150" />
                <el-table-column prop="backup_omc_ip" label="BACKUP OMC IP" width="150" />
                <el-table-column prop="ntp_ip1" label="NTP IP1" width="150" />
                <el-table-column prop="ntp_ip2" label="NTP IP2" width="150" />
                <el-table-column prop="kssb" label="Kssb" width="100" />
                <el-table-column prop="offset_to_point_a" label="Offset to PointA" width="160" />
                <el-table-column prop="slot_config" label="Slot config" width="120" />
                <el-table-column prop="slot_config_dl_ul" label="Slot DL/UL" width="120" />
                <el-table-column prop="symbol_config_dl_ul" label="Symbol DL/UL" width="130" />
                <el-table-column v-if="editMode" label="操作" width="180" fixed="right">
                  <template #default="{ row, $index }">
                    <el-button size="small" @click="editCell(row)">编辑</el-button>
                    <template v-if="canDeleteCell">
                      <el-button size="small" type="danger" @click="deleteCell(row)">删除</el-button>
                    </template>
                    <template v-else>
                      <el-tooltip content="受限编辑：禁止删除 Cell" placement="top">
                        <span>
                          <el-button size="small" type="danger" disabled>删除</el-button>
                        </span>
                      </el-tooltip>
                    </template>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>

        <el-tab-pane label="日志" name="logs">
          <el-table :data="logs" v-loading="logsLoading" border>
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="operation" label="操作" width="120" />
            <el-table-column label="操作者" width="160">
              <template #default="{ row }">
                {{ row.actor_name || row.actor_id || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" width="200">
              <template #default="{ row }">
                {{ formatDateTime(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="变更字段" min-width="260">
              <template #default="{ row }">
                <el-tag
                  v-for="f in (row.diff?.changed_fields || [])"
                  :key="f"
                  type="info"
                  class="mr8"
                >
                  {{ f }}
                </el-tag>
                <span v-if="!(row.diff?.changed_fields || []).length" class="muted">
                  （无结构化变更字段）
                </span>
              </template>
            </el-table-column>
            <el-table-column label="详情" width="120">
              <template #default="{ row }">
                <el-button link size="small" @click="openLogDetail(row)">查看详情</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- Cell 编辑对话框 -->
    <el-dialog
      v-model="cellEditDialogVisible"
      :title="isEditingNewCell ? '新增Cell' : '编辑Cell'"
      width="80%"
      :close-on-click-modal="false"
    >
      <el-form :model="cellEditForm" label-width="140px" size="small">
	        <el-row :gutter="16">
	          <el-col :span="8">
	            <el-form-item label="RAT">
	              <el-select v-model="cellEditForm.rat" :disabled="isLockedField('rat')">
	                <el-option label="LTE" value="LTE" />
	                <el-option label="NR" value="NR" />
	              </el-select>
	            </el-form-item>
	          </el-col>
	          <el-col :span="8">
	            <el-form-item label="频段代码">
	              <el-input v-model="cellEditForm.band_code" :disabled="isLockedField('band_code')" />
	            </el-form-item>
	          </el-col>
	          <el-col :span="8">
	            <el-form-item label="LOCAL CELL ID">
	              <el-input-number v-model="cellEditForm.local_cell_id" :min="1" :max="65535" :disabled="isLockedField('local_cell_id')" />
	            </el-form-item>
	          </el-col>
	        </el-row>

	        <el-row :gutter="16">
	          <el-col :span="8">
	            <el-form-item label="TOWER ID">
	              <el-input v-model="cellEditForm.tower_id" :disabled="isLockedField('tower_id')" />
	            </el-form-item>
	          </el-col>
	          <el-col :span="8">
	            <el-form-item label="SiteCode">
	              <el-input :model-value="site?.site_code || ''" disabled />
	            </el-form-item>
	          </el-col>
	          <el-col :span="8">
	            <el-form-item label="SITE NAME">
	              <el-input :model-value="site?.site_name || ''" disabled />
	            </el-form-item>
	          </el-col>
	        </el-row>

	        <el-row :gutter="16">
	          <el-col :span="12">
	            <el-form-item label="CELL NAME">
	              <el-input v-model="cellEditForm.cell_name" />
	            </el-form-item>
	          </el-col>
	          <el-col :span="12">
	            <el-form-item label="PLMN">
	              <el-input v-model="cellEditForm.plmn" />
	            </el-form-item>
	          </el-col>
	        </el-row>

	        <el-row :gutter="16">
	          <el-col :span="8">
	            <el-form-item label="Work Mode">
	              <el-input v-model="cellEditForm.work_mode" />
	            </el-form-item>
	          </el-col>
	          <el-col :span="8">
	            <el-form-item label="Duplex Mode">
	              <el-input v-model="cellEditForm.duplex_mode" />
	            </el-form-item>
	          </el-col>
	          <el-col :span="8">
	            <el-form-item label="MIMO">
	              <el-input v-model="cellEditForm.mimo" />
	            </el-form-item>
	          </el-col>
	        </el-row>

	        <el-row :gutter="16">
	          <el-col :span="8">
	            <el-form-item label="Cell ID">
	              <el-input v-model="cellEditForm.cell_id_in_file" />
	            </el-form-item>
	          </el-col>
	          <el-col v-if="cellEditForm.rat === 'LTE'" :span="8">
	            <el-form-item label="SA">
	              <el-input v-model="cellEditForm.sa" />
	            </el-form-item>
	          </el-col>
	          <el-col v-if="cellEditForm.rat === 'LTE'" :span="8">
	            <el-form-item label="SSP">
	              <el-input v-model="cellEditForm.ssp" />
	            </el-form-item>
	          </el-col>
	        </el-row>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="TAC">
              <el-input v-model="cellEditForm.tac" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="PCI">
              <el-input-number v-model="cellEditForm.pci" :min="0" :max="503" :disabled="isLockedField('pci')" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="ZC Root Index">
              <el-input-number v-model="cellEditForm.zc_root_index" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- LTE 特有字段 -->
	        <el-divider v-if="cellEditForm.rat === 'LTE'">LTE 专用参数</el-divider>
	        <el-row v-if="cellEditForm.rat === 'LTE'" :gutter="16">
	          <el-col :span="8">
	            <el-form-item label="ENB ID">
	              <el-input-number v-model="cellEditForm.enb_id" :disabled="isLockedField('enb_id')" />
	            </el-form-item>
	          </el-col>
	          <el-col :span="8">
	            <el-form-item label="ECI">
	              <el-input-number v-model="cellEditForm.eci" :disabled="isLockedField('eci')" />
	            </el-form-item>
	          </el-col>
	          <el-col :span="8">
	            <el-form-item label="功率(dBm)">
	              <el-input-number v-model="cellEditForm.power_dbm" :min="-50" :max="80" />
	            </el-form-item>
	          </el-col>
	        </el-row>

	        <el-row v-if="cellEditForm.rat === 'LTE'" :gutter="16">
	          <el-col :span="12">
	            <el-form-item label="PA">
	              <el-input v-model="cellEditForm.pa" />
	            </el-form-item>
	          </el-col>
	          <el-col :span="12">
	            <el-form-item label="PB">
	              <el-input v-model="cellEditForm.pb" />
	            </el-form-item>
	          </el-col>
	        </el-row>

        <!-- 5G 特有字段 -->
	        <el-divider v-if="cellEditForm.rat === 'NR'">5G 专用参数</el-divider>
	        <el-row v-if="cellEditForm.rat === 'NR'" :gutter="16">
	          <el-col :span="8">
	            <el-form-item label="gNB ID">
	              <el-input-number v-model="cellEditForm.gnb_id" :disabled="isLockedField('gnb_id')" />
	            </el-form-item>
	          </el-col>
	          <el-col :span="8">
	            <el-form-item label="Gnb length">
	              <el-input-number v-model="cellEditForm.gnb_length" />
	            </el-form-item>
	          </el-col>
	          <el-col :span="8">
	            <el-form-item label="NCI">
	              <el-input-number v-model="cellEditForm.nci" :disabled="isLockedField('nci')" />
	            </el-form-item>
	          </el-col>
	        </el-row>

	        <el-row v-if="cellEditForm.rat === 'NR'" :gutter="16">
	          <el-col :span="8">
	            <el-form-item label="SSB Absolute Freq">
	              <el-input v-model="cellEditForm.ssb_absolute_freq" />
	            </el-form-item>
	          </el-col>
	          <el-col :span="8">
	            <el-form-item label="DL SubCarrierSpacing">
	              <el-input v-model="cellEditForm.dl_subcarrier_spacing" />
	            </el-form-item>
	          </el-col>
	          <el-col :span="8">
	            <el-form-item label="功率(dBm)">
	              <el-input-number v-model="cellEditForm.power_dbm" :min="-50" :max="80" />
	            </el-form-item>
	          </el-col>
	        </el-row>

	        <el-row v-if="cellEditForm.rat === 'NR'" :gutter="16">
	          <el-col :span="12">
	            <el-form-item label="DL Bandwidth">
	              <el-input v-model="cellEditForm.dl_bandwidth" />
	            </el-form-item>
	          </el-col>
	          <el-col :span="12">
	            <el-form-item label="UL Bandwidth">
	              <el-input v-model="cellEditForm.ul_bandwidth" />
	            </el-form-item>
	          </el-col>
	        </el-row>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="经度">
              <el-input-number v-model="cellEditForm.longitude" :min="-180" :max="180" :precision="6" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="纬度">
              <el-input-number v-model="cellEditForm.latitude" :min="-90" :max="90" :precision="6" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="方位角(度)">
              <el-input-number v-model="cellEditForm.azimuth_deg" :min="0" :max="360" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="机械下倾(度)">
              <el-input-number v-model="cellEditForm.mechanical_downtilt_deg" :min="0" :max="90" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="电子下倾(度)">
              <el-input-number v-model="cellEditForm.electrical_downtilt_deg" :min="0" :max="90" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="塔高">
              <el-input-number v-model="cellEditForm.tower_height" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="天线高">
              <el-input-number v-model="cellEditForm.antenna_height" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="塔商">
              <el-input v-model="cellEditForm.tower_merchants" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="Cover Type">
              <el-input v-model="cellEditForm.cover_type" />
            </el-form-item>
          </el-col>
        </el-row>

	        <el-row :gutter="16">
	          <el-col v-if="cellEditForm.rat === 'LTE'" :span="12">
	            <el-form-item label="Bandwidth">
	              <el-input v-model="cellEditForm.bandwidth" :disabled="isLockedField('bandwidth')" />
	            </el-form-item>
	          </el-col>
	          <el-col :span="cellEditForm.rat === 'LTE' ? 12 : 24">
	            <el-form-item label="EARFCN">
	              <el-input-number v-model="cellEditForm.frequency" :disabled="isLockedField('frequency')" />
	            </el-form-item>
	          </el-col>
	        </el-row>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="Band Combination">
              <el-input v-model="cellEditForm.band_combination" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="天线端口">
              <el-input-number v-model="cellEditForm.antenna_ports" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="Cell Allocation">
              <el-input v-model="cellEditForm.cell_allocation" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider>覆盖信息</el-divider>
	        <el-row :gutter="16">
	          <el-col :span="8">
	            <el-form-item label="覆盖区域">
	              <el-input v-model="cellEditForm.coverage_area" />
	            </el-form-item>
	          </el-col>
	          <el-col :span="8">
	            <el-form-item label="覆盖场景">
	              <el-input v-model="cellEditForm.scenario" />
	            </el-form-item>
	          </el-col>
	          <el-col :span="8">
	            <el-form-item label="区域权重">
	              <el-input v-model="cellEditForm.coverage_weight" />
	            </el-form-item>
	          </el-col>
	        </el-row>

	        <el-row :gutter="16">
	          <el-col :span="12">
	            <el-form-item label="scenarios priority value">
	              <el-input v-model="cellEditForm.scenario_weight" />
	            </el-form-item>
	          </el-col>
	          <el-col :span="12">
	            <el-form-item label="Priority Value">
	              <el-input v-model="cellEditForm.weight" />
	            </el-form-item>
	          </el-col>
	        </el-row>

	        <el-divider>OMC / NTP</el-divider>
	        <el-row :gutter="16">
	          <el-col :span="12">
	            <el-form-item label="MASTER OMC IP">
	              <el-input v-model="cellEditForm.master_omc_ip" />
	            </el-form-item>
	          </el-col>
	          <el-col :span="12">
	            <el-form-item label="BACKUP OMC IP">
	              <el-input v-model="cellEditForm.backup_omc_ip" />
	            </el-form-item>
	          </el-col>
	        </el-row>
	        <el-row :gutter="16">
	          <el-col :span="12">
	            <el-form-item label="NTP IP1">
	              <el-input v-model="cellEditForm.ntp_ip1" />
	            </el-form-item>
	          </el-col>
	          <el-col :span="12">
	            <el-form-item label="NTP IP2">
	              <el-input v-model="cellEditForm.ntp_ip2" />
	            </el-form-item>
	          </el-col>
	        </el-row>

	        <el-divider>备注信息</el-divider>
	        <el-form-item label="备注">
	          <el-input v-model="cellEditForm.remark" type="textarea" rows="2" />
	        </el-form-item>

	        <!-- 5G 核心网字段 -->
	        <el-divider v-if="cellEditForm.rat === 'NR'">5G 核心网配置</el-divider>
	        <template v-if="cellEditForm.rat === 'NR'">
	          <el-row :gutter="16">
	            <el-col :span="24">
	              <el-form-item label="gNB WAN IP">
	                <el-input v-model="cellEditForm.gnb_wan_ip" />
	              </el-form-item>
	            </el-col>
	          </el-row>

	          <el-row :gutter="16">
	            <el-col :span="8">
	              <el-form-item label="MASTER 5GC IP1">
	                <el-input v-model="cellEditForm.master_5gc_ip1" />
	              </el-form-item>
	            </el-col>
	            <el-col :span="8">
	              <el-form-item label="MASTER 5GC IP2">
	                <el-input v-model="cellEditForm.master_5gc_ip2" />
	              </el-form-item>
	            </el-col>
	            <el-col :span="8">
	              <el-form-item label="MASTER 5GC IP3">
	                <el-input v-model="cellEditForm.master_5gc_ip3" />
	              </el-form-item>
	            </el-col>
	          </el-row>

	          <el-row :gutter="16">
	            <el-col :span="8">
	              <el-form-item label="BACKUP 5GC IP1">
	                <el-input v-model="cellEditForm.backup_5gc_ip1" />
	              </el-form-item>
	            </el-col>
	            <el-col :span="8">
	              <el-form-item label="BACKUP 5GC IP2">
	                <el-input v-model="cellEditForm.backup_5gc_ip2" />
	              </el-form-item>
	            </el-col>
	            <el-col :span="8">
	              <el-form-item label="BACKUP 5GC IP3">
	                <el-input v-model="cellEditForm.backup_5gc_ip3" />
	              </el-form-item>
	            </el-col>
	          </el-row>

	          <el-row :gutter="16">
	            <el-col :span="12">
	              <el-form-item label="Kssb">
	                <el-input-number v-model="cellEditForm.kssb" />
	              </el-form-item>
	            </el-col>
	            <el-col :span="12">
	              <el-form-item label="Offset to PointA">
	                <el-input v-model="cellEditForm.offset_to_point_a" />
	              </el-form-item>
	            </el-col>
	          </el-row>

	          <el-row :gutter="16">
	            <el-col :span="8">
	              <el-form-item label="Slot config">
	                <el-input v-model="cellEditForm.slot_config" />
	              </el-form-item>
	            </el-col>
	            <el-col :span="8">
	              <el-form-item label="Slot config DL/UL">
	                <el-input v-model="cellEditForm.slot_config_dl_ul" />
	              </el-form-item>
	            </el-col>
	            <el-col :span="8">
	              <el-form-item label="Symbol config DL/UL">
	                <el-input v-model="cellEditForm.symbol_config_dl_ul" />
	              </el-form-item>
	            </el-col>
	          </el-row>
	        </template>

	        <el-collapse v-model="cellEditCollapseActive">
	          <el-collapse-item name="template_extra" title="LLD 模板扩展字段">
	            <el-row :gutter="16">
	              <el-col :span="8">
	                <el-form-item label="Index">
	                  <el-input v-model="cellEditForm.excel_index" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item :label="cellEditForm.rat === 'LTE' ? 'Province Region' : 'Province'">
	                  <el-input v-if="cellEditForm.rat === 'LTE'" v-model="cellEditForm.province_region" />
	                  <el-input v-else v-model="cellEditForm.province" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="City">
	                  <el-input v-model="cellEditForm.city" />
	                </el-form-item>
	              </el-col>
	            </el-row>

	            <el-row :gutter="16">
	              <el-col :span="8">
	                <el-form-item label="County">
	                  <el-input v-model="cellEditForm.county" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="Town">
	                  <el-input v-model="cellEditForm.town" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="Address">
	                  <el-input v-model="cellEditForm.address" />
	                </el-form-item>
	              </el-col>
	            </el-row>

	            <el-row :gutter="16">
	              <el-col :span="8">
	                <el-form-item label="Cluster">
	                  <el-input v-model="cellEditForm.cluster" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="SN">
	                  <el-input v-model="cellEditForm.sn" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="TOWER NAME">
	                  <el-input v-model="cellEditForm.tower_name" />
	                </el-form-item>
	              </el-col>
	            </el-row>

	            <el-row :gutter="16">
	              <el-col :span="8">
	                <el-form-item label="Total Tilt">
	                  <el-input v-model="cellEditForm.total_tilt" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="Antenna modle">
	                  <el-input v-model="cellEditForm.antenna_model" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="Antenna Gain">
	                  <el-input v-model="cellEditForm.antenna_gain" />
	                </el-form-item>
	              </el-col>
	            </el-row>

	            <el-row :gutter="16">
	              <el-col :span="8">
	                <el-form-item label="RET">
	                  <el-input v-model="cellEditForm.ret" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="Transmission Port">
	                  <el-input v-model="cellEditForm.transmission_port" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="Type">
	                  <el-input v-model="cellEditForm.lld_type" />
	                </el-form-item>
	              </el-col>
	            </el-row>
	          </el-collapse-item>

	          <el-collapse-item name="oam" title="OAM / Control / User Plane">
	            <el-row :gutter="16">
	              <el-col :span="8">
	                <el-form-item label="oam IP Type">
	                  <el-input v-model="cellEditForm.oam_ip_type" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="oam Ip address">
	                  <el-input v-model="cellEditForm.oam_ip_address" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="oam Ip Submask">
	                  <el-input v-model="cellEditForm.oam_ip_submask" />
	                </el-form-item>
	              </el-col>
	            </el-row>
	            <el-row :gutter="16">
	              <el-col :span="8">
	                <el-form-item label="oam Ip Gateway">
	                  <el-input v-model="cellEditForm.oam_ip_gateway" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="oam Ip VLAN">
	                  <el-input v-model="cellEditForm.oam_ip_vlan" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="oam Ip DNS">
	                  <el-input v-model="cellEditForm.oam_ip_dns" />
	                </el-form-item>
	              </el-col>
	            </el-row>
	            <el-row :gutter="16">
	              <el-col :span="8">
	                <el-form-item label="OAM Binding port">
	                  <el-input v-model="cellEditForm.oam_binding_port" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="Control planet Ip Type">
	                  <el-input v-model="cellEditForm.control_plane_ip_type" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="Control planet address">
	                  <el-input v-model="cellEditForm.control_plane_address" />
	                </el-form-item>
	              </el-col>
	            </el-row>
	            <el-row :gutter="16">
	              <el-col :span="8">
	                <el-form-item label="Control planet Submask">
	                  <el-input v-model="cellEditForm.control_plane_submask" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="Control planet Gateway">
	                  <el-input v-model="cellEditForm.control_plane_gateway" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="Control planet VLAN">
	                  <el-input v-model="cellEditForm.control_plane_vlan" />
	                </el-form-item>
	              </el-col>
	            </el-row>
	            <el-row :gutter="16">
	              <el-col :span="8">
	                <el-form-item label="Control planet DNS">
	                  <el-input v-model="cellEditForm.control_plane_dns" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="Control planet binding port">
	                  <el-input v-model="cellEditForm.control_plane_binding_port" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="User planet Ip Type">
	                  <el-input v-model="cellEditForm.user_plane_ip_type" />
	                </el-form-item>
	              </el-col>
	            </el-row>
	            <el-row :gutter="16">
	              <el-col :span="8">
	                <el-form-item label="User planet address">
	                  <el-input v-model="cellEditForm.user_plane_address" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="User planet Submask">
	                  <el-input v-model="cellEditForm.user_plane_submask" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="User planet Gateway">
	                  <el-input v-model="cellEditForm.user_plane_gateway" />
	                </el-form-item>
	              </el-col>
	            </el-row>
	            <el-row :gutter="16">
	              <el-col :span="8">
	                <el-form-item label="User planet VLAN">
	                  <el-input v-model="cellEditForm.user_plane_vlan" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="User planet DNS">
	                  <el-input v-model="cellEditForm.user_plane_dns" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="User planet binding port">
	                  <el-input v-model="cellEditForm.user_plane_binding_port" />
	                </el-form-item>
	              </el-col>
	            </el-row>
	          </el-collapse-item>

	          <el-collapse-item v-if="cellEditForm.rat === 'LTE'" name="lte_net" title="4G：X2 / MME">
	            <el-row :gutter="16">
	              <el-col :span="8">
	                <el-form-item label="X2 Ip Type">
	                  <el-input v-model="cellEditForm.x2_ip_type" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="X2 address">
	                  <el-input v-model="cellEditForm.x2_address" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="X2 Submask">
	                  <el-input v-model="cellEditForm.x2_submask" />
	                </el-form-item>
	              </el-col>
	            </el-row>
	            <el-row :gutter="16">
	              <el-col :span="8">
	                <el-form-item label="X2 Gateway">
	                  <el-input v-model="cellEditForm.x2_gateway" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="X2 VLAN">
	                  <el-input v-model="cellEditForm.x2_vlan" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="X2 DNS">
	                  <el-input v-model="cellEditForm.x2_dns" />
	                </el-form-item>
	              </el-col>
	            </el-row>
	            <el-row :gutter="16">
	              <el-col :span="8">
	                <el-form-item label="X2 binding port">
	                  <el-input v-model="cellEditForm.x2_binding_port" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="MME IP 1">
	                  <el-input v-model="cellEditForm.mme_ip_1" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="MME IP 2">
	                  <el-input v-model="cellEditForm.mme_ip_2" />
	                </el-form-item>
	              </el-col>
	            </el-row>
	            <el-row :gutter="16">
	              <el-col :span="8">
	                <el-form-item label="MME IP 3">
	                  <el-input v-model="cellEditForm.mme_ip_3" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="MME IP 4">
	                  <el-input v-model="cellEditForm.mme_ip_4" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="MME IP 5">
	                  <el-input v-model="cellEditForm.mme_ip_5" />
	                </el-form-item>
	              </el-col>
	            </el-row>
	            <el-row :gutter="16">
	              <el-col :span="8">
	                <el-form-item label="MME IP 6">
	                  <el-input v-model="cellEditForm.mme_ip_6" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="MME IP 7">
	                  <el-input v-model="cellEditForm.mme_ip_7" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="MME IP 8">
	                  <el-input v-model="cellEditForm.mme_ip_8" />
	                </el-form-item>
	              </el-col>
	            </el-row>
	          </el-collapse-item>

	          <el-collapse-item v-if="cellEditForm.rat === 'NR'" name="nr_net" title="5G：XN">
	            <el-row :gutter="16">
	              <el-col :span="8">
	                <el-form-item label="XN Ip Type">
	                  <el-input v-model="cellEditForm.xn_ip_type" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="XN address">
	                  <el-input v-model="cellEditForm.xn_address" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="XN Submask">
	                  <el-input v-model="cellEditForm.xn_submask" />
	                </el-form-item>
	              </el-col>
	            </el-row>
	            <el-row :gutter="16">
	              <el-col :span="8">
	                <el-form-item label="XN Gateway">
	                  <el-input v-model="cellEditForm.xn_gateway" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="XN VLAN">
	                  <el-input v-model="cellEditForm.xn_vlan" />
	                </el-form-item>
	              </el-col>
	              <el-col :span="8">
	                <el-form-item label="XN DNS">
	                  <el-input v-model="cellEditForm.xn_dns" />
	                </el-form-item>
	              </el-col>
	            </el-row>
	            <el-row :gutter="16">
	              <el-col :span="8">
	                <el-form-item label="XN binding port">
	                  <el-input v-model="cellEditForm.xn_binding_port" />
	                </el-form-item>
	              </el-col>
	            </el-row>
	          </el-collapse-item>
	        </el-collapse>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="cellEditDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveCell" :loading="savingCell">
            {{ isEditingNewCell ? '新增' : '保存' }}
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 添加Cell按钮 -->
    <el-button
      v-if="editMode && canAddCell"
      type="primary"
      circle
      class="add-cell-btn"
      @click="addNewCell"
      title="添加新的Cell"
    >
      <el-icon><Plus /></el-icon>
    </el-button>

    <!-- 规划变更日志详情对话框 -->
    <el-dialog
      v-model="logDetailVisible"
      title="规划变更详情"
      width="760px"
    >
      <div v-if="logDetail">
        <el-descriptions :column="2" border size="small" class="mb16">
          <el-descriptions-item label="操作">{{ logDetail.operation }}</el-descriptions-item>
          <el-descriptions-item label="时间">{{ logDetail.created_at }}</el-descriptions-item>
          <el-descriptions-item label="操作者">
            {{ logDetail.actor_name || logDetail.actor_id || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="摘要">
            {{ logDetail.summary || '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="mb16">
          <div class="section-title">变更字段</div>
          <div>
            <el-tag
              v-for="f in (logDetail.diff?.changed_fields || [])"
              :key="f"
              type="info"
              class="mr8"
            >
              {{ f }}
            </el-tag>
            <span v-if="!(logDetail.diff?.changed_fields || []).length" class="muted">
              无结构化变更字段
            </span>
          </div>
        </div>

        <div>
          <div class="section-title">Cell 级变更</div>
          <div v-if="Array.isArray(logDetail.diff?.cell_changes) && logDetail.diff.cell_changes.length">
            <el-timeline>
              <el-timeline-item
                v-for="(chg, idx) in logDetail.diff.cell_changes"
                :key="idx"
              >
                <div class="cell-change-header">
                  <span class="mono">
                    {{ chg.key?.rat || '-' }} / {{ chg.key?.band_code || '-' }} / LCID={{ chg.key?.local_cell_id ?? '-' }}
                  </span>
                  <el-tag
                    size="small"
                    :type="chg.change_type === 'created' ? 'success' : chg.change_type === 'deleted' ? 'danger' : 'warning'"
                  >
                    {{ chg.change_type || 'updated' }}
                  </el-tag>
                </div>
                <ul class="change-list">
                  <li v-for="(f, i) in (chg.changes || [])" :key="i">
                    <span class="field-name">{{ f.field }}</span>
                    ：<span class="old-val">{{ f.old ?? '∅' }}</span>
                    →
                    <span class="new-val">{{ f.new ?? '∅' }}</span>
                  </li>
                </ul>
              </el-timeline-item>
            </el-timeline>
          </div>
          <div v-else class="muted">
            本次变更未记录 Cell 级差异（可能为早期导入或仅概要变更）。
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="logDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'
import sitePlanningApi from '../../api/sitePlanning'

const route = useRoute()
const router = useRouter()
const siteId = Number(route.params.id)

const loading = ref(false)
const importing = ref(false)
const dryRun = ref(true)
const importInfo = ref('')
const activeTab = ref('overview')

const formatDateTime = (val) => {
  if (!val) return '-'
  const d = new Date(val)
  if (Number.isNaN(d.getTime())) return String(val)
  return d.toLocaleString('zh-CN')
}

// 编辑模式相关
const editMode = ref(false)
const saving = ref(false)
const hasChanges = ref(false)
const originalCells = ref([])

const site = ref(null)
const planning = ref(null)
const summary = ref(null)
const cells = ref([])
const editPolicy = ref(null)
const editingCellOriginal = ref(null)

// Cell编辑对话框
const cellEditDialogVisible = ref(false)
const isEditingNewCell = ref(false)
const editingCellId = ref(null)
const savingCell = ref(false)
const cellEditCollapseActive = ref(['template_extra'])
const cellEditForm = reactive({
  rat: 'LTE',
  band_code: '',
  tower_id: '',
  local_cell_id: null,
  cell_name: '',
  plmn: '',
  tac: '',
  work_mode: '',
  duplex_mode: '',
  mimo: '',
  cell_id_in_file: '',
  pci: null,
  zc_root_index: null,
  longitude: null,
  latitude: null,
  power_dbm: null,
  pa: '',
  pb: '',
  cover_type: '',
  band_in_file: '',
  frequency: null,
  bandwidth: '',
  dl_bandwidth: '',
  ul_bandwidth: '',
  ssb_absolute_freq: '',
  dl_subcarrier_spacing: '',
  mechanical_downtilt_deg: null,
  electrical_downtilt_deg: null,
  total_tilt: '',
  azimuth_deg: null,
  tower_height: null,
  antenna_height: null,
  tower_merchants: '',
  band_combination: '',
  antenna_ports: null,
  cell_allocation: '',
  tower_name: '',
  town: '',
  region: '',
  coverage_area: '',
  coverage_weight: '',
  scenario: '',
  scenario_weight: '',
  weight: '',
  remark: '',
  // 模板扩展字段（地市区等）
  excel_index: '',
  province_region: '',
  province: '',
  city: '',
  county: '',
  address: '',
  cluster: '',
  sn: '',
  sa: '',
  ssp: '',
  antenna_model: '',
  antenna_gain: '',
  ret: '',
  transmission_port: '',
  lld_type: '',
  // OAM / Control / User Plane
  oam_ip_type: '',
  oam_ip_address: '',
  oam_ip_submask: '',
  oam_ip_gateway: '',
  oam_ip_vlan: '',
  oam_ip_dns: '',
  oam_binding_port: '',
  control_plane_ip_type: '',
  control_plane_address: '',
  control_plane_submask: '',
  control_plane_gateway: '',
  control_plane_vlan: '',
  control_plane_dns: '',
  control_plane_binding_port: '',
  user_plane_ip_type: '',
  user_plane_address: '',
  user_plane_submask: '',
  user_plane_gateway: '',
  user_plane_vlan: '',
  user_plane_dns: '',
  user_plane_binding_port: '',
  // X2（4G）
  x2_ip_type: '',
  x2_address: '',
  x2_submask: '',
  x2_gateway: '',
  x2_vlan: '',
  x2_dns: '',
  x2_binding_port: '',
  // XN（5G）
  xn_ip_type: '',
  xn_address: '',
  xn_submask: '',
  xn_gateway: '',
  xn_vlan: '',
  xn_dns: '',
  xn_binding_port: '',
  // MME（4G）
  mme_ip_1: '',
  mme_ip_2: '',
  mme_ip_3: '',
  mme_ip_4: '',
  mme_ip_5: '',
  mme_ip_6: '',
  mme_ip_7: '',
  mme_ip_8: '',
  // LTE 专用
  enb_id: null,
  eci: null,
  // 5G 专用
  gnb_id: null,
  gnb_length: null,
  nci: null,
  gnb_wan_ip: '',
  master_5gc_ip1: '',
  master_5gc_ip2: '',
  master_5gc_ip3: '',
  backup_5gc_ip1: '',
  backup_5gc_ip2: '',
  backup_5gc_ip3: '',
  master_omc_ip: '',
  backup_omc_ip: '',
  ntp_ip1: '',
  ntp_ip2: '',
  kssb: null,
  offset_to_point_a: '',
  slot_config: '',
  slot_config_dl_ul: '',
  symbol_config_dl_ul: '',
})

const logs = ref([])
const logsLoading = ref(false)
const logDetailVisible = ref(false)
const logDetail = ref(null)

// 过滤条件
const bandOptions = computed(() => (summary.value?.bands || []))

const lteBandFilter = ref('')
const ltePciFilter = ref('')
const lteKeyword = ref('')

const nrBandFilter = ref('')
const nrNciFilter = ref('')
const nrKeyword = ref('')
const nrViewMode = ref('basic')

const editPolicyMode = computed(() => editPolicy.value?.mode || null)
const editPolicyReason = computed(() => editPolicy.value?.reason || '当前账号无权限编辑规划')
const canEdit = computed(() => !!editPolicy.value?.can_edit)
const canImport = computed(() => !!editPolicy.value?.can_import)
const canAddCell = computed(() => !!editPolicy.value?.can_add_cell)
const canDeleteCell = computed(() => !!editPolicy.value?.can_delete_cell)

const extractErrorMessage = (error, fallback = '操作失败') => {
  const detail = error?.response?.data?.detail
  if (!detail) return fallback
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.filter(Boolean).join('；') || fallback
  if (typeof detail === 'object') {
    const parts = []
    if (detail.message) parts.push(detail.message)
    if (detail.reason) parts.push(detail.reason)
    if (Array.isArray(detail.attempted_fields) && detail.attempted_fields.length) {
      parts.push(`尝试修改字段：${detail.attempted_fields.join('，')}`)
    }
    return parts.join('；') || fallback
  }
  return String(detail)
}

const isLockedField = (field) => {
  if (editPolicyMode.value !== 'limited') return false
  return (editPolicy.value?.locked_fields || []).includes(field)
}

const goBack = () => router.back()

const loadSite = async () => {
  try {
    const res = await request.get(`/api/sites/${siteId}`)
    site.value = res
  } catch (e) {
    // ignore
  }
}

const loadLldPlanning = async () => {
  try {
    loading.value = true
    const res = await sitePlanningApi.getLldPlanning(siteId)
    planning.value = res.planning || null
    summary.value = res.summary || null
    cells.value = Array.isArray(res.cells) ? res.cells : []
    editPolicy.value = res.edit_policy || null

    if (route.query.edit === '1' && planning.value && canEdit.value && !editMode.value) {
      originalCells.value = JSON.parse(JSON.stringify(cells.value))
      editMode.value = true
      hasChanges.value = false
      if (editPolicyMode.value === 'limited' && editPolicy.value?.reason) {
        ElMessage.info(editPolicy.value.reason)
      }
    }
  } catch (e) {
    planning.value = null
    summary.value = null
    cells.value = []
    editPolicy.value = null
    ElMessage.warning(extractErrorMessage(e, '加载 LLD 规划失败或尚未导入'))
  } finally {
    loading.value = false
  }
}

const loadLogs = async () => {
  try {
    logsLoading.value = true
    logs.value = await sitePlanningApi.listLogs(siteId, { limit: 100 })
  } catch (e) {
    // ignore
  } finally {
    logsLoading.value = false
  }
}

const openLogDetail = (row) => {
  logDetail.value = row
  logDetailVisible.value = true
}

const downloadLldTemplate = async () => {
  try {
    const res = await sitePlanningApi.downloadLldBatchTemplate()
    const blob = new Blob([res])
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'site_planning_lld_template.xlsx'
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error('下载 LLD 模板失败')
  }
}

const onBeforeUpload = () => {
  if (!canImport.value) {
    ElMessage.warning(editPolicyReason.value || '无权限执行导入')
    return false
  }
  return true
}

const onUploadLld = async (opts) => {
  try {
    importing.value = true
    importInfo.value = '正在解析 LLD...'
    const res = await sitePlanningApi.lldImportPlanning(siteId, opts.file, dryRun.value)
    if (dryRun.value) {
      importInfo.value = res.success
        ? `试运行成功：4G Cells=${res.lte_cell_count || 0}, 5G Cells=${res.nr_cell_count || 0}, Bands=${(res.bands || []).join(', ')}`
        : `试运行失败：${(res.errors || []).join('; ')}`
    } else {
      if (res.success) {
        importInfo.value = `导入成功，生成版本 v${res.version_created || ''}`
        await loadLldPlanning()
        await loadLogs()
      } else {
        importInfo.value = `导入失败：${(res.errors || []).join('; ')}`
      }
    }
    opts.onSuccess(res)
  } catch (e) {
    importInfo.value = extractErrorMessage(e, '导入失败')
    opts.onError(e)
  } finally {
    importing.value = false
  }
}

const filteredLteCells = computed(() => {
  return cells.value
    .filter(c => c.rat === 'LTE')
    .filter(c => {
      if (lteBandFilter.value && c.band_code !== lteBandFilter.value) return false
      if (ltePciFilter.value && String(c.pci || '').indexOf(ltePciFilter.value.trim()) === -1) return false
      const kw = lteKeyword.value.trim().toLowerCase()
      if (!kw) return true
      const text = `${c.tower_id || ''} ${c.cell_name || ''}`.toLowerCase()
      return text.includes(kw)
    })
})

const filteredNrCells = computed(() => {
  return cells.value
    .filter(c => c.rat === 'NR')
    .filter(c => {
      if (nrBandFilter.value && c.band_code !== nrBandFilter.value) return false
      if (nrNciFilter.value && String(c.nci || '').indexOf(nrNciFilter.value.trim()) === -1) return false
      const kw = nrKeyword.value.trim().toLowerCase()
      if (!kw) return true
      const text = `${c.tower_id || ''} ${c.cell_name || ''}`.toLowerCase()
      return text.includes(kw)
    })
})

// 编辑模式方法
const toggleEditMode = () => {
  if (!canEdit.value) {
    ElMessage.warning(editPolicyReason.value || '无权限编辑规划')
    return
  }
  if (editMode.value) {
    // 退出编辑模式
    if (hasChanges.value) {
      ElMessageBox.confirm('当前有未保存的更改，确定要退出编辑模式吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        editMode.value = false
        hasChanges.value = false
        // 恢复原始数据
        cells.value = JSON.parse(JSON.stringify(originalCells.value))
      }).catch(() => {})
    } else {
      editMode.value = false
    }
  } else {
    // 进入编辑模式
    originalCells.value = JSON.parse(JSON.stringify(cells.value))
    editMode.value = true
    hasChanges.value = false
    if (editPolicyMode.value === 'limited' && editPolicy.value?.reason) {
      ElMessage.info(editPolicy.value.reason)
    }
  }
}

const cancelEdit = () => {
  ElMessageBox.confirm('确定要取消编辑吗？所有未保存的更改将丢失。', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    editMode.value = false
    hasChanges.value = false
    // 恢复原始数据
    cells.value = JSON.parse(JSON.stringify(originalCells.value))
  }).catch(() => {})
}

const saveChanges = async () => {
  if (!planning.value) {
    ElMessage.error('没有可保存的规划数据')
    return
  }

  try {
    saving.value = true
    await sitePlanningApi.updateLldPlanning(siteId, planning.value.version)
    ElMessage.success('规划保存成功，已创建新版本')

    // 重新加载数据
    await loadLldPlanning()
    await loadLogs()

    editMode.value = false
    hasChanges.value = false
    originalCells.value = []
  } catch (error) {
    ElMessage.error(extractErrorMessage(error, '保存失败'))
  } finally {
    saving.value = false
  }
}

// Cell编辑方法
const addNewCell = () => {
  if (!canAddCell.value) {
    ElMessage.warning('受限编辑：禁止新增 Cell')
    return
  }
  isEditingNewCell.value = true
  editingCellId.value = null
  editingCellOriginal.value = null

  // 重置表单
  Object.keys(cellEditForm).forEach(key => {
    cellEditForm[key] = key === 'rat' ? 'LTE' : (typeof cellEditForm[key] === 'string' ? '' : null)
  })
  // 默认填充 TOWER ID
  cellEditForm.tower_id = site.value?.site_code || ''

  cellEditDialogVisible.value = true
}

const editCell = (row) => {
  isEditingNewCell.value = false
  editingCellId.value = row.id
  editingCellOriginal.value = row

  // 填充表单
  Object.keys(cellEditForm).forEach(key => {
    if (row.hasOwnProperty(key)) {
      cellEditForm[key] = row[key]
    } else {
      cellEditForm[key] = key === 'rat' ? 'LTE' : (typeof cellEditForm[key] === 'string' ? '' : null)
    }
  })
  // 兜底：若历史数据缺失 TOWER ID，则默认回填站点编码
  if (!cellEditForm.tower_id) {
    cellEditForm.tower_id = site.value?.site_code || ''
  }

  cellEditDialogVisible.value = true
}

const saveCell = async () => {
  try {
    savingCell.value = true

    const normalize = (v) => {
      if (v === undefined) return null
      if (typeof v === 'string') {
        const s = v.trim()
        return s === '' ? null : s
      }
      return v
    }

    const requiredKeys = ['rat', 'band_code', 'local_cell_id']

    // 构建要保存的数据
    const cellData = {}
    if (isEditingNewCell.value) {
      // 必填校验 + 默认填充
      const rat = normalize(cellEditForm.rat)
      const bandCode = normalize(cellEditForm.band_code)
      const localCellId = cellEditForm.local_cell_id

      if (!rat) {
        ElMessage.warning('RAT不能为空')
        return
      }
      if (!bandCode) {
        ElMessage.warning('Band不能为空')
        return
      }
      if (localCellId === null || localCellId === undefined) {
        ElMessage.warning('LOCAL CELL ID不能为空')
        return
      }

      const towerId = normalize(cellEditForm.tower_id) || (site.value?.site_code || null)
      if (!towerId) {
        ElMessage.warning('TOWER ID不能为空')
        return
      }

      Object.keys(cellEditForm).forEach(key => {
        const v = normalize(cellEditForm[key])
        if (v !== null) cellData[key] = v
      })
      // 确保 tower_id 总是有值（避免空白导致后端拒绝）
      cellData.tower_id = towerId
    } else {
      const original = editingCellOriginal.value || {}
      const attemptedLocked = []
      const invalidRequired = []
      Object.keys(cellEditForm).forEach(key => {
        let newValue = normalize(cellEditForm[key])
        const oldValue = normalize(original[key])

        // tower_id 允许“清空→默认回填站点编码”
        if (key === 'tower_id' && newValue === null) {
          newValue = site.value?.site_code || null
        }
        if (oldValue === newValue) return

        if (isLockedField(key)) {
          attemptedLocked.push(key)
          return
        }

        if (requiredKeys.includes(key) && newValue === null) {
          invalidRequired.push(key)
          return
        }
        cellData[key] = newValue
      })
      if (attemptedLocked.length) {
        ElMessage.warning(`受限编辑：禁止修改关键字段（${attemptedLocked.join('，')}）`)
        return
      }
      if (invalidRequired.length) {
        ElMessage.warning(`关键字段不可清空：${invalidRequired.join('，')}`)
        return
      }
      if (!Object.keys(cellData).length) {
        ElMessage.info('未检测到任何修改')
        return
      }
    }

    if (isEditingNewCell.value) {
      // 创建新Cell
      await sitePlanningApi.createLldCell(siteId, cellData, planning.value.version)
      ElMessage.success('新增Cell成功')
    } else {
      // 更新现有Cell
      await sitePlanningApi.updateLldCell(siteId, editingCellId.value, cellData, planning.value.version)
      ElMessage.success('更新Cell成功')
    }

    cellEditDialogVisible.value = false
    hasChanges.value = true

    // 重新加载数据以获取最新的版本
    await loadLldPlanning()
    await loadLogs()

  } catch (error) {
    if (error?.response?.data?.errors) {
      const errors = error.response.data.errors
      ElMessage.error(`验证失败：${Array.isArray(errors) ? errors.join('；') : errors}`)
      return
    }
    if (error?.response?.data?.conflicts) {
      const conflicts = error.response.data.conflicts
      ElMessage.warning(`数据冲突：${Array.isArray(conflicts) ? conflicts.join('；') : conflicts}`)
      return
    }
    ElMessage.error(extractErrorMessage(error, '保存失败'))
  } finally {
    savingCell.value = false
  }
}

const deleteCell = async (row) => {
  try {
    if (!canDeleteCell.value) {
      ElMessage.warning('受限编辑：禁止删除 Cell')
      return
    }
    await ElMessageBox.confirm(
      `确定要删除这个${row.rat} Cell (${row.band_code}, 扇区${row.local_cell_id}) 吗？`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await sitePlanningApi.deleteLldCell(siteId, row.id, planning.value.version)
    ElMessage.success('删除Cell成功')

    hasChanges.value = true

    // 重新加载数据
    await loadLldPlanning()
    await loadLogs()

  } catch (error) {
    if (error === 'cancel') return

    ElMessage.error(extractErrorMessage(error, '删除失败'))
  }
}

onMounted(async () => {
  await loadSite()
  await loadLldPlanning()
  await loadLogs()
})
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; gap: 12px; }
.mb16 { margin-bottom: 16px; }
.import-row { display:flex; align-items:center; gap: 12px; }
.import-info { color: #666; }
.meta-row { display:flex; gap: 12px; margin-bottom: 8px; align-items: center; flex-wrap: wrap; }
.filter-row { display:flex; gap: 12px; margin-bottom: 8px; flex-wrap: wrap; }
.mr8 { margin-right: 8px; }
.expand-groups { display: flex; flex-direction: column; gap: 12px; padding: 8px 0; }
.expand-group { border-top: 1px solid #eee; padding-top: 8px; }
.expand-group:first-child { border-top: none; padding-top: 0; }
.group-title { font-weight: 600; margin-bottom: 4px; color: #333; }
.group-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 4px 12px; }
.field-item { display:flex; justify-content: space-between; gap: 8px; font-size: 12px; }
.field-label { color: #666; white-space: nowrap; }
.field-value { color: #333; word-break: break-all; text-align: right; }
.inner-tabs { margin-top: 4px; }

/* 编辑模式相关样式 */
.add-cell-btn {
  position: fixed;
  bottom: 30px;
  right: 30px;
  width: 56px;
  height: 56px;
  z-index: 1000;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

/* 编辑模式指示器 */
.page-header h1::before {
  content: '';
  display: inline-block;
  width: 8px;
  height: 8px;
  background: #f56c6c;
  border-radius: 50%;
  margin-right: 8px;
  animation: pulse 1.5s ease-in-out infinite;
  opacity: 0;
}

.page-header h1.edit-mode::before {
  opacity: 1;
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(245, 108, 108, 0.4);
  }
  70% {
    box-shadow: 0 0 0 10px rgba(245, 108, 108, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(245, 108, 108, 0);
  }
}

/* 表格编辑模式样式 */
.el-table--border {
  --el-table-border-color: #dcdfe6;
}

.el-table--border.edit-mode {
  --el-table-border-color: #e1a3a3;
}

/* 编辑对话框样式优化 */
.el-dialog__body {
  max-height: 70vh;
  overflow-y: auto;
}

.el-form-item {
  margin-bottom: 16px;
}

.el-form-item__label {
  line-height: 32px;
}

.el-divider {
  margin: 16px 0;
}

.el-divider__text {
  background: #f5f7fa;
  padding: 8px 16px;
  border-radius: 4px;
  font-weight: 500;
}
</style>
