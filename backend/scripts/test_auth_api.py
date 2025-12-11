"""测试认证 API"""
import asyncio
import httpx


async def test_auth():
    """测试认证流程"""
    base_url = "http://localhost:8000/api"
    
    async with httpx.AsyncClient() as client:
        print("🧪 测试认证 API\n")
        
        # 1. 测试注册
        print("1️⃣ 测试用户注册...")
        register_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "test123456",
            "full_name": "测试用户"
        }
        
        try:
            response = await client.post(f"{base_url}/auth/register", json=register_data)
            if response.status_code == 201:
                print("   ✅ 注册成功")
                print(f"   用户信息: {response.json()}")
            elif response.status_code == 400:
                print(f"   ⚠️  用户已存在: {response.json()['detail']}")
            else:
                print(f"   ❌ 注册失败: {response.text}")
        except Exception as e:
            print(f"   ❌ 请求失败: {e}")
            print("   💡 请确保后端服务已启动: uv run python main.py")
            return
        
        print()
        
        # 2. 测试登录
        print("2️⃣ 测试用户登录...")
        login_data = {
            "username": "admin",
            "password": "admin123"
        }
        
        response = await client.post(f"{base_url}/auth/login", json=login_data)
        if response.status_code == 200:
            print("   ✅ 登录成功")
            data = response.json()
            access_token = data["access_token"]
            refresh_token = data["refresh_token"]
            print(f"   用户: {data['user']['username']}")
            print(f"   Access Token: {access_token[:50]}...")
        else:
            print(f"   ❌ 登录失败: {response.text}")
            return
        
        print()
        
        # 3. 测试获取当前用户信息
        print("3️⃣ 测试获取当前用户信息...")
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await client.get(f"{base_url}/auth/me", headers=headers)
        if response.status_code == 200:
            print("   ✅ 获取成功")
            print(f"   用户信息: {response.json()}")
        else:
            print(f"   ❌ 获取失败: {response.text}")
        
        print()
        
        # 4. 测试刷新令牌
        print("4️⃣ 测试刷新令牌...")
        response = await client.post(
            f"{base_url}/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        if response.status_code == 200:
            print("   ✅ 刷新成功")
            data = response.json()
            print(f"   新 Access Token: {data['access_token'][:50]}...")
        else:
            print(f"   ❌ 刷新失败: {response.text}")
        
        print()
        print("✅ 认证系统测试完成！")


if __name__ == "__main__":
    asyncio.run(test_auth())
