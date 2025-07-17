#!/usr/bin/env python3
"""
流式音频传输系统测试脚本
测试性能统计和3kbps速率限制功能
"""

import subprocess
import time
import os
import signal
import sys

def test_streaming_with_stats():
    """测试带性能统计的流式传输"""
    print("=== 流式音频传输系统测试 ===")
    print("功能：")
    print("1. 音频流式编码和传输")
    print("2. 3kbps速率限制")
    print("3. 详细性能统计")
    print("4. 传输量、编码时间、传输时间、解码时间统计")
    print()
    
    # 启动接收端
    print("启动接收端...")
    receiver_port = 8892
    receiver_cmd = [
        "conda", "run", "-n", "esc", "python", "-m", "scripts.receiver",
        "--model_path", "./model/esc9kbps_base_adversarial",
        "--port", str(receiver_port),
        "--save_path", "./output/streaming_test"
    ]
    
    receiver_proc = subprocess.Popen(receiver_cmd, 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE,
                                   text=True)
    
    # 等待接收端启动
    print("等待接收端启动...")
    time.sleep(3)
    
    try:
        # 启动发送端
        print("启动发送端...")
        sender_cmd = [
            "conda", "run", "-n", "esc", "python", "-m", "scripts.sender",
            "--input", "./data/speech_1.wav",
            "--model_path", "./model/esc9kbps_base_adversarial",
            "--port", str(receiver_port)
        ]
        
        print("正在传输音频...")
        sender_proc = subprocess.run(sender_cmd, 
                                   capture_output=True, 
                                   text=True)
        
        print("发送端输出:")
        print(sender_proc.stdout)
        if sender_proc.stderr:
            print("发送端错误:", sender_proc.stderr)
        
        # 等待接收端完成
        time.sleep(2)
        
        # 获取接收端输出
        receiver_proc.terminate()
        receiver_stdout, receiver_stderr = receiver_proc.communicate(timeout=5)
        
        print("接收端输出:")
        print(receiver_stdout)
        if receiver_stderr:
            print("接收端错误:", receiver_stderr)
        
        # 检查输出文件
        output_dir = "./output/streaming_test"
        if os.path.exists(output_dir):
            files = os.listdir(output_dir)
            audio_files = [f for f in files if f.endswith('.wav')]
            if audio_files:
                print(f"\n生成的音频文件:")
                for file in audio_files:
                    filepath = os.path.join(output_dir, file)
                    size = os.path.getsize(filepath)
                    print(f"  {file} ({size:,} bytes)")
        
        print("\n=== 测试完成 ===")
        
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
    finally:
        # 清理进程
        try:
            receiver_proc.terminate()
            receiver_proc.wait(timeout=5)
        except:
            try:
                receiver_proc.kill()
            except:
                pass

def main():
    """主函数"""
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print(__doc__)
        return
    
    # 检查必要文件
    required_files = [
        "./model/esc9kbps_base_adversarial/config.yaml",
        "./model/esc9kbps_base_adversarial/model.pth",
        "./data/speech_1.wav",
        "./scripts/sender.py",
        "./scripts/receiver.py"
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print("错误：缺少必要文件:")
        for file in missing_files:
            print(f"  {file}")
        return
    
    # 创建输出目录
    os.makedirs("./output/streaming_test", exist_ok=True)
    
    # 运行测试
    test_streaming_with_stats()

if __name__ == "__main__":
    main()
