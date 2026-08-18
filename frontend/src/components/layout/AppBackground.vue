<script setup lang="ts">
/**
 * AppBackground — 全局氛围背景（对齐素材库 v2 稿）：
 *   1. 基底径向渐变（body 层级）
 *   2. Galaxy WebGL 星图
 *   3. atmos 双色漂移光斑（brand + cyan，screen 混合）
 *   4. grain SVG 噪点（soft-light，电影颗粒感）
 * Landing 主页有自己的视频 Hero，不挂此背景。
 */
import { defineAsyncComponent } from 'vue'

const GalaxyBackground = defineAsyncComponent(
  () => import('@/components/three/GalaxyBackground.vue'),
)
</script>

<template>
  <!-- 1. 基底渐变 -->
  <div
    class="pointer-events-none fixed inset-0 -z-10"
    style="background: radial-gradient(120% 80% at 50% -10%, #0d1320, #0b0f1a 60%)"
    aria-hidden="true"
  />

  <!-- 2. Galaxy 星图 -->
  <GalaxyBackground />

  <!-- 3. atmos 漂移光斑 -->
  <div class="atmos pointer-events-none fixed inset-0 -z-[8] overflow-hidden" aria-hidden="true" />

  <!-- 4. grain 噪点 -->
  <div class="grain pointer-events-none fixed inset-0 z-[60]" aria-hidden="true" />
</template>

<style scoped>
.atmos {
  background: radial-gradient(
    42vw 42vw at 80% 10%,
    rgba(34, 211, 238, 0.14),
    transparent 70%
  );
}
.atmos::before,
.atmos::after {
  content: '';
  position: absolute;
  border-radius: 50%;
  filter: blur(95px);
  mix-blend-mode: screen;
}
.atmos::before {
  width: 66vw;
  height: 66vw;
  top: -14vw;
  left: -8vw;
  opacity: 0.32;
  background: radial-gradient(circle, rgba(79, 140, 255, 0.5), transparent 70%);
  animation: drift1 26s ease-in-out infinite alternate;
}
.atmos::after {
  width: 60vw;
  height: 60vw;
  bottom: -18vw;
  right: -12vw;
  opacity: 0.28;
  background: radial-gradient(circle, rgba(34, 211, 238, 0.45), transparent 70%);
  animation: drift2 32s ease-in-out infinite alternate;
}
@keyframes drift1 {
  to {
    transform: translate(9vw, 7vw) scale(1.18);
  }
}
@keyframes drift2 {
  to {
    transform: translate(-7vw, -5vw) scale(1.12);
  }
}

.grain {
  opacity: 0.03;
  mix-blend-mode: soft-light;
  background-size: 180px 180px;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
}

@media (prefers-reduced-motion: reduce) {
  .atmos::before,
  .atmos::after {
    animation: none;
  }
}
</style>
