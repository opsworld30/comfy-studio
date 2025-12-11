"""认证工具函数"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from ..config import get_settings

settings = get_settings()

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    # bcrypt 限制密码长度为 72 字节
    if len(password.encode('utf-8')) > 72:
        password = password[:72]
    return pwd_context.hash(password)


def create_access_token(user_id: int, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "type": "access"
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(user_id: int, expires_delta: Optional[timedelta] = None) -> str:
    """创建刷新令牌"""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
    
    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh"
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """解码 JWT 令牌"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def get_token_expire_time(days: int = 0, minutes: int = 0) -> datetime:
    """获取令牌过期时间"""
    return datetime.now(timezone.utc) + timedelta(days=days, minutes=minutes)
