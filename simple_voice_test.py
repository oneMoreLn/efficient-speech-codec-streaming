#!/usr/bin/env python3
"""
Voice Process 简单示例
演示如何使用VoiceProcessor进行音频编码和解码
"""

import numpy as np
import wave
import time
from voice_process import VoiceProcessor


def simple_test():
    """简单的音频处理测试"""
    print("🧪 Voice Process 简单测试")
    
    # 1. 创建处理器
    processor = VoiceProcessor()
    processor.start_workers()
    
    try:
        # 2. 生成测试音频 (5秒，440Hz正弦波，4096Hz采样率)
        sample_rate = 4096
        duration = 5.0
        chunk_duration = 0.25  # 250ms
        chunk_size = int(sample_rate * chunk_duration)  # 1024 samples
        
        print(f"📊 生成测试音频: {duration}秒, {sample_rate}Hz采样率")
        
        # 生成音频数据
        total_samples = int(sample_rate * duration)
        t = np.linspace(0, duration, total_samples)
        audio_data = (np.sin(2 * np.pi * 440 * t) * 16383).astype(np.int16)
        
        # 3. 分块发送到处理器
        print("📤 发送音频数据到处理器...")
        chunk_count = 0
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            
            # 填充最后一块
            if len(chunk) < chunk_size:
                padded_chunk = np.zeros(chunk_size, dtype=np.int16)
                padded_chunk[:len(chunk)] = chunk
                chunk = padded_chunk
            
            processor.put_voice_data(chunk)
            chunk_count += 1
            
            # 模拟实时处理
            time.sleep(chunk_duration * 0.1)
        
        print(f"   已发送 {chunk_count} 个音频块")
        
        # 4. 等待处理并收集结果
        print("⏳ 等待处理完成...")
        time.sleep(3.0)
        
        # 5. 收集解码结果
        print("📥 收集解码结果...")
        decoded_chunks = []
        timeout = time.time() + 10.0
        
        while time.time() < timeout:
            chunk = processor.get_voice_data()
            if chunk is not None:
                decoded_chunks.append(chunk)
            else:
                time.sleep(0.1)
            
            # 如果3秒没有新数据，停止
            if len(decoded_chunks) > 0 and time.time() > timeout - 7.0:
                recent_data = False
                for _ in range(30):  # 检查3秒
                    if processor.get_voice_data() is not None:
                        recent_data = True
                        break
                    time.sleep(0.1)
                if not recent_data:
                    break
        
        # 6. 保存结果
        if decoded_chunks:
            decoded_audio = np.concatenate(decoded_chunks)
            
            # 保存原始音频
            with wave.open("output/original_test.wav", 'wb') as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(sample_rate)
                f.writeframes(audio_data.tobytes())
            
            # 保存解码音频
            with wave.open("output/decoded_test.wav", 'wb') as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(sample_rate)
                f.writeframes(decoded_audio.tobytes())
            
            print(f"✅ 测试完成!")
            print(f"   原始音频: {len(audio_data)} 样本 ({len(audio_data)/sample_rate:.2f}秒)")
            print(f"   解码音频: {len(decoded_audio)} 样本 ({len(decoded_audio)/sample_rate:.2f}秒)")
            print(f"   收集到 {len(decoded_chunks)} 个解码块")
            print(f"   文件已保存: output/original_test.wav, output/decoded_test.wav")
            
            # 7. 显示统计信息
            status = processor.get_queue_status()
            print(f"📊 队列状态: {status}")
            
        else:
            print("❌ 未收集到解码数据")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        processor.stop_workers()


def process_file(input_file, output_file):
    """处理音频文件"""
    print(f"🎵 处理音频文件: {input_file} -> {output_file}")
    
    # 1. 加载音频文件
    with wave.open(input_file, 'rb') as f:
        sample_rate = f.getframerate()
        channels = f.getnchannels()
        frames = f.getnframes()
        audio_data = f.readframes(frames)
    
    # 转换为numpy数组
    audio_np = np.frombuffer(audio_data, dtype=np.int16)
    if channels == 2:
        audio_np = audio_np.reshape(-1, 2).mean(axis=1).astype(np.int16)
    
    print(f"   原始采样率: {sample_rate}Hz, 通道数: {channels}, 长度: {len(audio_np)} 样本")
    
    # 2. 重采样到4096Hz
    target_rate = 4096
    if sample_rate != target_rate:
        target_length = int(len(audio_np) * target_rate / sample_rate)
        indices = np.linspace(0, len(audio_np) - 1, target_length)
        audio_np = np.interp(indices, np.arange(len(audio_np)), audio_np).astype(np.int16)
        print(f"   重采样到: {target_rate}Hz, 长度: {len(audio_np)} 样本")
    
    # 3. 创建处理器
    processor = VoiceProcessor()
    processor.start_workers()
    
    try:
        # 4. 分块处理
        chunk_size = 1024  # 250ms @ 4096Hz
        chunk_count = 0
        
        print("📤 开始处理...")
        for i in range(0, len(audio_np), chunk_size):
            chunk = audio_np[i:i + chunk_size]
            
            # 填充最后一块
            if len(chunk) < chunk_size:
                padded_chunk = np.zeros(chunk_size, dtype=np.int16)
                padded_chunk[:len(chunk)] = chunk
                chunk = padded_chunk
            
            processor.put_voice_data(chunk)
            chunk_count += 1
            
            if chunk_count % 20 == 0:
                print(f"   已处理 {chunk_count} 个块")
        
        # 5. 等待处理完成并收集结果
        print("⏳ 等待处理完成...")
        time.sleep(3.0)
        
        decoded_chunks = []
        timeout = time.time() + 10.0
        
        while time.time() < timeout:
            chunk = processor.get_voice_data()
            if chunk is not None:
                decoded_chunks.append(chunk)
            else:
                if len(decoded_chunks) > 0 and time.time() > timeout - 5.0:
                    break
                time.sleep(0.1)
        
        # 6. 保存结果
        if decoded_chunks:
            decoded_audio = np.concatenate(decoded_chunks)
            
            with wave.open(output_file, 'wb') as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(target_rate)
                f.writeframes(decoded_audio.tobytes())
            
            print(f"✅ 处理完成!")
            print(f"   输入: {len(audio_np)} 样本 ({len(audio_np)/target_rate:.2f}秒)")
            print(f"   输出: {len(decoded_audio)} 样本 ({len(decoded_audio)/target_rate:.2f}秒)")
            print(f"   文件已保存: {output_file}")
            
        else:
            print("❌ 未获得解码结果")
            
    except Exception as e:
        print(f"❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        processor.stop_workers()


def test_different_num_streams():
    """测试不同的num_streams参数"""
    print("🔄 测试不同的num_streams参数")
    
    # 生成测试音频数据
    duration = 2.0  # 2秒
    sample_rate = 4096
    t = np.linspace(0, duration, int(sample_rate * duration))
    test_audio = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)
    
    # 测试不同的num_streams值
    for num_streams in [1, 3, 6, 9]:
        print(f"\n📊 测试 num_streams = {num_streams}")
        
        # 创建处理器
        processor = VoiceProcessor(num_streams=num_streams)
        processor.start_workers()
        
        try:
            start_time = time.time()
            
            # 逐块添加音频数据
            chunk_size = 1024  # 每个块的大小
            for i in range(0, len(test_audio), chunk_size):
                chunk = test_audio[i:i+chunk_size]
                processor.voice_send_queue.put(chunk)
            
            # 等待处理完成
            time.sleep(1.0)
            
            # 收集结果
            decoded_audio = []
            while not processor.voice_recv_queue.empty():
                chunk = processor.voice_recv_queue.get()
                decoded_audio.extend(chunk)
            
            processing_time = time.time() - start_time
            
            print(f"  ⏱️  处理时间: {processing_time:.3f}s")
            print(f"  📊 输入长度: {len(test_audio)}")
            print(f"  📈 输出长度: {len(decoded_audio)}")
            
            # 保存结果
            if decoded_audio:
                output_file = f"output/test_streams_{num_streams}.wav"
                with wave.open(output_file, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(sample_rate)
                    audio_int16 = np.clip(np.array(decoded_audio) * 32767, -32768, 32767).astype(np.int16)
                    wav_file.writeframes(audio_int16.tobytes())
                print(f"  💾 保存到: {output_file}")
            
        except Exception as e:
            print(f"  ❌ 测试失败: {e}")
        
        finally:
            processor.stop_workers()
    
    print("\n✅ num_streams参数测试完成")


if __name__ == "__main__":
    import sys
    import os
    
    # 确保输出目录存在
    os.makedirs("output", exist_ok=True)
    
    if len(sys.argv) > 1 and sys.argv[1] == "streams":
        # 测试不同的num_streams参数
        test_different_num_streams()
    elif len(sys.argv) > 1:
        # 处理指定的音频文件
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else "output/processed_output.wav"
        
        if os.path.exists(input_file):
            process_file(input_file, output_file)
        else:
            print(f"❌ 文件不存在: {input_file}")
    else:
        # 运行简单测试
        simple_test()
