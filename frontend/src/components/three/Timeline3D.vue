<script setup lang="ts">
/**
 * Timeline3D — Three.js 分支时间线。
 * 发光节点按年份螺旋上升排布，高度映射 payback_ratio，颜色映射结局走向。
 * 懒加载 three + OrbitControls；reduced-motion / 触屏降级为静态帧。
 */
import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import type * as ThreeNS from 'three'
import type { YearRecord } from '@/stores/simulation'

const props = defineProps<{ years: YearRecord[] }>()

const containerRef = ref<HTMLDivElement | null>(null)
const ready = ref(false)
const fallback = ref(false)
const cleanup = shallowRef<(() => void) | null>(null)

onMounted(async () => {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const coarse = window.matchMedia('(pointer: coarse)').matches
  if (reduce || coarse) {
    fallback.value = true
    return
  }
  const el = containerRef.value
  if (!el || props.years.length === 0) return

  try {
    const THREE = await import('three')
    const { OrbitControls } = await import('three/examples/jsm/controls/OrbitControls.js')

    const w = el.clientWidth
    const h = el.clientHeight

    const scene = new THREE.Scene()
    scene.fog = new THREE.FogExp2(0x0b0f1a, 0.028)

    const camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 200)
    camera.position.set(9, 7, 13)

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setSize(w, h)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    el.appendChild(renderer.domElement)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.06
    controls.autoRotate = true
    controls.autoRotateSpeed = 0.6
    controls.maxDistance = 30
    controls.minDistance = 5

    // 灯光
    scene.add(new THREE.AmbientLight(0x334466, 1.4))
    const keyLight = new THREE.PointLight(0x4f8cff, 60, 60)
    keyLight.position.set(6, 10, 6)
    scene.add(keyLight)
    const rimLight = new THREE.PointLight(0x22d3ee, 40, 60)
    rimLight.position.set(-6, 4, -6)
    scene.add(rimLight)

    // 地面网格
    const grid = new THREE.GridHelper(40, 40, 0x1a2234, 0x141a2a)
    ;(grid.material as ThreeNS.Material).opacity = 0.5
    ;(grid.material as ThreeNS.Material).transparent = true
    scene.add(grid)

    // 节点：按年份螺旋上升
    const nodeGroup = new THREE.Group()
    const points: ThreeNS.Vector3[] = []
    const n = props.years.length

    props.years.forEach((yr, i) => {
      const t = n > 1 ? i / (n - 1) : 0
      const angle = t * Math.PI * 1.6 - Math.PI * 0.8
      const radius = 5
      const x = Math.cos(angle) * radius
      const z = Math.sin(angle) * radius
      const y = Math.max(0.5, yr.worldState.payback_ratio * 6 + i * 0.8)

      const isEnd = i === n - 1
      const profit = yr.worldState.monthly_profit
      const color = profit >= 0 ? 0x34d399 : 0xf87171
      const size = isEnd ? 0.55 : 0.38

      const geo = new THREE.SphereGeometry(size, 24, 24)
      const mat = new THREE.MeshStandardMaterial({
        color,
        emissive: color,
        emissiveIntensity: isEnd ? 1.6 : 0.9,
        roughness: 0.25,
        metalness: 0.4,
      })
      const mesh = new THREE.Mesh(geo, mat)
      mesh.position.set(x, y, z)
      nodeGroup.add(mesh)

      // 光晕外壳
      const haloGeo = new THREE.SphereGeometry(size * 1.7, 16, 16)
      const haloMat = new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: 0.08,
        side: THREE.BackSide,
      })
      const halo = new THREE.Mesh(haloGeo, haloMat)
      halo.position.copy(mesh.position)
      nodeGroup.add(halo)

      points.push(new THREE.Vector3(x, y, z))
    })
    scene.add(nodeGroup)

    // 连线：发光曲线路径
    if (points.length > 1) {
      const curve = new THREE.CatmullRomCurve3(points)
      const tubeGeo = new THREE.TubeGeometry(curve, 64, 0.05, 8, false)
      const tubeMat = new THREE.MeshBasicMaterial({
        color: 0x4f8cff,
        transparent: true,
        opacity: 0.55,
      })
      scene.add(new THREE.Mesh(tubeGeo, tubeMat))
    }

    // 星尘
    const starGeo = new THREE.BufferGeometry()
    const starCount = 300
    const pos = new Float32Array(starCount * 3)
    for (let i = 0; i < starCount; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 50
      pos[i * 3 + 1] = Math.random() * 20 - 2
      pos[i * 3 + 2] = (Math.random() - 0.5) * 50
    }
    starGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
    const stars = new THREE.Points(
      starGeo,
      new THREE.PointsMaterial({ color: 0x8cb4ff, size: 0.06, transparent: true, opacity: 0.5 }),
    )
    scene.add(stars)

    let raf = 0
    const clock = new THREE.Clock()
    const tick = () => {
      raf = requestAnimationFrame(tick)
      const t = clock.getElapsedTime()
      // 节点呼吸
      nodeGroup.children.forEach((m, i) => {
        if (i % 2 === 0) {
          const s = 1 + Math.sin(t * 2 + i) * 0.06
          m.scale.setScalar(s)
        }
      })
      controls.update()
      renderer.render(scene, camera)
    }
    tick()
    ready.value = true

    const onResize = () => {
      const nw = el.clientWidth
      const nh = el.clientHeight
      camera.aspect = nw / nh
      camera.updateProjectionMatrix()
      renderer.setSize(nw, nh)
    }
    window.addEventListener('resize', onResize)

    cleanup.value = () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onResize)
      controls.dispose()
      renderer.dispose()
      scene.traverse((obj) => {
        const mesh = obj as ThreeNS.Mesh
        if (mesh.geometry) mesh.geometry.dispose()
        const mat = mesh.material as ThreeNS.Material | ThreeNS.Material[] | undefined
        if (Array.isArray(mat)) mat.forEach((m) => m.dispose())
        else if (mat) mat.dispose()
      })
      el.removeChild(renderer.domElement)
    }
  } catch {
    fallback.value = true
  }
})

onBeforeUnmount(() => {
  cleanup.value?.()
})
</script>

<template>
  <div class="relative h-[420px] w-full overflow-hidden rounded-card">
    <div
      v-if="fallback"
      class="flex h-full items-center justify-center text-sm text-ink-muted"
    >
      3D 视图在当前设备已降级。共 {{ years.length }} 个推演节点。
    </div>
    <div v-show="!fallback" ref="containerRef" class="h-full w-full" />
    <div
      v-if="!fallback && !ready"
      class="absolute inset-0 flex items-center justify-center text-sm text-ink-muted"
    >
      正在加载 3D 引擎…
    </div>
    <div
      v-if="ready && !fallback"
      class="absolute bottom-3 right-4 font-mono text-[10px] uppercase tracking-wider text-ink-muted"
    >
      拖拽旋转 · 滚轮缩放
    </div>
  </div>
</template>
