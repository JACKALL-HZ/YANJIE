<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import NavBar from '@/components/layout/NavBar.vue'
import GlassPanel from '@/components/ui/GlassPanel.vue'
import FancyButton from '@/components/ui/FancyButton.vue'
import SkeletonCard from '@/components/ui/SkeletonCard.vue'
import { useScenariosStore } from '@/stores/scenarios'
import type { ScenarioSummary } from '@/api/types'

type Category = '全部' | '创业' | '升学' | '职场' | '买房' | '投资'

interface SceneMeta {
  category: Exclude<Category, '全部'>
  summary: string
  scope: string
  variables: string[]
  tone: string
  order: number
}

const store = useScenariosStore()
const router = useRouter()
const activeCategory = ref<Category>('全部')
const selectedId = ref('')

const categories: Category[] = ['全部', '创业', '升学', '职场', '买房', '投资']
const STARTUP_SUBTYPES = new Set(['milktea_startup', 'restaurant_startup', 'retail_store', 'saas_startup'])

const SCENE_META: Record<string, SceneMeta> = {
  general_startup: {
    category: '创业',
    summary: '从你的具体业态、预算、城市和周期出发，动态生成适用于餐饮、茶饮、零售、软件或服务业务的创业推演。',
    scope: '餐饮、茶饮、零售、软件、服务与其他创业',
    variables: ['启动资金', '所在城市', '项目方向', '推演年数'],
    tone: 'border-cyan-glow/35 hover:border-cyan-glow/70',
    order: 0,
  },
  saas_startup: {
    category: '创业',
    summary: '围绕产品验证、获客成本、团队节奏与现金跑道评估软件创业。',
    scope: '软件产品、订阅服务、AI 工具',
    variables: ['启动资金', '所在城市', '所属行业', '推演年数'],
    tone: 'border-brand/35 hover:border-brand/70',
    order: 1,
  },
  retail_store: {
    category: '创业',
    summary: '从选址、货品、客流和库存周转推演线下零售小店的经营选择。',
    scope: '便利店、服装店、社区零售',
    variables: ['启动资金', '所在城市', '所属行业', '推演年数'],
    tone: 'border-agent-env/35 hover:border-agent-env/70',
    order: 2,
  },
  restaurant_startup: {
    category: '创业',
    summary: '评估餐饮门店的获客、成本、供应与本地经营策略。',
    scope: '餐馆、小吃、简餐、餐饮门店',
    variables: ['启动资金', '所在城市', '所属行业', '推演年数'],
    tone: 'border-amber-300/35 hover:border-amber-300/70',
    order: 3,
  },
  milktea_startup: {
    category: '创业',
    summary: '针对茶饮门店的选址、客流、产品差异化和回本节奏进行推演。',
    scope: '奶茶、咖啡、现制饮品',
    variables: ['启动资金', '所在城市', '所属行业', '推演年数'],
    tone: 'border-pink-300/35 hover:border-pink-300/70',
    order: 4,
  },
  grad_exam: {
    category: '升学',
    summary: '把目标院校、当前基础和备考周期拆成可执行的学习计划。',
    scope: '考研、复试、调剂',
    variables: ['目标院校', '当前基础', '备考月数'],
    tone: 'border-cyan-glow/35 hover:border-cyan-glow/70',
    order: 10,
  },
  study_abroad: {
    category: '升学',
    summary: '围绕目标国家、专业方向与预算评估留学申请的可行性。',
    scope: '本科、硕士、博士留学',
    variables: ['目标国家', '目标专业', '可用预算'],
    tone: 'border-brand/35 hover:border-brand/70',
    order: 11,
  },
  job_hunting: {
    category: '职场',
    summary: '结合经验、目标岗位和薪资预期规划求职策略与准备重点。',
    scope: '校招、社招、转行求职',
    variables: ['当前职位', '目标职位', '工作年限'],
    tone: 'border-agent-env/35 hover:border-agent-env/70',
    order: 20,
  },
  career_advance: {
    category: '职场',
    summary: '分析晋升目标、能力短板与组织环境，选择更有效的推进方式。',
    scope: '晋升、管理转型、职业发展',
    variables: ['当前职位', '目标职位', '工作年限'],
    tone: 'border-agent-env/35 hover:border-agent-env/70',
    order: 21,
  },
  house_purchase: {
    category: '买房',
    summary: '把预算、城市、收入和风险偏好放进同一套购房决策模型。',
    scope: '首套、改善、投资性购房',
    variables: ['可用预算', '所在城市', '当前月收入'],
    tone: 'border-amber-300/35 hover:border-amber-300/70',
    order: 30,
  },
  investment: {
    category: '投资',
    summary: '从资金规模、时间周期和风险承受能力出发，评估投资路径。',
    scope: '基金、股票、定投、资产配置',
    variables: ['计划投资金额', '风险偏好', '推演年数'],
    tone: 'border-agent-risk/35 hover:border-agent-risk/70',
    order: 40,
  },
}

const fallbackMeta: SceneMeta = {
  category: '创业',
  summary: '围绕你的真实条件进行多智能体推演。',
  scope: '待补充适用方向',
  variables: ['可用预算', '所在城市', '推演年数'],
  tone: 'border-white/15 hover:border-white/30',
  order: 99,
}

function metadata(scene: ScenarioSummary): SceneMeta {
  return SCENE_META[scene.scenario_id] || fallbackMeta
}

function displayTitle(scene: ScenarioSummary): string {
  return scene.scenario_id === 'general_startup' ? '创业' : scene.title
}

const filteredList = computed(() => {
  const visible = store.list.filter((scene) => !STARTUP_SUBTYPES.has(scene.scenario_id))
  const scenes = activeCategory.value === '全部'
    ? visible
    : visible.filter((scene) => metadata(scene).category === activeCategory.value)
  return [...scenes].sort((a, b) => metadata(a).order - metadata(b).order)
})

const selectedScenario = computed(() =>
  filteredList.value.find((scene) => scene.scenario_id === selectedId.value) || null,
)

const selectedMeta = computed(() =>
  selectedScenario.value ? metadata(selectedScenario.value) : null,
)

const detailReady = computed(() => store.current?.scenario_id === selectedId.value)

const categoryCounts = computed(() =>
  categories
    .filter((category) => category !== '全部')
    .map((category) => store.list.filter((scene) => !STARTUP_SUBTYPES.has(scene.scenario_id) && metadata(scene).category === category).length)
    .filter(Boolean)
    .length,
)

async function selectScene(sceneId: string) {
  if (!sceneId || selectedId.value === sceneId && detailReady.value) return
  selectedId.value = sceneId
  await store.fetchDetail(sceneId)
}

function selectFirstScene() {
  const first = filteredList.value[0]
  if (first) void selectScene(first.scenario_id)
  else selectedId.value = ''
}

watch(activeCategory, () => selectFirstScene())
watch(filteredList, (scenes) => {
  if (!scenes.some((scene) => scene.scenario_id === selectedId.value)) selectFirstScene()
})

onMounted(async () => {
  if (store.list.length === 0) await store.fetchList()
  selectFirstScene()
})

async function enterSim() {
  const scenario = selectedScenario.value
  if (!scenario) return
  await store.fetchDetail(scenario.scenario_id)
  router.push({ name: 'sim', params: { scenarioId: scenario.scenario_id } })
}

function categoryClass(category: Category) {
  return category === activeCategory.value
    ? 'border-cyan-glow/50 bg-cyan-glow/10 text-cyan-glow'
    : 'border-white/10 bg-white/[0.02] text-ink-muted hover:border-white/25 hover:text-ink-secondary'
}
</script>

<template>
  <div class="min-h-[100dvh]">
    <NavBar />

    <main class="mx-auto max-w-[1400px] px-5 pb-20 pt-24 md:px-8 md:pt-28">
      <header class="flex flex-wrap items-end justify-between gap-5 border-b border-white/10 pb-6">
        <div>
          <p class="eyebrow mb-2">决策场景库</p>
          <h1 class="font-display text-3xl font-bold text-ink-primary md:text-4xl">选择一个真实问题，开始推演</h1>
          <p class="mt-3 max-w-2xl text-sm leading-relaxed text-ink-secondary">
            先选择最接近的模板。创业没有默认赛道，未明确行业时请从「通用创业」开始。
          </p>
        </div>
        <div class="flex divide-x divide-white/10 border border-white/10 bg-surface-1/80 text-center">
          <div class="px-4 py-2"><p class="font-mono text-lg text-ink-primary">{{ store.list.length }}</p><p class="text-[10px] text-ink-muted">可用场景</p></div>
          <div class="px-4 py-2"><p class="font-mono text-lg text-cyan-glow">{{ categoryCounts }}</p><p class="text-[10px] text-ink-muted">决策领域</p></div>
        </div>
      </header>

      <nav class="mt-6 flex flex-wrap gap-2" aria-label="场景分类">
        <button
          v-for="category in categories"
          :key="category"
          class="border px-3.5 py-2 text-sm transition-colors"
          :class="categoryClass(category)"
          @click="activeCategory = category"
        >
          {{ category }}
          <span v-if="category !== '全部'" class="ml-1 font-mono text-[10px] opacity-70">
            {{ store.list.filter((scene) => !STARTUP_SUBTYPES.has(scene.scenario_id) && metadata(scene).category === category).length }}
          </span>
        </button>
      </nav>

      <div v-if="store.loading && !store.list.length" class="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <SkeletonCard v-for="n in 6" :key="n" :lines="3" />
      </div>
      <div v-else-if="store.error && !store.list.length" class="mt-8 border border-agent-risk/30 bg-agent-risk/10 p-5 text-agent-risk">
        <p class="text-sm">{{ store.error }}</p>
        <FancyButton variant="ghost" size="sm" class="mt-4" @click="store.fetchList()">重新加载</FancyButton>
      </div>
      <div v-else class="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section>
          <div class="mb-4 flex items-center justify-between gap-3">
            <h2 class="text-sm font-semibold text-ink-primary">{{ activeCategory }}场景</h2>
            <span class="font-mono text-xs text-ink-muted">{{ filteredList.length }} 个</span>
          </div>

          <div v-if="filteredList.length" class="grid gap-4 md:grid-cols-2">
            <button
              v-for="scene in filteredList"
              :key="scene.scenario_id"
              class="scene-card group relative min-h-[210px] overflow-hidden border bg-surface-1/85 p-5 text-left transition-all duration-200"
              :class="[
                metadata(scene).tone,
                selectedId === scene.scenario_id ? 'ring-1 ring-cyan-glow/60 bg-surface-2/95 shadow-[0_0_30px_rgba(34,211,238,0.10)]' : '',
              ]"
              @click="selectScene(scene.scenario_id)"
            >
              <div class="flex items-start justify-between gap-3">
                <span class="border border-white/10 px-2 py-1 text-[10px] text-ink-muted">{{ metadata(scene).category }}</span>
                <span v-if="selectedId === scene.scenario_id" class="text-[10px] text-cyan-glow">已选择</span>
              </div>
              <h3 class="mt-6 font-display text-xl font-bold text-ink-primary">{{ displayTitle(scene) }}</h3>
              <p class="mt-2 min-h-[42px] text-xs leading-relaxed text-ink-secondary">{{ metadata(scene).summary }}</p>
              <div class="mt-4 flex flex-wrap gap-1.5">
                <span v-for="variable in metadata(scene).variables" :key="variable" class="border border-white/8 bg-white/[0.03] px-2 py-1 text-[10px] text-ink-muted">{{ variable }}</span>
              </div>
              <div class="mt-5 flex items-center justify-between border-t border-white/8 pt-3 text-[11px]">
                <span class="text-ink-muted">{{ metadata(scene).scope }}</span>
                <span class="text-ink-secondary transition-colors group-hover:text-cyan-glow">查看详情 →</span>
              </div>
            </button>
          </div>
          <div v-else class="border border-dashed border-white/15 px-5 py-14 text-center text-sm text-ink-muted">这个分类暂时没有可用场景。</div>
        </section>

        <aside class="lg:sticky lg:top-24 lg:self-start">
          <GlassPanel v-if="selectedScenario" strong class="border-t-2 border-t-cyan-glow/60">
            <div class="flex items-center justify-between gap-3">
              <span class="border border-cyan-glow/30 bg-cyan-glow/10 px-2 py-1 text-[10px] text-cyan-glow">{{ selectedMeta?.category }}</span>
              <span class="text-[10px] text-ink-muted">推演模板</span>
            </div>
            <h2 class="mt-5 font-display text-2xl font-bold text-ink-primary">{{ displayTitle(selectedScenario) }}</h2>
            <p class="mt-3 text-xs leading-relaxed text-ink-secondary">{{ selectedMeta?.summary }}</p>

            <div class="mt-6 border-t border-white/8 pt-5">
              <p class="text-[10px] font-semibold text-ink-muted">进入前需要确认</p>
              <div class="mt-3 flex flex-wrap gap-2">
                <span v-for="variable in detailReady ? store.current?.decision_vars : selectedMeta?.variables" :key="typeof variable === 'string' ? variable : variable.name" class="border border-white/10 bg-white/[0.03] px-2 py-1.5 text-xs text-ink-secondary">
                  {{ typeof variable === 'string' ? variable : variable.label }}
                </span>
              </div>
            </div>

            <div class="mt-6 border-t border-white/8 pt-5">
              <p class="text-[10px] font-semibold text-ink-muted">参与分析的智能体</p>
              <div class="mt-3 grid grid-cols-2 gap-2">
                <div v-for="agent in store.current?.agents || []" :key="agent.agent_id" class="border border-white/8 bg-white/[0.02] px-2.5 py-2 text-xs text-ink-secondary">{{ agent.name }}</div>
              </div>
            </div>

            <FancyButton size="lg" class="mt-7 w-full" :disabled="store.loading" @click="enterSim">
              以此场景开始推演 →
            </FancyButton>
          </GlassPanel>
          <GlassPanel v-else class="py-12 text-center text-sm text-ink-muted">请选择一个场景查看详情。</GlassPanel>
        </aside>
      </div>
    </main>
  </div>
</template>

<style scoped>
.scene-card {
  border-radius: 8px;
}

.scene-card:hover {
  transform: translateY(-2px);
}
</style>
