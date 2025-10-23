<template>
  <div class="page">
    <div class="page-header">
      <h1>新建勘察</h1>
      <div class="header-actions">
        <el-button @click="goBack">
          <el-icon><Back /></el-icon>
          返回
        </el-button>
        <el-button type="primary" :loading="saving" @click="submit">
          <el-icon><Check /></el-icon>
          保存
        </el-button>
      </div>
    </div>

    <el-card>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="140px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="站点" prop="site_id">
              <el-select v-model="form.site_id" filterable placeholder="选择站点" style="width:100%" @visible-change="v=> v && loadSites()">
                <el-option v-for="s in siteOptions" :key="s.id" :label="`${s.site_name} (${s.site_code})`" :value="s.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="勘察日期" prop="survey_date">
              <el-date-picker v-model="form.survey_date" type="datetime" placeholder="选择日期时间" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="勘察人" prop="surveyor_name">
              <el-input v-model="form.surveyor_name" placeholder="姓名" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="6">
            <el-form-item label="勘察人电话">
              <el-input v-model="form.surveyor_phone" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="结论" prop="feasibility">
              <el-select v-model="form.feasibility" placeholder="选择结论" style="width:100%">
                <el-option label="可行" value="feasible" />
                <el-option label="有条件可行" value="conditionally_feasible" />
                <el-option label="不可行" value="infeasible" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="地址">
              <el-input v-model="form.address" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider>坐标位置</el-divider>
        <el-row :gutter="16">
          <el-col :span="6">
            <el-form-item label="纬度">
              <el-input-number v-model="form.latitude" :step="0.000001" :precision="6" :controls="false" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="经度">
              <el-input-number v-model="form.longitude" :step="0.000001" :precision="6" :controls="false" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="GPS精度(m)">
              <el-input-number v-model="form.gps_accuracy" :step="1" :controls="false" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider>场地与结构</el-divider>
        <el-row :gutter="16">
          <el-col :span="6"><el-form-item label="站点类型"><el-input v-model="form.site_type" /></el-form-item></el-col>
          <el-col :span="6"><el-form-item label="塔型"><el-input v-model="form.tower_type" /></el-form-item></el-col>
          <el-col :span="6"><el-form-item label="可用挂高(m)"><el-input-number v-model="form.available_height_m" :step="0.5" :controls="false" style="width:100%" /></el-form-item></el-col>
          <el-col :span="6"><el-form-item label="荷载(kg)"><el-input-number v-model="form.load_capacity_kg" :step="10" :controls="false" style="width:100%" /></el-form-item></el-col>
        </el-row>

        <el-divider>供电与回传</el-divider>
        <el-row :gutter="16">
          <el-col :span="6"><el-form-item label="市电可用"><el-switch v-model="form.power_available" /></el-form-item></el-col>
          <el-col :span="6"><el-form-item label="电源距离(m)"><el-input-number v-model="form.power_distance_m" :step="1" :controls="false" style="width:100%" /></el-form-item></el-col>
          <el-col :span="6"><el-form-item label="容量(kW)"><el-input-number v-model="form.power_capacity_kw" :step="0.1" :precision="1" :controls="false" style="width:100%" /></el-form-item></el-col>
          <el-col :span="6"><el-form-item label="接地可行"><el-switch v-model="form.earthing_feasible" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="6"><el-form-item label="光纤可用"><el-switch v-model="form.fiber_available" /></el-form-item></el-col>
          <el-col :span="6"><el-form-item label="光纤距离(m)"><el-input-number v-model="form.fiber_distance_m" :step="1" :controls="false" style="width:100%" /></el-form-item></el-col>
          <el-col :span="6"><el-form-item label="微波LoS"><el-switch v-model="form.microwave_los" /></el-form-item></el-col>
          <el-col :span="3"><el-form-item label="方位角(°)"><el-input-number v-model="form.los_azimuth_deg" :step="1" :controls="false" style="width:100%" /></el-form-item></el-col>
          <el-col :span="3"><el-form-item label="距离(km)"><el-input-number v-model="form.los_distance_km" :step="0.1" :precision="1" :controls="false" style="width:100%" /></el-form-item></el-col>
        </el-row>

        <el-divider>环境与进场</el-divider>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="敏感点"><el-input v-model="form.sensitive_points" type="textarea" :rows="2" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="安全/隐患"><el-input v-model="form.safety_notes" type="textarea" :rows="2" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="审批/物业限制"><el-input v-model="form.permits_constraints" type="textarea" :rows="2" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="进场限制"><el-input v-model="form.entry_constraints" type="textarea" :rows="2" /></el-form-item></el-col>
        </el-row>

        <el-divider>业主信息</el-divider>
        <el-row :gutter="16">
          <el-col :span="6"><el-form-item label="业主姓名"><el-input v-model="form.owner_name" /></el-form-item></el-col>
          <el-col :span="6"><el-form-item label="业主电话"><el-input v-model="form.owner_phone" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="时间窗口"><el-input v-model="form.access_time_window" /></el-form-item></el-col>
        </el-row>

        <el-divider>结论与建议</el-divider>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="风险清单"><el-input v-model="form.risks" type="textarea" :rows="3" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="建议"><el-input v-model="form.recommendations" type="textarea" :rows="3" /></el-form-item></el-col>
        </el-row>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'
import { siteSurveysApi } from '@/api/siteSurveys'

const router = useRouter()
const route = useRoute()
const saving = ref(false)
const formRef = ref()
const form = ref({
  site_id: route.query.site_id ? Number(route.query.site_id) : undefined,
  survey_date: new Date(),
  surveyor_name: '',
  feasibility: 'feasible'
})

const rules = {
  site_id: [{ required: true, message: '请选择站点', trigger: 'change' }],
  survey_date: [{ required: true, message: '请选择勘察日期', trigger: 'change' }],
  surveyor_name: [{ required: true, message: '请输入勘察人', trigger: 'blur' }],
  feasibility: [{ required: true, message: '请选择结论', trigger: 'change' }]
}

const siteOptions = ref([])
const sitesLoaded = ref(false)
const loadSites = async () => {
  if (sitesLoaded.value) return
  try {
    const res = await request.get('/api/sites/', { params: { limit: 500 } })
    siteOptions.value = res || []
    sitesLoaded.value = true
  } catch (e) {
    // ignore
  }
}

const submit = async () => {
  try {
    await formRef.value.validate()
    saving.value = true
    const payload = { ...form.value }
    // ISO strings
    if (payload.survey_date instanceof Date) payload.survey_date = payload.survey_date.toISOString()
    const res = await siteSurveysApi.create(payload)
    ElMessage.success('保存成功')
    router.replace({ name: 'SiteSurveyDetail', params: { id: res.id } })
  } catch (e) {
    if (e) {
      console.error(e)
      ElMessage.error('保存失败')
    }
  } finally {
    saving.value = false
  }
}

const goBack = () => router.back()

onMounted(() => {
  if (form.value.site_id) loadSites()
})
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; gap: 12px; }
</style>

