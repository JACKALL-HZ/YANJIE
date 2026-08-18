<script setup lang="ts">
/**
 * FancyButton — 基于素材库 fancy-button.html 的 3D 按压质感按钮，
 * 深色科技风改造：保留多层 inset box-shadow 的物理按压感，
 * 配色换为品牌蓝渐变 + 按压下沉。纯 CSS 动效，零 JS 开销。
 */
withDefaults(
  defineProps<{
    variant?: 'primary' | 'ghost'
    size?: 'sm' | 'md' | 'lg'
    disabled?: boolean
  }>(),
  { variant: 'primary', size: 'md', disabled: false },
)

const emit = defineEmits<{ click: [e: MouseEvent] }>()
</script>

<template>
  <button
    class="fancy-btn"
    :class="[`fancy-btn--${variant}`, `fancy-btn--${size}`]"
    :disabled="disabled"
    @click="emit('click', $event)"
  >
    <span class="fancy-btn__outer">
      <span class="fancy-btn__inner">
        <span class="fancy-btn__label"><slot /></span>
      </span>
    </span>
  </button>
</template>

<style scoped>
.fancy-btn {
  all: unset;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  position: relative;
  display: inline-block;
  border-radius: 100em;
}
.fancy-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
.fancy-btn__outer {
  position: relative;
  display: block;
  border-radius: inherit;
  transition: box-shadow 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  will-change: box-shadow;
}

/* —— primary：品牌蓝渐变胶囊 —— */
.fancy-btn--primary .fancy-btn__outer {
  box-shadow:
    0 0.35em 0.9em -0.2em rgba(79, 140, 255, 0.55),
    0 0.1em 0.3em -0.05em rgba(79, 140, 255, 0.4),
    0 0 0 1px rgba(79, 140, 255, 0.35);
}
.fancy-btn--primary:hover .fancy-btn__outer {
  box-shadow:
    0 0.15em 0.5em -0.15em rgba(79, 140, 255, 0.5),
    0 0.05em 0.15em -0.02em rgba(79, 140, 255, 0.35),
    0 0 0 1px rgba(107, 160, 255, 0.5);
}
.fancy-btn--primary .fancy-btn__inner {
  background-image: linear-gradient(135deg, #5f9bff 0%, #3f78e8 55%, #3567d6 100%);
  box-shadow:
    inset 0 0.08em 0.12em rgba(255, 255, 255, 0.35),
    inset 0 -0.1em 0.2em rgba(10, 30, 80, 0.5);
}
.fancy-btn--primary:hover .fancy-btn__inner {
  background-image: linear-gradient(135deg, #74abff 0%, #4f8cff 55%, #3f78e8 100%);
}
.fancy-btn--primary .fancy-btn__label {
  color: #f2f7ff;
  text-shadow: 0 1px 2px rgba(10, 30, 80, 0.6);
}

/* —— ghost：液态玻璃 —— */
.fancy-btn--ghost .fancy-btn__outer {
  box-shadow:
    0 0.3em 0.8em -0.25em rgba(0, 0, 0, 0.6),
    0 0 0 1px rgba(255, 255, 255, 0.1);
}
.fancy-btn--ghost:hover .fancy-btn__outer {
  box-shadow:
    0 0.12em 0.4em -0.15em rgba(0, 0, 0, 0.55),
    0 0 0 1px rgba(255, 255, 255, 0.18);
}
.fancy-btn--ghost .fancy-btn__inner {
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(12px);
  box-shadow:
    inset 0 0.08em 0.12em rgba(255, 255, 255, 0.12),
    inset 0 -0.08em 0.16em rgba(0, 0, 0, 0.35);
}
.fancy-btn--ghost .fancy-btn__label {
  color: var(--tw-text, #e6eaf2);
}

.fancy-btn__inner {
  --inset: 0.035em;
  position: relative;
  display: block;
  border-radius: inherit;
  overflow: clip;
  clip-path: inset(0 0 0 0 round 100em);
  transition:
    clip-path 0.25s cubic-bezier(0.16, 1, 0.3, 1),
    transform 0.25s cubic-bezier(0.16, 1, 0.3, 1),
    background-image 0.25s ease;
  will-change: clip-path, transform;
}
.fancy-btn:hover .fancy-btn__inner {
  clip-path: inset(1px 1px 1px 1px round 100em);
}
.fancy-btn:active .fancy-btn__inner {
  transform: scale(0.965);
}

.fancy-btn__label {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5em;
  font-weight: 600;
  letter-spacing: -0.01em;
  user-select: none;
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  will-change: transform;
}
.fancy-btn:active .fancy-btn__label {
  transform: scale(0.97);
}

.fancy-btn--sm .fancy-btn__label {
  padding: 0.5em 1.1em;
  font-size: 0.82rem;
}
.fancy-btn--md .fancy-btn__label {
  padding: 0.72em 1.6em;
  font-size: 0.95rem;
}
.fancy-btn--lg .fancy-btn__label {
  padding: 0.95em 2.2em;
  font-size: 1.05rem;
}
</style>
