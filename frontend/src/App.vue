<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import AppBackground from '@/components/layout/AppBackground.vue'
import { useAuthStore } from '@/stores/auth'
import { useSimulationStore } from '@/stores/simulation'

const route = useRoute()
const showBackground = computed(() => !route.meta.hideBackground)
const auth = useAuthStore()
const simulation = useSimulationStore()

watch(
  () => auth.user?.id ?? null,
  (userId, previousUserId) => {
    if (userId !== previousUserId) simulation.reset()
  },
)

onMounted(() => {
  auth.loadMe()
})
</script>

<template>
  <div class="min-h-screen overflow-x-hidden">
    <AppBackground v-if="showBackground" />

    <RouterView v-slot="{ Component }">
      <Transition
        enter-active-class="transition duration-300 ease-smooth"
        enter-from-class="opacity-0 translate-y-2"
        leave-active-class="transition duration-200 ease-smooth"
        leave-to-class="opacity-0"
        mode="out-in"
      >
        <KeepAlive include="SimView,CompareView">
          <component
            :is="Component"
            :key="`${auth.user?.id || 'anonymous'}:${String(route.name || '')}`"
          />
        </KeepAlive>
      </Transition>
    </RouterView>
  </div>
</template>
