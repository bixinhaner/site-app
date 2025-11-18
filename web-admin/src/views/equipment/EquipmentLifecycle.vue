<template>
  <div class="page">
    <div class="page-header">
      <h1>设备生命周期追踪</h1>
      <el-input
        v-model="searchSN"
        placeholder="输入设备序列号查询"
        clearable
        style="width: 400px"
        @keyup.enter="searchEquipment"
      >
        <template #append>
          <el-button :icon="Search" @click="searchEquipment" />
        </template>
      </el-input>
    </div>

    <EquipmentLifecycleTimeline
      v-if="searchSN"
      :sn="searchSN"
    />
    <el-empty
      v-else
      description="请输入设备序列号开始查询"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import EquipmentLifecycleTimeline from '@/components/equipment/EquipmentLifecycleTimeline.vue'

const route = useRoute()

const searchSN = ref('')

// 搜索设备
const searchEquipment = async () => {
  if (!searchSN.value.trim()) {
    ElMessage.warning('请输入设备序列号')
    return
  }

  try {
    // 这里只负责触发查询，实际数据加载在子组件中完成
    if (!searchSN.value.trim()) {
      return
    }
  } catch (error) {
    console.error('查询设备失败:', error)
    ElMessage.error('查询设备失败')
  }
}

onMounted(() => {
  const snParam = route.query.sn || route.query.serial_number
  if (snParam) {
    searchSN.value = String(snParam)
    searchEquipment()
  }
})
</script>

<style scoped>
.page {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.equipment-overview {
  margin-bottom: 24px;
}

.lifecycle-container {
  padding: 16px 0;
}

.stage-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.operator-info {
  color: #909399;
  font-size: 14px;
}

.stage-content {
  .stage-description {
    margin: 0 0 16px 0;
    color: #606266;
    font-size: 14px;
  }

  .location-info {
    margin-top: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
    color: #909399;
    font-size: 13px;
    font-family: 'Courier New', monospace;
  }
}
</style>
