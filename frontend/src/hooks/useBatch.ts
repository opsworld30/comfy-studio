import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { batchApi } from '@/lib/api'

// 批处理任务列表
export function useBatchTasks(params?: { status?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ['batch', 'tasks', params],
    queryFn: async () => {
      const { data } = await batchApi.list(params)
      return data
    },
    refetchInterval: 3000, // 每3秒刷新
  })
}

// 批处理统计
export function useBatchStats() {
  return useQuery({
    queryKey: ['batch', 'stats'],
    queryFn: async () => {
      const { data } = await batchApi.getStats()
      return data
    },
    refetchInterval: 5000,
  })
}

// 单个任务
export function useBatchTask(id: number) {
  return useQuery({
    queryKey: ['batch', 'tasks', id],
    queryFn: async () => {
      const { data } = await batchApi.get(id)
      return data
    },
    enabled: !!id,
    refetchInterval: 2000,
  })
}

// 创建任务
export function useCreateBatchTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; workflow_id?: number; variables?: object; config?: object; priority?: number }) => 
      batchApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['batch'] })
    },
  })
}

// 启动任务
export function useStartBatchTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => batchApi.start(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['batch'] })
    },
  })
}

// 暂停任务
export function usePauseBatchTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => batchApi.pause(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['batch'] })
    },
  })
}

// 取消任务
export function useCancelBatchTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => batchApi.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['batch'] })
    },
  })
}

// 删除任务
export function useDeleteBatchTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => batchApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['batch'] })
    },
  })
}
