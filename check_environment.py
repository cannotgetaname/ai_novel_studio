#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Writer 环境检测脚本
用于诊断部署问题
"""

import sys
import os
import platform
import subprocess

def print_header(title):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print('='*50)

def check_python():
    print_header("Python 环境")
    print(f"Python 版本: {sys.version}")
    print(f"Python 路径: {sys.executable}")
    print(f"平台: {platform.platform()}")
    print(f"系统: {platform.system()}")
    print(f"架构: {platform.machine()}")

    # 检查 Python 版本
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 9):
        print("❌ Python 版本过低，建议使用 Python 3.9+")
        return False
    print("✅ Python 版本符合要求 (3.9+)")
    return True

def check_dependencies():
    print_header("依赖检测")

    required_packages = {
        'nicegui': 'NiceGUI',
        'openai': 'OpenAI',
        'chromadb': 'ChromaDB',
        'networkx': 'NetworkX',
    }

    all_ok = True
    for package, name in required_packages.items():
        try:
            mod = __import__(package)
            version = getattr(mod, '__version__', 'unknown')
            print(f"✅ {name}: {version}")
        except ImportError:
            print(f"❌ {name}: 未安装")
            all_ok = False

    return all_ok

def check_files():
    print_header("文件检测")

    required_files = [
        'main.py',
        'backend.py',
        'config.json',
        'requirements.txt',
    ]

    optional_files = [
        'config.example.json',
        'novel_modules/__init__.py',
    ]

    all_ok = True
    for f in required_files:
        if os.path.exists(f):
            print(f"✅ {f}")
        else:
            print(f"❌ {f} - 缺失")
            all_ok = False

    for f in optional_files:
        if os.path.exists(f):
            print(f"✅ {f} (可选)")
        else:
            print(f"⚠️  {f} (可选) - 缺失")

    return all_ok

def check_directories():
    print_header("目录检测")

    dirs_to_check = [
        'projects',
        'novel_modules',
        'chroma_db',
    ]

    for d in dirs_to_check:
        if os.path.exists(d):
            print(f"✅ {d}/")
        else:
            print(f"⚠️  {d}/ - 不存在（首次运行会自动创建）")

def check_config():
    print_header("配置检测")

    if not os.path.exists('config.json'):
        print("❌ config.json 不存在")
        return False

    try:
        import json
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 检查必要配置项
        checks = [
            ('api_key', 'API Key'),
            ('base_url', 'Base URL'),
            ('models', '模型配置'),
            ('prompts', '提示词配置'),
        ]

        for key, name in checks:
            value = config.get(key)
            if value:
                if key == 'api_key':
                    # 隐藏 API Key
                    masked = value[:8] + '***' + value[-4:] if len(value) > 12 else '***'
                    print(f"✅ {name}: {masked}")
                else:
                    print(f"✅ {name}: 已配置")
            else:
                print(f"❌ {name}: 未配置")

        # 检查模型配置
        models = config.get('models', {})
        temps = config.get('temperatures', {})
        print(f"\n模型配置: {len(models)} 个任务")
        for task, model in models.items():
            temp = temps.get(task, 'N/A')
            print(f"  - {task}: {model} (temp: {temp})")

        return True

    except json.JSONDecodeError as e:
        print(f"❌ config.json 格式错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 读取配置失败: {e}")
        return False

def check_permissions():
    print_header("权限检测")

    # 检查当前目录写权限
    test_file = ".write_test"
    try:
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        print("✅ 当前目录可写")
    except Exception as e:
        print(f"❌ 当前目录不可写: {e}")
        return False

    return True

def check_network():
    print_header("网络检测")

    try:
        import urllib.request
        # 测试连接到 OpenAI API (使用配置中的 base_url)
        import json
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)

        base_url = config.get('base_url', 'https://api.openai.com')

        print(f"正在测试连接: {base_url}")
        # 简单的连接测试
        import socket
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        host = parsed.netloc

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, 443))
        sock.close()

        if result == 0:
            print(f"✅ 可以连接到 {host}")
            return True
        else:
            print(f"❌ 无法连接到 {host}")
            print("   请检查网络连接或代理设置")
            return False

    except Exception as e:
        print(f"⚠️  网络检测失败: {e}")
        return None

def check_chromadb():
    print_header("ChromaDB 检测")

    try:
        import chromadb
        print(f"✅ ChromaDB 版本: {chromadb.__version__}")

        # 测试创建客户端
        client = chromadb.Client()
        print("✅ ChromaDB 内存客户端创建成功")
        return True

    except Exception as e:
        print(f"❌ ChromaDB 问题: {e}")
        return False

def main():
    print("""
╔════════════════════════════════════════════════════╗
║       AI Writer 环境检测工具                       ║
║       Environment Diagnostic Tool                  ║
╚════════════════════════════════════════════════════╝
""")

    results = {
        'Python': check_python(),
        '依赖': check_dependencies(),
        '文件': check_files(),
        '配置': check_config(),
        '权限': check_permissions(),
        '网络': check_network(),
        'ChromaDB': check_chromadb(),
    }

    check_directories()

    print_header("检测结果汇总")

    all_ok = True
    for name, result in results.items():
        if result is True:
            print(f"✅ {name}: 正常")
        elif result is False:
            print(f"❌ {name}: 有问题")
            all_ok = False
        else:
            print(f"⚠️  {name}: 无法检测")

    print()
    if all_ok:
        print("🎉 环境检测通过，可以启动应用！")
        print("   运行命令: python main.py")
    else:
        print("⚠️  检测到问题，请根据上述提示修复后重试")

    print()
    input("按回车键退出...")

if __name__ == "__main__":
    main()