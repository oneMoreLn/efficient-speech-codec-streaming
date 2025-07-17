#!/usr/bin/env python3
"""
简单测试脚本，验证流式传输功能
"""

import os
import sys
import time
import subprocess
import signal
import threading

def test_streaming_functionality():
    """测试流式传输功能"""
    print("=== 流式传输功能测试 ===")
    
    # 检查必要文件
    required_files = [
        "data/speech_1.wav",
        "model/esc9kbps_base_adversarial/config.yaml",
        "model/esc9kbps_base_adversarial/model.pth"
    ]
    
    for file_path in required_files:
        if not os.path.exists(file_path):
            print(f"错误: 找不到必要文件 {file_path}")
            return False
    
    # 创建测试输出目录
    test_output = "./output/test_streaming"
    os.makedirs(test_output, exist_ok=True)
    
    print("1. 测试本地流式压缩...")
    try:
        # 测试改进的compress脚本的流式功能
        result = subprocess.run([
            sys.executable, "-m", "scripts.compress",
            "--input", "./data/speech_1.wav",
            "--save_path", test_output,
            "--model_path", "./model/esc9kbps_base_adversarial",
            "--num_streams", "6",
            "--device", "cpu",
            "--streaming",
            "--chunk_size", "8000",
            "--overlap_size", "800"
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print("✓ 本地流式压缩测试通过")
        else:
            print(f"✗ 本地流式压缩测试失败: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ 本地流式压缩测试超时")
        return False
    except Exception as e:
        print(f"✗ 本地流式压缩测试异常: {e}")
        return False
    
    print("2. 测试网络流式传输...")
    
    # 启动接收端
    receiver_process = None
    try:
        receiver_process = subprocess.Popen([
            sys.executable, "-m", "scripts.receiver",
            "--host", "localhost",
            "--port", "8889",  # 使用不同端口避免冲突
            "--save_path", test_output,
            "--model_path", "./model/esc9kbps_base_adversarial",
            "--device", "cpu"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 等待接收端启动
        time.sleep(3)
        
        # 启动发送端
        sender_result = subprocess.run([
            sys.executable, "-m", "scripts.sender",
            "--input", "./data/speech_1.wav",
            "--host", "localhost",
            "--port", "8889",
            "--model_path", "./model/esc9kbps_base_adversarial",
            "--num_streams", "6",
            "--device", "cpu",
            "--chunk_size", "8000",
            "--overlap_size", "800"
        ], capture_output=True, text=True, timeout=60)
        
        # 等待接收端处理完成
        time.sleep(2)
        
        if sender_result.returncode == 0:
            print("✓ 网络流式传输测试通过")
        else:
            print(f"✗ 网络流式传输测试失败: {sender_result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ 网络流式传输测试超时")
        return False
    except Exception as e:
        print(f"✗ 网络流式传输测试异常: {e}")
        return False
    finally:
        # 清理接收端进程
        if receiver_process:
            receiver_process.terminate()
            receiver_process.wait()
    
    print("3. 检查输出文件...")
    
    # 检查输出文件
    expected_files = [
        "decoded_9.0kbps_speech_1.wav",
        "encoded_9.0kbps_speech_1.pth"
    ]
    
    found_files = []
    for file_name in os.listdir(test_output):
        if file_name.endswith(('.wav', '.pth')):
            found_files.append(file_name)
    
    if found_files:
        print(f"✓ 找到输出文件: {found_files}")
        print("✓ 所有测试通过！")
        return True
    else:
        print("✗ 未找到预期的输出文件")
        return False

def main():
    """主函数"""
    success = test_streaming_functionality()
    
    if success:
        print("\n🎉 流式传输功能测试成功！")
        print("现在可以使用以下命令进行完整演示:")
        print("./scripts/demo_streaming.sh")
        return 0
    else:
        print("\n❌ 流式传输功能测试失败")
        print("请检查模型文件和依赖是否正确安装")
        return 1

if __name__ == "__main__":
    sys.exit(main())
