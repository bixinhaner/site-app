<template>
  <el-config-provider :locale="elementLocale">
    <div class="app-shell">
      <router-view />
    </div>
  </el-config-provider>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import en from 'element-plus/es/locale/lang/en'
import id from 'element-plus/es/locale/lang/id'
import { useUserStore } from './stores/user'
import { useLegacyDomI18n } from './i18n/useLegacyDomI18n'
import { ensureLegacyMapLoaded } from './i18n/translator'

const userStore = useUserStore()
const { locale } = useI18n()

const elementLocale = computed(() => {
  if (locale.value === 'zh-CN') return zhCn
  if (locale.value === 'id-ID') return id
  return en
})

useLegacyDomI18n()

onMounted(async () => {
  await ensureLegacyMapLoaded(locale.value)
  await userStore.initialize()
})
</script>

<style scoped lang="scss">
.app-shell {
  min-height: 100vh;
}
</style>
