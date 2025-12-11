import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { comfyuiApi } from '@/lib/api'

// ComfyUI 状态
export function useComfyUIStatus() {
  return useQuery({
    queryKey: ['comfyui', 'status'],
    queryFn: async () => {
      const { data } = await comfyuiApi.getStatus()
      return data
    },
    refetchInterval: 3000, // 每3秒刷新
    staleTime: 2000,
  })
}

// 队列状态
export function useQueue() {
  return useQuery({
    queryKey: ['comfyui', 'queue'],
    queryFn: async () => {
      const { data } = await comfyuiApi.getDetailedQueue()
      return data
    },
    refetchInterval: 2000,
  })
}

// 清空队列
export function useClearQueue() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => comfyuiApi.clearQueue(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comfyui', 'queue'] })
    },
  })
}

// 中断执行
export function useInterrupt() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => comfyuiApi.interrupt(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comfyui'] })
    },
  })
}

// 执行工作流
export function useExecuteWorkflow() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ workflowId, data }: { workflowId: number; data?: { workflow_data?: object } }) => 
      comfyuiApi.executeWorkflow(workflowId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comfyui', 'queue'] })
      queryClient.invalidateQueries({ queryKey: ['comfyui', 'executions'] })
    },
  })
}

// 执行历史
export function useExecutions(params?: { limit?: number; offset?: number; status?: string }) {
  return useQuery({
    queryKey: ['comfyui', 'executions', params],
    queryFn: async () => {
      const { data } = await comfyuiApi.getExecutions(params)
      return data
    },
  })
}

// 最近生成的图片
export function useRecentImages(limit = 50) {
  return useQuery({
    queryKey: ['comfyui', 'images', limit],
    queryFn: async () => {
      const { data } = await comfyuiApi.getRecentImagesWithPrompt(limit)
      return data
    },
    refetchInterval: 5000,
  })
}

// 可用模型
export function useModels() {
  return useQuery({
    queryKey: ['comfyui', 'models'],
    queryFn: async () => {
      const { data } = await comfyuiApi.getModels()
      return data
    },
    staleTime: 60000, // 1分钟
  })
}

// 可用 LoRA
export function useLoras() {
  return useQuery({
    queryKey: ['comfyui', 'loras'],
    queryFn: async () => {
      const { data } = await comfyuiApi.getLoras()
      return data
    },
    staleTime: 60000,
  })
}

// 采样器
export function useSamplers() {
  return useQuery({
    queryKey: ['comfyui', 'samplers'],
    queryFn: async () => {
      const { data } = await comfyuiApi.getSamplers()
      return data
    },
    staleTime: 300000, // 5分钟
  })
}

// 调度器
export function useSchedulers() {
  return useQuery({
    queryKey: ['comfyui', 'schedulers'],
    queryFn: async () => {
      const { data } = await comfyuiApi.getSchedulers()
      return data
    },
    staleTime: 300000,
  })
}
