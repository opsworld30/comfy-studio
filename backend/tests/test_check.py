import asyncio
from app.services.comfyui import comfyui_service

async def main():
    imgs = await comfyui_service.get_recent_images_with_prompt(5)
    for i in imgs:
        print(f"filename={i['filename']}, subfolder={i['subfolder']}")

asyncio.run(main())
