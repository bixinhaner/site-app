<template>
  <div class="page">
    <div class="page-header">
      <h1>站点规划（LLD新）</h1>
      <div class="header-actions">
        <el-button @click="goBack"><el-icon><Back /></el-icon>返回</el-button>
      </div>
    </div>

    <el-card class="mb16" v-loading="loading">
      <div class="meta-row">
        <el-tag type="info">Site ID: {{ siteId }}</el-tag>
        <el-tag v-if="site" type="success">站点: {{ site.site_code }} / {{ site.site_name }}</el-tag>
        <el-tag v-if="planning" type="warning">当前版本: v{{ planning.version }}</el-tag>
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
        <el-switch v-model="dryRun" active-text="试运行(dry run)" />
        <el-upload
          :show-file-list="false"
          :before-upload="onBeforeUpload"
          :http-request="onUploadLld"
        >
          <el-button type="success" :loading="importing">
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
                      <div class="field-item"><span class="field-label">SITE INFORMATION</span><span class="field-value">{{ row.site_information || '-' }}</span></div>
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
                      <div class="field-item"><span class="field-label">Frequency</span><span class="field-value">{{ row.frequency ?? '-' }}</span></div>
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
            <el-table-column prop="frequency" label="Freq" width="100" />
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
                          <div class="field-item"><span class="field-label">SITE INFORMATION</span><span class="field-value">{{ row.site_information || '-' }}</span></div>
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
                          <div class="field-item"><span class="field-label">Frequency</span><span class="field-value">{{ row.frequency ?? '-' }}</span></div>
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
                <el-table-column prop="frequency" label="Freq" width="100" />
                <el-table-column prop="bandwidth" label="Bandwidth" width="110" />
                <el-table-column prop="slot_config" label="Slot config" width="120" />
                <el-table-column prop="slot_config_dl_ul" label="Slot DL/UL" width="120" />
                <el-table-column prop="symbol_config_dl_ul" label="Symbol DL/UL" width="130" />
                <el-table-column prop="mechanical_downtilt_deg" label="机械下倾(°)" width="110" />
                <el-table-column prop="electrical_downtilt_deg" label="电子下倾(°)" width="110" />
                <el-table-column prop="azimuth_deg" label="Azimuth(°)" width="110" />
                <el-table-column prop="gnb_wan_ip" label="gNB WAN IP" width="150" />
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
              </el-table>
            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>

        <el-tab-pane label="日志" name="logs">
          <el-table :data="logs" v-loading="logsLoading" border>
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="operation" label="操作" width="120" />
            <el-table-column prop="actor_id" label="操作者" width="120" />
            <el-table-column prop="created_at" label="时间" width="200" />
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
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
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

const site = ref(null)
const planning = ref(null)
const summary = ref(null)
const cells = ref([])

const logs = ref([])
const logsLoading = ref(false)

// 过滤条件
const bandOptions = computed(() => (summary.value?.bands || []))

const lteBandFilter = ref('')
const ltePciFilter = ref('')
const lteKeyword = ref('')

const nrBandFilter = ref('')
const nrNciFilter = ref('')
const nrKeyword = ref('')
const nrViewMode = ref('basic')

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
  } catch (e) {
    planning.value = null
    summary.value = null
    cells.value = []
    const msg = e?.response?.data?.detail || '加载 LLD 规划失败或尚未导入'
    ElMessage.warning(msg)
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

const onBeforeUpload = () => true

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
    const msg = e?.response?.data?.detail || '导入失败'
    importInfo.value = msg
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
</style>
