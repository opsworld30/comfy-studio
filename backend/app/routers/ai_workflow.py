"""AI 工作流生成 API"""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db
from ..models import UserSettings

router = APIRouter(prefix="/ai", tags=["ai"])

# 数据文件路径
BUILTIN_FILE = Path(__file__).parent.parent / "data" / "builtin_workflows.json"

# 工作流生成系统提示词
WORKFLOW_SYSTEM_PROMPT = """你是一个专业的 ComfyUI 工作流生成专家。
用户会用中文描述想要的工作流，请根据描述生成一个完整的 ComfyUI 工作流 JSON。

你需要了解 ComfyUI 的节点系统：
- CheckpointLoaderSimple: 加载模型
- CLIPTextEncode: 文本编码（正向/负向提示词）
- EmptyLatentImage: 创建空的潜空间图像
- KSampler: 采样器，核心生成节点
- VAEDecode: 解码潜空间到图像
- SaveImage: 保存图像
- LoraLoader: 加载 LoRA
- ControlNetLoader: 加载 ControlNet
- ImageUpscaleWithModel: 图片放大

请严格按以下 JSON 格式输出，不要有任何其他内容：
{
  "name": "工作流名称",
  "description": "工作流描述",
  "workflow": {
    "last_node_id": 最后节点ID,
    "last_link_id": 最后连接ID,
    "nodes": [...节点数组...],
    "links": [...连接数组...],
    "groups": [],
    "config": {},
    "extra": {},
    "version": 0.4
  }
}

规则：
1. 生成完整可用的工作流 JSON
2. 节点位置要合理布局
3. 连接要正确
4. 根据用户描述选择合适的节点组合
5. 只输出 JSON，不要有任何解释"""


class ServerModels(BaseModel):
    """服务器模型信息"""
    checkpoints: list[str] = []
    loras: list[str] = []
    vaes: list[str] = []


class GenerateRequest(BaseModel):
    """生成请求"""
    prompt: str
    server_id: int | None = None
    selected_checkpoint: str | None = None
    selected_lora: str | None = None
    models: ServerModels | None = None


class GenerateResponse(BaseModel):
    """生成响应"""
    name: str
    description: str
    workflow: dict


def load_builtin_workflows():
    """加载内置工作流作为参考"""
    if not BUILTIN_FILE.exists():
        return []
    with open(BUILTIN_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("workflows", [])


def find_similar_workflow(prompt: str):
    """根据描述找到最相似的内置工作流"""
    workflows = load_builtin_workflows()
    prompt_lower = prompt.lower()
    
    # 关键词匹配
    keywords = {
        "flux": ["flux"],
        "sdxl": ["sdxl"],
        "sd3": ["sd3"],
        "sd1.5": ["sd1.5", "sd15", "1.5"],
        "lora": ["lora"],
        "放大": ["放大", "upscale", "超分"],
        "图生图": ["图生图", "img2img"],
    }
    
    for workflow in workflows:
        workflow_id = workflow.get("id", "")
        for key, terms in keywords.items():
            if any(term in prompt_lower for term in terms):
                if key in workflow_id.lower() or key in workflow.get("name", "").lower():
                    return workflow
    
    # 默认返回第一个
    return workflows[0] if workflows else None


@router.post("/generate-workflow", response_model=GenerateResponse)
async def generate_workflow(
    request: GenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    """使用 AI 生成工作流"""
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="请输入工作流描述")
    
    # 获取 AI 设置 (key-value 存储)
    ai_settings = {}
    result = await db.execute(
        select(UserSettings).where(UserSettings.key.in_([
            'ai_enabled', 'ai_api_key', 'ai_api_url', 'ai_model'
        ]))
    )
    for setting in result.scalars().all():
        ai_settings[setting.key] = setting.value
    
    ai_enabled = ai_settings.get('ai_enabled', False)
    ai_api_key = ai_settings.get('ai_api_key', '')
    ai_api_url = ai_settings.get('ai_api_url', 'https://api.openai.com/v1')
    ai_model = ai_settings.get('ai_model', 'gpt-3.5-turbo')
    
    if not ai_enabled or not ai_api_key:
        # AI 未启用，返回最相似的内置工作流
        similar = find_similar_workflow(prompt)
        if similar:
            return GenerateResponse(
                name=similar.get("name", "生成的工作流"),
                description=f"基于 '{prompt}' 推荐的工作流",
                workflow=similar.get("workflow_data", {})
            )
        raise HTTPException(status_code=400, detail="AI 功能未启用，且没有匹配的内置工作流")
    
    # 构建用户提示，包含选中的模型信息
    user_prompt = prompt
    models_info = []
    
    # 优先使用用户选中的模型
    if request.selected_checkpoint:
        models_info.append(f"请使用这个模型(checkpoint): {request.selected_checkpoint}")
    elif request.models and request.models.checkpoints:
        models_info.append(f"可用的模型(checkpoints): {', '.join(request.models.checkpoints[:5])}")
    
    if request.selected_lora:
        models_info.append(f"请使用这个 LoRA: {request.selected_lora}")
    elif request.models and request.models.loras:
        models_info.append(f"可用的 LoRA（可选）: {', '.join(request.models.loras[:5])}")
    
    if request.models and request.models.vaes:
        models_info.append(f"可用的 VAE: {', '.join(request.models.vaes[:3])}")
    
    if models_info:
        user_prompt = f"{prompt}\n\n用户指定的模型信息：\n" + "\n".join(models_info) + "\n\n请在工作流中使用这些实际存在的模型名称。"
    
    # 调用 AI 生成
    try:
        import httpx
        
        headers = {
            "Authorization": f"Bearer {ai_api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": ai_model,
            "messages": [
                {"role": "system", "content": WORKFLOW_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7,
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{ai_api_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
        
        # 解析响应
        content = data["choices"][0]["message"]["content"]
        
        # 尝试解析 JSON
        try:
            # 清理可能的 markdown 代码块
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            result = json.loads(content.strip())
            return GenerateResponse(
                name=result.get("name", "AI 生成的工作流"),
                description=result.get("description", prompt),
                workflow=result.get("workflow", {})
            )
        except json.JSONDecodeError:
            # JSON 解析失败，返回相似的内置工作流
            similar = find_similar_workflow(prompt)
            if similar:
                return GenerateResponse(
                    name=similar.get("name", "推荐的工作流"),
                    description="AI 生成失败，推荐相似工作流",
                    workflow=similar.get("workflow_data", {})
                )
            raise HTTPException(status_code=500, detail="AI 生成的内容格式错误")
            
    except httpx.HTTPError as e:
        # API 调用失败，返回相似的内置工作流
        similar = find_similar_workflow(prompt)
        if similar:
            return GenerateResponse(
                name=similar.get("name", "推荐的工作流"),
                description="AI 调用失败，推荐相似工作流",
                workflow=similar.get("workflow_data", {})
            )
        raise HTTPException(status_code=500, detail=f"AI 服务调用失败: {str(e)}")
