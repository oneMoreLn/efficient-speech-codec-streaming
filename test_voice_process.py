#!/usr/bin/env python3
"""
Voice Process 测试程序
支持从麦克风或本地文件读取音频，测试完整的编码-传输-解码流程
"""

import numpy as np
import pyaudio
import wave
import time
import threading
import argparse
import os
from pathlib import Path
import queue
from voice_process import VoiceProcessor


class AudioTester:
    """音频测试器 - 测试VoiceProcessor的完整功能"""
    
    def __init__(self, sample_rate=4096, chunk_duration=0.25):
        """
        初始化音频测试器
        
        Args:
            sample_rate: 采样率 (4096Hz)
            chunk_duration: 音频块时长 (250ms)
        """
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        self.chunk_size = int(sample_rate * chunk_duration)  # 1024 samples for 250ms @ 4096Hz
        
        # 初始化VoiceProcessor
        self.processor = VoiceProcessor()
        
        # 音频设备
        self.audio = None
        self.stream = None
        
        # 控制变量
        self.recording = False
        self.playing = False
        
        # 统计信息
        self.stats = {
            'chunks_sent': 0,
            'chunks_received': 0,
            'packets_sent': 0,
            'packets_received': 0
        }
    
    def init_audio(self):
        """初始化音频设备"""
        try:
            self.audio = pyaudio.PyAudio()
            print(f"✅ 音频设备初始化成功")
            return True
        except Exception as e:
            print(f"❌ 音频设备初始化失败: {e}")
            return False
    
    def list_audio_devices(self):
        """列出可用的音频设备"""
        if not self.audio:
            self.init_audio()
        
        print("📋 可用音频设备列表:")
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            print(f"  设备 {i}: {info['name']} - 输入通道: {info['maxInputChannels']}, 输出通道: {info['maxOutputChannels']}")
    
    def load_audio_file(self, file_path: str) -> np.ndarray:
        """
        从文件加载音频数据
        
        Args:
            file_path: 音频文件路径
            
        Returns:
            np.ndarray: 音频数据 (int16格式)
        """
        try:
            # 支持WAV文件
            if file_path.endswith('.wav'):
                with wave.open(file_path, 'rb') as wav_file:
                    frames = wav_file.getnframes()
                    sample_rate = wav_file.getframerate()
                    channels = wav_file.getnchannels()
                    sample_width = wav_file.getsampwidth()
                    
                    print(f"📁 加载音频文件: {file_path}")
                    print(f"   采样率: {sample_rate}Hz, 通道数: {channels}, 位深: {sample_width*8}bit, 长度: {frames}帧")
                    
                    # 读取音频数据
                    audio_data = wav_file.readframes(frames)
                    
                    # 转换为numpy数组
                    if sample_width == 1:
                        audio_np = np.frombuffer(audio_data, dtype=np.uint8).astype(np.int16) - 128
                    elif sample_width == 2:
                        audio_np = np.frombuffer(audio_data, dtype=np.int16)
                    else:
                        raise ValueError(f"不支持的位深: {sample_width*8}bit")
                    
                    # 如果是立体声，转换为单声道
                    if channels == 2:
                        audio_np = audio_np.reshape(-1, 2).mean(axis=1).astype(np.int16)
                    
                    # 重采样到目标采样率
                    if sample_rate != self.sample_rate:
                        # 简单的重采样（线性插值）
                        target_length = int(len(audio_np) * self.sample_rate / sample_rate)
                        indices = np.linspace(0, len(audio_np) - 1, target_length)
                        audio_np = np.interp(indices, np.arange(len(audio_np)), audio_np).astype(np.int16)
                        print(f"   重采样: {sample_rate}Hz -> {self.sample_rate}Hz, 长度: {len(audio_np)}样本")
                    
                    return audio_np
            else:
                raise ValueError(f"不支持的文件格式: {file_path}")
                
        except Exception as e:
            print(f"❌ 加载音频文件失败: {e}")
            return np.array([], dtype=np.int16)
    
    def save_audio_file(self, audio_data: np.ndarray, file_path: str):
        """
        保存音频数据到文件
        
        Args:
            audio_data: 音频数据 (int16格式)
            file_path: 保存路径
        """
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with wave.open(file_path, 'wb') as wav_file:
                wav_file.setnchannels(1)  # 单声道
                wav_file.setsampwidth(2)  # 16bit
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(audio_data.tobytes())
            
            duration = len(audio_data) / self.sample_rate
            print(f"💾 音频文件已保存: {file_path}")
            print(f"   采样率: {self.sample_rate}Hz, 长度: {len(audio_data)}样本 ({duration:.2f}秒)")
            
        except Exception as e:
            print(f"❌ 保存音频文件失败: {e}")
    
    def record_from_microphone(self, duration: float, device_index: int = None):
        """
        从麦克风录制音频
        
        Args:
            duration: 录制时长（秒）
            device_index: 音频设备索引，None为默认设备
            
        Returns:
            np.ndarray: 录制的音频数据
        """
        try:
            if not self.audio:
                self.init_audio()
            
            # 打开音频流
            stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk_size
            )
            
            print(f"🎤 开始录制音频 - 时长: {duration}秒, 采样率: {self.sample_rate}Hz")
            
            frames = []
            total_chunks = int(duration * self.sample_rate / self.chunk_size)
            
            for i in range(total_chunks):
                data = stream.read(self.chunk_size)
                frames.append(data)
                
                if (i + 1) % 10 == 0:
                    print(f"   录制进度: {i+1}/{total_chunks} 块")
            
            stream.stop_stream()
            stream.close()
            
            # 转换为numpy数组
            audio_data = b''.join(frames)
            audio_np = np.frombuffer(audio_data, dtype=np.int16)
            
            print(f"✅ 录制完成 - 共 {len(audio_np)} 样本")
            return audio_np
            
        except Exception as e:
            print(f"❌ 录制音频失败: {e}")
            return np.array([], dtype=np.int16)
    
    def feed_audio_chunks(self, audio_data: np.ndarray):
        """
        将音频数据分块放入处理队列
        
        Args:
            audio_data: 完整的音频数据
        """
        print(f"📤 开始发送音频数据 - 总长度: {len(audio_data)} 样本")
        
        chunk_count = 0
        for i in range(0, len(audio_data), self.chunk_size):
            chunk = audio_data[i:i + self.chunk_size]
            
            # 如果最后一块不足长度，填充零
            if len(chunk) < self.chunk_size:
                padded_chunk = np.zeros(self.chunk_size, dtype=np.int16)
                padded_chunk[:len(chunk)] = chunk
                chunk = padded_chunk
            
            # 放入处理队列
            self.processor.put_voice_data(chunk)
            chunk_count += 1
            self.stats['chunks_sent'] += 1
            
            if chunk_count % 10 == 0:
                print(f"   已发送 {chunk_count} 个音频块")
            
            # 模拟实时处理间隔
            time.sleep(self.chunk_duration * 0.1)  # 10倍速处理
        
        print(f"✅ 音频数据发送完成 - 总共 {chunk_count} 个块")
    
    def collect_decoded_audio(self, timeout: float = 10.0) -> np.ndarray:
        """
        收集解码后的音频数据
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            np.ndarray: 解码后的音频数据
        """
        print(f"📥 开始收集解码音频数据...")
        
        collected_chunks = []
        start_time = time.time()
        last_activity = start_time
        wait_for_data = True
        cycles_detected = 0
        empty_polls = 0  # 连续空轮询计数
        
        while time.time() - start_time < timeout:
            try:
                # 尝试获取解码数据
                chunk = self.processor.get_voice_data()
                if chunk is not None:
                    collected_chunks.append(chunk)
                    self.stats['chunks_received'] += 1
                    last_activity = time.time()
                    wait_for_data = False
                    empty_polls = 0  # 重置空轮询计数
                    
                    # 检测编码周期（每个周期约20个chunk）
                    if len(collected_chunks) % 20 == 1 and len(collected_chunks) > 20:
                        cycles_detected += 1
                        print(f"   检测到第 {cycles_detected} 个解码周期")
                    
                    if len(collected_chunks) % 10 == 1:
                        print(f"   已收集 {len(collected_chunks)} 个解码音频块")
                else:
                    empty_polls += 1
                    
                    # 如果还在等待初始数据
                    if wait_for_data:
                        time.sleep(0.5)
                    else:
                        # 检查队列状态来决定是否继续等待
                        status = self.processor.get_queue_status()
                        remaining_data = status.get('voice_recv_queue', 0)
                        
                        # 如果队列中还有数据，继续等待
                        if remaining_data > 0:
                            print(f"   队列中还有 {remaining_data} 个音频块，继续等待...")
                            time.sleep(0.2)
                            empty_polls = 0  # 重置计数，因为还有数据
                        else:
                            # 只有当队列空了且连续多次轮询都为空时才停止
                            if empty_polls > 30:  # 3秒 (30 * 0.1)
                                print(f"   队列为空且连续{empty_polls}次无数据，停止收集")
                                break
                            time.sleep(0.1)
                    
            except Exception as e:
                print(f"❌ 收集音频数据时出错: {e}")
                break
        
        if collected_chunks:
            decoded_audio = np.concatenate(collected_chunks)
            print(f"✅ 音频数据收集完成 - 总长度: {len(decoded_audio)} 样本")
            return decoded_audio
        else:
            print("⚠️ 未收集到解码音频数据")
            return np.array([], dtype=np.int16)
    
    def monitor_processing(self, duration: float = 15.0):
        """
        监控处理过程
        
        Args:
            duration: 监控时长（秒）
        """
        print(f"📊 开始监控处理过程...")
        
        start_time = time.time()
        last_status_time = start_time
        
        while time.time() - start_time < duration:
            # 积极传输所有可用的消息包
            packets_transferred = 0
            while True:
                packet = self.processor.get_message_data()
                if packet is not None:
                    self.stats['packets_sent'] += 1
                    # 将数据包放回解码队列进行测试
                    self.processor.put_message_data(packet)
                    self.stats['packets_received'] += 1
                    packets_transferred += 1
                else:
                    break
            
            # 每2秒显示一次状态（减少输出频率）
            current_time = time.time()
            if current_time - last_status_time >= 2.0:
                status = self.processor.get_queue_status()
                print(f"   队列状态: 发送={status['voice_send_queue']}, 接收={status['voice_recv_queue']}, "
                      f"消息发送={status['voice2msg_queue']}, 消息接收={status['msg2voice_queue']}")
                print(f"   统计: 音频块发送={self.stats['chunks_sent']}, 音频块接收={self.stats['chunks_received']}, "
                      f"数据包发送={self.stats['packets_sent']}, 数据包接收={self.stats['packets_received']}")
                if packets_transferred > 0:
                    print(f"   本轮传输了 {packets_transferred} 个数据包")
                last_status_time = current_time
            
            time.sleep(0.1)  # 减少等待时间，提高传输效率
    
    def test_file_processing(self, input_file: str, output_file: str):
        """
        测试文件处理流程
        
        Args:
            input_file: 输入音频文件路径
            output_file: 输出音频文件路径
        """
        print(f"🧪 开始文件处理测试...")
        print(f"   输入文件: {input_file}")
        print(f"   输出文件: {output_file}")
        
        # 启动处理器
        self.processor.start_workers()
        
        try:
            # 1. 加载音频文件
            audio_data = self.load_audio_file(input_file)
            if len(audio_data) == 0:
                print("❌ 无法加载音频文件")
                return False
            
            # 2. 开始监控
            monitor_thread = threading.Thread(target=self.monitor_processing, args=(60.0,))  # 增加监控时间
            monitor_thread.start()
            
            # 3. 发送音频数据
            feed_thread = threading.Thread(target=self.feed_audio_chunks, args=(audio_data,))
            feed_thread.start()
            
            # 4. 等待处理并收集结果  
            time.sleep(5.0)  # 等待处理开始 - 增加等待时间
            decoded_audio = self.collect_decoded_audio(45.0)  # 大幅增加收集超时时间
            
            # 5. 等待线程完成
            feed_thread.join()
            monitor_thread.join()
            
            # 6. 保存结果
            if len(decoded_audio) > 0:
                self.save_audio_file(decoded_audio, output_file)
                print(f"✅ 文件处理测试完成")
                return True
            else:
                print(f"❌ 未获得解码结果")
                return False
                
        except Exception as e:
            print(f"❌ 文件处理测试失败: {e}")
            return False
        finally:
            self.processor.stop_workers()
    
    def test_microphone_processing(self, duration: float, output_file: str, device_index: int = None):
        """
        测试麦克风处理流程
        
        Args:
            duration: 录制时长（秒）
            output_file: 输出音频文件路径
            device_index: 音频设备索引
        """
        print(f"🧪 开始麦克风处理测试...")
        print(f"   录制时长: {duration}秒")
        print(f"   输出文件: {output_file}")
        
        # 初始化音频设备
        if not self.init_audio():
            return False
        
        # 启动处理器
        self.processor.start_workers()
        
        try:
            # 1. 录制音频
            audio_data = self.record_from_microphone(duration, device_index)
            if len(audio_data) == 0:
                print("❌ 录制失败")
                return False
            
            # 2. 开始监控
            monitor_thread = threading.Thread(target=self.monitor_processing, args=(duration + 10.0,))
            monitor_thread.start()
            
            # 3. 发送音频数据
            feed_thread = threading.Thread(target=self.feed_audio_chunks, args=(audio_data,))
            feed_thread.start()
            
            # 4. 等待处理并收集结果
            time.sleep(2.0)  # 等待处理开始
            decoded_audio = self.collect_decoded_audio(duration + 5.0)
            
            # 5. 等待线程完成
            feed_thread.join()
            monitor_thread.join()
            
            # 6. 保存结果
            if len(decoded_audio) > 0:
                self.save_audio_file(decoded_audio, output_file)
                print(f"✅ 麦克风处理测试完成")
                return True
            else:
                print(f"❌ 未获得解码结果")
                return False
                
        except Exception as e:
            print(f"❌ 麦克风处理测试失败: {e}")
            return False
        finally:
            if self.audio:
                self.audio.terminate()
            self.processor.stop_workers()
    
    def cleanup(self):
        """清理资源"""
        if self.audio:
            self.audio.terminate()
        self.processor.stop_workers()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Voice Process 测试程序")
    parser.add_argument("--mode", choices=["file", "mic", "devices"], default="file",
                      help="测试模式: file(文件), mic(麦克风), devices(列出设备)")
    parser.add_argument("--input", type=str, help="输入音频文件路径 (file模式)")
    parser.add_argument("--output", type=str, default="output/test_voice_process_output.wav",
                      help="输出音频文件路径")
    parser.add_argument("--duration", type=float, default=10.0,
                      help="录制时长(秒) (mic模式)")
    parser.add_argument("--device", type=int, help="音频设备索引 (mic模式)")
    parser.add_argument("--sample-rate", type=int, default=4096,
                      help="采样率 (默认4096Hz)")
    
    args = parser.parse_args()
    
    # 创建测试器
    tester = AudioTester(sample_rate=args.sample_rate)
    
    try:
        if args.mode == "devices":
            # 列出音频设备
            tester.list_audio_devices()
        
        elif args.mode == "file":
            # 文件处理测试
            if not args.input:
                print("❌ 文件模式需要指定 --input 参数")
                return
            
            if not os.path.exists(args.input):
                print(f"❌ 输入文件不存在: {args.input}")
                return
            
            success = tester.test_file_processing(args.input, args.output)
            if success:
                print(f"🎉 文件处理测试成功！请查看输出文件: {args.output}")
            else:
                print(f"💥 文件处理测试失败")
        
        elif args.mode == "mic":
            # 麦克风处理测试
            success = tester.test_microphone_processing(args.duration, args.output, args.device)
            if success:
                print(f"🎉 麦克风处理测试成功！请查看输出文件: {args.output}")
            else:
                print(f"💥 麦克风处理测试失败")
    
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断测试")
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        tester.cleanup()


if __name__ == "__main__":
    main()
