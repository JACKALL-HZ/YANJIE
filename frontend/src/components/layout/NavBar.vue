<script setup lang="ts">
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import FancyButton from '@/components/ui/FancyButton.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const onLanding = computed(() => route.name === 'landing')

const links = [
  { to: '/library', label: '场景库' },
  { to: '/sim', label: '推演' },
  { to: '/profile', label: '画像' },
  { to: '/history', label: '历史' },
  { to: '/diary', label: '日记' },
]

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <header
    class="fixed inset-x-0 top-0 z-50 transition-all duration-300"
    :class="onLanding ? 'bg-transparent' : 'glass-strong border-b border-white/5'"
  >
    <nav class="mx-auto flex h-16 max-w-[1400px] items-center justify-between px-5 md:px-8">
      <RouterLink to="/" class="group flex items-baseline gap-2">
        <span class="font-display text-xl font-bold tracking-tight text-ink-primary">
          衍界
        </span>
        <span class="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-ink-muted transition-colors group-hover:text-cyan-glow">
          YanJie AI
        </span>
      </RouterLink>

      <div class="flex items-center gap-0.5 overflow-x-auto md:gap-2">
        <RouterLink
          v-for="l in links"
          :key="l.to"
          :to="l.to"
          class="whitespace-nowrap rounded-btn px-2.5 py-2 text-[13px] text-ink-secondary transition-all duration-200 hover:bg-white/5 hover:text-ink-primary md:px-4 md:text-sm"
          active-class="!text-ink-primary bg-white/5"
        >
          {{ l.label }}
        </RouterLink>
      </div>

      <div class="ml-2 flex shrink-0 items-center gap-2">
        <template v-if="auth.user">
          <span class="hidden text-sm text-ink-secondary sm:inline">
            {{ auth.user.username }}
          </span>
          <FancyButton size="sm" variant="ghost" @click="logout">
            退出
          </FancyButton>
        </template>
        <template v-else>
          <RouterLink
            to="/login"
            class="rounded-btn px-3 py-2 text-sm text-ink-secondary transition hover:text-ink-primary"
          >
            登录
          </RouterLink>
          <RouterLink to="/register">
            <FancyButton size="sm">注册</FancyButton>
          </RouterLink>
        </template>
      </div>
    </nav>
  </header>
</template>
