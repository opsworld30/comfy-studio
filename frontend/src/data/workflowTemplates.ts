// 常用文生图工作流模板
export interface WorkflowTemplate {
  id: string
  name: string
  description: string
  category: string
  tags: string[]
  difficulty: 'beginner' | 'intermediate' | 'advanced'
  workflowData: Record<string, any>
  thumbnail?: string
  recommendedModels?: string[]
  parameters?: {
    steps: number
    cfg: number
    sampler: string
    scheduler: string
    size: { width: number; height: number }
  }
}

export const WORKFLOW_TEMPLATES: WorkflowTemplate[] = [
  {
    id: 'txt2img_basic',
    name: '基础文生图',
    description: '适合新手的简单文生图工作流，快速生成高质量图片',
    category: '基础',
    tags: ['文生图', '入门', '快速'],
    difficulty: 'beginner',
    recommendedModels: ['v1-5-pruned-emaonly.safetensors'],
    parameters: {
      steps: 20,
      cfg: 7,
      sampler: 'euler_ancestral',
      scheduler: 'normal',
      size: { width: 512, height: 512 }
    },
    workflowData: {
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
          "text": "masterpiece, best quality, 1girl, beautiful detailed eyes, looking at viewer, portrait, soft lighting, professional photography, 8k uhd, high resolution"
        }
      },
      "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {
          "clip": ["4", 1],
          "text": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry, bad feet, poorly drawn face, mutation, deformed"
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
  {
    id: 'txt2img_sdxl',
    name: 'SDXL 高清文生图',
    description: '使用 SDXL 模型生成超高清图片，适合专业创作',
    category: 'SDXL',
    tags: ['文生图', 'SDXL', '高清', '专业'],
    difficulty: 'intermediate',
    recommendedModels: ['sd_xl_base_1.0.safetensors'],
    parameters: {
      steps: 25,
      cfg: 7,
      sampler: 'euler_ancestral',
      scheduler: 'normal',
      size: { width: 1024, height: 1024 }
    },
    workflowData: {
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
          "text": "masterpiece, best quality, highly detailed, professional photography, 8k uhd, ultra realistic"
        }
      },
      "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {
          "clip": ["4", 1],
          "text": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry"
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
  {
    id: 'txt2img_anime',
    name: '动漫风格生成',
    description: '专门用于生成高质量动漫风格图片的工作流',
    category: '动漫',
    tags: ['文生图', '动漫', '二次元', '角色'],
    difficulty: 'beginner',
    recommendedModels: ['anything-v4.5-pruned.ckpt', 'meinamix_meinaV9.safetensors'],
    parameters: {
      steps: 28,
      cfg: 7,
      sampler: 'DPM++ 2M Karras',
      scheduler: 'normal',
      size: { width: 512, height: 768 }
    },
    workflowData: {
      "3": {
        "class_type": "KSampler",
        "inputs": {
          "cfg": 7,
          "denoise": 1,
          "latent_image": ["5", 0],
          "model": ["4", 0],
          "negative": ["7", 0],
          "positive": ["6", 0],
          "sampler_name": "DPM++ 2M Karras",
          "scheduler": "normal",
          "seed": 0,
          "steps": 28
        }
      },
      "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
          "ckpt_name": "anything-v4.5-pruned.ckpt"
        }
      },
      "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {
          "batch_size": 1,
          "height": 768,
          "width": 512
        }
      },
      "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {
          "clip": ["4", 1],
          "text": "masterpiece, best quality, 1girl, anime style, beautiful detailed eyes, colorful, vibrant colors, detailed background, illustration, pixiv, trending on artstation"
        }
      },
      "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {
          "clip": ["4", 1],
          "text": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, 3d, realistic"
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
          "filename_prefix": "anime",
          "images": ["8", 0]
        }
      }
    }
  },
  {
    id: 'txt2img_realistic',
    name: '写实人像',
    description: '生成超写实人像作品，适合摄影级效果',
    category: '写实',
    tags: ['文生图', '写实', '人像', '摄影'],
    difficulty: 'intermediate',
    recommendedModels: ['realisticVisionV51_v51VAE.safetensors', 'chilloutmix_NiPrunedFp32Fix.safetensors'],
    parameters: {
      steps: 30,
      cfg: 7,
      sampler: 'DPM++ SDE Karras',
      scheduler: 'normal',
      size: { width: 512, height: 768 }
    },
    workflowData: {
      "3": {
        "class_type": "KSampler",
        "inputs": {
          "cfg": 7,
          "denoise": 1,
          "latent_image": ["5", 0],
          "model": ["4", 0],
          "negative": ["7", 0],
          "positive": ["6", 0],
          "sampler_name": "DPM++ SDE Karras",
          "scheduler": "normal",
          "seed": 0,
          "steps": 30
        }
      },
      "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
          "ckpt_name": "realisticVisionV51_v51VAE.safetensors"
        }
      },
      "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {
          "batch_size": 1,
          "height": 768,
          "width": 512
        }
      },
      "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {
          "clip": ["4", 1],
          "text": "masterpiece, best quality, photorealistic, hyperrealistic, 1person, portrait, detailed skin texture, professional photography, studio lighting, 8k uhd, raw photo, film grain"
        }
      },
      "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {
          "clip": ["4", 1],
          "text": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, cartoon, anime, illustration, painting"
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
          "filename_prefix": "realistic",
          "images": ["8", 0]
        }
      }
    }
  },
  {
    id: 'txt2img_lora',
    name: 'LoRA 风格化',
    description: '使用 LoRA 模型增强特定风格效果',
    category: 'LoRA',
    tags: ['文生图', 'LoRA', '风格化', '角色'],
    difficulty: 'intermediate',
    recommendedModels: ['v1-5-pruned-emaonly.safetensors'],
    parameters: {
      steps: 25,
      cfg: 7,
      sampler: 'euler_ancestral',
      scheduler: 'normal',
      size: { width: 512, height: 512 }
    },
    workflowData: {
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
          "steps": 25
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
          "text": "masterpiece, best quality, 1girl, beautiful detailed eyes"
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
  {
    id: 'txt2img_hires_fix',
    name: '高清修复',
    description: '两阶段生成，先低分辨率后放大细化，获得更清晰细节',
    category: '高级',
    tags: ['文生图', '高清', '修复', '细节'],
    difficulty: 'advanced',
    recommendedModels: ['v1-5-pruned-emaonly.safetensors'],
    parameters: {
      steps: 20,
      cfg: 7,
      sampler: 'euler_ancestral',
      scheduler: 'normal',
      size: { width: 512, height: 512 }
    },
    workflowData: {
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
          "text": "masterpiece, best quality, highly detailed"
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
  {
    id: 'txt2img_landscape',
    name: '风景画生成',
    description: '生成壮观的自然风景和城市景观',
    category: '基础',
    tags: ['文生图', '风景', '自然', '城市'],
    difficulty: 'beginner',
    recommendedModels: ['v1-5-pruned-emaonly.safetensors', 'dreamshaper_8.safetensors'],
    parameters: {
      steps: 25,
      cfg: 7.5,
      sampler: 'euler_ancestral',
      scheduler: 'normal',
      size: { width: 768, height: 512 }
    },
    workflowData: {
      "3": {
        "class_type": "KSampler",
        "inputs": {
          "cfg": 7.5,
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
          "ckpt_name": "v1-5-pruned-emaonly.safetensors"
        }
      },
      "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {
          "batch_size": 1,
          "height": 512,
          "width": 768
        }
      },
      "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {
          "clip": ["4", 1],
          "text": "masterpiece, best quality, landscape, beautiful scenery, nature, mountains, forest, river, dramatic lighting, golden hour, 8k uhd, professional photography"
        }
      },
      "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {
          "clip": ["4", 1],
          "text": "lowres, bad quality, blurry, jpeg artifacts, watermark, text, signature, people, person"
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
          "filename_prefix": "landscape",
          "images": ["8", 0]
        }
      }
    }
  },
  {
    id: 'txt2img_portrait_anime',
    name: '动漫头像',
    description: '生成精美的动漫角色头像和半身像',
    category: '动漫',
    tags: ['文生图', '动漫', '头像', '角色'],
    difficulty: 'beginner',
    recommendedModels: ['anything-v4.5-pruned.ckpt', 'counterfeit-v3.0.safetensors'],
    parameters: {
      steps: 25,
      cfg: 7,
      sampler: 'DPM++ 2M Karras',
      scheduler: 'normal',
      size: { width: 512, height: 512 }
    },
    workflowData: {
      "3": {
        "class_type": "KSampler",
        "inputs": {
          "cfg": 7,
          "denoise": 1,
          "latent_image": ["5", 0],
          "model": ["4", 0],
          "negative": ["7", 0],
          "positive": ["6", 0],
          "sampler_name": "dpmpp_2m_sde_gpu",
          "scheduler": "karras",
          "seed": 0,
          "steps": 25
        }
      },
      "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
          "ckpt_name": "anything-v4.5-pruned.ckpt"
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
          "text": "masterpiece, best quality, 1girl, solo, portrait, close-up, beautiful detailed eyes, looking at viewer, smile, anime style, colorful, vibrant, detailed face"
        }
      },
      "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {
          "clip": ["4", 1],
          "text": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, jpeg artifacts, signature, watermark, blurry, 3d, realistic, multiple people"
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
          "filename_prefix": "anime_portrait",
          "images": ["8", 0]
        }
      }
    }
  },
  {
    id: 'txt2img_concept_art',
    name: '概念艺术',
    description: '生成游戏和电影级别的概念艺术作品',
    category: '高级',
    tags: ['文生图', '概念艺术', '游戏', '电影'],
    difficulty: 'intermediate',
    recommendedModels: ['dreamshaper_8.safetensors', 'deliberate_v3.safetensors'],
    parameters: {
      steps: 30,
      cfg: 8,
      sampler: 'DPM++ 2M Karras',
      scheduler: 'normal',
      size: { width: 768, height: 512 }
    },
    workflowData: {
      "3": {
        "class_type": "KSampler",
        "inputs": {
          "cfg": 8,
          "denoise": 1,
          "latent_image": ["5", 0],
          "model": ["4", 0],
          "negative": ["7", 0],
          "positive": ["6", 0],
          "sampler_name": "dpmpp_2m_sde_gpu",
          "scheduler": "karras",
          "seed": 0,
          "steps": 30
        }
      },
      "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
          "ckpt_name": "dreamshaper_8.safetensors"
        }
      },
      "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {
          "batch_size": 1,
          "height": 512,
          "width": 768
        }
      },
      "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {
          "clip": ["4", 1],
          "text": "masterpiece, best quality, concept art, digital painting, fantasy, epic scene, dramatic lighting, cinematic, artstation, trending, highly detailed, intricate details"
        }
      },
      "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {
          "clip": ["4", 1],
          "text": "lowres, bad quality, blurry, jpeg artifacts, watermark, text, signature, amateur, ugly, deformed"
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
          "filename_prefix": "concept_art",
          "images": ["8", 0]
        }
      }
    }
  },
  {
    id: 'txt2img_product',
    name: '产品渲染',
    description: '生成专业的产品展示图和商业摄影效果',
    category: '写实',
    tags: ['文生图', '产品', '商业', '摄影'],
    difficulty: 'intermediate',
    recommendedModels: ['realisticVisionV51_v51VAE.safetensors', 'deliberate_v3.safetensors'],
    parameters: {
      steps: 30,
      cfg: 7,
      sampler: 'DPM++ SDE Karras',
      scheduler: 'normal',
      size: { width: 512, height: 512 }
    },
    workflowData: {
      "3": {
        "class_type": "KSampler",
        "inputs": {
          "cfg": 7,
          "denoise": 1,
          "latent_image": ["5", 0],
          "model": ["4", 0],
          "negative": ["7", 0],
          "positive": ["6", 0],
          "sampler_name": "dpmpp_sde_gpu",
          "scheduler": "karras",
          "seed": 0,
          "steps": 30
        }
      },
      "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
          "ckpt_name": "realisticVisionV51_v51VAE.safetensors"
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
          "text": "masterpiece, best quality, product photography, studio lighting, white background, professional, commercial, high resolution, 8k uhd, clean, minimalist"
        }
      },
      "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {
          "clip": ["4", 1],
          "text": "lowres, bad quality, blurry, jpeg artifacts, watermark, text, signature, messy background, cluttered"
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
          "filename_prefix": "product",
          "images": ["8", 0]
        }
      }
    }
  },
  {
    id: 'txt2img_sdxl_turbo',
    name: 'SDXL Turbo 快速生成',
    description: '使用 SDXL Turbo 实现 4 步快速生成',
    category: 'SDXL',
    tags: ['文生图', 'SDXL', '快速', 'Turbo'],
    difficulty: 'beginner',
    recommendedModels: ['sd_xl_turbo_1.0_fp16.safetensors'],
    parameters: {
      steps: 4,
      cfg: 1,
      sampler: 'euler_ancestral',
      scheduler: 'normal',
      size: { width: 512, height: 512 }
    },
    workflowData: {
      "3": {
        "class_type": "KSampler",
        "inputs": {
          "cfg": 1,
          "denoise": 1,
          "latent_image": ["5", 0],
          "model": ["4", 0],
          "negative": ["7", 0],
          "positive": ["6", 0],
          "sampler_name": "euler_ancestral",
          "scheduler": "normal",
          "seed": 0,
          "steps": 4
        }
      },
      "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
          "ckpt_name": "sd_xl_turbo_1.0_fp16.safetensors"
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
          "text": "masterpiece, best quality, highly detailed"
        }
      },
      "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {
          "clip": ["4", 1],
          "text": ""
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
          "filename_prefix": "turbo",
          "images": ["8", 0]
        }
      }
    }
  },
  {
    id: 'txt2img_illustration',
    name: '插画风格',
    description: '生成精美的数字插画和艺术作品',
    category: '基础',
    tags: ['文生图', '插画', '艺术', '数字绘画'],
    difficulty: 'beginner',
    recommendedModels: ['dreamshaper_8.safetensors', 'revAnimated_v122.safetensors'],
    parameters: {
      steps: 28,
      cfg: 7,
      sampler: 'DPM++ 2M Karras',
      scheduler: 'normal',
      size: { width: 512, height: 768 }
    },
    workflowData: {
      "3": {
        "class_type": "KSampler",
        "inputs": {
          "cfg": 7,
          "denoise": 1,
          "latent_image": ["5", 0],
          "model": ["4", 0],
          "negative": ["7", 0],
          "positive": ["6", 0],
          "sampler_name": "dpmpp_2m_sde_gpu",
          "scheduler": "karras",
          "seed": 0,
          "steps": 28
        }
      },
      "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
          "ckpt_name": "dreamshaper_8.safetensors"
        }
      },
      "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {
          "batch_size": 1,
          "height": 768,
          "width": 512
        }
      },
      "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {
          "clip": ["4", 1],
          "text": "masterpiece, best quality, illustration, digital art, detailed, vibrant colors, artistic, trending on artstation, beautiful composition"
        }
      },
      "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {
          "clip": ["4", 1],
          "text": "lowres, bad quality, blurry, jpeg artifacts, watermark, text, signature, ugly, deformed, amateur"
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
          "filename_prefix": "illustration",
          "images": ["8", 0]
        }
      }
    }
  }
]

export const getTemplatesByCategory = (category: string) => {
  return WORKFLOW_TEMPLATES.filter(template => template.category === category)
}

export const getTemplateById = (id: string) => {
  return WORKFLOW_TEMPLATES.find(template => template.id === id)
}

export const getAllCategories = () => {
  return [...new Set(WORKFLOW_TEMPLATES.map(template => template.category))]
}