"""FastAPI 应用入口"""
import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import websockets

from .config import get_settings
from .database import init_db
from .routers import workflows_router, comfyui_router, templates_router, prompts_router
from .routers.health import router as health_router
from .routers.settings import router as settings_router
from .routers.comfyui_servers import router as comfyui_servers_router
from .routers.batch import router as batch_router
from .routers.models import router as models_router
from .routers.performance import router as performance_router
from .routers.marketplace import router as marketplace_router
from .routers.civitai import router as civitai_router
from .routers.builtin_workflows import router as builtin_workflows_router
from .routers.ai_workflow import router as ai_workflow_router
from .routers.smart_create import router as smart_create_router
from .routers.auth import router as auth_router
from .routers.ai_templates import router as ai_templates_router
from .middleware import RateLimitMiddleware, RequestLoggerMiddleware, SlowQueryMiddleware, set_slow_query_middleware
from .services.cleanup import cleanup_service
from .services.backup import backup_service
from .services.auto_migrate import auto_migrate_service
from .services.smart_create_executor import smart_create_executor
from .services.smart_create_progress import smart_create_progress_manager
from .services.task_queue import start_all_queues, stop_all_queues
from .logging_config import setup_logging, get_logger

# 配置日志系统
setup_logging()
logger = get_logger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动时初始化数据库
    await init_db()
    
    # 启动后台服务
    await cleanup_service.start(interval_minutes=30)
    await backup_service.start(interval_hours=6)
    await auto_migrate_service.start()
    
    # 启动任务队列
    await start_all_queues()
    
    # 恢复中断的智能创作任务
    asyncio.create_task(smart_create_executor.recover_interrupted_tasks())
    
    yield
    
    # 关闭时清理资源
    await stop_all_queues()
    await cleanup_service.stop()
    await backup_service.stop()
    await auto_migrate_service.stop()


app = FastAPI(
    title="ComfyUI Helper",
    description="ComfyUI 工作流管理器",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gzip 压缩中间件
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 请求日志中间件
app.add_middleware(RequestLoggerMiddleware)

# 速率限制中间件（支持精细化控制）
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=120,
    requests_per_second=20,
)

# 慢查询监控中间件
slow_query_middleware = SlowQueryMiddleware(
    app,
    slow_threshold_ms=1000,  # 1秒以上为慢请求
    very_slow_threshold_ms=5000,  # 5秒以上为非常慢
)
set_slow_query_middleware(slow_query_middleware)
app.add_middleware(SlowQueryMiddleware, slow_threshold_ms=1000, very_slow_threshold_ms=5000)

# 注册路由
app.include_router(auth_router, prefix="/api")
app.include_router(workflows_router, prefix="/api")
app.include_router(comfyui_router, prefix="/api")
app.include_router(templates_router, prefix="/api")
app.include_router(prompts_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(comfyui_servers_router, prefix="/api")
app.include_router(batch_router, prefix="/api")
app.include_router(models_router, prefix="/api")
app.include_router(performance_router, prefix="/api")
app.include_router(marketplace_router, prefix="/api")
app.include_router(civitai_router, prefix="/api")
app.include_router(builtin_workflows_router, prefix="/api")
app.include_router(ai_workflow_router, prefix="/api")
app.include_router(smart_create_router, prefix="/api")
app.include_router(ai_templates_router, prefix="/api")
app.include_router(health_router)


@app.get("/")
async def root():
    return {"message": "ComfyUI Helper API", "version": "0.1.0"}


class ConnectionManager:
    """WebSocket 连接管理器"""
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 端点 - 代理 ComfyUI 的实时消息，带心跳检测"""
    await manager.connect(websocket)
    
    comfyui_ws_url = settings.COMFYUI_URL.replace("http://", "ws://").replace("https://", "wss://")
    comfyui_ws_url = f"{comfyui_ws_url}/ws"
    
    # 心跳间隔（秒）
    HEARTBEAT_INTERVAL = 30
    
    try:
        async with websockets.connect(comfyui_ws_url) as comfyui_ws:
            async def forward_to_client():
                """从 ComfyUI 转发消息到客户端"""
                try:
                    async for message in comfyui_ws:
                        try:
                            data = json.loads(message)
                            await websocket.send_json(data)
                        except json.JSONDecodeError:
                            pass
                except websockets.exceptions.ConnectionClosed:
                    pass
            
            async def forward_to_comfyui():
                """从客户端转发消息到 ComfyUI"""
                try:
                    while True:
                        data = await websocket.receive_text()
                        # 处理心跳消息
                        if data == '{"type":"ping"}':
                            await websocket.send_json({"type": "pong"})
                            continue
                        await comfyui_ws.send(data)
                except WebSocketDisconnect:
                    pass
            
            async def heartbeat():
                """发送心跳保持连接"""
                try:
                    while True:
                        await asyncio.sleep(HEARTBEAT_INTERVAL)
                        await websocket.send_json({"type": "heartbeat", "timestamp": asyncio.get_event_loop().time()})
                except Exception:
                    pass
            
            # 同时运行转发和心跳任务
            await asyncio.gather(
                forward_to_client(),
                forward_to_comfyui(),
                heartbeat(),
                return_exceptions=True
            )
    except Exception as e:
        # ComfyUI 连接失败，发送错误消息
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": f"无法连接到 ComfyUI: {str(e)}"}
            })
        except Exception:
            pass
    finally:
        manager.disconnect(websocket)


@app.websocket("/ws/smart-create")
async def smart_create_websocket(websocket: WebSocket):
    """智能创作任务进度 WebSocket 端点"""
    await websocket.accept()

    # 默认订阅全局更新
    await smart_create_progress_manager.subscribe(websocket)

    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_json()

            # 处理订阅/取消订阅请求
            action = data.get("action")
            task_id = data.get("task_id")

            if action == "subscribe" and task_id:
                await smart_create_progress_manager.subscribe(websocket, task_id)
                await websocket.send_json({
                    "type": "subscribed",
                    "task_id": task_id
                })
            elif action == "unsubscribe" and task_id:
                await smart_create_progress_manager.unsubscribe(websocket, task_id)
                await websocket.send_json({
                    "type": "unsubscribed",
                    "task_id": task_id
                })
            elif action == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"SmartCreate WebSocket error: {e}")
    finally:
        await smart_create_progress_manager.unsubscribe(websocket)
