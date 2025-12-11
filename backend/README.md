# ComfyUI Helper Backend

ComfyUI 工作流管理器后端服务。

## 技术栈

- FastAPI
- SQLAlchemy + aiosqlite
- Pydantic
- httpx

## 安装

```bash
cd backend
uv sync
```

## 运行

```bash
uv run python run.py
```

或者：

```bash
uv run uvicorn app.main:app --reload --port 8000
```

## API 文档

启动后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 配置

创建 `.env` 文件：

```env
COMFYUI_URL=http://127.0.0.1:8188
DATABASE_URL=sqlite+aiosqlite:///./data/workflows.db
```
