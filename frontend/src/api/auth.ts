import { api } from './client'
import type { AuthToken, AuthUser, LoginPayload, RegisterPayload } from './types'

export const authApi = {
  register(body: RegisterPayload) {
    return api.post<AuthToken>('/auth/register', body)
  },
  login(body: LoginPayload) {
    return api.post<AuthToken>('/auth/login', body)
  },
  me() {
    return api.get<AuthUser>('/auth/me')
  },
}
