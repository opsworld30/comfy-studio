import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { workflowsApi, type WorkflowCreate, type Workflow } from '@/lib/api'

// 工作流列表
export function useWorkflows(params?: { category?: string; search?: string; favorite_only?: boolean }) {
  return useQuery({
    queryKey: ['workflows', params],
    queryFn: async () => {
      const { data } = await workflowsApi.list(params)
      return data
    },
    staleTime: 2 * 60 * 1000, // 2 分钟
  })
}

// 单个工作流
export function useWorkflow(id: number) {
  return useQuery({
    queryKey: ['workflows', id],
    queryFn: async () => {
      const { data } = await workflowsApi.get(id)
      return data
    },
    enabled: !!id,
  })
}

// 创建工作流
export function useCreateWorkflow() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: WorkflowCreate) => workflowsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
    },
  })
}

// 更新工作流
export function useUpdateWorkflow() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<WorkflowCreate> }) => 
      workflowsApi.update(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
      queryClient.invalidateQueries({ queryKey: ['workflows', id] })
    },
  })
}

// 删除工作流（乐观更新）
export function useDeleteWorkflow() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => workflowsApi.delete(id),
    // 乐观更新：立即从列表中移除
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ['workflows'] })
      const previousWorkflows = queryClient.getQueryData<Workflow[]>(['workflows'])
      
      queryClient.setQueriesData<Workflow[]>(
        { queryKey: ['workflows'] },
        (old) => old?.filter(w => w.id !== id) ?? []
      )
      
      return { previousWorkflows }
    },
    onError: (_err, _id, context) => {
      // 回滚
      if (context?.previousWorkflows) {
        queryClient.setQueryData(['workflows'], context.previousWorkflows)
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
    },
  })
}

// 切换收藏（乐观更新）
export function useToggleFavorite() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => workflowsApi.toggleFavorite(id),
    // 乐观更新：立即切换收藏状态
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ['workflows'] })
      const previousWorkflows = queryClient.getQueryData<Workflow[]>(['workflows'])
      
      queryClient.setQueriesData<Workflow[]>(
        { queryKey: ['workflows'] },
        (old) => old?.map(w => 
          w.id === id ? { ...w, is_favorite: !w.is_favorite } : w
        ) ?? []
      )
      
      return { previousWorkflows }
    },
    onError: (_err, _id, context) => {
      if (context?.previousWorkflows) {
        queryClient.setQueryData(['workflows'], context.previousWorkflows)
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
    },
  })
}

// 版本历史
export function useWorkflowVersions(workflowId: number) {
  return useQuery({
    queryKey: ['workflows', workflowId, 'versions'],
    queryFn: async () => {
      const { data } = await workflowsApi.getVersions(workflowId)
      return data
    },
    enabled: !!workflowId,
  })
}

// 创建版本
export function useCreateVersion() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ workflowId, changeNote }: { workflowId: number; changeNote?: string }) => 
      workflowsApi.createVersion(workflowId, changeNote),
    onSuccess: (_, { workflowId }) => {
      queryClient.invalidateQueries({ queryKey: ['workflows', workflowId, 'versions'] })
    },
  })
}

// 恢复版本
export function useRestoreVersion() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ workflowId, versionId }: { workflowId: number; versionId: number }) => 
      workflowsApi.restoreVersion(workflowId, versionId),
    onSuccess: (_, { workflowId }) => {
      queryClient.invalidateQueries({ queryKey: ['workflows', workflowId] })
      queryClient.invalidateQueries({ queryKey: ['workflows', workflowId, 'versions'] })
    },
  })
}

// 分类列表
export function useCategories() {
  return useQuery({
    queryKey: ['workflows', 'categories'],
    queryFn: async () => {
      const { data } = await workflowsApi.getCategories()
      return data
    },
  })
}

// 导入工作流
export function useImportWorkflow() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => workflowsApi.import(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
    },
  })
}
