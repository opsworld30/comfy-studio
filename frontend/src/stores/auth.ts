/**
 * 认证状态管理
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import * as authApi from '@/lib/api/auth'
import { tokenManager } from '@/lib/api/client'

export interface User {
  id: number
  username: string
  email: string
  full_name: string
  is_active: boolean
  is_superuser: boolean
  avatar: string
  created_at: string
  last_login: string | null
}

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null

  // Actions
  login: (username: string, password: string) => Promise<void>
  register: (username: string, email: string, password: string, fullName?: string) => Promise<void>
  logout: () => Promise<void>
  fetchCurrentUser: () => Promise<void>
  updateUser: (data: authApi.UserUpdateRequest) => Promise<void>
  changePassword: (oldPassword: string, newPassword: string) => Promise<void>
  clearError: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (username: string, password: string) => {
        set({ isLoading: true, error: null })
        try {
          const response = await authApi.login({ username, password })
          
          // 保存 token
          tokenManager.setTokens(response.access_token, response.refresh_token)
          
          // 更新用户状态
          set({
            user: response.user,
            isAuthenticated: true,
            isLoading: false,
          })
        } catch (error: any) {
          const errorMessage = error.response?.data?.detail || '登录失败'
          set({
            error: errorMessage,
            isLoading: false,
            isAuthenticated: false,
          })
          throw error
        }
      },

      register: async (username: string, email: string, password: string, fullName?: string) => {
        set({ isLoading: true, error: null })
        try {
          await authApi.register({
            username,
            email,
            password,
            full_name: fullName,
          })
          
          // 注册成功后自动登录
          await get().login(username, password)
        } catch (error: any) {
          const errorMessage = error.response?.data?.detail || '注册失败'
          set({
            error: errorMessage,
            isLoading: false,
          })
          throw error
        }
      },

      logout: async () => {
        const refreshToken = tokenManager.getRefreshToken()
        
        try {
          if (refreshToken) {
            await authApi.logout(refreshToken)
          }
        } catch (error) {
          console.error('登出请求失败:', error)
        } finally {
          // 无论请求是否成功，都清除本地状态
          tokenManager.clearTokens()
          set({
            user: null,
            isAuthenticated: false,
            error: null,
          })
        }
      },

      fetchCurrentUser: async () => {
        // 如果没有 token，直接返回
        if (!tokenManager.getAccessToken()) {
          set({ isAuthenticated: false, user: null })
          return
        }

        set({ isLoading: true })
        try {
          const user = await authApi.getCurrentUser()
          set({
            user,
            isAuthenticated: true,
            isLoading: false,
          })
        } catch (error) {
          // 获取用户信息失败，清除认证状态
          tokenManager.clearTokens()
          set({
            user: null,
            isAuthenticated: false,
            isLoading: false,
          })
        }
      },

      updateUser: async (data: authApi.UserUpdateRequest) => {
        set({ isLoading: true, error: null })
        try {
          const user = await authApi.updateCurrentUser(data)
          set({
            user,
            isLoading: false,
          })
        } catch (error: any) {
          const errorMessage = error.response?.data?.detail || '更新失败'
          set({
            error: errorMessage,
            isLoading: false,
          })
          throw error
        }
      },

      changePassword: async (oldPassword: string, newPassword: string) => {
        set({ isLoading: true, error: null })
        try {
          await authApi.changePassword({
            old_password: oldPassword,
            new_password: newPassword,
          })
          set({ isLoading: false })
        } catch (error: any) {
          const errorMessage = error.response?.data?.detail || '修改密码失败'
          set({
            error: errorMessage,
            isLoading: false,
          })
          throw error
        }
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)
