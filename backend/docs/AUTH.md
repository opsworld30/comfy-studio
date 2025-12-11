# 认证系统文档

## 概述

ComfyUI Studio 使用 JWT (JSON Web Token) 认证系统，提供安全的用户身份验证和授权功能。

## 技术栈

- **JWT**: 使用 `python-jose` 生成和验证令牌
- **密码加密**: 使用 `passlib` + `bcrypt` 进行密码哈希
- **令牌类型**: Access Token (30分钟) + Refresh Token (7天)

## API 端点

### 1. 用户注册

```http
POST /api/auth/register
Content-Type: application/json

{
  "username": "testuser",
  "email": "test@example.com",
  "password": "password123",
  "full_name": "测试用户"
}
```

**响应**:
```json
{
  "id": 1,
  "username": "testuser",
  "email": "test@example.com",
  "full_name": "测试用户",
  "is_active": true,
  "is_superuser": false,
  "avatar": "",
  "created_at": "2025-12-11T03:00:00Z",
  "last_login": null
}
```

### 2. 用户登录

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "testuser",
  "password": "password123"
}
```

**响应**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "testuser",
    "email": "test@example.com",
    ...
  }
}
```

### 3. 刷新令牌

```http
POST /api/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### 4. 获取当前用户信息

```http
GET /api/auth/me
Authorization: Bearer <access_token>
```

### 5. 更新用户信息

```http
PUT /api/auth/me
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "email": "newemail@example.com",
  "full_name": "新名字",
  "avatar": "https://example.com/avatar.jpg"
}
```

### 6. 修改密码

```http
POST /api/auth/change-password
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "old_password": "oldpassword",
  "new_password": "newpassword123"
}
```

### 7. 登出

```http
POST /api/auth/logout
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

## 使用方式

### 在路由中使用认证

```python
from fastapi import APIRouter, Depends
from app.dependencies.auth import get_current_user, get_current_superuser
from app.models import User

router = APIRouter()

# 需要登录的端点
@router.get("/protected")
async def protected_route(current_user: User = Depends(get_current_user)):
    return {"message": f"Hello {current_user.username}"}

# 需要管理员权限的端点
@router.delete("/admin-only")
async def admin_route(current_user: User = Depends(get_current_superuser)):
    return {"message": "Admin access granted"}

# 可选认证（允许未登录访问）
from app.dependencies.auth import get_current_user_optional

@router.get("/optional-auth")
async def optional_auth_route(current_user: User | None = Depends(get_current_user_optional)):
    if current_user:
        return {"message": f"Hello {current_user.username}"}
    return {"message": "Hello guest"}
```

## 配置

在 `.env` 文件中配置:

```env
# JWT 密钥（生产环境必须修改为随机字符串）
SECRET_KEY=your-secret-key-change-in-production-min-32-chars

# JWT 算法
ALGORITHM=HS256

# Access Token 过期时间（分钟）
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Refresh Token 过期时间（天）
REFRESH_TOKEN_EXPIRE_DAYS=7
```

## 初始化

### 创建默认管理员

```bash
cd backend
uv run python scripts/create_admin.py
```

默认管理员账号:
- 用户名: `admin`
- 密码: `admin123`
- ⚠️ **请立即修改默认密码！**

## 安全建议

1. **生产环境必须修改 SECRET_KEY**
   ```bash
   # 生成随机密钥
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **使用 HTTPS** - 生产环境必须使用 HTTPS 传输令牌

3. **定期更换密钥** - 建议定期更换 SECRET_KEY

4. **令牌存储** - 前端应将令牌存储在 httpOnly cookie 或安全的存储中

5. **密码策略** - 建议实施更强的密码策略（长度、复杂度等）

## 数据库模型

### User 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| username | String(50) | 用户名（唯一） |
| email | String(255) | 邮箱（唯一） |
| hashed_password | String(255) | 密码哈希 |
| full_name | String(100) | 全名 |
| is_active | Boolean | 是否激活 |
| is_superuser | Boolean | 是否超级管理员 |
| avatar | Text | 头像 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |
| last_login | DateTime | 最后登录时间 |

### RefreshToken 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| user_id | Integer | 用户ID（外键） |
| token | String(500) | 刷新令牌 |
| expires_at | DateTime | 过期时间 |
| created_at | DateTime | 创建时间 |
| revoked | Boolean | 是否已撤销 |

## 测试

运行认证测试:

```bash
cd backend
uv run pytest tests/test_auth.py -v
```

## 常见问题

### Q: 如何延长令牌有效期？

A: 修改 `.env` 中的 `ACCESS_TOKEN_EXPIRE_MINUTES` 和 `REFRESH_TOKEN_EXPIRE_DAYS`

### Q: 如何实现"记住我"功能？

A: 前端可以选择性地存储 refresh_token，并在 access_token 过期时自动刷新

### Q: 如何撤销所有用户的令牌？

A: 修改 `SECRET_KEY` 会使所有现有令牌失效

### Q: 如何实现单点登录？

A: 可以在登录时撤销该用户的所有旧 refresh_token
