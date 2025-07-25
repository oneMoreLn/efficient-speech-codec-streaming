#!/usr/bin/env python3
"""
麦克风流式传输测试脚本
测试从麦克风实时采集音频并流式传输的功能
"""

import subprocess
import time
import os
import sys
import signal

def test_microphone_streaming():
    """测试麦克风流式传输"""
    print("=== 麦克风流式传输测试 ===")
    print("功能：")
    print("1. 从麦克风实时采集16kHz音频")
    print("2. 流式编码和传输")
    print("3. 性能统计和监控")
    print("4. 支持速率限制")
    print()
    
    # 检查依赖
    print("检查依赖...")
    try:
        import pyaudio
        print("✅ PyAudio 已安装")
    except ImportError:
        print("❌ PyAudio 未安装")
        print("请运行: pip install pyaudio")
        return False
    
    # 列出音频设备
    print("\n列出可用音频设备...")
    try:
        result = subprocess.run([
            "conda", "run", "-n", "esc", "python", "-m", "scripts.sender",
            "--list_devices",
            "--model_path", "./model/esc9kbps_base_adversarial"
        ], capture_output=True, text=True, timeout=10)
        
        print("可用设备：")
        print(result.stdout)
        
    except subprocess.TimeoutExpired:
        print("⏱️ 列出设备超时")
    except Exception as e:
        print(f"❌ 列出设备失败: {e}")
    
    # 启动接收端
    print("\n启动接收端...")
    receiver_port = 8999
    receiver_cmd = [
        "conda", "run", "-n", "esc", "python", "-m", "scripts.receiver",
        "--model_path", "./model/esc9kbps_base_adversarial",
        "--port", str(receiver_port),
        "--save_path", "./output/microphone_test"
    ]
    
    receiver_proc = subprocess.Popen(receiver_cmd, 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE,
                                   text=True)
    
    # 等待接收端启动
    time.sleep(3)
    
    try:
        # 测试配置
        test_configs = [
            {
                "name": "基本麦克风流式传输",
                "args": ["--microphone"],
                "duration": 10
            },
            {
                "name": "麦克风流式传输 + 速率限制",
                "args": ["--microphone", "--enable_rate_limit"],
                "duration": 10
            },
            {
                "name": "麦克风流式传输 + 音频保存",
                "args": ["--microphone", "--mic_save_path", "./output/microphone_test/recorded_audio.wav"],
                "duration": 8
            },
            {
                "name": "完整功能测试 (速率限制 + 音频保存)",
                "args": ["--microphone", "--enable_rate_limit", "--mic_save_path", "./output/microphone_test/"],
                "duration": 8
            }
        ]
        
        for config in test_configs:
            print(f"\n{'='*50}")
            print(f"测试: {config['name']}")
            print(f"持续时间: {config['duration']}秒")
            print('='*50)
            
            # 构建发送端命令
            sender_cmd = [
                "conda", "run", "-n", "esc", "python", "-m", "scripts.sender",
                "--model_path", "./model/esc9kbps_base_adversarial",
                "--port", str(receiver_port)
            ] + config['args']
            
            print(f"命令: {' '.join(sender_cmd)}")
            print("开始录制...")
            print("⚠️  请对着麦克风说话")
            print(f"⏰ 将在{config['duration']}秒后自动停止")
            
            # 启动发送端
            start_time = time.time()
            sender_proc = subprocess.Popen(sender_cmd,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE,
                                         text=True)
            
            # 等待指定时间
            time.sleep(config['duration'])
            
            # 停止发送端
            sender_proc.terminate()
            try:
                sender_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                sender_proc.kill()
                sender_proc.wait()
            
            end_time = time.time()
            actual_duration = end_time - start_time
            
            print(f"实际录制时间: {actual_duration:.2f}秒")
            
            # 获取输出
            stdout, stderr = sender_proc.communicate()
            
            # 提取统计信息
            if stdout:
                lines = stdout.split('\n')
                for line in lines:
                    if "Rate limiting:" in line:
                        print(f"速率限制: {line.split('Rate limiting:')[1].strip()}")
                    elif "chunks processed" in line:
                        print(f"处理块数: {line.strip()}")
                    elif "Average transmission rate:" in line:
                        print(f"平均传输速率: {line.split('Average transmission rate:')[1].strip()}")
            
            if stderr and "warning" not in stderr.lower():
                print(f"⚠️  警告: {stderr}")
            
            print(f"✅ 完成: {config['name']}")
            
            # 休息一下
            time.sleep(2)
        
        print(f"\n{'='*50}")
        print("麦克风流式传输测试完成！")
        
        # 检查生成的文件
        output_dir = "./output/microphone_test"
        if os.path.exists(output_dir):
            files = os.listdir(output_dir)
            audio_files = [f for f in files if f.endswith('.wav')]
            if audio_files:
                print(f"\n生成的音频文件:")
                for file in audio_files:
                    filepath = os.path.join(output_dir, file)
                    size = os.path.getsize(filepath)
                    print(f"  {file} ({size:,} bytes)")
            else:
                print("⚠️  没有生成音频文件")
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
    finally:
        # 清理接收端进程
        try:
            receiver_proc.terminate()
            receiver_proc.wait(timeout=5)
        except:
            try:
                receiver_proc.kill()
            except:
                pass
        
        print("清理完成")

def show_microphone_usage():
    """显示麦克风使用说明"""
    print("麦克风流式传输使用说明")
    print("\n安装依赖:")
    print("  conda run -n esc conda install -c conda-forge pyaudio")
    print("\n基本用法:")
    print("1. 列出音频设备:")
    print("   python -m scripts.sender --list_devices --model_path ./model/esc9kbps_base_adversarial")
    print("\n2. 基本麦克风流式传输:")
    print("   python -m scripts.sender --microphone --model_path ./model/esc9kbps_base_adversarial")
    print("\n3. 指定音频设备:")
    print("   python -m scripts.sender --microphone --mic_device 1 --model_path ./model/esc9kbps_base_adversarial")
    print("\n4. 带速率限制的麦克风传输:")
    print("   python -m scripts.sender --microphone --enable_rate_limit --model_path ./model/esc9kbps_base_adversarial")
    print("\n5. 保存录制的音频:")
    print("   python -m scripts.sender --microphone --mic_save_path ./output/my_recording.wav --model_path ./model/esc9kbps_base_adversarial")
    print("\n6. 保存到目录 (自动生成文件名):")
    print("   python -m scripts.sender --microphone --mic_save_path ./output/ --model_path ./model/esc9kbps_base_adversarial")
    print("\n7. 完整功能 (速率限制 + 音频保存):")
    print("   python -m scripts.sender --microphone --enable_rate_limit --mic_save_path ./recordings/ --model_path ./model/esc9kbps_base_adversarial")
    print("\n特性:")
    print("  - 固定16kHz采样率")
    print("  - 低延迟音频采集")
    print("  - 实时编码和传输")
    print("  - 支持速率限制")
    print("  - 性能监控")
    print("  - 音频录制保存")
    print("  - 优雅的中断处理 (Ctrl+C)")

def main():
    """主函数"""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help" or sys.argv[1] == "-h":
            show_microphone_usage()
            return
        elif sys.argv[1] == "--usage":
            show_microphone_usage()
            return
    
    # 检查必要文件
    required_files = [
        "./model/esc9kbps_base_adversarial/config.yaml",
        "./model/esc9kbps_base_adversarial/model.pth",
        "./scripts/sender.py",
        "./scripts/receiver.py",
        "./scripts/microphone_input.py"
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
    os.makedirs("./output/microphone_test", exist_ok=True)
    
    # 运行测试
    test_microphone_streaming()

if __name__ == "__main__":
    main()
