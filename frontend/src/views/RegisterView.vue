<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AuthShell from '@/components/auth/AuthShell.vue'
import FancyButton from '@/components/ui/FancyButton.vue'
const auth = useAuthStore(); const router = useRouter()
const username = ref(''); const email = ref(''); const password = ref(''); const showPassword = ref(false); const err = ref('')
const passwordStrength = computed(() => { const value = password.value; let score = 0; if (value.length >= 8) score += 1; if (/[A-Z]/.test(value) && /[a-z]/.test(value)) score += 1; if (/\d/.test(value) || /[^A-Za-z0-9]/.test(value)) score += 1; return { score, label: ['请设置至少 8 位密码','基础保护','更稳妥','保护良好'][score], tone: ['muted','amber','cyan','green'][score] } })
async function submit() { err.value = ''; try { await auth.register(username.value.trim(), password.value, email.value.trim() || undefined); router.push('/') } catch { err.value = auth.error || '注册失败，请稍后再试。' } }
</script>
<template>
  <AuthShell>
    <template #title><h1>建立决策档案</h1></template>
    <template #subtitle><p>从这里开始，让每一次选择都有据可循。</p></template>
    <template #form>
      <form class="auth-form" @submit.prevent="submit">
        <label class="auth-field"><span class="auth-field__label">用户名 <small class="auth-field__hint">3-32 位字母、数字或下划线</small></span><input v-model="username" class="auth-input" type="text" autocomplete="username" required minlength="3" maxlength="32" placeholder="为你的档案命名" /></label>
        <label class="auth-field"><span class="auth-field__label">邮箱 <small class="auth-field__hint">可选</small></span><input v-model="email" class="auth-input" type="email" autocomplete="email" placeholder="you@example.com" /></label>
        <label class="auth-field"><span class="auth-field__label">设置密码</span><span class="auth-input-wrap"><input v-model="password" class="auth-input auth-input--with-action" :type="showPassword ? 'text' : 'password'" autocomplete="new-password" required minlength="8" placeholder="至少 8 位" /><button type="button" class="auth-icon-button" :title="showPassword ? '隐藏密码' : '显示密码'" :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword"><span class="auth-eye" :class="{ 'auth-eye--closed': !showPassword }" aria-hidden="true" /></button></span><span class="strength" :class="`strength--${passwordStrength.tone}`"><i v-for="item in 3" :key="item" :class="{ 'strength__bar--active': item <= passwordStrength.score }" /><small>{{ passwordStrength.label }}</small></span></label>
        <p v-if="err" class="auth-error" role="alert" aria-live="polite">{{ err }}</p>
        <FancyButton type="submit" size="lg" :disabled="auth.busy" class="w-full justify-center">{{ auth.busy ? '正在建立档案…' : '创建并进入' }}</FancyButton>
      </form>
    </template>
    <template #footer><p class="auth-footer">已有账号？ <RouterLink to="/login">直接登录</RouterLink></p></template>
  </AuthShell>
</template>
<style scoped>
.strength{display:flex;align-items:center;gap:4px;margin-top:1px}.strength i{display:block;width:25px;height:3px;border-radius:2px;background:rgba(130,160,175,.2)}.strength small{margin-left:5px;color:#718a99;font-size:11px}.strength--amber .strength__bar--active{background:#e8b45c}.strength--amber small{color:#e8b45c}.strength--cyan .strength__bar--active{background:#72ddd9}.strength--cyan small{color:#72ddd9}.strength--green .strength__bar--active{background:#73d7a6}.strength--green small{color:#73d7a6}
</style>
