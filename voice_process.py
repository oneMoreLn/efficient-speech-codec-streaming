#!/usr/bin/env python3
"""
语音处理模块 - Voice Processing Module
实现语音编码、解码、分包和解包功能
"""

import numpy as np
import torch
import queue
import time
import threading
import struct
import warnings
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import yaml

# 导入ESC模型相关组件
from esc.models import make_model
from scripts.utils import read_yaml

warnings.filterwarnings("ignore")


class VoiceProcessor:
    """语音处理器 - 负责语音编码、解码、分包和重组"""
    
    def __init__(self, model_path: str = "model/esc9kbps_base_adversarial", device: str = "cpu", num_streams: int = 6):
        """
        初始化语音处理器
        
        Args:
            model_path: 模型路径
            device: 设备类型 ("cpu" 或 "cuda")
            num_streams: 编码时使用的流数量 (默认6)
        """
        self.device = torch.device(device)
        self.model = None
        self.model_path = model_path
        self.num_streams = num_streams
        self.sample_rate = 4096
        self.chunks_per_period = 20  # 5秒包含20个250ms音频块
        self.period_chunks = 20  # 每个周期的音频块数量
        self.packet_size = 2088  # 数据包大小
        
        # 队列
        self.voice_send_queue = queue.Queue()
        self.voice_recv_queue = queue.Queue()
        self.voice2msg_queue = queue.Queue()
        self.msg2voice_queue = queue.Queue()
        
        # 数据缓冲
        self.encode_buffer = []
        self.decode_buffer = []
        self.packet_buffer = {}  # 用于重组多个数据包
        
        # 线程
        self.encode_thread = None
        self.decode_thread = None
        self.running = False
        
        # 加载模型
        try:
            self._load_model(model_path)
            print(f"✅ 模型加载成功: {model_path}")
        except Exception as e:
            print(f"❌ 模型加载失败: {e}")
            print("将在运行时尝试重新加载模型")
    
    def _load_model(self, model_path: str):
        """加载ESC模型"""
        try:
            self.model_path = model_path
            # 加载配置文件
            config = read_yaml(f"{self.model_path}/config.yaml")
            
            # 构建模型
            self.model = make_model(config['model'], config['model_name'])
            
            # 加载权重
            checkpoint = torch.load(f"{self.model_path}/model.pth", map_location=self.device)
            self.model.load_state_dict(checkpoint["model_state_dict"])
            self.model = self.model.to(self.device)
            self.model.eval()
            
            print(f"✅ ESC模型加载成功")
            
        except Exception as e:
            print(f"❌ 模型加载失败: {e}")
            self.model = None
    
    def voice_encode(self, audio_chunk: np.ndarray):
        """
        用于发送语音编码数据压缩
        
        Args:
            audio_chunk: 音频数据块 (1024,) int16 数组，代表250ms音频
        """
        try:
            # 添加到编码缓冲区
            self.encode_buffer.append(audio_chunk)

            # 检查是否达到一个周期的数据量（5秒 = 20个chunk）
            if len(self.encode_buffer) >= self.period_chunks:
                # 提取5秒音频数据
                period_audio = np.concatenate(self.encode_buffer[:self.period_chunks])
                
                # 转换为浮点数并归一化
                audio_float = period_audio.astype(np.float32) / 32768.0
                
                # 转换为torch tensor
                audio_tensor = torch.from_numpy(audio_float).unsqueeze(0).to(self.device)
                
                # 语音编码
                with torch.no_grad():
                    if self.model is not None:
                        try:
                            codes, size = self.model.encode(audio_tensor, num_streams=self.num_streams)
                            
                            # 序列化编码数据 - codes是tensor，size是tuple
                            encoded_bytes = self._serialize_encoded_data(codes, size)
                            
                            # 分包处理
                            packets = self._create_packets(encoded_bytes)
                            
                            # 放入发送队列
                            for packet in packets:
                                self.voice2msg_queue.put(packet)
                                
                            print(f"✅ 编码完成 - 音频长度: {len(period_audio)}, 生成包数: {len(packets)}")
                            
                        except Exception as e:
                            print(f"❌ 编码失败: {e}")
                            import traceback
                            traceback.print_exc()
                    else:
                        print("❌ 模型未加载，无法编码")
                
                # 清理已处理的数据
                self.encode_buffer = self.encode_buffer[self.period_chunks:]
                
        except Exception as e:
            print(f"语音编码错误: {e}")
    
    def voice_decode(self, recv_data: bytes):
        """
        用于接收语音数据解压缩
        
        Args:
            recv_data: 接收到的数据包
        """
        try:
            # 解析数据包头部
            packet_id = struct.unpack('I', recv_data[:4])[0]
            total_packets = struct.unpack('I', recv_data[4:8])[0]
            
            # 将数据包存储到缓冲区
            if total_packets not in self.packet_buffer:
                self.packet_buffer[total_packets] = {}
            
            self.packet_buffer[total_packets][packet_id] = recv_data
            
            # 检查是否收集到所有数据包
            if len(self.packet_buffer[total_packets]) == total_packets:
                # 重组完整数据
                packets_list = []
                for i in range(total_packets):
                    if i in self.packet_buffer[total_packets]:
                        packets_list.append(self.packet_buffer[total_packets][i])
                
                complete_data = self._reconstruct_from_packets(packets_list)
                
                if complete_data is not None:
                    print(f"🔍 重组数据长度: {len(complete_data)} 字节")
                    
                    # 反序列化编码数据
                    codes, size = self._deserialize_encoded_data(complete_data)
                    
                    # 语音解码
                    with torch.no_grad():
                        if self.model is not None:
                            try:
                                decoded_tensor = self.model.decode(codes, size)
                                
                                # 转换回numpy数组
                                decoded_audio = decoded_tensor.cpu().numpy().squeeze()
                                
                                # 转换为int16格式
                                decoded_int16 = (decoded_audio * 32767).astype(np.int16)
                                
                                # 分割成250ms的chunk放入接收队列
                                chunk_samples = int(0.25 * self.sample_rate)  # 4000 samples for 250ms
                                
                                for i in range(0, len(decoded_int16), chunk_samples):
                                    chunk = decoded_int16[i:i + chunk_samples]
                                    if len(chunk) == chunk_samples:  # 只有完整的chunk才放入队列
                                        self.voice_recv_queue.put(chunk)
                                        
                                print(f"✅ 解码完成 - 生成音频长度: {len(decoded_int16)}")
                                
                            except Exception as e:
                                print(f"❌ 解码失败: {e}")
                        else:
                            print("❌ 模型未加载，无法解码")
                
                # 清理已处理的数据包缓冲
                del self.packet_buffer[total_packets]
                
        except Exception as e:
            print(f"语音解码错误: {e}")
    
    def _serialize_encoded_data(self, codes: torch.Tensor, size: tuple) -> bytes:
        """序列化编码数据 - codes是tensor，size是tuple"""
        try:
            data = bytearray()
            
            # 序列化codes tensor
            codes_np = codes.cpu().numpy().astype(np.int64)
            
            # 写入codes的shape信息
            codes_shape_bytes = struct.pack('I' * len(codes_np.shape), *codes_np.shape)
            data.extend(struct.pack('I', len(codes_shape_bytes)))
            data.extend(codes_shape_bytes)
            
            # 写入codes数据
            codes_bytes = codes_np.tobytes()
            data.extend(struct.pack('I', len(codes_bytes)))
            data.extend(codes_bytes)
            
            # 序列化size tuple
            size_data = struct.pack('I' * len(size), *size)
            data.extend(struct.pack('I', len(size)))
            data.extend(size_data)
            
            print(f"🔍 序列化完成 - 数据长度: {len(data)} 字节")
            
            return bytes(data)
            
        except Exception as e:
            print(f"序列化错误: {e}")
            import traceback
            traceback.print_exc()
            return b""
    
    def _deserialize_encoded_data(self, data: bytes) -> Tuple[torch.Tensor, tuple]:
        """反序列化编码数据 - 返回codes tensor和size tuple"""
        try:
            offset = 0
            
            # 读取codes的shape长度
            codes_shape_len = struct.unpack('I', data[offset:offset+4])[0]
            offset += 4
            
            # 读取codes的shape
            codes_shape_data = data[offset:offset+codes_shape_len]
            offset += codes_shape_len
            codes_shape = struct.unpack('I' * (codes_shape_len // 4), codes_shape_data)
            
            # 读取codes数据长度
            codes_data_len = struct.unpack('I', data[offset:offset+4])[0]
            offset += 4
            
            # 读取codes数据
            codes_bytes = data[offset:offset+codes_data_len]
            offset += codes_data_len
            
            # 重构codes tensor
            codes_np = np.frombuffer(codes_bytes, dtype=np.int64).reshape(codes_shape)
            codes = torch.from_numpy(codes_np).to(self.device)
            
            # 读取size tuple长度
            size_len = struct.unpack('I', data[offset:offset+4])[0]
            offset += 4
            
            # 读取size tuple数据
            size_data = data[offset:offset+size_len*4]
            size = struct.unpack('I' * size_len, size_data)
            
            return codes, size
            
        except Exception as e:
            print(f"反序列化错误: {e}")
            import traceback
            traceback.print_exc()
            return torch.tensor([]), ()
    
    def _create_packets(self, data: bytes) -> List[bytes]:
        """
        将数据分割成固定大小的数据包
        
        Args:
            data: 要分包的数据
        
        Returns:
            List[bytes]: 数据包列表
        """
        packets = []
        data_per_packet = self.packet_size - 8  # 减去头部8字节
        
        # 计算总包数
        total_packets = (len(data) + data_per_packet - 1) // data_per_packet
        
        for i in range(total_packets):
            start_idx = i * data_per_packet
            end_idx = min(start_idx + data_per_packet, len(data))
            chunk = data[start_idx:end_idx]
            
            # 构造数据包: 4字节包序号 + 4字节总包数 + 4字节数据长度 + 数据
            packet = bytearray()
            packet.extend(struct.pack('I', i))  # 包序号
            packet.extend(struct.pack('I', total_packets))  # 总包数
            packet.extend(struct.pack('I', len(chunk)))  # 数据长度
            packet.extend(chunk)  # 数据
            
            # 填充到固定大小
            while len(packet) < self.packet_size:
                packet.append(0)
            
            packets.append(bytes(packet))
            
        print(f"🔍 分包完成 - 原始数据: {len(data)} 字节, 生成包数: {len(packets)}")
            
        return packets
    
    def _reconstruct_from_packets(self, packets: List[bytes]) -> Optional[bytes]:
        """
        从数据包重组原始数据
        
        Args:
            packets: 按顺序排列的数据包列表
        
        Returns:
            Optional[bytes]: 重组后的数据，如果失败返回None
        """
        if not packets:
            return None
            
        try:
            # 合并所有数据包的数据部分
            combined_data = bytearray()
            
            for packet in packets:
                # 解析数据包：前8字节是包序号和总包数，第9-12字节是数据长度
                data_len = struct.unpack('I', packet[8:12])[0]
                # 提取实际数据
                data_part = packet[12:12+data_len]
                combined_data.extend(data_part)
            
            result = bytes(combined_data)
            print(f"🔍 重组完成 - 重组数据长度: {len(result)} 字节")
            
            return result
            
        except Exception as e:
            print(f"数据包重组错误: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def start_workers(self):
        """启动编码和解码工作线程"""
        if self.running:
            return
            
        self.running = True
        
        # 启动编码线程
        self.encode_thread = threading.Thread(target=self._encode_worker, daemon=True)
        self.encode_thread.start()
        
        # 启动解码线程
        self.decode_thread = threading.Thread(target=self._decode_worker, daemon=True)
        self.decode_thread.start()
        
        print("✅ 语音处理工作线程已启动")
    
    def stop_workers(self):
        """停止工作线程"""
        self.running = False
        
        if self.encode_thread:
            self.encode_thread.join(timeout=1.0)
        if self.decode_thread:
            self.decode_thread.join(timeout=1.0)
            
        print("✅ 语音处理工作线程已停止")
    
    def _encode_worker(self):
        """编码工作线程"""
        while self.running:
            try:
                # 从发送队列获取音频数据
                audio_chunk = self.voice_send_queue.get(timeout=0.1)
                self.voice_encode(audio_chunk)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"编码工作线程错误: {e}")
                
    def _decode_worker(self):
        """解码工作线程"""
        while self.running:
            try:
                # 从消息队列获取数据包
                packet = self.msg2voice_queue.get(timeout=0.1)
                self.voice_decode(packet)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"解码工作线程错误: {e}")
    
    def put_voice_data(self, audio_chunk: np.ndarray):
        """
        放入语音数据进行编码
        
        Args:
            audio_chunk: 音频数据块 (1024,) int16 数组
        """
        try:
            self.voice_send_queue.put(audio_chunk, block=False)
        except queue.Full:
            print("⚠️ 发送队列已满，丢弃数据")
    
    def get_voice_data(self) -> Optional[np.ndarray]:
        """
        获取解码后的语音数据
        
        Returns:
            Optional[np.ndarray]: 解码后的音频数据块，如果没有数据返回None
        """
        try:
            return self.voice_recv_queue.get(block=False)
        except queue.Empty:
            return None
    
    def put_message_data(self, packet: bytes):
        """
        放入接收到的消息数据包
        
        Args:
            packet: 数据包
        """
        try:
            self.msg2voice_queue.put(packet, block=False)
        except queue.Full:
            print("⚠️ 消息队列已满，丢弃数据")
    
    def get_message_data(self) -> Optional[bytes]:
        """
        获取要发送的消息数据包
        
        Returns:
            Optional[bytes]: 数据包，如果没有数据返回None
        """
        try:
            return self.voice2msg_queue.get(block=False)
        except queue.Empty:
            return None
    
    def get_queue_status(self) -> Dict[str, int]:
        """
        获取队列状态信息
        
        Returns:
            Dict[str, int]: 各队列的大小
        """
        return {
            "voice_send_queue": self.voice_send_queue.qsize(),
            "voice_recv_queue": self.voice_recv_queue.qsize(),
            "voice2msg_queue": self.voice2msg_queue.qsize(),
            "msg2voice_queue": self.msg2voice_queue.qsize(),
            "encode_buffer": len(self.encode_buffer),
            "decode_buffer": len(self.decode_buffer)
        }


def test_voice_processor():
    """测试语音处理器功能"""
    print("🧪 开始测试语音处理器...")
    
    # 设置模型路径
    model_path = "model/esc9kbps_base_adversarial"
    
    # 创建处理器
    processor = VoiceProcessor(model_path)
    
    # 启动工作线程
    processor.start_workers()
    
    try:
        # 模拟音频数据
        sample_rate = 4096
        duration = 0.25  # 250ms
        samples = int(sample_rate * duration)
        
        print(f"📊 生成测试音频数据 - 采样率: {sample_rate}Hz, 时长: {duration*1000}ms, 样本数: {samples}")

        # 生成20个250ms的音频块（总共5秒）
        for i in range(20):
            # 生成1024个样本的音频数据 (250ms @ 4.096kHz)
            t = np.linspace(0, duration, samples)
            frequency = 440 + i * 10  # 变化的频率
            audio_chunk = (np.sin(2 * np.pi * frequency * t) * 16383).astype(np.int16)
            
            # 放入处理器
            processor.put_voice_data(audio_chunk)
            
            if i % 10 == 0:
                print(f"📤 已发送第 {i+1}/20 个音频块")

            time.sleep(0.01)  # 短暂延迟
        
        # 等待处理完成
        print("⏳ 等待编码处理完成...")
        time.sleep(3.0)
        
        # 检查队列状态
        status = processor.get_queue_status()
        print(f"📊 队列状态: {status}")
        
        # 获取编码数据包
        packet_count = 0
        while True:
            packet = processor.get_message_data()
            if packet is None:
                break
            packet_count += 1
            print(f"📦 获取到数据包 {packet_count}, 大小: {len(packet)} 字节")
            
            # 将数据包放入解码队列进行测试
            processor.put_message_data(packet)
        
        # 等待解码完成
        print("⏳ 等待解码处理完成...")
        time.sleep(2.0)
        
        # 获取解码结果
        decoded_count = 0
        while True:
            decoded_chunk = processor.get_voice_data()
            if decoded_chunk is None:
                break
            decoded_count += 1
            print(f"🎵 获取到解码音频块 {decoded_count}, 大小: {decoded_chunk.shape}")
        
        print(f"✅ 测试完成 - 发送了20个音频块，生成了{packet_count}个数据包，解码了{decoded_count}个音频块")
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 停止工作线程
        processor.stop_workers()
        print("🏁 测试结束")


if __name__ == "__main__":
    test_voice_processor()
