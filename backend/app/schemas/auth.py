"""认证相关的 Pydantic Schema"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


# ============ 用户相关 Schema ============

class UserBase(BaseModel):
    """用户基础信息"""
    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_-]+$")
    email: EmailStr
    full_name: Optional[str] = ""


class UserCreate(UserBase):
    """用户注册"""
    password: str = Field(..., min_length=6, max_length=100)
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError('密码长度至少6位')
        return v


class UserUpdate(BaseModel):
    """用户信息更新"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    avatar: Optional[str] = None


class UserChangePassword(BaseModel):
    """修改密码"""
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=100)


class UserInDB(UserBase):
    """数据库中的用户（包含敏感信息）"""
    id: int
    hashed_password: str
    is_active: bool
    is_superuser: bool
    avatar: str
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserResponse(UserBase):
    """用户响应（不含敏感信息）"""
    id: int
    is_active: bool
    is_superuser: bool
    avatar: str
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ============ 认证相关 Schema ============

class Token(BaseModel):
    """访问令牌响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """JWT Token 载荷"""
    sub: int  # user_id
    exp: datetime
    type: str  # "access" or "refresh"


class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求"""
    refresh_token: str


class LoginResponse(BaseModel):
    """登录响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
