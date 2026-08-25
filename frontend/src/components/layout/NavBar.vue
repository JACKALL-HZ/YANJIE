<script setup lang="ts">
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { computed, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import FancyButton from '@/components/ui/FancyButton.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const mobileOpen = ref(false)

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
function closeMenu() {
  mobileOpen.value = false
}
</script>

<template>
  <header
    class="fixed inset-x-0 top-0 z-50 transition-all duration-300"
    :class="onLanding ? 'bg-transparent' : 'glass-strong border-b border-white/5'"
  >
    <nav class="mx-auto flex h-16 max-w-[1400px] items-center justify-between px-5 md:px-8">
      <RouterLink to="/" class="group flex items-baseline gap-2" @click="closeMenu">
        <span class="font-display text-xl font-bold tracking-tight text-ink-primary">
          衍界
        </span>
        <span class="font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-ink-muted transition-colors group-hover:text-cyan-glow">
          YanJie AI
        </span>
      </RouterLink>

      <!-- 桌面导航 -->
      <div class="hidden items-center gap-0.5 md:flex md:gap-2">
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

      <!-- 桌面右侧 -->
      <div class="hidden shrink-0 items-center gap-2 md:flex">
        <template v-if="auth.user">
          <span class="text-sm text-ink-secondary">
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

      <!-- 移动端汉堡 -->
      <button
        class="flex h-10 w-10 items-center justify-center rounded-btn text-ink-secondary transition hover:bg-white/5 hover:text-ink-primary md:hidden"
        :aria-expanded="mobileOpen"
        aria-label="菜单"
        @click="mobileOpen = !mobileOpen"
      >
        <svg v-if="!mobileOpen" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M4 7h16M4 12h16M4 17h16" />
        </svg>
        <svg v-else width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>
    </nav>

    <!-- 移动端抽屉 -->
    <transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <div
        v-if="mobileOpen"
        class="glass-strong absolute inset-x-0 top-16 border-b border-white/5 px-5 py-4 md:hidden"
      >
        <div class="flex flex-col">
          <RouterLink
            v-for="l in links"
            :key="l.to"
            :to="l.to"
            class="rounded-btn px-3 py-3 text-base text-ink-secondary transition hover:bg-white/5 hover:text-ink-primary"
            active-class="!text-ink-primary bg-white/5"
            @click="closeMenu"
          >
            {{ l.label }}
          </RouterLink>
        </div>
        <div class="mt-3 flex items-center gap-3 border-t border-white/5 pt-4">
          <template v-if="auth.user">
            <span class="flex-1 text-sm text-ink-secondary">{{ auth.user.username }}</span>
            <FancyButton size="sm" variant="ghost" @click="logout(); closeMenu()">退出</FancyButton>
          </template>
          <template v-else>
            <RouterLink to="/login" class="flex-1 rounded-btn px-3 py-2 text-center text-sm text-ink-secondary transition hover:text-ink-primary" @click="closeMenu">登录</RouterLink>
            <RouterLink to="/register" class="flex-1" @click="closeMenu">
              <FancyButton size="sm" class="w-full">注册</FancyButton>
            </RouterLink>
          </template>
        </div>
      </div>
    </transition>
  </header>
</template>
