<template>
  <section v-if="visible" class="cell-expansion">
    <div class="section-head">
      <div>
        <h2 class="section-title">{{ t('dashboard.cellExpansionOverview.title') }}</h2>
        <p class="section-subtitle">{{ t('dashboard.cellExpansionOverview.subtitle') }}</p>
      </div>
      <el-button size="small" plain type="primary" @click="onClick(baseRoute)">
        <el-icon><Tickets /></el-icon>
        {{ t('dashboard.cellExpansionOverview.viewOrders') }}
      </el-button>
    </div>

    <div class="cards">
      <button v-for="card in cards" :key="card.key" class="card" type="button" @click="onClick(card.route)">
        <span class="card-icon" :class="card.type">
          <el-icon><component :is="card.icon" /></el-icon>
        </span>
        <span class="card-main">
          <span class="card-title">{{ card.title }}</span>
          <span class="card-value">{{ card.value }}</span>
          <span class="card-desc">{{ card.desc }}</span>
        </span>
      </button>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { CircleCheck, Connection, Finished, MagicStick, OfficeBuilding, Promotion, Tickets } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  progress: { type: Object, default: null },
})

const emit = defineEmits(['goto'])
const { t } = useI18n()

const baseRoute = { name: 'WorkOrderList', query: { type: 'cell_expansion' } }
const activeRoute = {
  name: 'WorkOrderList',
  query: { type: 'cell_expansion', status_in: 'PENDING,ACTIVE,SUBMITTED,UNDER_REVIEW,APPROVED,ACTIVATED' },
}
const completedRoute = { name: 'WorkOrderList', query: { type: 'cell_expansion', status: 'COMPLETED' } }

const n = (value) => Number(value || 0)
const visible = computed(() => Boolean(props.progress?.visible && n(props.progress?.orders?.total) > 0))
const newDevices = computed(() => props.progress?.new_devices || {})
const denominator = computed(() => n(newDevices.value?.total))
const fraction = (key) => `${n(newDevices.value?.[key])}/${denominator.value}`

const cards = computed(() => [
  {
    key: 'sites',
    title: t('dashboard.cellExpansionOverview.cards.sites.title'),
    value: n(props.progress?.sites?.total),
    desc: t('dashboard.cellExpansionOverview.cards.sites.desc'),
    icon: OfficeBuilding,
    type: 'site',
    route: baseRoute,
  },
  {
    key: 'newCells',
    title: t('dashboard.cellExpansionOverview.cards.newCells.title'),
    value: n(props.progress?.new_cells?.total),
    desc: t('dashboard.cellExpansionOverview.cards.newCells.desc'),
    icon: Connection,
    type: 'cell',
    route: baseRoute,
  },
  {
    key: 'bound',
    title: t('dashboard.cellExpansionOverview.cards.bound.title'),
    value: fraction('bound'),
    desc: t('dashboard.cellExpansionOverview.cards.bound.desc'),
    icon: CircleCheck,
    type: 'bound',
    route: baseRoute,
  },
  {
    key: 'online',
    title: t('dashboard.cellExpansionOverview.cards.online.title'),
    value: fraction('online'),
    desc: t('dashboard.cellExpansionOverview.cards.online.desc', {
      full: n(props.progress?.online?.full_sites),
      partial: n(props.progress?.online?.partial_sites),
    }),
    icon: Promotion,
    type: 'online',
    route: baseRoute,
  },
  {
    key: 'activated',
    title: t('dashboard.cellExpansionOverview.cards.activated.title'),
    value: fraction('activated'),
    desc: t('dashboard.cellExpansionOverview.cards.activated.desc', {
      full: n(props.progress?.activated?.full_sites),
      partial: n(props.progress?.activated?.partial_sites),
    }),
    icon: MagicStick,
    type: 'activated',
    route: baseRoute,
  },
  {
    key: 'activeOrders',
    title: t('dashboard.cellExpansionOverview.cards.activeOrders.title'),
    value: n(props.progress?.orders?.active),
    desc: t('dashboard.cellExpansionOverview.cards.activeOrders.desc'),
    icon: Tickets,
    type: 'active',
    route: activeRoute,
  },
  {
    key: 'completedOrders',
    title: t('dashboard.cellExpansionOverview.cards.completedOrders.title'),
    value: n(props.progress?.orders?.completed),
    desc: t('dashboard.cellExpansionOverview.cards.completedOrders.desc'),
    icon: Finished,
    type: 'done',
    route: completedRoute,
  },
])

const onClick = (route) => emit('goto', route)
</script>

<style scoped lang="scss">
.cell-expansion {
  margin-bottom: 20px;
}

.section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 10px;
}

.section-title {
  margin: 0;
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 700;
}

.section-subtitle {
  margin: 4px 0 0;
  color: var(--text-light);
  font-size: 13px;
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 10px;
}

.card {
  display: flex;
  min-height: 104px;
  align-items: flex-start;
  gap: 12px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: #fff;
  padding: 14px;
  text-align: left;
  cursor: pointer;
  transition: box-shadow .18s ease, transform .18s ease, border-color .18s ease;
}

.card:hover,
.card:focus-visible {
  border-color: #8bb8ff;
  box-shadow: 0 8px 20px rgba(15, 23, 42, .08);
  transform: translateY(-1px);
  outline: none;
}

.card-icon {
  display: inline-flex;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: #fff;
  font-size: 17px;
}

.card-icon.site { background: #2563eb; }
.card-icon.cell { background: #0f766e; }
.card-icon.bound { background: #16a34a; }
.card-icon.online { background: #0891b2; }
.card-icon.activated { background: #d97706; }
.card-icon.active { background: #4f46e5; }
.card-icon.done { background: #059669; }

.card-main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.card-title {
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.25;
}

.card-value {
  color: var(--text-primary);
  font-size: 24px;
  font-weight: 750;
  line-height: 1.1;
}

.card-desc {
  color: var(--text-light);
  font-size: 12px;
  line-height: 1.35;
}

@media (max-width: 768px) {
  .section-head {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
