<template>
  <div class="site-progress">
    <div class="section-head">
      <h2 class="section-title">{{ t('dashboard.siteOverview.title') }}</h2>
      <el-button v-if="canViewSiteMap" class="map-jump-btn" type="primary" plain size="small" @click="goToSiteMap">
        <el-icon><MapLocation /></el-icon>
        {{ t('dashboard.siteOverview.mapButton') }}
      </el-button>
    </div>
    <div class="cards">
      <div class="card" v-for="card in cards" :key="card.key" @click="onClick(card.route)">
        <div class="card-header">
          <el-icon :class="['icon', card.type]">
            <component :is="card.icon" />
          </el-icon>
          <span class="title">{{ card.title }}</span>
        </div>
        <div class="card-body">
          <div class="value-block">
            <div class="value">{{ card.value }}</div>
            <div v-if="card.fraction" class="device-fraction">{{ card.fraction }}</div>
          </div>
          <div class="desc">{{ card.desc }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Tickets, Finished, Promotion, MagicStick, SuccessFilled, OfficeBuilding, MapLocation } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/stores/user'

const props = defineProps({ progress: { type: Object, default: null } })
const emit = defineEmits(['goto'])
const userStore = useUserStore()
const { t } = useI18n()

const total = computed(() => Number(props.progress?.total || 0))
const val = (k) => Number(props.progress?.[k] || 0)
const valWithFallback = (key, fallbackKey) => {
  if (props.progress?.[key] === undefined || props.progress?.[key] === null) {
    return val(fallbackKey)
  }
  return Number(props.progress?.[key] || 0)
}
const deviceFraction = (key, type) => {
  const bucket = props.progress?.device_progress?.[key]
  const denominator = Number(bucket?.denominator || 0)
  if (!denominator) return ''
  const numerator = Number(bucket?.numerator || 0)
  return t(`dashboard.siteOverview.deviceFraction.${type}`, { numerator, denominator })
}
const canViewSiteMap = computed(() => userStore.hasPermission('sites:list:read'))
const siteListRoute = (siteProgressFilter) => ({
  name: 'SiteList',
  query: { site_progress_filter: siteProgressFilter },
})

const cards = computed(() => [
  { key: 'survey', title: t('dashboard.siteOverview.cards.survey.title'), value: `${val('survey_done')}/${total.value}`, desc: t('dashboard.siteOverview.cards.survey.desc'), icon: Tickets, type: 'info', route: siteListRoute('survey_done') },
  { key: 'planning', title: t('dashboard.siteOverview.cards.planning.title'), value: `${val('planning_done')}/${total.value}`, desc: t('dashboard.siteOverview.cards.planning.desc'), icon: Finished, type: 'primary', route: siteListRoute('planning_done') },
  { key: 'install_started', title: t('dashboard.siteOverview.cards.installStarted.title'), value: `${val('install_started')}/${total.value}`, desc: t('dashboard.siteOverview.cards.installStarted.desc'), icon: OfficeBuilding, type: 'install-start', route: siteListRoute('install_started') },
  { key: 'installed', title: t('dashboard.siteOverview.cards.installed.title'), value: `${val('installed')}/${total.value}`, desc: t('dashboard.siteOverview.cards.installed.desc'), icon: OfficeBuilding, type: 'install', route: siteListRoute('installed') },
  { key: 'partial_online', title: t('dashboard.siteOverview.cards.partialOnline.title'), value: `${val('partial_online')}/${total.value}`, desc: t('dashboard.siteOverview.cards.partialOnline.desc'), icon: Promotion, type: 'partial-online', route: siteListRoute('partial_online'), fraction: deviceFraction('partial_online', 'online') },
  { key: 'fully_online', title: t('dashboard.siteOverview.cards.fullyOnline.title'), value: `${valWithFallback('fully_online', 'online')}/${total.value}`, desc: t('dashboard.siteOverview.cards.fullyOnline.desc'), icon: Promotion, type: 'success', route: siteListRoute('fully_online'), fraction: deviceFraction('fully_online', 'online') },
  { key: 'partial_activated', title: t('dashboard.siteOverview.cards.partialActivated.title'), value: `${val('partial_activated')}/${total.value}`, desc: t('dashboard.siteOverview.cards.partialActivated.desc'), icon: MagicStick, type: 'partial-activated', route: siteListRoute('partial_activated'), fraction: deviceFraction('partial_activated', 'activated') },
  { key: 'fully_activated', title: t('dashboard.siteOverview.cards.fullyActivated.title'), value: `${valWithFallback('fully_activated', 'activated')}/${total.value}`, desc: t('dashboard.siteOverview.cards.fullyActivated.desc'), icon: MagicStick, type: 'warning', route: siteListRoute('fully_activated'), fraction: deviceFraction('fully_activated', 'activated') },
  { key: 'ssv', title: t('dashboard.siteOverview.cards.ssv.title'), value: `${val('ssv_passed')}/${total.value}`, desc: t('dashboard.siteOverview.cards.ssv.desc'), icon: SuccessFilled, type: 'success', route: siteListRoute('ssv_passed') },
])

const onClick = (route) => emit('goto', route)
const goToSiteMap = () => emit('goto', { name: 'SiteMap' })
</script>

<style scoped lang="scss">
.site-progress {
  margin-bottom: 20px;
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.section-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}
.map-jump-btn {
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  border-color: #1d4ed8;
  color: #fff;
  border-radius: 999px;
  padding-inline: 14px;
  font-weight: 600;
}

.map-jump-btn:hover,
.map-jump-btn:focus {
  background: linear-gradient(135deg, #1d4ed8, #1e40af);
  border-color: #1e40af;
  color: #fff;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.card {
  background: #fff;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: all .2s ease;
}
.card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,.08); }
.card-header { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
.icon { width:32px; height:32px; border-radius:8px; display:flex; align-items:center; justify-content:center; color:#fff; }
.icon.info { background: linear-gradient(45deg,#3b82f6,#60a5fa); }
.icon.primary { background: linear-gradient(45deg,#f97316,#fb923c); }
.icon.success { background: linear-gradient(45deg,#10b981,#34d399); }
.icon.warning { background: linear-gradient(45deg,#f59e0b,#fbbf24); }
.icon.install { background: linear-gradient(45deg,#0ea5e9,#22d3ee); }
.icon.install-start { background: linear-gradient(45deg,#14b8a6,#2dd4bf); }
.title { font-weight: 600; color: var(--text-secondary); }
.card-body { display:flex; align-items:flex-start; gap:10px; min-height: 48px; }
.value-block { flex: 0 0 auto; min-width: 74px; }
.value { font-size: 28px; font-weight: 700; color: var(--text-primary); }
.device-fraction { margin-top: 2px; color: var(--text-light); font-size: 12px; line-height: 1.25; white-space: nowrap; }
.desc { padding-top: 8px; color: var(--text-light); font-size: 13px; line-height: 1.35; }
.icon.partial-online { background: linear-gradient(45deg,#0ea5e9,#10b981); }
.icon.partial-activated { background: linear-gradient(45deg,#f97316,#f59e0b); }

@media (max-width: 768px) {
  .section-head {
    align-items: stretch;
    flex-direction: column;
  }

  .map-jump-btn {
    width: 100%;
  }
}
</style>
