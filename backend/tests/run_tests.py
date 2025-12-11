"""
测试运行脚本
"""
import os
import sys
import subprocess
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置测试环境变量
os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"


def run_tests():
    """运行所有测试"""
    print("🧪 开始运行测试...")
    
    # 测试命令 - 使用uv运行
    commands = [
        # 运行所有测试
        ["uv", "run", "pytest", "tests/", "-v", "--tb=short"],
        
        # 运行单元测试
        # ["uv", "run", "pytest", "tests/test_services.py", "-v", "-m", "unit"],
        
        # 运行API测试
        # ["uv", "run", "pytest", "tests/test_api.py", "-v", "-m", "api"],
        
        # 运行模型测试
        # ["uv", "run", "pytest", "tests/test_models.py", "-v"],
        
        # 生成覆盖率报告
        # ["uv", "run", "pytest", "tests/", "--cov=app", "--cov-report=html"],
    ]
    
    for cmd in commands:
        print(f"\n📋 执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=project_root)
        
        if result.returncode != 0:
            print(f"❌ 测试失败，退出码: {result.returncode}")
            return False
    
    print("\n✅ 所有测试通过！")
    return True


def run_specific_test(test_file: str):
    """运行特定的测试文件"""
    test_path = Path(__file__).parent / test_file
    if not test_path.exists():
        print(f"❌ 测试文件不存在: {test_path}")
        return False
    
    print(f"🧪 运行测试文件: {test_file}")
    cmd = ["uv", "run", "pytest", str(test_path), "-v", "--tb=short"]
    result = subprocess.run(cmd, cwd=project_root)
    
    if result.returncode != 0:
        print(f"❌ 测试失败，退出码: {result.returncode}")
        return False
    
    print("✅ 测试通过！")
    return True


def run_with_coverage():
    """运行测试并生成覆盖率报告"""
    print("🧪 运行测试并生成覆盖率报告...")
    
    cmd = [
        "uv", "run", "pytest",
        "tests/",
        "--cov=app",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov",
        "--cov-report=xml",
        "-v"
    ]
    
    result = subprocess.run(cmd, cwd=project_root)
    
    if result.returncode == 0:
        print("\n✅ 测试完成！")
        print("📊 覆盖率报告已生成:")
        print("   - 终端报告: 已显示在上方")
        print("   - HTML报告: htmlcov/index.html")
        print("   - XML报告: coverage.xml")
        return True
    else:
        print(f"❌ 测试失败，退出码: {result.returncode}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="运行测试")
    parser.add_argument(
        "--file",
        help="运行特定的测试文件",
        default=None
    )
    parser.add_argument(
        "--coverage",
        help="生成覆盖率报告",
        action="store_true"
    )
    
    args = parser.parse_args()
    
    if args.file:
        success = run_specific_test(args.file)
    elif args.coverage:
        success = run_with_coverage()
    else:
        success = run_tests()
    
    sys.exit(0 if success else 1)