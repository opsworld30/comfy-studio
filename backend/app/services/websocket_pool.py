"""WebSocket 连接池管理

提供高效的 WebSocket 连接管理，支持：
- 连接池复用
- 自动重连
- 心跳检测
- 连接状态监控
- 消息广播
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine

import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


class ConnectionState(str, Enum):
    """连接状态"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"
    FAILED = "failed"


@dataclass
class ConnectionInfo:
    """连接信息"""
    id: str
    url: str
    state: ConnectionState = ConnectionState.DISCONNECTED
    created_at: float = field(default_factory=time.time)
    connected_at: float = 0
    last_activity: float = 0
    reconnect_count: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    errors: list[str] = field(default_factory=list)


class WebSocketConnection:
    """单个 WebSocket 连接的封装"""
    
    def __init__(
        self,
        connection_id: str,
        url: str,
        on_message: Callable[[dict], Coroutine] = None,
        on_connect: Callable[[], Coroutine] = None,
        on_disconnect: Callable[[], Coroutine] = None,
        on_error: Callable[[Exception], Coroutine] = None,
        auto_reconnect: bool = True,
        reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 30.0,
        heartbeat_interval: float = 30.0,
        ping_timeout: float = 10.0,
    ):
        self.id = connection_id
        self.url = url
        self.auto_reconnect = auto_reconnect
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        self.heartbeat_interval = heartbeat_interval
        self.ping_timeout = ping_timeout
        
        # 回调
        self._on_message = on_message
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_error = on_error
        
        # 状态
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._info = ConnectionInfo(id=connection_id, url=url)
        self._running = False
        self._current_reconnect_delay = reconnect_delay
        
        # 任务
        self._receive_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        
        # 消息队列（用于发送）
        self._send_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=1000)
        self._send_task: asyncio.Task | None = None
    
    @property
    def info(self) -> ConnectionInfo:
        return self._info
    
    @property
    def is_connected(self) -> bool:
        return self._ws is not None and self._info.state == ConnectionState.CONNECTED
    
    async def connect(self):
        """建立连接"""
        if self._running:
            return
        
        self._running = True
        self._info.state = ConnectionState.CONNECTING
        
        try:
            self._ws = await websockets.connect(
                self.url,
                ping_interval=None,  # 我们自己处理心跳
                ping_timeout=self.ping_timeout,
                close_timeout=5,
            )
            
            self._info.state = ConnectionState.CONNECTED
            self._info.connected_at = time.time()
            self._info.last_activity = time.time()
            self._current_reconnect_delay = self.reconnect_delay
            
            logger.info(f"WebSocket connected: {self.id} -> {self.url}")
            
            # 触发连接回调
            if self._on_connect:
                await self._safe_callback(self._on_connect)
            
            # 启动接收和心跳任务
            self._receive_task = asyncio.create_task(self._receive_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self._send_task = asyncio.create_task(self._send_loop())
            
        except Exception as e:
            self._info.state = ConnectionState.FAILED
            self._info.errors.append(str(e))
            logger.error(f"WebSocket connection failed: {self.id} - {e}")
            
            if self._on_error:
                await self._safe_callback(self._on_error, e)
            
            if self.auto_reconnect:
                asyncio.create_task(self._reconnect())
    
    async def disconnect(self):
        """断开连接"""
        self._running = False
        
        # 取消所有任务
        for task in [self._receive_task, self._heartbeat_task, self._send_task, self._reconnect_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # 关闭 WebSocket
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        
        self._info.state = ConnectionState.DISCONNECTED
        
        if self._on_disconnect:
            await self._safe_callback(self._on_disconnect)
        
        logger.info(f"WebSocket disconnected: {self.id}")
    
    async def send(self, message: dict):
        """发送消息（异步队列）"""
        if not self.is_connected:
            raise ConnectionError("WebSocket is not connected")
        
        await self._send_queue.put(message)
    
    def send_nowait(self, message: dict) -> bool:
        """发送消息（非阻塞）"""
        if not self.is_connected:
            return False
        
        try:
            self._send_queue.put_nowait(message)
            return True
        except asyncio.QueueFull:
            logger.warning(f"Send queue full for connection {self.id}")
            return False
    
    async def _send_loop(self):
        """发送消息循环"""
        while self._running:
            try:
                message = await asyncio.wait_for(self._send_queue.get(), timeout=1.0)
                if self._ws:
                    await self._ws.send(json.dumps(message))
                    self._info.messages_sent += 1
                    self._info.last_activity = time.time()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Send error: {e}")
    
    async def _receive_loop(self):
        """接收消息循环"""
        while self._running and self._ws:
            try:
                message = await self._ws.recv()
                self._info.last_activity = time.time()
                self._info.messages_received += 1
                
                try:
                    data = json.loads(message)
                    if self._on_message:
                        await self._safe_callback(self._on_message, data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON message: {message[:100]}")
                    
            except ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {self.id} - {e}")
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Receive error: {e}")
                self._info.errors.append(str(e))
                break
        
        # 连接断开，尝试重连
        if self._running and self.auto_reconnect:
            asyncio.create_task(self._reconnect())
    
    async def _heartbeat_loop(self):
        """心跳循环"""
        while self._running and self._ws:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                if self._ws:
                    # 发送 ping
                    pong_waiter = await self._ws.ping()
                    await asyncio.wait_for(pong_waiter, timeout=self.ping_timeout)
                    self._info.last_activity = time.time()
                    
            except asyncio.TimeoutError:
                logger.warning(f"Heartbeat timeout: {self.id}")
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                break
        
        # 心跳失败，断开连接
        if self._running:
            await self.disconnect()
            if self.auto_reconnect:
                asyncio.create_task(self._reconnect())
    
    async def _reconnect(self):
        """重连逻辑"""
        if not self._running or not self.auto_reconnect:
            return
        
        self._info.state = ConnectionState.RECONNECTING
        self._info.reconnect_count += 1
        
        logger.info(f"Reconnecting {self.id} in {self._current_reconnect_delay}s...")
        
        await asyncio.sleep(self._current_reconnect_delay)
        
        # 指数退避
        self._current_reconnect_delay = min(
            self._current_reconnect_delay * 2,
            self.max_reconnect_delay
        )
        
        # 重新连接
        self._ws = None
        await self.connect()
    
    async def _safe_callback(self, callback: Callable, *args):
        """安全执行回调"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            logger.error(f"Callback error: {e}")


class WebSocketPool:
    """WebSocket 连接池
    
    管理多个 WebSocket 连接，支持：
    - 连接复用
    - 自动重连
    - 状态监控
    - 消息广播
    """
    
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self._connections: dict[str, WebSocketConnection] = {}
        self._lock = asyncio.Lock()
    
    async def get_or_create(
        self,
        connection_id: str,
        url: str,
        **kwargs
    ) -> WebSocketConnection:
        """获取或创建连接"""
        async with self._lock:
            if connection_id in self._connections:
                conn = self._connections[connection_id]
                if conn.is_connected:
                    return conn
                # 连接已断开，移除并重新创建
                del self._connections[connection_id]
            
            if len(self._connections) >= self.max_connections:
                # 移除最老的断开连接
                disconnected = [
                    cid for cid, c in self._connections.items()
                    if not c.is_connected
                ]
                if disconnected:
                    del self._connections[disconnected[0]]
                else:
                    raise RuntimeError(f"Connection pool is full (max={self.max_connections})")
            
            conn = WebSocketConnection(connection_id, url, **kwargs)
            self._connections[connection_id] = conn
            return conn
    
    async def connect(self, connection_id: str, url: str, **kwargs) -> WebSocketConnection:
        """创建并连接"""
        conn = await self.get_or_create(connection_id, url, **kwargs)
        if not conn.is_connected:
            await conn.connect()
        return conn
    
    async def disconnect(self, connection_id: str):
        """断开指定连接"""
        async with self._lock:
            if connection_id in self._connections:
                await self._connections[connection_id].disconnect()
                del self._connections[connection_id]
    
    async def disconnect_all(self):
        """断开所有连接"""
        async with self._lock:
            for conn in self._connections.values():
                await conn.disconnect()
            self._connections.clear()
    
    def get_connection(self, connection_id: str) -> WebSocketConnection | None:
        """获取连接"""
        return self._connections.get(connection_id)
    
    async def broadcast(self, message: dict, exclude: list[str] = None):
        """广播消息到所有连接"""
        exclude = exclude or []
        for conn_id, conn in self._connections.items():
            if conn_id not in exclude and conn.is_connected:
                try:
                    await conn.send(message)
                except Exception as e:
                    logger.error(f"Broadcast to {conn_id} failed: {e}")
    
    def get_stats(self) -> dict:
        """获取连接池统计"""
        connections = []
        for conn_id, conn in self._connections.items():
            info = conn.info
            connections.append({
                "id": conn_id,
                "url": info.url,
                "state": info.state.value,
                "connected_at": datetime.fromtimestamp(info.connected_at, tz=timezone.utc).isoformat() if info.connected_at else None,
                "last_activity": datetime.fromtimestamp(info.last_activity, tz=timezone.utc).isoformat() if info.last_activity else None,
                "reconnect_count": info.reconnect_count,
                "messages_sent": info.messages_sent,
                "messages_received": info.messages_received,
            })
        
        return {
            "max_connections": self.max_connections,
            "active_connections": len([c for c in self._connections.values() if c.is_connected]),
            "total_connections": len(self._connections),
            "connections": connections,
        }


class ClientConnectionManager:
    """客户端 WebSocket 连接管理器
    
    管理来自前端的 WebSocket 连接
    """
    
    def __init__(self, max_connections_per_client: int = 5):
        self.max_connections_per_client = max_connections_per_client
        self._connections: dict[str, list[Any]] = {}  # client_id -> [websocket, ...]
        self._connection_info: dict[int, dict] = {}  # id(websocket) -> info
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket, client_id: str = "default") -> bool:
        """注册新连接"""
        async with self._lock:
            if client_id not in self._connections:
                self._connections[client_id] = []
            
            # 检查连接数限制
            if len(self._connections[client_id]) >= self.max_connections_per_client:
                # 移除最老的连接
                old_ws = self._connections[client_id].pop(0)
                try:
                    await old_ws.close()
                except Exception:
                    pass
                self._connection_info.pop(id(old_ws), None)
            
            self._connections[client_id].append(websocket)
            self._connection_info[id(websocket)] = {
                "client_id": client_id,
                "connected_at": time.time(),
                "last_activity": time.time(),
                "messages_sent": 0,
                "messages_received": 0,
            }
            
            logger.debug(f"Client connected: {client_id}, total: {len(self._connections[client_id])}")
            return True
    
    async def disconnect(self, websocket):
        """移除连接"""
        async with self._lock:
            ws_id = id(websocket)
            info = self._connection_info.pop(ws_id, None)
            
            if info:
                client_id = info["client_id"]
                if client_id in self._connections:
                    try:
                        self._connections[client_id].remove(websocket)
                        if not self._connections[client_id]:
                            del self._connections[client_id]
                    except ValueError:
                        pass
                
                logger.debug(f"Client disconnected: {client_id}")
    
    async def broadcast(self, message: dict, client_id: str = None):
        """广播消息"""
        targets = []
        
        if client_id:
            targets = self._connections.get(client_id, [])
        else:
            for ws_list in self._connections.values():
                targets.extend(ws_list)
        
        for ws in targets:
            try:
                await ws.send_json(message)
                info = self._connection_info.get(id(ws))
                if info:
                    info["messages_sent"] += 1
                    info["last_activity"] = time.time()
            except Exception as e:
                logger.debug(f"Broadcast failed: {e}")
    
    def record_message_received(self, websocket):
        """记录收到消息"""
        info = self._connection_info.get(id(websocket))
        if info:
            info["messages_received"] += 1
            info["last_activity"] = time.time()
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        total_connections = sum(len(ws_list) for ws_list in self._connections.values())
        
        return {
            "total_clients": len(self._connections),
            "total_connections": total_connections,
            "max_per_client": self.max_connections_per_client,
            "clients": {
                client_id: len(ws_list)
                for client_id, ws_list in self._connections.items()
            }
        }


# ========== 全局实例 ==========

# ComfyUI 连接池
comfyui_ws_pool = WebSocketPool(max_connections=5)

# 客户端连接管理器
client_manager = ClientConnectionManager(max_connections_per_client=5)
