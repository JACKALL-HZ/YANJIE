import { defineStore } from 'pinia'
import { ref } from 'vue'
import { authApi } from '@/api/auth'
import type { AuthUser } from '@/api/types'

const TOKEN_KEY = 'yanjie_token'
const USER_KEY = 'yanjie_user'
const GUEST_KEY = 'yanjie_guest_id'

function loadStoredUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as AuthUser
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<AuthUser | null>(loadStoredUser())
  const busy = ref(false)
  const error = ref<string | null>(null)

  function persist(t: string, u: AuthUser) {
    token.value = t
    user.value = u
    localStorage.setItem(TOKEN_KEY, t)
    localStorage.setItem(USER_KEY, JSON.stringify(u))
  }

  function clear() {
    token.value = null
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem(GUEST_KEY)
  }

  async function register(username: string, password: string, email?: string) {
    busy.value = true
    error.value = null
    try {
      const data = await authApi.register({ username, password, email })
      persist(data.access_token, data.user)
      return data.user
    } catch (e) {
      error.value = (e as Error).message
      throw e
    } finally {
      busy.value = false
    }
  }

  async function login(identifier: string, password: string) {
    busy.value = true
    error.value = null
    try {
      const data = await authApi.login({ identifier, password })
      persist(data.access_token, data.user)
      return data.user
    } catch (e) {
      error.value = (e as Error).message
      throw e
    } finally {
      busy.value = false
    }
  }

  function logout() {
    clear()
  }

  async function loadMe() {
    if (!token.value) return null
    try {
      const u = await authApi.me()
      user.value = u
      localStorage.setItem(USER_KEY, JSON.stringify(u))
      return u
    } catch {
      clear()
      return null
    }
  }

  return { token, user, busy, error, register, login, logout, loadMe, clear }
})
