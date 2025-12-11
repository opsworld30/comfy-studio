"""
ComfyUI API 测试案例
"""
import pytest
import asyncio
from httpx import AsyncClient
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.database import get_db, async_session
from app.models import Workflow, ExecutionHistory


class TestComfyUIAPI:
    """ComfyUI 相关API测试"""
    
    @pytest.fixture
    async def client(self):
        """创建测试客户端"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    
    @pytest.fixture
    async def db_session(self):
        """创建测试数据库会话"""
        async with async_session() as session:
            yield session
    
    @pytest.fixture
    async def sample_workflow(self, db_session: AsyncSession):
        """创建示例工作流"""
        workflow = Workflow(
            name="测试工作流",
            description="用于测试的工作流",
            workflow_data={
                "1": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {
                        "ckpt_name": "v1-5-pruned-emaonly.safetensors"
                    }
                },
                "2": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {
                        "text": "a beautiful landscape",
                        "clip": ["1", 1]
                    }
                }
            },
            category="测试"
        )
        db_session.add(workflow)
        await db_session.commit()
        await db_session.refresh(workflow)
        yield workflow
        await db_session.delete(workflow)
        await db_session.commit()
    
    async def test_get_status(self, client: AsyncClient):
        """测试获取ComfyUI状态"""
        response = await client.get("/comfyui/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "connected" in data
        assert isinstance(data["connected"], bool)
        
        if data["connected"]:
            assert "queue_remaining" in data
            assert isinstance(data["queue_remaining"], int)
    
    async def test_get_queue(self, client: AsyncClient):
        """测试获取队列状态"""
        response = await client.get("/comfyui/queue")
        assert response.status_code == 200
        
        data = response.json()
        assert "queue_running" in data
        assert "queue_pending" in data
        assert isinstance(data["queue_running"], list)
        assert isinstance(data["queue_pending"], list)
    
    async def test_clear_queue(self, client: AsyncClient):
        """测试清空队列"""
        response = await client.post("/comfyui/queue/clear")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert data["message"] == "队列已清空"
    
    async def test_interrupt(self, client: AsyncClient):
        """测试中断执行"""
        response = await client.post("/comfyui/interrupt")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert data["message"] == "已中断"
    
    async def test_get_object_info(self, client: AsyncClient):
        """测试获取节点信息"""
        response = await client.get("/comfyui/object_info")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
    
    async def test_get_models(self, client: AsyncClient):
        """测试获取模型列表"""
        response = await client.get("/comfyui/models")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
    
    async def test_execute_workflow(self, client: AsyncClient, sample_workflow: Workflow):
        """测试执行工作流"""
        response = await client.post(
            f"/comfyui/execute/{sample_workflow.id}",
            json={}
        )
        # 如果ComfyUI未连接，会返回500错误，这是正常的
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "prompt_id" in data
            assert "workflow_id" in data
            assert "status" in data
    
    async def test_execute_direct(self, client: AsyncClient):
        """测试直接执行工作流"""
        workflow_data = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "v1-5-pruned-emaonly.safetensors"
                }
            }
        }
        
        response = await client.post(
            "/comfyui/execute/direct",
            json=workflow_data
        )
        # 如果ComfyUI未连接，会返回500错误，这是正常的
        assert response.status_code in [200, 500]
    
    async def test_get_execution_history(self, client: AsyncClient):
        """测试获取执行历史列表"""
        response = await client.get("/comfyui/executions")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    async def test_get_detailed_queue(self, client: AsyncClient):
        """测试获取详细队列信息"""
        response = await client.get("/comfyui/queue/detailed")
        assert response.status_code == 200
        
        data = response.json()
        assert "running" in data
        assert "pending" in data
        assert isinstance(data["running"], list)
        assert isinstance(data["pending"], list)
    
    async def test_get_recent_images(self, client: AsyncClient):
        """测试获取最近生成的图片"""
        response = await client.get("/comfyui/history/images")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    async def test_get_storage_stats(self, client: AsyncClient):
        """测试获取存储统计"""
        response = await client.get("/comfyui/storage/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
    
    async def test_list_stored_images(self, client: AsyncClient):
        """测试获取已存储的图片列表"""
        response = await client.get("/comfyui/storage/images")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    async def test_get_image_404(self, client: AsyncClient):
        """测试获取不存在的图片"""
        response = await client.get("/comfyui/image/nonexistent.png")
        assert response.status_code == 404
    
    async def test_get_thumbnail_404(self, client: AsyncClient):
        """测试获取不存在的缩略图"""
        response = await client.get("/comfyui/thumbnail/nonexistent.png")
        assert response.status_code == 404
    
    async def test_migrate_images(self, client: AsyncClient):
        """测试迁移图片"""
        response = await client.post("/comfyui/storage/migrate")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        assert "migrated" in data
        assert "failed" in data


class TestWorkflowAPI:
    """工作流API测试"""
    
    @pytest.fixture
    async def client(self):
        """创建测试客户端"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    
    @pytest.fixture
    async def db_session(self):
        """创建测试数据库会话"""
        async with async_session() as session:
            yield session
    
    async def test_list_workflows(self, client: AsyncClient):
        """测试获取工作流列表"""
        response = await client.get("/workflows")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    async def test_create_workflow(self, client: AsyncClient, db_session: AsyncSession):
        """测试创建工作流"""
        workflow_data = {
            "name": "测试工作流",
            "description": "这是一个测试工作流",
            "workflow_data": {
                "1": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": "test.safetensors"}
                }
            },
            "category": "测试",
            "tags": ["测试", "demo"],
            "is_favorite": False
        }
        
        response = await client.post("/workflows", json=workflow_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == workflow_data["name"]
        assert data["category"] == workflow_data["category"]
        
        # 清理测试数据
        await db_session.execute(
            "DELETE FROM workflows WHERE name = '测试工作流'"
        )
        await db_session.commit()
    
    async def test_get_workflow_not_found(self, client: AsyncClient):
        """测试获取不存在的工作流"""
        response = await client.get("/workflows/99999")
        assert response.status_code == 404
    
    async def test_export_all_workflows(self, client: AsyncClient):
        """测试导出所有工作流"""
        response = await client.get("/workflows/export/all")
        assert response.status_code == 200
        
        data = response.json()
        assert "version" in data
        assert "workflows" in data
        assert isinstance(data["workflows"], list)
    
    async def test_list_categories(self, client: AsyncClient):
        """测试获取所有分类"""
        response = await client.get("/workflows/categories/list")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)


class TestPromptAPI:
    """Prompt API测试"""
    
    @pytest.fixture
    async def client(self):
        """创建测试客户端"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    
    @pytest.fixture
    async def db_session(self):
        """创建测试数据库会话"""
        async with async_session() as session:
            yield session
    
    async def test_list_prompts(self, client: AsyncClient):
        """测试获取Prompt列表"""
        response = await client.get("/prompts")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    async def test_get_categories(self, client: AsyncClient):
        """测试获取Prompt分类"""
        response = await client.get("/prompts/categories")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        if data:  # 如果有数据
            assert "category" in data[0]
            assert "count" in data[0]
    
    async def test_create_prompt(self, client: AsyncClient, db_session: AsyncSession):
        """测试创建Prompt"""
        prompt_data = {
            "name": "测试Prompt",
            "positive": "a beautiful landscape, masterpiece",
            "negative": "blurry, low quality",
            "category": "测试",
            "tags": ["测试", "风景"]
        }
        
        response = await client.post("/prompts", json=prompt_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == prompt_data["name"]
        assert data["positive"] == prompt_data["positive"]
        assert data["category"] == prompt_data["category"]
        
        # 清理测试数据
        await db_session.execute(
            "DELETE FROM saved_prompts WHERE name = '测试Prompt'"
        )
        await db_session.commit()
    
    async def test_extract_from_workflow_data(self, client: AsyncClient):
        """测试从工作流数据提取Prompt"""
        workflow_data = {
            "1": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "a beautiful landscape",
                    "clip": ["2", 1]
                }
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "blurry, low quality, ugly",
                    "clip": ["2", 1]
                }
            },
            "2": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "v1-5-pruned-emaonly.safetensors"
                }
            }
        }
        
        response = await client.post(
            "/prompts/extract/workflow-data",
            json=workflow_data
        )
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        if data:  # 如果提取到了Prompt
            assert "positive" in data[0]
            assert "negative" in data[0]
    
    async def test_get_online_sources(self, client: AsyncClient):
        """测试获取在线提示词来源"""
        response = await client.get("/prompts/online/sources")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    async def test_search_online_prompts(self, client: AsyncClient):
        """测试搜索在线提示词"""
        response = await client.get(
            "/prompts/online/search",
            params={"query": "landscape", "source": "civitai", "limit": 5}
        )
        # 可能会因为网络问题失败，这是正常的
        assert response.status_code in [200, 500]
    
    async def test_get_trending_prompts(self, client: AsyncClient):
        """测试获取热门提示词"""
        response = await client.get("/prompts/online/trending?limit=5")
        # 可能会因为网络问题失败，这是正常的
        assert response.status_code in [200, 500]


class TestSettingsAPI:
    """设置API测试"""
    
    @pytest.fixture
    async def client(self):
        """创建测试客户端"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    
    async def test_get_page_settings(self, client: AsyncClient):
        """测试获取页面设置"""
        response = await client.get("/settings/page-modules")
        assert response.status_code == 200
        
        data = response.json()
        assert "monitor" in data
        assert "gallery" in data
        assert "pages" in data
    
    async def test_update_page_settings(self, client: AsyncClient):
        """测试更新页面设置"""
        settings_data = {
            "monitor": {
                "showSystemStatus": True,
                "showExecutionQueue": False,
                "showGeneratedImages": True,
                "showExecutionHistory": True,
            },
            "gallery": {
                "showSearchBar": True,
                "showLayoutToggle": False,
                "showSelectionMode": True,
            },
            "pages": {
                "showGallery": True,
                "showPrompts": False,
            }
        }
        
        response = await client.put("/settings/page-modules", json=settings_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["monitor"]["showExecutionQueue"] == False
        assert data["gallery"]["showLayoutToggle"] == False
        assert data["pages"]["showPrompts"] == False
    
    async def test_reset_page_settings(self, client: AsyncClient):
        """测试重置页面设置"""
        response = await client.post("/settings/page-modules/reset")
        assert response.status_code == 200
        
        data = response.json()
        assert "monitor" in data
        assert "gallery" in data
        assert "pages" in data
    
    async def test_get_ai_settings(self, client: AsyncClient):
        """测试获取AI设置"""
        response = await client.get("/settings/ai")
        assert response.status_code == 200
        
        data = response.json()
        assert "api_url" in data
        assert "model" in data
        assert "enabled" in data
    
    async def test_update_ai_settings(self, client: AsyncClient):
        """测试更新AI设置"""
        settings_data = {
            "api_url": "https://api.test.com/v1",
            "model": "test-model",
            "enabled": True,
            "api_key": "test-key-1234"
        }
        
        response = await client.put("/settings/ai", json=settings_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["api_url"] == settings_data["api_url"]
        assert data["model"] == settings_data["model"]
        assert data["enabled"] == settings_data["enabled"]
        # API Key应该被掩码
        assert data["api_key"].startswith("***")
    
    async def test_get_comfyui_settings(self, client: AsyncClient):
        """测试获取ComfyUI设置"""
        response = await client.get("/settings/comfyui")
        assert response.status_code == 200
        
        data = response.json()
        assert "url" in data
        assert "auto_migrate" in data
        assert "delete_original" in data
    
    async def test_update_comfyui_settings(self, client: AsyncClient):
        """测试更新ComfyUI设置"""
        settings_data = {
            "url": "http://127.0.0.1:8188",
            "output_dir": "/path/to/output",
            "auto_migrate": False,
            "delete_original": False
        }
        
        response = await client.put("/settings/comfyui", json=settings_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["url"] == settings_data["url"]
        assert data["auto_migrate"] == settings_data["auto_migrate"]
        assert data["delete_original"] == settings_data["delete_original"]


class TestHealthAPI:
    """健康检查API测试"""
    
    @pytest.fixture
    async def client(self):
        """创建测试客户端"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac
    
    async def test_health_check(self, client: AsyncClient):
        """测试健康检查"""
        response = await client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])