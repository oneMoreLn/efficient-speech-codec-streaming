#!/usr/bin/env python3
"""
麦克风和文件传输演示脚本
展示两种音频传输模式的区别和用法
"""

import sys
import os
import time
import signal
import threading
import subprocess

def print_banner():
    """显示程序横幅"""
    print("=" * 60)
    print("    ESC 音频流式传输系统 - 演示脚本")
    print("=" * 60)
    print("支持的传输模式：")
    print("  1. 文件传输模式 - 从音频文件读取并传输")
    print("  2. 麦克风传输模式 - 从麦克风实时采集并传输")
    print("=" * 60)

def demo_file_streaming():
    """演示文件流式传输"""
    print("\n🎵 演示 1: 文件流式传输")
    print("-" * 40)
    
    # 检查测试文件
    test_files = [
        "./data/speech_1.wav",
        "./data/speech_2.wav", 
        "./data/speech_3.wav"
    ]
    
    available_files = [f for f in test_files if os.path.exists(f)]
    
    if not available_files:
        print("❌ 没有找到测试音频文件")
        print("请确保在data/目录下有音频文件")
        return
    
    print(f"找到 {len(available_files)} 个测试文件")
    
    # 选择测试文件
    test_file = available_files[0]
    print(f"使用测试文件: {test_file}")
    
    print("\n启动接收端...")
    
    # 启动接收端
    receiver_cmd = [
        "conda", "run", "-n", "esc", "python", "-m", "scripts.receiver",
        "--model_path", "./model/esc9kbps_base_adversarial",
        "--port", "8999",
        "--save_path", "./output/demo_file"
    ]
    
    receiver_proc = subprocess.Popen(receiver_cmd, 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE,
                                   text=True)
    
    # 等待接收端启动
    time.sleep(2)
    
    try:
        print("启动发送端 (文件模式)...")
        print("传输文件:", test_file)
        
        # 启动发送端
        sender_cmd = [
            "conda", "run", "-n", "esc", "python", "-m", "scripts.sender",
            "--model_path", "./model/esc9kbps_base_adversarial",
            "--audio_file", test_file,
            "--port", "8999"
        ]
        
        sender_proc = subprocess.Popen(sender_cmd,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     text=True)
        
        # 等待传输完成
        sender_proc.wait()
        
        print("✅ 文件传输完成")
        
        # 显示输出
        stdout, stderr = sender_proc.communicate()
        if stdout:
            print("发送端输出:")
            print(stdout)
        
    except Exception as e:
        print(f"❌ 文件传输失败: {e}")
    finally:
        # 停止接收端
        receiver_proc.terminate()
        try:
            receiver_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            receiver_proc.kill()

def demo_microphone_streaming():
    """演示麦克风流式传输"""
    print("\n🎤 演示 2: 麦克风流式传输")
    print("-" * 40)
    
    # 检查PyAudio
    try:
        result = subprocess.run([
            "conda", "run", "-n", "esc", "python", "-c", "import pyaudio"
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print("❌ PyAudio 未安装或无法导入")
            print("请运行安装脚本: ./install_microphone_deps.sh")
            return
        
        print("✅ PyAudio 可用")
        
    except Exception as e:
        print(f"❌ 检查PyAudio失败: {e}")
        return
    
    print("\n启动接收端...")
    
    # 启动接收端
    receiver_cmd = [
        "conda", "run", "-n", "esc", "python", "-m", "scripts.receiver",
        "--model_path", "./model/esc9kbps_base_adversarial",
        "--port", "8998",
        "--save_path", "./output/demo_microphone"
    ]
    
    receiver_proc = subprocess.Popen(receiver_cmd, 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE,
                                   text=True)
    
    # 等待接收端启动
    time.sleep(2)
    
    sender_proc = None
    try:
        print("启动发送端 (麦克风模式)...")
        print("⚠️  请对着麦克风说话")
        print("⏰ 将录制10秒钟")
        print("🛑 按Ctrl+C可提前停止")
        
        # 启动发送端
        sender_cmd = [
            "conda", "run", "-n", "esc", "python", "-m", "scripts.sender",
            "--model_path", "./model/esc9kbps_base_adversarial",
            "--microphone",
            "--port", "8998"
        ]
        
        sender_proc = subprocess.Popen(sender_cmd,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     text=True)
        
        # 等待10秒或用户中断
        for i in range(10):
            time.sleep(1)
            if sender_proc.poll() is not None:
                break
            print(f"录制中... {i+1}/10秒")
        
        # 停止发送端
        sender_proc.terminate()
        try:
            sender_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            sender_proc.kill()
        
        print("✅ 麦克风传输完成")
        
    except KeyboardInterrupt:
        print("\n🛑 用户中断")
        if sender_proc:
            sender_proc.terminate()
    except Exception as e:
        print(f"❌ 麦克风传输失败: {e}")
    finally:
        # 停止发送端
        if sender_proc:
            try:
                sender_proc.terminate()
                sender_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                sender_proc.kill()
            except:
                pass
        
        # 停止接收端
        receiver_proc.terminate()
        try:
            receiver_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            receiver_proc.kill()

def show_comparison():
    """显示两种模式的比较"""
    print("\n📊 传输模式对比")
    print("=" * 60)
    
    comparison = [
        ("特性", "文件传输", "麦克风传输"),
        ("数据源", "预存音频文件", "实时麦克风采集"),
        ("延迟", "文件读取延迟", "实时低延迟"),
        ("交互性", "一次性传输", "实时交互"),
        ("资源消耗", "较低", "较高"),
        ("适用场景", "测试、批处理", "实时通话、直播"),
        ("停止方式", "传输完成自动停止", "手动停止"),
        ("依赖", "音频文件", "音频硬件+PyAudio"),
    ]
    
    for row in comparison:
        print(f"{row[0]:<12} | {row[1]:<20} | {row[2]:<20}")
    
    print("=" * 60)

def main():
    """主函数"""
    print_banner()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "file":
            demo_file_streaming()
            return
        elif sys.argv[1] == "microphone":
            demo_microphone_streaming()
            return
        elif sys.argv[1] == "compare":
            show_comparison()
            return
        elif sys.argv[1] == "--help":
            print("用法:")
            print("  python demo.py              # 完整演示")
            print("  python demo.py file         # 只演示文件传输")
            print("  python demo.py microphone   # 只演示麦克风传输")
            print("  python demo.py compare      # 显示对比表")
            return
    
    # 检查必要文件
    required_files = [
        "./model/esc9kbps_base_adversarial/config.yaml",
        "./model/esc9kbps_base_adversarial/model.pth",
        "./scripts/sender.py",
        "./scripts/receiver.py"
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print("❌ 缺少必要文件:")
        for file in missing_files:
            print(f"  {file}")
        return
    
    # 创建输出目录
    os.makedirs("./output/demo_file", exist_ok=True)
    os.makedirs("./output/demo_microphone", exist_ok=True)
    
    print("开始演示...")
    
    # 演示文件传输
    demo_file_streaming()
    
    print("\n" + "=" * 60)
    
    # 演示麦克风传输
    demo_microphone_streaming()
    
    # 显示对比
    show_comparison()
    
    print("\n🎉 演示完成!")
    print("生成的文件保存在 ./output/demo_file 和 ./output/demo_microphone 目录中")

if __name__ == "__main__":
    main()
