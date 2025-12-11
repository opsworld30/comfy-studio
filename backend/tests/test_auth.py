"""认证功能测试"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import User
from app.utils.auth import get_password_hash, verify_password


class TestAuth:
    """认证测试"""
    
    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient, db: AsyncSession):
        """测试用户注册成功"""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "password123",
                "full_name": "测试用户"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert "id" in data
        
        # 验证数据库中是否创建了用户
        result = await db.execute(select(User).where(User.username == "testuser"))
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.email == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: AsyncClient, db: AsyncSession):
        """测试注册重复用户名"""
        # 先创建一个用户
        user = User(
            username="existing",
            email="existing@example.com",
            hashed_password=get_password_hash("password123")
        )
        db.add(user)
        await db.commit()
        
        # 尝试注册相同用户名
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "existing",
                "email": "new@example.com",
                "password": "password123"
            }
        )
        
        assert response.status_code == 400
        assert "用户名已被注册" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, db: AsyncSession):
        """测试登录成功"""
        # 创建测试用户
        user = User(
            username="logintest",
            email="login@example.com",
            hashed_password=get_password_hash("password123"),
            is_active=True
        )
        db.add(user)
        await db.commit()
        
        # 登录
        response = await client.post(
            "/api/auth/login",
            json={
                "username": "logintest",
                "password": "password123"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "logintest"
    
    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, db: AsyncSession):
        """测试错误密码登录"""
        # 创建测试用户
        user = User(
            username="wrongpwd",
            email="wrongpwd@example.com",
            hashed_password=get_password_hash("password123")
        )
        db.add(user)
        await db.commit()
        
        # 使用错误密码登录
        response = await client.post(
            "/api/auth/login",
            json={
                "username": "wrongpwd",
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401
        assert "用户名或密码错误" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_get_current_user(self, client: AsyncClient, db: AsyncSession):
        """测试获取当前用户信息"""
        # 创建并登录用户
        user = User(
            username="currentuser",
            email="current@example.com",
            hashed_password=get_password_hash("password123"),
            is_active=True
        )
        db.add(user)
        await db.commit()
        
        # 登录获取 token
        login_response = await client.post(
            "/api/auth/login",
            json={
                "username": "currentuser",
                "password": "password123"
            }
        )
        token = login_response.json()["access_token"]
        
        # 获取当前用户信息
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "currentuser"
        assert data["email"] == "current@example.com"
    
    @pytest.mark.asyncio
    async def test_refresh_token(self, client: AsyncClient, db: AsyncSession):
        """测试刷新令牌"""
        # 创建并登录用户
        user = User(
            username="refreshtest",
            email="refresh@example.com",
            hashed_password=get_password_hash("password123"),
            is_active=True
        )
        db.add(user)
        await db.commit()
        
        # 登录获取 token
        login_response = await client.post(
            "/api/auth/login",
            json={
                "username": "refreshtest",
                "password": "password123"
            }
        )
        refresh_token = login_response.json()["refresh_token"]
        
        # 刷新令牌
        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_change_password(self, client: AsyncClient, db: AsyncSession):
        """测试修改密码"""
        # 创建并登录用户
        user = User(
            username="changepwd",
            email="changepwd@example.com",
            hashed_password=get_password_hash("oldpassword"),
            is_active=True
        )
        db.add(user)
        await db.commit()
        
        # 登录获取 token
        login_response = await client.post(
            "/api/auth/login",
            json={
                "username": "changepwd",
                "password": "oldpassword"
            }
        )
        token = login_response.json()["access_token"]
        
        # 修改密码
        response = await client.post(
            "/api/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "old_password": "oldpassword",
                "new_password": "newpassword123"
            }
        )
        
        assert response.status_code == 200
        
        # 验证新密码可以登录
        new_login = await client.post(
            "/api/auth/login",
            json={
                "username": "changepwd",
                "password": "newpassword123"
            }
        )
        assert new_login.status_code == 200


class TestPasswordHashing:
    """密码加密测试"""
    
    def test_password_hash(self):
        """测试密码哈希"""
        password = "testpassword123"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert verify_password(password, hashed)
        assert not verify_password("wrongpassword", hashed)
