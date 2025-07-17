#!/usr/bin/env python3
"""
简单的流式传输测试脚本
"""

import subprocess
import sys
import time
import signal
import os

def cleanup_port(port):
    """清理端口"""
    print(f"Cleaning up port {port}...")
    try:
        # 使用lsof查找并杀死占用端口的进程
        result = subprocess.run(['lsof', '-ti', f':{port}'], 
                              capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid.isdigit():
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        print(f"Killed process {pid}")
                        time.sleep(1)
                    except:
                        pass
    except:
        pass

def test_streaming():
    """测试流式传输"""
    port = 8889  # 使用不同的端口避免冲突
    
    # 清理端口
    cleanup_port(port)
    
    print("=== 流式传输测试 ===")
    
    # 检查必要文件
    if not os.path.exists("data/speech_1.wav"):
        print("错误: 找不到 data/speech_1.wav")
        return False
    
    if not os.path.exists("model/esc9kbps_base_adversarial"):
        print("错误: 找不到模型文件夹")
        return False
    
    # 创建输出目录
    os.makedirs("output/test_streaming", exist_ok=True)
    
    print("1. 启动接收端...")
    receiver_process = subprocess.Popen([
        "python", "-m", "scripts.receiver",
        "--host", "localhost",
        "--port", str(port),
        "--save_path", "./output/test_streaming",
        "--model_path", "./model/esc9kbps_base_adversarial",
        "--device", "cpu"
    ])
    
    # 等待接收端启动
    time.sleep(3)
    
    print("2. 启动发送端...")
    sender_result = subprocess.run([
        "python", "-m", "scripts.sender",
        "--input", "./data/speech_1.wav",
        "--host", "localhost",
        "--port", str(port),
        "--model_path", "./model/esc9kbps_base_adversarial",
        "--num_streams", "6",
        "--device", "cpu",
        "--chunk_size", "8000",
        "--overlap_size", "800"
    ], timeout=120)
    
    print("发送端完成，等待接收端处理...")
    # 等待更长时间让接收端处理完所有数据
    time.sleep(5)
    
    # 发送结束信号让接收端正常退出
    receiver_process.terminate()
    
    # 等待接收端进程结束
    try:
        receiver_process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        receiver_process.kill()
        receiver_process.wait()
    
    print("3. 检查输出文件...")
    output_files = os.listdir("output/test_streaming")
    if output_files:
        print(f"✓ 找到输出文件: {output_files}")
        return True
    else:
        print("✗ 未找到输出文件")
        return False

if __name__ == "__main__":
    try:
        success = test_streaming()
        if success:
            print("\n✓ 流式传输测试成功!")
        else:
            print("\n✗ 流式传输测试失败")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试异常: {e}")
        sys.exit(1)
