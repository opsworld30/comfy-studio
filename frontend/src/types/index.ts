export interface Workflow {
  id: string
  name: string
  version: string
  description?: string
  thumbnail?: string
  tags: string[]
  category: string
  runCount: number
  isFavorite: boolean
  createdAt: string
  updatedAt: string
}

export interface Task {
  id: string
  workflowId: string
  workflowName: string
  status: 'running' | 'queued' | 'completed' | 'failed' | 'paused'
  progress: number
  currentStep: number
  totalSteps: number
  currentNode?: string
  batchIndex: number
  batchTotal: number
  startTime?: string
  endTime?: string
  duration?: number
  server: string
  priority: 'high' | 'medium' | 'low'
  images: string[]
  error?: string
}

export interface GalleryImage {
  id: string
  filename: string
  path: string
  thumbnail: string
  width: number
  height: number
  size: number
  format: string
  workflowId?: string
  workflowName?: string
  prompt?: string
  negativePrompt?: string
  model?: string
  sampler?: string
  steps?: number
  cfg?: number
  seed?: number
  createdAt: string
  tags: string[]
  isFavorite: boolean
}

export interface Model {
  id: string
  name: string
  filename: string
  type: 'checkpoint' | 'lora' | 'vae' | 'embedding' | 'controlnet' | 'upscale'
  size: number
  baseModel: 'SD1.5' | 'SDXL' | 'SD3' | 'Flux'
  description?: string
  thumbnail?: string
  tags: string[]
  usageCount: number
  isInstalled: boolean
  civitaiId?: string
  rating?: number
  downloads?: number
}

export interface Prompt {
  id: string
  name: string
  positive: string
  negative: string
  category: string
  tags: string[]
  usageCount: number
  rating: number
  successRate: number
  isFavorite: boolean
  recommendedModel?: string
  recommendedLora?: string
  examples: string[]
  createdAt: string
  updatedAt: string
}

export interface Server {
  id: string
  name: string
  url: string
  isDefault: boolean
  status: 'online' | 'offline' | 'connecting'
  latency: number
  version?: string
  gpuName?: string
  gpuUsage: number
  vramUsed: number
  vramTotal: number
  temperature: number
  cpuUsage: number
  ramUsed: number
  ramTotal: number
  queueCount: number
  uptime: number
  modelsCount: number
  lorasCount: number
  nodesCount: number
}

export interface PerformanceStats {
  timestamp: string
  gpuUsage: number
  vramUsage: number
  temperature: number
  cpuUsage: number
  ramUsage: number
}
