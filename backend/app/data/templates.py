"""工作流模板和 Prompt 模板

常用 ComfyUI 插件参考:
- ComfyUI Manager: 插件管理器
- WAS Node Suite: 图像处理、提示词处理
- ComfyUI Impact Pack: 人脸修复、图像分割
- ComfyUI IPAdapter Plus: 风格迁移
- ComfyUI Essentials: 基础工具节点
- KJNodes: 颜色匹配、图像处理
- ComfyUI ControlNet Aux: ControlNet 预处理器
- rgthree-comfy: 工作流优化节点
- ComfyUI-AnimateDiff-Evolved: 动画生成
- ComfyUI-Easy-Use: 简化工作流
"""

# 常用 Prompt 模板
PROMPT_TEMPLATES = {
    "portrait": {
        "name": "人像写真",
        "category": "人物",
        "positive": "masterpiece, best quality, 1girl, solo, beautiful detailed eyes, looking at viewer, portrait, upper body, soft lighting, professional photography, 8k uhd, high resolution",
        "negative": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry, bad feet, poorly drawn face, mutation, deformed",
    },
    "anime_girl": {
        "name": "动漫少女",
        "category": "动漫",
        "positive": "masterpiece, best quality, 1girl, solo, anime style, beautiful detailed eyes, colorful, vibrant colors, detailed background, illustration, pixiv, trending on artstation",
        "negative": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, 3d, realistic",
    },
    "landscape": {
        "name": "风景摄影",
        "category": "风景",
        "positive": "masterpiece, best quality, landscape, nature, beautiful scenery, mountains, sky, clouds, sunlight, golden hour, professional photography, 8k uhd, high resolution, wide angle",
        "negative": "lowres, text, error, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, oversaturated, ugly",
    },
    "cyberpunk": {
        "name": "赛博朋克",
        "category": "科幻",
        "positive": "masterpiece, best quality, cyberpunk, neon lights, futuristic city, night, rain, reflections, hologram, sci-fi, blade runner style, detailed background, atmospheric, cinematic lighting",
        "negative": "lowres, bad anatomy, text, error, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, daylight, bright",
    },
    "fantasy": {
        "name": "奇幻场景",
        "category": "奇幻",
        "positive": "masterpiece, best quality, fantasy, magical, ethereal, mystical forest, glowing particles, fairy tale, enchanted, detailed background, volumetric lighting, concept art",
        "negative": "lowres, text, error, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, modern, urban, realistic",
    },
    "product": {
        "name": "产品摄影",
        "category": "商业",
        "positive": "masterpiece, best quality, product photography, studio lighting, clean background, professional, commercial, high detail, sharp focus, 8k uhd",
        "negative": "lowres, text, error, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, messy background, shadows",
    },
    "food": {
        "name": "美食摄影",
        "category": "商业",
        "positive": "masterpiece, best quality, food photography, delicious, appetizing, professional lighting, restaurant quality, fresh ingredients, vibrant colors, close-up, shallow depth of field",
        "negative": "lowres, text, error, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, unappetizing, messy",
    },
    "architecture": {
        "name": "建筑摄影",
        "category": "建筑",
        "positive": "masterpiece, best quality, architecture photography, modern building, interior design, clean lines, minimalist, professional photography, wide angle, natural lighting, 8k uhd",
        "negative": "lowres, text, error, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, cluttered, messy",
    },
    "realistic_portrait": {
        "name": "写实人像",
        "category": "人物",
        "positive": "masterpiece, best quality, photorealistic, hyperrealistic, 1person, portrait, detailed skin texture, professional photography, studio lighting, 8k uhd, raw photo, film grain",
        "negative": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, cartoon, anime, illustration, painting",
    },
    "dark_fantasy": {
        "name": "黑暗奇幻",
        "category": "奇幻",
        "positive": "masterpiece, best quality, dark fantasy, gothic, dramatic lighting, moody atmosphere, detailed, intricate, dark colors, mysterious, ominous, concept art, digital painting",
        "negative": "lowres, text, error, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, bright, cheerful, cartoon",
    },
    "watercolor": {
        "name": "水彩风格",
        "category": "艺术",
        "positive": "masterpiece, best quality, watercolor painting, soft colors, delicate brushstrokes, artistic, traditional media, paper texture, flowing colors, beautiful composition",
        "negative": "lowres, text, error, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, digital art, 3d render, photograph",
    },
    "oil_painting": {
        "name": "油画风格",
        "category": "艺术",
        "positive": "masterpiece, best quality, oil painting, classical art, rich colors, visible brushstrokes, canvas texture, museum quality, fine art, detailed, renaissance style",
        "negative": "lowres, text, error, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, digital art, photograph, anime",
    },
    "minimalist": {
        "name": "极简风格",
        "category": "艺术",
        "positive": "masterpiece, best quality, minimalist, simple, clean, geometric shapes, limited color palette, negative space, modern design, elegant, sophisticated",
        "negative": "lowres, text, error, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, cluttered, busy, detailed, complex",
    },
    "vintage": {
        "name": "复古风格",
        "category": "艺术",
        "positive": "masterpiece, best quality, vintage, retro, nostalgic, film photography, grain, faded colors, 1970s style, analog, old photograph, warm tones",
        "negative": "lowres, text, error, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, modern, digital, sharp, oversaturated",
    },
    "horror": {
        "name": "恐怖氛围",
        "category": "氛围",
        "positive": "masterpiece, best quality, horror, creepy, unsettling, dark atmosphere, fog, shadows, eerie lighting, haunted, nightmare, detailed, cinematic",
        "negative": "lowres, text, error, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, bright, cheerful, cute, cartoon",
    },
}

# 常用工作流模板
WORKFLOW_TEMPLATES = {
    "txt2img_basic": {
        "name": "文生图-基础",
        "description": "基础的文生图工作流，适合快速生成图片",
        "category": "基础",
        "workflow": {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 7,
                    "denoise": 1,
                    "latent_image": ["5", 0],
                    "model": ["4", 0],
                    "negative": ["7", 0],
                    "positive": ["6", 0],
                    "sampler_name": "euler_ancestral",
                    "scheduler": "normal",
                    "seed": 0,
                    "steps": 20
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "v1-5-pruned-emaonly.safetensors"
                }
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "batch_size": 1,
                    "height": 512,
                    "width": 512
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": "masterpiece, best quality, 1girl"
                }
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": "lowres, bad anatomy, bad hands, text, error"
                }
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2]
                }
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "ComfyUI",
                    "images": ["8", 0]
                }
            }
        }
    },
    "txt2img_sdxl": {
        "name": "文生图-SDXL",
        "description": "SDXL 模型的文生图工作流，生成高质量图片",
        "category": "SDXL",
        "workflow": {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 7,
                    "denoise": 1,
                    "latent_image": ["5", 0],
                    "model": ["4", 0],
                    "negative": ["7", 0],
                    "positive": ["6", 0],
                    "sampler_name": "euler_ancestral",
                    "scheduler": "normal",
                    "seed": 0,
                    "steps": 25
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "sd_xl_base_1.0.safetensors"
                }
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "batch_size": 1,
                    "height": 1024,
                    "width": 1024
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": "masterpiece, best quality"
                }
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": "lowres, bad anatomy, bad hands, text, error"
                }
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2]
                }
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "SDXL",
                    "images": ["8", 0]
                }
            }
        }
    },
    "img2img_basic": {
        "name": "图生图-基础",
        "description": "基础的图生图工作流，用于图片风格转换",
        "category": "基础",
        "workflow": {
            "1": {
                "class_type": "LoadImage",
                "inputs": {
                    "image": "input.png"
                }
            },
            "2": {
                "class_type": "VAEEncode",
                "inputs": {
                    "pixels": ["1", 0],
                    "vae": ["4", 2]
                }
            },
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 7,
                    "denoise": 0.75,
                    "latent_image": ["2", 0],
                    "model": ["4", 0],
                    "negative": ["7", 0],
                    "positive": ["6", 0],
                    "sampler_name": "euler_ancestral",
                    "scheduler": "normal",
                    "seed": 0,
                    "steps": 20
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "v1-5-pruned-emaonly.safetensors"
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": "masterpiece, best quality"
                }
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": "lowres, bad anatomy, bad hands, text, error"
                }
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2]
                }
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "img2img",
                    "images": ["8", 0]
                }
            }
        }
    },
    "upscale_basic": {
        "name": "图片放大-基础",
        "description": "使用 AI 放大图片，提升分辨率",
        "category": "后处理",
        "workflow": {
            "1": {
                "class_type": "LoadImage",
                "inputs": {
                    "image": "input.png"
                }
            },
            "2": {
                "class_type": "UpscaleModelLoader",
                "inputs": {
                    "model_name": "RealESRGAN_x4plus.pth"
                }
            },
            "3": {
                "class_type": "ImageUpscaleWithModel",
                "inputs": {
                    "image": ["1", 0],
                    "upscale_model": ["2", 0]
                }
            },
            "4": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "upscaled",
                    "images": ["3", 0]
                }
            }
        }
    },
    "inpaint_basic": {
        "name": "局部重绘-基础",
        "description": "对图片局部区域进行重绘修改",
        "category": "编辑",
        "workflow": {
            "1": {
                "class_type": "LoadImage",
                "inputs": {
                    "image": "input.png"
                }
            },
            "2": {
                "class_type": "LoadImageMask",
                "inputs": {
                    "channel": "alpha",
                    "image": "mask.png"
                }
            },
            "3": {
                "class_type": "VAEEncodeForInpaint",
                "inputs": {
                    "grow_mask_by": 6,
                    "mask": ["2", 0],
                    "pixels": ["1", 0],
                    "vae": ["5", 2]
                }
            },
            "4": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 7,
                    "denoise": 1,
                    "latent_image": ["3", 0],
                    "model": ["5", 0],
                    "negative": ["8", 0],
                    "positive": ["7", 0],
                    "sampler_name": "euler_ancestral",
                    "scheduler": "normal",
                    "seed": 0,
                    "steps": 20
                }
            },
            "5": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "v1-5-pruned-emaonly.safetensors"
                }
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["5", 1],
                    "text": "masterpiece, best quality"
                }
            },
            "8": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["5", 1],
                    "text": "lowres, bad anatomy, bad hands, text, error"
                }
            },
            "9": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["4", 0],
                    "vae": ["5", 2]
                }
            },
            "10": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "inpaint",
                    "images": ["9", 0]
                }
            }
        }
    },
    "controlnet_canny": {
        "name": "ControlNet-边缘检测",
        "description": "使用 Canny 边缘检测控制生成",
        "category": "ControlNet",
        "workflow": {
            "1": {
                "class_type": "LoadImage",
                "inputs": {
                    "image": "input.png"
                }
            },
            "2": {
                "class_type": "CannyEdgePreprocessor",
                "inputs": {
                    "high_threshold": 200,
                    "image": ["1", 0],
                    "low_threshold": 100
                }
            },
            "3": {
                "class_type": "ControlNetLoader",
                "inputs": {
                    "control_net_name": "control_v11p_sd15_canny.pth"
                }
            },
            "4": {
                "class_type": "ControlNetApply",
                "inputs": {
                    "conditioning": ["7", 0],
                    "control_net": ["3", 0],
                    "image": ["2", 0],
                    "strength": 1
                }
            },
            "5": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "v1-5-pruned-emaonly.safetensors"
                }
            },
            "6": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "batch_size": 1,
                    "height": 512,
                    "width": 512
                }
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["5", 1],
                    "text": "masterpiece, best quality"
                }
            },
            "8": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["5", 1],
                    "text": "lowres, bad anatomy, bad hands, text, error"
                }
            },
            "9": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 7,
                    "denoise": 1,
                    "latent_image": ["6", 0],
                    "model": ["5", 0],
                    "negative": ["8", 0],
                    "positive": ["4", 0],
                    "sampler_name": "euler_ancestral",
                    "scheduler": "normal",
                    "seed": 0,
                    "steps": 20
                }
            },
            "10": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["9", 0],
                    "vae": ["5", 2]
                }
            },
            "11": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "controlnet",
                    "images": ["10", 0]
                }
            }
        }
    },
    "lora_basic": {
        "name": "LoRA-基础",
        "description": "加载 LoRA 模型增强生成效果",
        "category": "LoRA",
        "workflow": {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 7,
                    "denoise": 1,
                    "latent_image": ["5", 0],
                    "model": ["10", 0],
                    "negative": ["7", 0],
                    "positive": ["6", 0],
                    "sampler_name": "euler_ancestral",
                    "scheduler": "normal",
                    "seed": 0,
                    "steps": 20
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "v1-5-pruned-emaonly.safetensors"
                }
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "batch_size": 1,
                    "height": 512,
                    "width": 512
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["10", 1],
                    "text": "masterpiece, best quality"
                }
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["10", 1],
                    "text": "lowres, bad anatomy, bad hands, text, error"
                }
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2]
                }
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "lora",
                    "images": ["8", 0]
                }
            },
            "10": {
                "class_type": "LoraLoader",
                "inputs": {
                    "clip": ["4", 1],
                    "lora_name": "example.safetensors",
                    "model": ["4", 0],
                    "strength_clip": 1,
                    "strength_model": 1
                }
            }
        }
    },
    "hires_fix": {
        "name": "高清修复",
        "description": "两阶段生成，先低分辨率后放大细化",
        "category": "高级",
        "workflow": {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 7,
                    "denoise": 1,
                    "latent_image": ["5", 0],
                    "model": ["4", 0],
                    "negative": ["7", 0],
                    "positive": ["6", 0],
                    "sampler_name": "euler_ancestral",
                    "scheduler": "normal",
                    "seed": 0,
                    "steps": 20
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "v1-5-pruned-emaonly.safetensors"
                }
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "batch_size": 1,
                    "height": 512,
                    "width": 512
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": "masterpiece, best quality"
                }
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": "lowres, bad anatomy, bad hands, text, error"
                }
            },
            "10": {
                "class_type": "LatentUpscale",
                "inputs": {
                    "crop": "disabled",
                    "height": 1024,
                    "samples": ["3", 0],
                    "upscale_method": "nearest-exact",
                    "width": 1024
                }
            },
            "11": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 7,
                    "denoise": 0.5,
                    "latent_image": ["10", 0],
                    "model": ["4", 0],
                    "negative": ["7", 0],
                    "positive": ["6", 0],
                    "sampler_name": "euler_ancestral",
                    "scheduler": "normal",
                    "seed": 0,
                    "steps": 15
                }
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["11", 0],
                    "vae": ["4", 2]
                }
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "hires",
                    "images": ["8", 0]
                }
            }
        }
    },
    "face_detailer": {
        "name": "人脸修复 (Impact Pack)",
        "description": "使用 Impact Pack 的 FaceDetailer 修复人脸细节",
        "category": "后处理",
        "workflow": {
            "1": {
                "class_type": "LoadImage",
                "inputs": {
                    "image": "input.png"
                }
            },
            "2": {
                "class_type": "UltralyticsDetectorProvider",
                "inputs": {
                    "model_name": "bbox/face_yolov8m.pt"
                }
            },
            "3": {
                "class_type": "SAMLoader",
                "inputs": {
                    "device_mode": "AUTO",
                    "model_name": "sam_vit_b_01ec64.pth"
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "v1-5-pruned-emaonly.safetensors"
                }
            },
            "5": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": "detailed face, sharp focus, high quality"
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": "blurry, low quality"
                }
            },
            "7": {
                "class_type": "FaceDetailer",
                "inputs": {
                    "image": ["1", 0],
                    "model": ["4", 0],
                    "clip": ["4", 1],
                    "vae": ["4", 2],
                    "positive": ["5", 0],
                    "negative": ["6", 0],
                    "bbox_detector": ["2", 0],
                    "sam_model_opt": ["3", 0],
                    "denoise": 0.5,
                    "steps": 20,
                    "cfg": 7,
                    "sampler_name": "euler_ancestral",
                    "scheduler": "normal"
                }
            },
            "8": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "face_detail",
                    "images": ["7", 0]
                }
            }
        }
    },
    "ipadapter_style": {
        "name": "风格迁移 (IPAdapter)",
        "description": "使用 IPAdapter 进行图片风格迁移",
        "category": "风格",
        "workflow": {
            "1": {
                "class_type": "LoadImage",
                "inputs": {
                    "image": "style_reference.png"
                }
            },
            "2": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "v1-5-pruned-emaonly.safetensors"
                }
            },
            "3": {
                "class_type": "IPAdapterUnifiedLoader",
                "inputs": {
                    "model": ["2", 0],
                    "preset": "PLUS (high strength)"
                }
            },
            "4": {
                "class_type": "IPAdapterAdvanced",
                "inputs": {
                    "model": ["3", 0],
                    "ipadapter": ["3", 1],
                    "image": ["1", 0],
                    "weight": 0.8,
                    "weight_type": "style transfer"
                }
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "batch_size": 1,
                    "height": 512,
                    "width": 512
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["2", 1],
                    "text": "masterpiece, best quality"
                }
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["2", 1],
                    "text": "lowres, bad quality"
                }
            },
            "8": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 7,
                    "denoise": 1,
                    "latent_image": ["5", 0],
                    "model": ["4", 0],
                    "negative": ["7", 0],
                    "positive": ["6", 0],
                    "sampler_name": "euler_ancestral",
                    "scheduler": "normal",
                    "seed": 0,
                    "steps": 20
                }
            },
            "9": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["8", 0],
                    "vae": ["2", 2]
                }
            },
            "10": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "ipadapter",
                    "images": ["9", 0]
                }
            }
        }
    },
    "controlnet_openpose": {
        "name": "ControlNet-姿态控制",
        "description": "使用 OpenPose 控制人物姿态",
        "category": "ControlNet",
        "workflow": {
            "1": {
                "class_type": "LoadImage",
                "inputs": {
                    "image": "pose_reference.png"
                }
            },
            "2": {
                "class_type": "OpenposePreprocessor",
                "inputs": {
                    "image": ["1", 0],
                    "detect_body": True,
                    "detect_face": True,
                    "detect_hand": True
                }
            },
            "3": {
                "class_type": "ControlNetLoader",
                "inputs": {
                    "control_net_name": "control_v11p_sd15_openpose.pth"
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "v1-5-pruned-emaonly.safetensors"
                }
            },
            "5": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": "masterpiece, best quality, 1girl, standing"
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": "lowres, bad anatomy, bad hands"
                }
            },
            "7": {
                "class_type": "ControlNetApply",
                "inputs": {
                    "conditioning": ["5", 0],
                    "control_net": ["3", 0],
                    "image": ["2", 0],
                    "strength": 1
                }
            },
            "8": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "batch_size": 1,
                    "height": 768,
                    "width": 512
                }
            },
            "9": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 7,
                    "denoise": 1,
                    "latent_image": ["8", 0],
                    "model": ["4", 0],
                    "negative": ["6", 0],
                    "positive": ["7", 0],
                    "sampler_name": "euler_ancestral",
                    "scheduler": "normal",
                    "seed": 0,
                    "steps": 20
                }
            },
            "10": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["9", 0],
                    "vae": ["4", 2]
                }
            },
            "11": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "openpose",
                    "images": ["10", 0]
                }
            }
        }
    },
    "controlnet_depth": {
        "name": "ControlNet-深度图",
        "description": "使用深度图控制空间结构",
        "category": "ControlNet",
        "workflow": {
            "1": {
                "class_type": "LoadImage",
                "inputs": {
                    "image": "input.png"
                }
            },
            "2": {
                "class_type": "MiDaS-DepthMapPreprocessor",
                "inputs": {
                    "image": ["1", 0],
                    "a": 6.283185307179586,
                    "bg_threshold": 0.1
                }
            },
            "3": {
                "class_type": "ControlNetLoader",
                "inputs": {
                    "control_net_name": "control_v11f1p_sd15_depth.pth"
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "v1-5-pruned-emaonly.safetensors"
                }
            },
            "5": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": "masterpiece, best quality, detailed background"
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": "lowres, bad quality"
                }
            },
            "7": {
                "class_type": "ControlNetApply",
                "inputs": {
                    "conditioning": ["5", 0],
                    "control_net": ["3", 0],
                    "image": ["2", 0],
                    "strength": 1
                }
            },
            "8": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "batch_size": 1,
                    "height": 512,
                    "width": 512
                }
            },
            "9": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 7,
                    "denoise": 1,
                    "latent_image": ["8", 0],
                    "model": ["4", 0],
                    "negative": ["6", 0],
                    "positive": ["7", 0],
                    "sampler_name": "euler_ancestral",
                    "scheduler": "normal",
                    "seed": 0,
                    "steps": 20
                }
            },
            "10": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["9", 0],
                    "vae": ["4", 2]
                }
            },
            "11": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "depth",
                    "images": ["10", 0]
                }
            }
        }
    },
    "batch_generation": {
        "name": "批量生成",
        "description": "一次生成多张图片",
        "category": "高级",
        "workflow": {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "cfg": 7,
                    "denoise": 1,
                    "latent_image": ["5", 0],
                    "model": ["4", 0],
                    "negative": ["7", 0],
                    "positive": ["6", 0],
                    "sampler_name": "euler_ancestral",
                    "scheduler": "normal",
                    "seed": 0,
                    "steps": 20
                }
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "v1-5-pruned-emaonly.safetensors"
                }
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "batch_size": 4,
                    "height": 512,
                    "width": 512
                }
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": "masterpiece, best quality"
                }
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["4", 1],
                    "text": "lowres, bad anatomy, bad hands, text, error"
                }
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2]
                }
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "batch",
                    "images": ["8", 0]
                }
            }
        }
    }
}

# 常用 ComfyUI 插件列表
POPULAR_PLUGINS = {
    "comfyui_manager": {
        "name": "ComfyUI Manager",
        "description": "插件管理器，安装和更新其他插件的必备工具",
        "url": "https://github.com/ltdrdata/ComfyUI-Manager",
        "category": "核心"
    },
    "was_node_suite": {
        "name": "WAS Node Suite",
        "description": "最流行的节点包，包含数百个图像处理和工作流节点",
        "url": "https://github.com/WASasquatch/was-node-suite-comfyui",
        "category": "图像处理"
    },
    "impact_pack": {
        "name": "ComfyUI Impact Pack",
        "description": "人脸修复、图像分割、检测器等高级功能",
        "url": "https://github.com/ltdrdata/ComfyUI-Impact-Pack",
        "category": "图像增强"
    },
    "ipadapter_plus": {
        "name": "ComfyUI IPAdapter Plus",
        "description": "图片风格迁移，支持参考图生成",
        "url": "https://github.com/cubiq/ComfyUI_IPAdapter_plus",
        "category": "风格迁移"
    },
    "controlnet_aux": {
        "name": "ComfyUI ControlNet Aux",
        "description": "ControlNet 预处理器集合，包含各种边缘检测和姿态估计",
        "url": "https://github.com/Fannovel16/comfyui_controlnet_aux",
        "category": "ControlNet"
    },
    "essentials": {
        "name": "ComfyUI Essentials",
        "description": "基础工具节点，图像尺寸、裁剪、翻转等",
        "url": "https://github.com/cubiq/ComfyUI_essentials",
        "category": "基础工具"
    },
    "kjnodes": {
        "name": "KJNodes",
        "description": "颜色匹配、图像处理等实用节点",
        "url": "https://github.com/kijai/ComfyUI-KJNodes",
        "category": "图像处理"
    },
    "rgthree": {
        "name": "rgthree-comfy",
        "description": "工作流优化节点，包括上下文切换、节点组等",
        "url": "https://github.com/rgthree/rgthree-comfy",
        "category": "工作流"
    },
    "animatediff": {
        "name": "ComfyUI-AnimateDiff-Evolved",
        "description": "动画和视频生成",
        "url": "https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved",
        "category": "动画"
    },
    "easy_use": {
        "name": "ComfyUI-Easy-Use",
        "description": "简化版节点，降低工作流复杂度",
        "url": "https://github.com/yolain/ComfyUI-Easy-Use",
        "category": "简化"
    },
    "custom_scripts": {
        "name": "ComfyUI-Custom-Scripts",
        "description": "界面增强脚本，包括图片预览、节点搜索等",
        "url": "https://github.com/pythongosssss/ComfyUI-Custom-Scripts",
        "category": "界面"
    },
    "layer_style": {
        "name": "ComfyUI LayerStyle",
        "description": "图层样式处理，类似 Photoshop 的图层功能",
        "url": "https://github.com/chflame163/ComfyUI_LayerStyle",
        "category": "图像处理"
    },
    "inpaint_nodes": {
        "name": "ComfyUI Inpaint Nodes",
        "description": "高级局部重绘节点",
        "url": "https://github.com/Acly/comfyui-inpaint-nodes",
        "category": "重绘"
    },
    "prompt_styler": {
        "name": "SDXL Prompt Styler",
        "description": "SDXL 提示词风格化工具",
        "url": "https://github.com/twri/sdxl_prompt_styler",
        "category": "提示词"
    }
}

# 采样器配置
SAMPLER_PRESETS = {
    "fast": {
        "name": "快速",
        "sampler_name": "euler_ancestral",
        "scheduler": "normal",
        "steps": 15,
        "cfg": 7
    },
    "balanced": {
        "name": "平衡",
        "sampler_name": "euler_ancestral",
        "scheduler": "normal",
        "steps": 20,
        "cfg": 7
    },
    "quality": {
        "name": "高质量",
        "sampler_name": "dpmpp_2m",
        "scheduler": "karras",
        "steps": 30,
        "cfg": 7
    },
    "creative": {
        "name": "创意",
        "sampler_name": "euler_ancestral",
        "scheduler": "normal",
        "steps": 25,
        "cfg": 5
    },
    "precise": {
        "name": "精确",
        "sampler_name": "dpmpp_sde",
        "scheduler": "karras",
        "steps": 35,
        "cfg": 9
    }
}

# 分辨率预设
RESOLUTION_PRESETS = {
    "sd_square": {"name": "SD 方形", "width": 512, "height": 512},
    "sd_portrait": {"name": "SD 竖版", "width": 512, "height": 768},
    "sd_landscape": {"name": "SD 横版", "width": 768, "height": 512},
    "sdxl_square": {"name": "SDXL 方形", "width": 1024, "height": 1024},
    "sdxl_portrait": {"name": "SDXL 竖版", "width": 896, "height": 1152},
    "sdxl_landscape": {"name": "SDXL 横版", "width": 1152, "height": 896},
    "hd": {"name": "高清 16:9", "width": 1920, "height": 1080},
    "phone": {"name": "手机壁纸", "width": 1080, "height": 1920},
    "avatar": {"name": "头像", "width": 512, "height": 512},
}
