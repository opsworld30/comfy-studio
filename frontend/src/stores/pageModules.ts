import { create } from 'zustand'
import { settingsApi, type PageModuleSettings } from '@/lib/api'

interface PageModulesState {
  modules: PageModuleSettings | null
  isLoading: boolean
  error: string | null
  fetchModules: () => Promise<void>
  isPageVisible: (page: string) => boolean
  isModuleVisible: (page: keyof PageModuleSettings, module: string) => boolean
}

const defaultModules: PageModuleSettings = {
  pages: {
    showDashboard: true,
    showBatch: true,
    showGallery: true,
    showModels: false,
    showPrompts: true,
    showMonitor: true,
    showMarket: false,
  },
  dashboard: {
    showQuickActions: true,
    showRecentImages: true,
    showSystemStatus: true,
    showStatistics: true,
  },
  gallery: {
    showSearchBar: true,
    showLayoutToggle: true,
    showCategories: true,
    showFavorites: true,
  },
  prompts: {
    showCategories: true,
    showAIGenerate: true,
    showFavorites: true,
  },
  models: {
    showLocalModels: true,
    showCivitai: true,
  },
  monitor: {
    showSystemStatus: true,
    showExecutionQueue: true,
    showPerformanceChart: true,
    showExecutionHistory: true,
  },
}

export const usePageModulesStore = create<PageModulesState>((set, get) => ({
  modules: null,
  isLoading: false,
  error: null,

  fetchModules: async () => {
    set({ isLoading: true, error: null })
    try {
      const { data } = await settingsApi.getPageModules()
      set({ modules: data, isLoading: false })
    } catch (error) {
      set({ error: '加载设置失败', isLoading: false, modules: defaultModules })
    }
  },

  isPageVisible: (page: string) => {
    const modules = get().modules || defaultModules
    const key = `show${page.charAt(0).toUpperCase() + page.slice(1)}` as keyof typeof defaultModules.pages
    return modules.pages?.[key] ?? defaultModules.pages[key] ?? true
  },

  isModuleVisible: (page: keyof PageModuleSettings, module: string) => {
    const modules = get().modules || defaultModules
    const pageModules = modules[page]
    if (!pageModules) return true
    return pageModules[module] ?? true
  },
}))
