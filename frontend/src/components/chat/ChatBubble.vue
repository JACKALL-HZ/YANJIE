<script setup lang="ts">
/**
 * ChatBubble — 通用聊天气泡。
 * role: 'user' | 'agent' — agent 可指定 agentId 来着色 (market/env/personal/risk)
 * typing: true 时显示打字动画（三点跳动）
 * Agent 消息自动渲染轻量 Markdown：**粗体** _斜体_ `代码` • 列表 换行
 */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    role: 'user' | 'agent'
    agentId?: string
    content: string
    typing?: boolean
    time?: string
  }>(),
  { agentId: '', typing: false, time: '' },
)

const agentMeta = computed(() => {
  const map: Record<string, { name: string; emoji: string; color: string; bg: string }> = {
    market:  { name: '市场智能体', emoji: '📊', color: '#4F8CFF', bg: 'rgba(79,140,255,0.12)' },
    environment: { name: '环境智能体', emoji: '🌍', color: '#34D399', bg: 'rgba(52,211,153,0.12)' },
    personal: { name: '个人智能体', emoji: '🧠', color: '#A78BFA', bg: 'rgba(167,139,250,0.12)' },
    risk:    { name: '风险智能体', emoji: '🛡️', color: '#F87171', bg: 'rgba(248,113,113,0.12)' },
    guide:   { name: '衍界向导',  emoji: '✦',  color: '#22D3EE', bg: 'rgba(34,211,238,0.1)' },
  }
  return map[props.agentId || ''] || null
})

/**
 * 轻量 Markdown → HTML（无外部依赖）
 * 支持：**粗体**  _斜体_  `代码`  • 列表项  换行  分隔线
 */
function renderMarkdown(text: string): string {
  let html = text
    // 转义 HTML 特殊字符（防止 XSS）
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // 行内代码 `...`（在 ** 之前处理，避免内部格式被误解析）
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')

  // **粗体**
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong class="text-ink-primary">$1</strong>')

  // _斜体_（不匹配 __ 下划线）
  html = html.replace(/(?<!_)_([^_]+)_(?!_)/g, '<em>$1</em>')

  // • 列表项 → 带缩进
  html = html.replace(/^[•●]\s+(.+)$/gm, '<li class="ml-2 list-disc marker:text-ink-muted">$1</li>')

  // 数字列表 1. 2. 等
  html = html.replace(/^(\d+)\.\s+(.+)$/gm, '<li class="ml-2">$1. $2</li>')

  // 连续多个 <li> 包裹进 <ul>
  html = html.replace(/((?:<li[^>]*>.*?<\/li>\n?)+)/g, '<ul class="space-y-0.5 my-1">$1</ul>')

  // --- 分隔线
  html = html.replace(/^---$/gm, '<hr class="border-white/10 my-2">')

  // 换行：双换行 → 段落分隔，单换行 → <br>
  html = html.replace(/\n\n/g, '</p><p class="min-h-[0.3em]">')
  html = html.replace(/\n/g, '<br>')

  // 包裹段落
  html = '<p>' + html + '</p>'

  return html
}

const formattedContent = computed(() => {
  if (props.role === 'user') return ''
  return renderMarkdown(props.content)
})
</script>

<template>
  <div
    class="flex gap-3"
    :class="role === 'user' ? 'flex-row-reverse' : 'flex-row'"
  >
    <!-- 头像 -->
    <div class="shrink-0 pt-0.5">
      <div
        v-if="role === 'agent' && agentMeta"
        class="flex h-8 w-8 items-center justify-center rounded-full text-sm"
        :style="{ backgroundColor: agentMeta.bg }"
      >
        {{ agentMeta.emoji }}
      </div>
      <div
        v-else-if="role === 'agent'"
        class="flex h-8 w-8 items-center justify-center rounded-full bg-cyan-glow/10 text-sm"
      >
        ✦
      </div>
      <div
        v-else
        class="flex h-8 w-8 items-center justify-center rounded-full bg-brand/15 text-xs font-medium text-brand"
      >
        你
      </div>
    </div>

    <!-- 气泡内容 -->
    <div class="max-w-[75%] min-w-0">
      <!-- Agent 名称 -->
      <div
        v-if="role === 'agent' && agentMeta"
        class="mb-1 text-[11px] font-medium"
        :style="{ color: agentMeta.color }"
      >
        {{ agentMeta.name }}
      </div>

      <!-- 气泡 -->
      <div
        class="rounded-2xl px-4 py-3 text-sm leading-relaxed"
        :class="role === 'user'
          ? 'rounded-tr-md bg-brand/15 text-ink-primary'
          : 'rounded-tl-md bg-white/[0.05] text-ink-secondary border border-white/5'"
      >
        <!-- Typing 动画（仅当内容为空时显示三点） -->
        <span v-if="typing && !content" class="flex gap-1 py-1">
          <span class="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-brand" />
          <span class="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-brand" style="animation-delay:0.15s" />
          <span class="h-1.5 w-1.5 animate-pulse-soft rounded-full bg-brand" style="animation-delay:0.3s" />
        </span>
        <!-- Agent 消息：渲染 Markdown（打字中逐字显示，完成后完整渲染） -->
        <span v-else-if="role === 'agent'" v-html="formattedContent" class="bubble-content" />
        <!-- 用户消息：纯文本 -->
        <span v-else>{{ content }}</span>
        <!-- 打字中光标 -->
        <span v-if="typing && content" class="ml-0.5 inline-block h-4 w-[2px] animate-pulse-soft bg-ink-primary align-middle">&#8203;</span>
      </div>

      <!-- 时间 -->
      <div
        v-if="time"
        class="mt-1 font-mono text-[10px] text-ink-muted/60"
        :class="role === 'user' ? 'text-right' : 'text-left'"
      >
        {{ time }}
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 气泡内的 Markdown 样式 */
.bubble-content :deep(p) {
  margin: 0;
}
.bubble-content :deep(p + p) {
  margin-top: 0.5em;
}
.bubble-content :deep(strong) {
  font-weight: 600;
}
.bubble-content :deep(em) {
  font-style: italic;
  opacity: 0.85;
}
.bubble-content :deep(.inline-code) {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.85em;
  background: rgba(255,255,255,0.08);
  padding: 0.1em 0.35em;
  border-radius: 4px;
}
.bubble-content :deep(ul) {
  list-style: none;
  padding-left: 0;
}
.bubble-content :deep(li) {
  display: flex;
  align-items: baseline;
  gap: 0.4em;
}
.bubble-content :deep(li::before) {
  content: '•';
  color: #6B7689;
  flex-shrink: 0;
}
.bubble-content :deep(hr) {
  border: none;
  border-top: 1px solid rgba(255,255,255,0.08);
  margin: 0.5em 0;
}
</style>
