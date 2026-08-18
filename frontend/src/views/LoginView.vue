<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AuthShell from '@/components/auth/AuthShell.vue'
import FancyButton from '@/components/ui/FancyButton.vue'
const auth = useAuthStore(); const router = useRouter(); const route = useRoute()
const identifier = ref(''); const password = ref(''); const showPassword = ref(false); const err = ref('')
async function submit() { err.value = ''; try { await auth.login(identifier.value.trim(), password.value); router.push((route.query.redirect as string) || '/') } catch { err.value = auth.error || '登录失败，请检查账号和密码后重试。' } }
</script>
<template>
  <AuthShell>
    <template #title><h1>继续你的判断</h1></template>
    <template #subtitle><p>登录后，从上一次思考继续向前。</p></template>
    <template #form>
      <form class="auth-form" @submit.prevent="submit">
        <label class="auth-field"><span class="auth-field__label">用户名或邮箱</span><input v-model="identifier" class="auth-input" type="text" autocomplete="username" required placeholder="输入你的账号" /></label>
        <label class="auth-field"><span class="auth-field__label">密码</span><span class="auth-input-wrap"><input v-model="password" class="auth-input auth-input--with-action" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" required placeholder="输入密码" /><button type="button" class="auth-icon-button" :title="showPassword ? '隐藏密码' : '显示密码'" :aria-label="showPassword ? '隐藏密码' : '显示密码'" @click="showPassword = !showPassword"><span class="auth-eye" :class="{ 'auth-eye--closed': !showPassword }" aria-hidden="true" /></button></span></label>
        <p v-if="err" class="auth-error" role="alert" aria-live="polite">{{ err }}</p>
        <FancyButton type="submit" size="lg" :disabled="auth.busy" class="w-full justify-center">{{ auth.busy ? '正在验证身份…' : '进入衍界' }}</FancyButton>
      </form>
    </template>
    <template #footer><p class="auth-footer">还没有账号？ <RouterLink to="/register">创建你的决策档案</RouterLink></p></template>
  </AuthShell>
</template>
