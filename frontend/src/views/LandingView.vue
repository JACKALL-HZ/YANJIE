<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import NavBar from '@/components/layout/NavBar.vue'
import FancyButton from '@/components/ui/FancyButton.vue'
import GlassPanel from '@/components/ui/GlassPanel.vue'
import ParticleField from '@/components/motion/ParticleField.vue'
import ScrollVelocity from '@/components/motion/ScrollVelocity.vue'
import TypewriterText from '@/components/motion/TypewriterText.vue'

const router = useRouter()

const heroReady = ref(false)
onMounted(() => {
  requestAnimationFrame(() => (heroReady.value = true))
})

/* ── 自然语言输入 ────────────────────────── */
const userQuery = ref('')

function handleSubmit() {
  const q = userQuery.value.trim()
  if (!q) return
  // 统一由 BreakdownView 调用一次拆解接口，避免主页重复请求和场景结果不同步。
  void router.push({ name: 'breakdown', query: { query: q } })
}

const decisionSteps = [
  {
    id: 'clarify', num: '01', title: '澄清价值', en: '第一步',
    desc: '抛开所有“应该”，列出你生命中最重要的三样东西。',
  },
  {
    id: 'preview', num: '02', title: '预演结果', en: '第二步',
    desc: '想象选择 A 和 B 后，一天、一年、十年的生活图景，感受身体的反应。',
  },
  {
    id: 'risk', num: '03', title: '风险评估', en: '第三步',
    desc: '评估最坏的结果你是否能承受，这往往能释放不必要的恐惧。',
  },
]

const marqueeTexts = ['决策需要指南，而非硬币', 'DECISION NEEDS A GUIDE']
</script>

<template>
  <div class="min-h-[100dvh] bg-abyss">
    <NavBar />

    <!-- ── Hero：视频背景 ─────────────────────────── -->
    <section class="relative flex min-h-[100dvh] items-center justify-center overflow-hidden">
      <video
        class="absolute inset-0 h-full w-full object-cover"
        src="/assets/videos/hero-earth.mp4"
        poster="/assets/videos/hero-poster.jpg"
        autoplay muted loop playsinline preload="metadata"
        aria-hidden="true"
      />
      <div class="absolute inset-0 bg-gradient-to-b from-abyss/70 via-abyss/40 to-abyss" />
      <div class="absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_0%,rgba(11,15,26,0.55)_100%)]" />

      <div
        class="relative z-10 mx-auto max-w-[900px] px-5 text-center transition-all duration-1000 ease-smooth md:px-8"
        :class="heroReady ? 'translate-y-0 opacity-100' : 'translate-y-8 opacity-0'"
      >
        <p class="eyebrow mb-6 animate-fade-up">AI 决策推演工作台</p>
        <h1 class="font-display text-[clamp(3.5rem,10vw,7rem)] font-bold leading-none tracking-tighter">
          <span class="brand-word"><span class="bw-char">衍</span><span class="bw-char">界</span></span>
        </h1>
        <p class="mt-6 text-[clamp(1.25rem,2.8vw,1.75rem)] font-light text-ink-primary">
          <TypewriterText text="当面临重大选择时" :speed="70" />
        </p>
        <p class="mx-auto mt-8 max-w-[520px] text-sm leading-relaxed text-ink-muted md:text-base">
          站在人生的十字路口，我理解那份沉重的犹豫。先把选择放进推演，再决定下一步怎么走。
        </p>

        <div class="mt-12 flex flex-col items-center gap-4">
          <div class="relative w-full max-w-[560px]">
            <input
              v-model="userQuery"
              type="text"
              placeholder="描述你正在面对的选择，例如：要不要换工作、创业，或买房…"
              class="w-full rounded-2xl border border-white/10 bg-white/[0.06] px-6 py-4 text-base text-ink-primary outline-none backdrop-blur-md transition-all duration-300 placeholder:text-ink-muted/60 focus:border-brand/60 focus:bg-white/[0.09] focus:shadow-[0_0_40px_rgba(79,140,255,0.15)] disabled:opacity-60"
              @keydown.enter="handleSubmit"
            />
            <span v-if="userQuery.length > 0" class="absolute right-4 top-1/2 -translate-y-1/2 font-mono text-xs text-ink-muted/50">{{ userQuery.length }}</span>
          </div>

          <FancyButton size="lg" :disabled="!userQuery.trim()" @click="handleSubmit">
            开始推演
          </FancyButton>

          <RouterLink to="/library" class="text-xs text-ink-muted transition-colors hover:text-ink-secondary">
            或者先浏览场景库，了解可推演的世界
          </RouterLink>
        </div>
      </div>

      <div class="absolute bottom-8 left-1/2 z-10 -translate-x-1/2">
        <div class="flex h-9 w-6 items-start justify-center rounded-full border border-white/20 p-1.5">
          <div class="h-2 w-1 animate-bounce rounded-full bg-cyan-glow/80" />
        </div>
      </div>
    </section>

    <!-- ── ScrollVelocity 分隔带 ───────────────────── -->
    <section class="relative border-y border-white/5 bg-abyss-2/80 py-10">
      <ScrollVelocity
        :texts="marqueeTexts"
        :base-velocity="2"
        :num-copies="5"
        class-name="font-display text-[clamp(2rem,5vw,3.5rem)] font-bold tracking-tight text-white/[0.07]"
      />
    </section>

    <!-- ── 三步决策引导 ───────────────────────────── -->
    <section class="relative mx-auto max-w-[1400px] px-5 py-24 md:px-8 md:py-32">
      <ParticleField class="opacity-40" />
      <div class="relative z-10">
        <p class="eyebrow mb-4">面对选择</p>
        <h2 class="max-w-[680px] font-display text-3xl font-bold tracking-tight md:text-5xl">先把犹豫拆成三个能回答的问题</h2>
        <div class="mt-14 grid gap-5 md:grid-cols-3 md:gap-6">
          <GlassPanel v-for="(step, i) in decisionSteps" :key="step.id" spotlight class="group animate-fade-up" :style="{ animationDelay: `${i * 120}ms` }">
            <div class="mb-6 flex items-baseline justify-between">
              <span class="font-mono text-sm text-cyan-glow/70">{{ step.num }}</span>
              <span class="font-mono text-[10px] tracking-[0.2em] text-ink-muted transition-colors group-hover:text-ink-secondary">{{ step.en }}</span>
            </div>
            <h3 class="font-display text-2xl font-bold tracking-tight">{{ step.title }}</h3>
            <p class="mt-3 text-sm leading-relaxed text-ink-secondary">{{ step.desc }}</p>
          </GlassPanel>
        </div>
      </div>
    </section>

    <!-- ── CTA ────────────────────────────────────── -->
    <section class="relative overflow-hidden border-t border-white/5">
      <div class="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom,rgba(79,140,255,0.12),transparent_60%)]" />
      <div class="relative z-10 mx-auto max-w-[800px] px-5 py-24 text-center md:py-32">
        <h2 class="font-display text-3xl font-bold tracking-tight md:text-5xl">决策需要指南，<br class="sm:hidden" />而非硬币</h2>
        <p class="mx-auto mt-6 max-w-[520px] text-sm leading-relaxed text-ink-muted md:text-base">如果你需要梳理思路，我愿成为你的“思考伙伴”。把眼前的选择交给衍界，先看清路径，再做决定。</p>
        <div class="mt-10 flex justify-center">
          <RouterLink to="/library">
            <FancyButton size="lg">开始第一次推演</FancyButton>
          </RouterLink>
        </div>
      </div>
    </section>

    <!-- ── Footer ─────────────────────────────────── -->
    <footer class="border-t border-white/5 py-8">
      <div class="mx-auto flex max-w-[1400px] flex-col items-center justify-between gap-3 px-5 text-xs text-ink-muted md:flex-row md:px-8">
        <span class="font-mono tracking-wider">衍界 AI · 决策推演工作台</span>
        <span>让每一个选择都有回响</span>
      </div>
    </footer>
  </div>
</template>

<style scoped>
/* ── 衍界 · 品牌字动效 ─────────────────────────────
   入场 reveal → 深空冰蓝渐变流动 + 锐利扫光 + 错峰漂浮
   + 空气感辉光呼吸 + 全息底座光线
   全部 transform / filter / background-position，60fps 友好 */
.brand-word {
  position: relative;
  display: inline-flex;
  cursor: default;
  transition: transform 0.5s cubic-bezier(0.16, 1, 0.3, 1);
  animation: bwIn 1.4s cubic-bezier(0.16, 1, 0.3, 1) backwards;
}
.brand-word:hover {
  transform: scale(1.035) translateY(-2px);
}

/* 全息底座：字下一条青蓝光线，呼吸伸缩 */
.brand-word::after {
  content: '';
  position: absolute;
  left: 6%;
  right: 6%;
  bottom: -0.16em;
  height: 3px;
  border-radius: 999px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(158, 232, 255, 0.95) 35%,
    rgba(79, 140, 255, 0.95) 65%,
    transparent
  );
  filter: blur(3px);
  animation: bwHalo 3.4s ease-in-out infinite;
  pointer-events: none;
}

.bw-char {
  display: inline-block;
  /* 第一层 = 锐利扫光带，第二层 = 深空冰蓝主渐变（同色相明度起伏，首尾同色 → 无缝循环） */
  background-image:
    linear-gradient(115deg, transparent 45%, rgba(255, 255, 255, 0.95) 50%, transparent 55%),
    linear-gradient(100deg, #f4f9ff 0%, #9be8ff 22%, #4fc3ff 45%, #3d7bff 68%, #8fd8ff 88%, #f4f9ff 100%);
  background-size: 240% 100%, 300% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  -webkit-text-stroke: 1px rgba(190, 225, 255, 0.18);
  animation:
    bwShift 4.6s linear infinite,
    bwFloat 4.6s ease-in-out infinite,
    bwGlow 3.4s ease-in-out infinite;
}
/* 第二字全部错峰，形成波浪联动 */
.bw-char:last-child {
  animation-delay: -0.6s, -2.3s, -1.7s;
}

/* 入场：模糊 + 放大 + 上浮，落定后交还给循环动画 */
@keyframes bwIn {
  from {
    opacity: 0;
    transform: translateY(26px) scale(1.22);
    filter: blur(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
    filter: blur(0);
  }
}

/* 扫光前 34% 时间掠过字面，主渐变全程匀速流动（0→300% 无缝） */
@keyframes bwShift {
  0% {
    background-position: -150% 0, 0% 0;
  }
  34% {
    background-position: 150% 0, 102% 0;
  }
  100% {
    background-position: 150% 0, 300% 0;
  }
}

/* 漂浮呼吸 */
@keyframes bwFloat {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-7px);
  }
}

/* 空气感辉光：低饱和冰青 ↔ 深空蓝，大半径柔光 */
@keyframes bwGlow {
  0%,
  100% {
    filter: drop-shadow(0 0 18px rgba(125, 211, 252, 0.55))
      drop-shadow(0 0 55px rgba(79, 140, 255, 0.32));
  }
  50% {
    filter: drop-shadow(0 0 30px rgba(158, 232, 255, 0.9))
      drop-shadow(0 0 90px rgba(96, 165, 250, 0.5));
  }
}

/* 全息底座呼吸 */
@keyframes bwHalo {
  0%,
  100% {
    opacity: 0.35;
    transform: scaleX(0.82);
  }
  50% {
    opacity: 0.9;
    transform: scaleX(1);
  }
}

/* 无障碍降级：用户系统开"减少动态"时回到静态高级渐变 */
@media (prefers-reduced-motion: reduce) {
  .brand-word,
  .brand-word:hover {
    animation: none;
    transform: none;
  }
  .brand-word::after {
    animation: none;
    opacity: 0.5;
  }
  .bw-char {
    animation: none;
    filter: drop-shadow(0 0 20px rgba(125, 211, 252, 0.5));
  }
}
</style>
