<template>
  <el-dropdown trigger="click" @command="handleLocaleChange">
    <button class="locale-switcher" type="button">
      <el-icon><Operation /></el-icon>
      <span>{{ languageLabel }}</span>
      <el-icon class="arrow"><ArrowDown /></el-icon>
    </button>

    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="zh-CN" :disabled="currentLocale === 'zh-CN'">
          {{ t('common.chinese') }}
        </el-dropdown-item>
        <el-dropdown-item command="en-US" :disabled="currentLocale === 'en-US'">
          {{ t('common.english') }}
        </el-dropdown-item>
        <el-dropdown-item command="id-ID" :disabled="currentLocale === 'id-ID'">
          {{ t('common.indonesian') }}
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowDown, Operation } from '@element-plus/icons-vue'
import { getCurrentLocale, setAppLocale } from '../../i18n/translator'

const { locale, t } = useI18n()

const currentLocale = computed(() => locale.value || getCurrentLocale())
const languageLabel = computed(() => t('common.language'))

const handleLocaleChange = async (nextLocale) => {
  await setAppLocale(nextLocale)
}
</script>

<style scoped lang="scss">
.locale-switcher {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: #fff;
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    border-color: var(--primary-color);
    color: var(--primary-color);
  }

  .arrow {
    font-size: 12px;
  }
}

@media (max-width: 768px) {
  .locale-switcher {
    padding: 0 8px;
  }
}
</style>
