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
          <div class="value">{{ card.value }}</div>
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
const canViewSiteMap = computed(() => userStore.hasPermission('sites:list:read'))

const cards = computed(() => [
  { key: 'survey', title: t('dashboard.siteOverview.cards.survey.title'), value: `${val('survey_done')}/${total.value}`, desc: t('dashboard.siteOverview.cards.survey.desc'), icon: Tickets, type: 'info', route: { name: 'SurveyArchives' } },
  { key: 'planning', title: t('dashboard.siteOverview.cards.planning.title'), value: `${val('planning_done')}/${total.value}`, desc: t('dashboard.siteOverview.cards.planning.desc'), icon: Finished, type: 'primary', route: { name: 'SitePlanningLld' } },
  { key: 'install_started', title: t('dashboard.siteOverview.cards.installStarted.title'), value: `${val('install_started')}/${total.value}`, desc: t('dashboard.siteOverview.cards.installStarted.desc'), icon: OfficeBuilding, type: 'install-start', route: { name: 'WorkOrderList' } },
  { key: 'installed', title: t('dashboard.siteOverview.cards.installed.title'), value: `${val('installed')}/${total.value}`, desc: t('dashboard.siteOverview.cards.installed.desc'), icon: OfficeBuilding, type: 'install', route: { name: 'WorkOrderList', query: { preset: 'installed_sites' } } },
  { key: 'online', title: t('dashboard.siteOverview.cards.online.title'), value: `${val('online')}/${total.value}`, desc: t('dashboard.siteOverview.cards.online.desc'), icon: Promotion, type: 'success', route: { name: 'SiteList' } },
  { key: 'activated', title: t('dashboard.siteOverview.cards.activated.title'), value: `${val('activated')}/${total.value}`, desc: t('dashboard.siteOverview.cards.activated.desc'), icon: MagicStick, type: 'warning', route: { name: 'SiteList' } },
  { key: 'ssv', title: t('dashboard.siteOverview.cards.ssv.title'), value: `${val('ssv_passed')}/${total.value}`, desc: t('dashboard.siteOverview.cards.ssv.desc'), icon: SuccessFilled, type: 'success', route: { name: 'SiteList' } },
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
.card-body { display:flex; align-items:baseline; gap:10px; }
.value { font-size: 28px; font-weight: 700; color: var(--text-primary); }
.desc { color: var(--text-light); font-size: 13px; }

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
