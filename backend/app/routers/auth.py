"""认证路由"""
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db
from ..models import User, RefreshToken, UserSettings
from ..schemas.auth import (
    UserCreate, UserResponse, LoginRequest, LoginResponse,
    RefreshTokenRequest, Token, UserUpdate, UserChangePassword
)
from ..utils.auth import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token,
    decode_token, get_token_expire_time
)
from ..dependencies.auth import get_current_user, get_current_active_user

router = APIRouter(prefix="/auth", tags=["认证"])


async def is_registration_allowed(db: AsyncSession) -> bool:
    """检查是否允许注册"""
    result = await db.execute(
        select(UserSettings).where(UserSettings.key == "system_settings")
    )
    settings = result.scalar_one_or_none()
    if settings:
        return settings.value.get("allow_registration", True)
    return True  # 默认允许注册


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """用户注册"""
    # 检查是否允许注册
    if not await is_registration_allowed(db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="系统已关闭注册功能"
        )
    
    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == user_in.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已被注册"
        )
    
    # 检查邮箱是否已存在
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册"
        )
    
    # 创建用户
    user = User(
        username=user_in.username,
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        is_active=True,
        is_superuser=False
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return user


@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """用户登录"""
    # 查询用户
    result = await db.execute(select(User).where(User.username == login_data.username))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )
    
    # 生成令牌
    access_token = create_access_token(user.id)
    refresh_token_str = create_refresh_token(user.id)
    
    # 保存刷新令牌到数据库
    refresh_token = RefreshToken(
        user_id=user.id,
        token=refresh_token_str,
        expires_at=get_token_expire_time(days=7)
    )
    db.add(refresh_token)
    
    # 更新最后登录时间
    user.last_login = datetime.now(timezone.utc)
    
    await db.commit()
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token_str,
        "token_type": "bearer",
        "user": user
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """刷新访问令牌"""
    # 解码刷新令牌
    payload = decode_token(refresh_data.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌"
        )
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的刷新令牌"
        )
    
    # 验证刷新令牌是否在数据库中且未被撤销
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token == refresh_data.refresh_token,
            RefreshToken.user_id == int(user_id),
            RefreshToken.revoked == False
        )
    )
    db_token = result.scalar_one_or_none()
    
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="刷新令牌已失效"
        )
    
    # 检查是否过期
    if db_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="刷新令牌已过期"
        )
    
    # 生成新的访问令牌和刷新令牌
    access_token = create_access_token(int(user_id))
    new_refresh_token = create_refresh_token(int(user_id))
    
    # 撤销旧的刷新令牌
    db_token.revoked = True
    
    # 保存新的刷新令牌
    new_db_token = RefreshToken(
        user_id=int(user_id),
        token=new_refresh_token,
        expires_at=get_token_expire_time(days=7)
    )
    db.add(new_db_token)
    
    await db.commit()
    
    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }


@router.post("/logout")
async def logout(
    refresh_data: RefreshTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """用户登出（撤销刷新令牌）"""
    # 撤销指定的刷新令牌
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token == refresh_data.refresh_token,
            RefreshToken.user_id == current_user.id
        )
    )
    db_token = result.scalar_one_or_none()
    
    if db_token:
        db_token.revoked = True
        await db.commit()
    
    return {"message": "登出成功"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """获取当前用户信息"""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """更新当前用户信息"""
    # 如果更新邮箱，检查是否已被使用
    if user_update.email and user_update.email != current_user.email:
        result = await db.execute(select(User).where(User.email == user_update.email))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被使用"
            )
        current_user.email = user_update.email
    
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name
    
    if user_update.avatar is not None:
        current_user.avatar = user_update.avatar
    
    await db.commit()
    await db.refresh(current_user)
    
    return current_user


@router.post("/change-password")
async def change_password(
    password_data: UserChangePassword,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """修改密码"""
    # 验证旧密码
    if not verify_password(password_data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误"
        )
    
    # 更新密码
    current_user.hashed_password = get_password_hash(password_data.new_password)
    await db.commit()
    
    return {"message": "密码修改成功"}
