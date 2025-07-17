#!/usr/bin/env python3
"""
流式音频传输系统 - 速率限制超参数测试
展示如何使用速率限制超参数进行不同的传输配置
"""

import subprocess
import time
import os
import signal
import sys

def test_rate_limiting_options():
    """测试不同的速率限制配置"""
    print("=== 流式音频传输系统 - 速率限制超参数测试 ===")
    print("测试配置：")
    print("1. 无速率限制（默认）")
    print("2. 3kbps速率限制（默认限制）")
    print("3. 8kbps速率限制（自定义）")
    print()
    
    test_configs = [
        {
            "name": "无速率限制",
            "port": 8896,
            "args": [],
            "expected_time": "< 10秒"
        },
        {
            "name": "3kbps速率限制",
            "port": 8897,
            "args": ["--enable_rate_limit"],
            "expected_time": "约60秒"
        },
        {
            "name": "8kbps速率限制",
            "port": 8898,
            "args": ["--enable_rate_limit", "--rate_limit_bps", "1000"],
            "expected_time": "约25秒"
        }
    ]
    
    for config in test_configs:
        print(f"\n{'='*50}")
        print(f"测试配置: {config['name']}")
        print(f"预期传输时间: {config['expected_time']}")
        print(f"端口: {config['port']}")
        print(f"参数: {' '.join(config['args'])}")
        print('='*50)
        
        # 启动接收端
        print("启动接收端...")
        receiver_cmd = [
            "conda", "run", "-n", "esc", "python", "-m", "scripts.receiver",
            "--model_path", "./model/esc9kbps_base_adversarial",
            "--port", str(config['port']),
            "--save_path", f"./output/test_{config['name'].replace(' ', '_')}"
        ]
        
        receiver_proc = subprocess.Popen(receiver_cmd, 
                                       stdout=subprocess.PIPE, 
                                       stderr=subprocess.PIPE,
                                       text=True)
        
        # 等待接收端启动
        time.sleep(2)
        
        try:
            # 构建发送端命令
            sender_cmd = [
                "conda", "run", "-n", "esc", "python", "-m", "scripts.sender",
                "--input", "./data/speech_1.wav",
                "--model_path", "./model/esc9kbps_base_adversarial",
                "--port", str(config['port'])
            ] + config['args']
            
            print(f"启动发送端: {' '.join(sender_cmd)}")
            
            # 对于长时间测试，设置超时
            timeout = 30 if "8kbps" in config['name'] else 10 if "无速率限制" in config['name'] else 70
            
            start_time = time.time()
            sender_proc = subprocess.run(sender_cmd, 
                                       capture_output=True, 
                                       text=True,
                                       timeout=timeout)
            end_time = time.time()
            
            actual_time = end_time - start_time
            
            print(f"实际传输时间: {actual_time:.2f}秒")
            
            # 提取关键统计信息
            output_lines = sender_proc.stdout.split('\n')
            for line in output_lines:
                if "Rate limiting:" in line:
                    print(f"速率限制状态: {line.split('Rate limiting:')[1].strip()}")
                elif "Average transmission rate:" in line:
                    print(f"平均传输速率: {line.split('Average transmission rate:')[1].strip()}")
                elif "Total transmission time:" in line:
                    print(f"总传输时间: {line.split('Total transmission time:')[1].strip()}")
            
            if sender_proc.returncode == 0:
                print("✅ 测试成功完成")
            else:
                print("❌ 测试失败")
                if sender_proc.stderr:
                    print(f"错误: {sender_proc.stderr}")
            
        except subprocess.TimeoutExpired:
            print(f"⏱️ 测试超时 (>{timeout}秒)，终止测试")
        except Exception as e:
            print(f"❌ 测试过程中出现错误: {e}")
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
        
        print(f"完成配置: {config['name']}")
    
    print(f"\n{'='*50}")
    print("所有测试完成！")
    print("\n总结:")
    print("- 无速率限制：最快传输，适合本地测试")
    print("- 3kbps限制：模拟低带宽环境")
    print("- 8kbps限制：模拟中等带宽环境")
    print("- 可通过--rate_limit_bps参数自定义任意速率")

def show_usage():
    """显示使用说明"""
    print("流式音频传输系统 - 速率限制超参数使用说明")
    print("\n基本用法:")
    print("python -m scripts.sender --input <音频文件> --model_path <模型路径> [选项]")
    print("\n速率限制选项:")
    print("  --enable_rate_limit       启用速率限制")
    print("  --rate_limit_bps <值>     设置速率限制(字节/秒), 默认375 (3kbps)")
    print("\n示例:")
    print("1. 无速率限制 (默认):")
    print("   python -m scripts.sender --input audio.wav --model_path ./model/esc9kbps_base_adversarial")
    print("\n2. 3kbps速率限制:")
    print("   python -m scripts.sender --input audio.wav --model_path ./model/esc9kbps_base_adversarial --enable_rate_limit")
    print("\n3. 自定义速率限制 (例: 8kbps):")
    print("   python -m scripts.sender --input audio.wav --model_path ./model/esc9kbps_base_adversarial --enable_rate_limit --rate_limit_bps 1000")
    print("\n4. 更高速率限制 (例: 16kbps):")
    print("   python -m scripts.sender --input audio.wav --model_path ./model/esc9kbps_base_adversarial --enable_rate_limit --rate_limit_bps 2000")

def main():
    """主函数"""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help" or sys.argv[1] == "-h":
            show_usage()
            return
        elif sys.argv[1] == "--usage":
            show_usage()
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
    os.makedirs("./output", exist_ok=True)
    
    # 运行测试
    test_rate_limiting_options()

if __name__ == "__main__":
    main()
