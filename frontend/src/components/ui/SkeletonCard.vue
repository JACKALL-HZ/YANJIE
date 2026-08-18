<script setup lang="ts">
withDefaults(defineProps<{ lines?: number; hasTitle?: boolean }>(), {
  lines: 3,
  hasTitle: true,
})
</script>

<template>
  <div class="glass rounded-card p-6" aria-busy="true" aria-label="加载中">
    <div v-if="hasTitle" class="skeleton mb-4 h-5 w-2/5" />
    <div
      v-for="n in lines"
      :key="n"
      class="skeleton mb-3 h-3.5 last:mb-0"
      :style="{ width: `${88 - n * 12}%` }"
    />
  </div>
</template>
