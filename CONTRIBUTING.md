# 贡献指南

感谢你对 ComfyUI Studio 项目的关注！欢迎提交 Issue 和 Pull Request。

## 🤝 如何贡献

### 报告 Bug

创建 Issue 时请包含：
- 清晰的标题和描述
- 复现步骤
- 系统环境信息（OS、Python 版本、Node 版本等）
- 相关的日志或截图

### 提交代码

1. Fork 项目并创建分支
2. 进行开发和测试
3. 提交 Pull Request

## 📝 代码规范

### Python (后端)

- 遵循 [PEP 8](https://pep8.org/) 规范
- 使用类型注解和文档字符串

```python
async def get_workflow_by_id(workflow_id: int) -> Optional[Workflow]:
    """根据 ID 获取工作流"""
    return await db.query(Workflow).filter(Workflow.id == workflow_id).first()
```

### TypeScript (前端)

- 使用 TypeScript 严格模式
- 函数式组件 + Hooks

```typescript
interface WorkflowCardProps {
  workflow: Workflow
  onEdit: (id: number) => void
}

export const WorkflowCard: React.FC<WorkflowCardProps> = ({ workflow, onEdit }) => {
  // 组件实现
}
```

### Git Commit 规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

- `feat:` 新功能
- `fix:` Bug 修复
- `docs:` 文档更新
- `refactor:` 代码重构

## 🧪 测试

```bash
# 后端测试
cd backend && uv run pytest

# 前端测试
cd frontend && pnpm test && pnpm lint
```

## 📄 许可证

提交代码即表示你同意将代码以 MIT 许可证发布。
