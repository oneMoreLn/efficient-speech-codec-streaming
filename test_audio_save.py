#!/usr/bin/env python3
"""
模拟音频保存功能测试
用于验证音频保存逻辑在没有真实音频设备的环境中
"""

import numpy as np
import wave
import os
from datetime import datetime
import sys
import tempfile

def create_test_audio(duration=3, sample_rate=16000):
    """创建测试音频数据"""
    # 创建一个简单的正弦波
    t = np.linspace(0, duration, duration * sample_rate, False)
    frequency = 440  # A4音符
    audio = np.sin(2 * np.pi * frequency * t).astype(np.float32)
    return audio

def save_audio_wav(audio_data, filepath, sample_rate=16000, channels=1):
    """保存音频为WAV文件"""
    # 确保目录存在
    save_dir = os.path.dirname(filepath)
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
    
    # 转换为16位整数
    audio_int16 = (audio_data * 32767).astype(np.int16)
    
    # 保存WAV文件
    with wave.open(filepath, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_int16.tobytes())
    
    return filepath

def test_audio_save():
    """测试音频保存功能"""
    print("=== 音频保存功能测试 ===")
    
    # 创建测试音频
    print("生成测试音频数据...")
    test_audio = create_test_audio(duration=3)
    print(f"生成了 {len(test_audio)} 个采样点的音频")
    
    # 测试不同的保存方式
    test_cases = [
        {
            "name": "保存到指定文件",
            "path": "./output/test_microphone_save/test_audio.wav"
        },
        {
            "name": "保存到目录（自动命名）", 
            "path": "./output/test_microphone_save/"
        }
    ]
    
    for case in test_cases:
        print(f"\n测试: {case['name']}")
        try:
            # 处理保存路径
            save_path = case['path']
            if os.path.isdir(save_path) or save_path.endswith('/'):
                # 目录形式，生成文件名
                if not os.path.exists(save_path):
                    os.makedirs(save_path, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"microphone_recording_{timestamp}.wav"
                filepath = os.path.join(save_path, filename)
            else:
                # 文件形式
                filepath = save_path
            
            # 保存音频
            actual_path = save_audio_wav(test_audio, filepath)
            
            # 验证文件
            if os.path.exists(actual_path):
                file_size = os.path.getsize(actual_path)
                duration = len(test_audio) / 16000
                
                print(f"✅ 保存成功: {actual_path}")
                print(f"   文件大小: {file_size:,} 字节")
                print(f"   音频时长: {duration:.2f} 秒")
                
                # 验证文件内容
                try:
                    with wave.open(actual_path, 'rb') as wav_file:
                        channels = wav_file.getnchannels()
                        sample_width = wav_file.getsampwidth()
                        framerate = wav_file.getframerate()
                        frames = wav_file.getnframes()
                        
                        print(f"   声道数: {channels}")
                        print(f"   位深: {sample_width * 8} bit")
                        print(f"   采样率: {framerate} Hz")
                        print(f"   总帧数: {frames}")
                        
                        if channels == 1 and sample_width == 2 and framerate == 16000:
                            print("   ✅ 音频格式正确")
                        else:
                            print("   ⚠️  音频格式可能不正确")
                            
                except Exception as e:
                    print(f"   ❌ 读取音频文件失败: {e}")
                    
            else:
                print(f"❌ 保存失败: 文件不存在")
                
        except Exception as e:
            print(f"❌ 保存过程出错: {e}")
    
    print(f"\n{'='*50}")
    print("音频保存功能测试完成！")
    
    # 显示生成的文件
    output_dir = "./output/test_microphone_save"
    if os.path.exists(output_dir):
        files = os.listdir(output_dir)
        audio_files = [f for f in files if f.endswith('.wav')]
        if audio_files:
            print(f"\n生成的音频文件:")
            for file in audio_files:
                filepath = os.path.join(output_dir, file)
                size = os.path.getsize(filepath)
                print(f"  {file} ({size:,} bytes)")

def test_microphone_streamer_save():
    """测试MicrophoneStreamer的保存功能（模拟）"""
    print("\n=== MicrophoneStreamer 保存功能测试 ===")
    
    try:
        # 模拟MicrophoneStreamer的保存逻辑
        save_path = "./output/test_microphone_save/streamer_test.wav"
        
        # 模拟录制的音频数据（多个chunk）
        chunk_duration = 0.5  # 每个chunk 0.5秒
        num_chunks = 6  # 总共3秒
        sample_rate = 16000
        
        recorded_audio = []
        for i in range(num_chunks):
            # 生成不同频率的chunk来模拟变化
            frequency = 440 + i * 50  # 递增频率
            t = np.linspace(0, chunk_duration, int(chunk_duration * sample_rate), False)
            chunk = np.sin(2 * np.pi * frequency * t).astype(np.float32)
            recorded_audio.append(chunk)
        
        # 合并所有音频
        full_audio = np.concatenate(recorded_audio)
        
        print(f"模拟录制了 {num_chunks} 个音频块")
        print(f"总时长: {len(full_audio) / sample_rate:.2f} 秒")
        
        # 保存音频
        save_audio_wav(full_audio, save_path, sample_rate)
        
        if os.path.exists(save_path):
            file_size = os.path.getsize(save_path)
            print(f"✅ MicrophoneStreamer保存测试成功")
            print(f"   文件: {save_path}")
            print(f"   大小: {file_size:,} 字节")
        else:
            print("❌ MicrophoneStreamer保存测试失败")
            
    except Exception as e:
        print(f"❌ MicrophoneStreamer保存测试出错: {e}")

def main():
    """主函数"""
    # 创建输出目录
    os.makedirs("./output/test_microphone_save", exist_ok=True)
    
    # 运行测试
    test_audio_save()
    test_microphone_streamer_save()
    
    print(f"\n🎉 所有音频保存功能测试完成！")
    print("这些测试验证了音频保存逻辑的正确性，即使在没有真实音频设备的环境中也能工作。")

if __name__ == "__main__":
    main()
