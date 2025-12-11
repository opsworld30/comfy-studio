"""
数据库模型测试
"""
import pytest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Workflow, SavedPrompt, ExecutionHistory, StoredImage, UserSettings


class TestWorkflowModel:
    """工作流模型测试"""
    
    @pytest.mark.asyncio
    async def test_create_workflow(self, db_session: AsyncSession):
        """测试创建工作流"""
        workflow = Workflow(
            name="测试工作流",
            description="这是一个测试工作流",
            workflow_data={"1": {"class_type": "TestNode"}},
            thumbnail="thumbnail.png",
            category="测试",
            tags=["测试", "demo"],
            is_favorite=True
        )
        
        db_session.add(workflow)
        await db_session.commit()
        await db_session.refresh(workflow)
        
        assert workflow.id is not None
        assert workflow.name == "测试工作流"
        assert workflow.category == "测试"
        assert workflow.is_favorite is True
        assert workflow.created_at is not None
        assert workflow.updated_at is not None
        
        # 清理
        await db_session.delete(workflow)
        await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_update_workflow(self, db_session: AsyncSession):
        """测试更新工作流"""
        # 创建
        workflow = Workflow(
            name="原始名称",
            workflow_data={"test": "data"},
            category="原始分类"
        )
        db_session.add(workflow)
        await db_session.commit()
        await db_session.refresh(workflow)
        
        original_updated_at = workflow.updated_at
        
        # 等待一小段时间确保时间戳不同
        import time
        time.sleep(0.01)
        
        # 更新
        workflow.name = "更新后的名称"
        workflow.is_favorite = True
        await db_session.commit()
        await db_session.refresh(workflow)
        
        assert workflow.name == "更新后的名称"
        assert workflow.is_favorite is True
        assert workflow.updated_at > original_updated_at
        
        # 清理
        await db_session.delete(workflow)
        await db_session.commit()


class TestSavedPromptModel:
    """保存的Prompt模型测试"""
    
    @pytest.mark.asyncio
    async def test_create_saved_prompt(self, db_session: AsyncSession):
        """测试创建保存的Prompt"""
        prompt = SavedPrompt(
            name="测试Prompt",
            positive="a beautiful landscape, masterpiece",
            negative="blurry, low quality, ugly",
            category="风景",
            tags=["风景", "自然"],
            source="manual",
            source_workflow_id=1,
            source_image="image.png",
            use_count=5,
            is_favorite=True,
            model="SD 1.5",
            sampler="euler",
            steps=20,
            cfg=7.0,
            seed=12345,
            width=512,
            height=512
        )
        
        db_session.add(prompt)
        await db_session.commit()
        await db_session.refresh(prompt)
        
        assert prompt.id is not None
        assert prompt.name == "测试Prompt"
        assert prompt.category == "风景"
        assert prompt.use_count == 5
        assert prompt.is_favorite is True
        assert prompt.steps == 20
        assert prompt.cfg == 7.0
        
        # 清理
        await db_session.delete(prompt)
        await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_increment_use_count(self, db_session: AsyncSession):
        """测试增加使用次数"""
        # 创建
        prompt = SavedPrompt(
            name="测试Prompt",
            positive="test prompt",
            category="测试",
            use_count=10
        )
        db_session.add(prompt)
        await db_session.commit()
        await db_session.refresh(prompt)
        
        original_count = prompt.use_count
        
        # 增加使用次数
        prompt.use_count += 1
        await db_session.commit()
        await db_session.refresh(prompt)
        
        assert prompt.use_count == original_count + 1
        
        # 清理
        await db_session.delete(prompt)
        await db_session.commit()


class TestExecutionHistoryModel:
    """执行历史模型测试"""
    
    @pytest.mark.asyncio
    async def test_create_execution_history(self, db_session: AsyncSession):
        """测试创建执行历史"""
        execution = ExecutionHistory(
            workflow_id=1,
            prompt_id="test-prompt-123",
            status="pending",
            result={"outputs": {"1": {"images": [{"filename": "test.png"}]}}}
        )
        
        db_session.add(execution)
        await db_session.commit()
        await db_session.refresh(execution)
        
        assert execution.id is not None
        assert execution.workflow_id == 1
        assert execution.prompt_id == "test-prompt-123"
        assert execution.status == "pending"
        assert execution.started_at is not None
        assert execution.completed_at is None
        
        # 清理
        await db_session.delete(execution)
        await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_complete_execution(self, db_session: AsyncSession):
        """测试完成执行"""
        # 创建
        execution = ExecutionHistory(
            workflow_id=1,
            prompt_id="test-prompt-123",
            status="running"
        )
        db_session.add(execution)
        await db_session.commit()
        await db_session.refresh(execution)
        
        assert execution.completed_at is None
        
        # 完成执行
        execution.status = "completed"
        execution.completed_at = datetime.now(timezone.utc)
        await db_session.commit()
        await db_session.refresh(execution)
        
        assert execution.status == "completed"
        assert execution.completed_at is not None
        
        # 清理
        await db_session.delete(execution)
        await db_session.commit()


class TestStoredImageModel:
    """存储图片模型测试"""
    
    @pytest.mark.asyncio
    async def test_create_stored_image(self, db_session: AsyncSession):
        """测试创建存储图片记录"""
        image = StoredImage(
            filename="test_image.png",
            filepath="/path/to/test_image.png",
            width=512,
            height=512,
            size=1024 * 1024,  # 1MB
            positive="a beautiful landscape",
            negative="blurry, low quality",
            seed=12345,
            steps=20,
            cfg=7.0,
            sampler="euler",
            model="SD 1.5",
            prompt_id=1,
            comfyui_prompt_id="prompt-123",
            is_deleted=False
        )
        
        db_session.add(image)
        await db_session.commit()
        await db_session.refresh(image)
        
        assert image.id is not None
        assert image.filename == "test_image.png"
        assert image.width == 512
        assert image.height == 512
        assert image.size == 1024 * 1024
        assert image.prompt_id == 1
        assert image.is_deleted is False
        assert image.created_at is not None
        
        # 清理
        await db_session.delete(image)
        await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_soft_delete_image(self, db_session: AsyncSession):
        """测试软删除图片"""
        # 创建
        image = StoredImage(
            filename="test_image.png",
            filepath="/path/to/test_image.png",
            width=512,
            height=512,
            size=1024 * 1024
        )
        db_session.add(image)
        await db_session.commit()
        await db_session.refresh(image)
        
        assert image.is_deleted is False
        
        # 软删除
        image.is_deleted = True
        await db_session.commit()
        await db_session.refresh(image)
        
        assert image.is_deleted is True
        
        # 清理
        await db_session.delete(image)
        await db_session.commit()


class TestUserSettingsModel:
    """用户设置模型测试"""
    
    @pytest.mark.asyncio
    async def test_create_user_settings(self, db_session: AsyncSession):
        """测试创建用户设置"""
        settings = UserSettings(
            key="test_settings",
            value={
                "option1": True,
                "option2": "value",
                "nested": {
                    "suboption": 123
                }
            }
        )
        
        db_session.add(settings)
        await db_session.commit()
        await db_session.refresh(settings)
        
        assert settings.id is not None
        assert settings.key == "test_settings"
        assert settings.value["option1"] is True
        assert settings.value["nested"]["suboption"] == 123
        assert settings.created_at is not None
        assert settings.updated_at is not None
        
        # 清理
        await db_session.delete(settings)
        await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_update_user_settings(self, db_session: AsyncSession):
        """测试更新用户设置"""
        # 创建
        settings = UserSettings(
            key="test_settings",
            value={"option1": "original"}
        )
        db_session.add(settings)
        await db_session.commit()
        await db_session.refresh(settings)
        
        original_updated_at = settings.updated_at
        
        # 等待一小段时间确保时间戳不同
        import time
        time.sleep(0.01)
        
        # 更新
        settings.value = {
            "option1": "updated",
            "new_option": True
        }
        await db_session.commit()
        await db_session.refresh(settings)
        
        assert settings.value["option1"] == "updated"
        assert settings.value["new_option"] is True
        assert settings.updated_at > original_updated_at
        
        # 清理
        await db_session.delete(settings)
        await db_session.commit()


class TestModelRelationships:
    """模型关系测试"""
    
    @pytest.mark.asyncio
    async def test_workflow_execution_relationship(self, db_session: AsyncSession):
        """测试工作流与执行历史的关系"""
        # 创建工作流
        workflow = Workflow(
            name="测试工作流",
            workflow_data={"test": "data"}
        )
        db_session.add(workflow)
        await db_session.commit()
        await db_session.refresh(workflow)
        
        # 创建执行历史
        execution = ExecutionHistory(
            workflow_id=workflow.id,
            prompt_id="test-123",
            status="completed"
        )
        db_session.add(execution)
        await db_session.commit()
        await db_session.refresh(execution)
        
        # 验证关系
        assert execution.workflow_id == workflow.id
        
        # 清理
        await db_session.delete(execution)
        await db_session.delete(workflow)
        await db_session.commit()
    
    @pytest.mark.asyncio
    async def test_prompt_image_relationship(self, db_session: AsyncSession):
        """测试Prompt与图片的关系"""
        # 创建Prompt
        prompt = SavedPrompt(
            name="测试Prompt",
            positive="test positive",
            negative="test negative"
        )
        db_session.add(prompt)
        await db_session.commit()
        await db_session.refresh(prompt)
        
        # 创建图片
        image = StoredImage(
            filename="test.png",
            filepath="/path/to/test.png",
            width=512,
            height=512,
            size=1024,
            positive="test positive",
            negative="test negative",
            prompt_id=prompt.id
        )
        db_session.add(image)
        await db_session.commit()
        await db_session.refresh(image)
        
        # 验证关系
        assert image.prompt_id == prompt.id
        
        # 清理
        await db_session.delete(image)
        await db_session.delete(prompt)
        await db_session.commit()


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])