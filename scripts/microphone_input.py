"""
Microphone Input Module - Real-time audio capture from microphone
"""

import pyaudio
import numpy as np
import torch
import threading
import queue
import time
import warnings
from typing import Optional, Iterator, Tuple
import signal
import sys
import wave
import os
from datetime import datetime

warnings.filterwarnings("ignore")

class MicrophoneStreamer:
    def __init__(self, sample_rate: int = 16000, chunk_size: int = 16000, 
                 overlap_size: int = 1600, channels: int = 1, dtype=np.float32,
                 save_path: Optional[str] = None):
        """
        Initialize microphone streamer
        
        Args:
            sample_rate: Target sample rate (16kHz)
            chunk_size: Size of each audio chunk in samples
            overlap_size: Overlap between chunks in samples
            channels: Number of audio channels (1 for mono)
            dtype: Data type for audio samples
            save_path: Path to save recorded audio (optional)
        """
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        self.hop_size = chunk_size - overlap_size
        self.channels = channels
        self.dtype = dtype
        
        # Audio saving
        self.save_path = save_path
        self.recorded_audio = []  # Store all recorded audio for saving
        
        # PyAudio configuration
        self.format = pyaudio.paFloat32
        self.frames_per_buffer = 1024  # Smaller buffer for low latency
        
        # Audio processing
        self.audio_queue = queue.Queue(maxsize=50)
        self.buffer = np.array([], dtype=dtype)
        self.chunk_counter = 0
        
        # Threading
        self.recording = False
        self.stop_event = threading.Event()
        self.record_thread = None
        
        # PyAudio instance
        self.audio = pyaudio.PyAudio()
        self.stream = None
        
        # Signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        
    def _signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully"""
        print("\n麦克风录制被用户中断")
        self.stop_recording()
        sys.exit(0)
    
    def list_audio_devices(self):
        """List available audio input devices"""
        print("可用的音频输入设备:")
        for i in range(self.audio.get_device_count()):
            device_info = self.audio.get_device_info_by_index(i)
            max_input_channels = device_info.get('maxInputChannels', 0)
            if isinstance(max_input_channels, (int, float)) and max_input_channels > 0:
                device_name = device_info.get('name', 'Unknown')
                default_rate = device_info.get('defaultSampleRate', 0)
                print(f"  {i}: {device_name} "
                      f"(channels: {max_input_channels}, "
                      f"rate: {default_rate})")
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Audio callback function for PyAudio"""
        if status:
            print(f"Audio callback status: {status}")
        
        # Convert bytes to numpy array
        audio_data = np.frombuffer(in_data, dtype=np.float32)
        
        # Save raw audio data if save_path is specified
        if self.save_path:
            self.recorded_audio.append(audio_data.copy())
        
        # Put data into queue
        if not self.audio_queue.full():
            self.audio_queue.put(audio_data)
        else:
            print("警告: 音频队列已满，丢弃数据")
        
        return (None, pyaudio.paContinue)
    
    def start_recording(self, device_index: Optional[int] = None):
        """Start recording from microphone"""
        try:
            # Get device info
            if device_index is None:
                default_device = self.audio.get_default_input_device_info()
                device_index = int(default_device.get('index', 0))
            
            device_info = self.audio.get_device_info_by_index(device_index)
            device_name = device_info.get('name', 'Unknown Device')
            print(f"使用音频设备: {device_name}")
            
            # Clear recorded audio buffer
            self.recorded_audio = []
            
            # Open audio stream
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.frames_per_buffer,
                stream_callback=self._audio_callback,
                start=False
            )
            
            # Start recording
            self.recording = True
            self.stop_event.clear()
            self.stream.start_stream()
            
            print(f"开始录制音频 (采样率: {self.sample_rate}Hz, 声道: {self.channels})")
            if self.save_path:
                print(f"音频将保存到: {self.save_path}")
            print("按 Ctrl+C 停止录制")
            
            return True
            
        except Exception as e:
            print(f"启动录制失败: {e}")
            return False
    
    def stop_recording(self):
        """Stop recording"""
        self.recording = False
        self.stop_event.set()
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        
        # Save recorded audio if save_path is specified
        if self.save_path and self.recorded_audio:
            self.save_recorded_audio()
        
        print("录制已停止")
    
    def save_recorded_audio(self):
        """Save recorded audio to file"""
        if not self.recorded_audio or not self.save_path:
            print("没有录制的音频数据或未指定保存路径")
            return
        
        try:
            # Concatenate all recorded audio
            full_audio = np.concatenate(self.recorded_audio)
            
            # Ensure save directory exists
            save_dir = os.path.dirname(self.save_path)
            if save_dir:
                os.makedirs(save_dir, exist_ok=True)
            
            # Generate filename with timestamp if not specified
            if os.path.isdir(self.save_path):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"microphone_recording_{timestamp}.wav"
                filepath = os.path.join(self.save_path, filename)
            else:
                filepath = self.save_path
                
            # Convert float32 to int16 for WAV file
            audio_int16 = (full_audio * 32767).astype(np.int16)
            
            # Save as WAV file
            with wave.open(filepath, 'wb') as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(audio_int16.tobytes())
            
            duration = len(full_audio) / self.sample_rate
            file_size = os.path.getsize(filepath)
            
            print(f"✅ 音频已保存到: {filepath}")
            print(f"   时长: {duration:.2f} 秒")
            print(f"   文件大小: {file_size:,} 字节")
            
        except Exception as e:
            print(f"❌ 保存音频失败: {e}")
    
    def set_save_path(self, save_path: str):
        """Set save path for recorded audio"""
        self.save_path = save_path
    
    def _process_audio_buffer(self):
        """Process audio buffer and yield chunks"""
        while self.recording or not self.audio_queue.empty():
            try:
                # Get audio data from queue
                audio_data = self.audio_queue.get(timeout=0.1)
                
                # Add to buffer
                self.buffer = np.concatenate([self.buffer, audio_data])
                
                # Yield chunks when buffer is large enough
                while len(self.buffer) >= self.chunk_size:
                    # Extract chunk
                    chunk = self.buffer[:self.chunk_size]
                    self.buffer = self.buffer[self.hop_size:]  # Keep overlap
                    
                    # Convert to torch tensor
                    chunk_tensor = torch.from_numpy(chunk).float().unsqueeze(0)  # Add batch dimension
                    
                    self.chunk_counter += 1
                    yield chunk_tensor, self.chunk_counter
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"处理音频缓冲区错误: {e}")
                break
    
    def stream_chunks(self) -> Iterator[Tuple[torch.Tensor, int]]:
        """Stream audio chunks from microphone"""
        if not self.recording:
            print("请先启动录制")
            return
        
        # Start processing thread
        try:
            for chunk, chunk_idx in self._process_audio_buffer():
                yield chunk, chunk_idx
                
        except KeyboardInterrupt:
            print("\n流式处理被用户中断")
        finally:
            self.stop_recording()
    
    def get_stream_info(self) -> dict:
        """Get stream information"""
        return {
            "sample_rate": self.sample_rate,
            "chunk_size": self.chunk_size,
            "overlap_size": self.overlap_size,
            "channels": self.channels,
            "hop_size": self.hop_size
        }
    
    def test_recording(self, duration: int = 5):
        """Test recording for specified duration"""
        print(f"测试录制 {duration} 秒...")
        
        if not self.start_recording():
            return False
        
        chunk_count = 0
        start_time = time.time()
        
        try:
            for chunk, chunk_idx in self.stream_chunks():
                chunk_count += 1
                elapsed = time.time() - start_time
                
                if elapsed >= duration:
                    break
                    
                if chunk_count % 10 == 0:  # Print every 10 chunks
                    print(f"已录制 {chunk_count} 个音频块 ({elapsed:.1f}s)")
                    
        except KeyboardInterrupt:
            print("\n测试被用户中断")
        finally:
            self.stop_recording()
        
        print(f"测试完成: 录制了 {chunk_count} 个音频块")
        return True
    
    def __del__(self):
        """Cleanup resources"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.audio:
            self.audio.terminate()


def main():
    """Test microphone streaming"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Microphone Streaming Test")
    parser.add_argument("--list_devices", action="store_true", help="list available audio devices")
    parser.add_argument("--device", type=int, help="audio device index to use")
    parser.add_argument("--duration", type=int, default=10, help="test duration in seconds")
    parser.add_argument("--sample_rate", type=int, default=16000, help="sample rate")
    parser.add_argument("--chunk_size", type=int, default=16000, help="chunk size")
    parser.add_argument("--overlap_size", type=int, default=1600, help="overlap size")
    parser.add_argument("--save_path", type=str, help="path to save recorded audio")
    
    args = parser.parse_args()
    
    # Create microphone streamer
    mic_streamer = MicrophoneStreamer(
        sample_rate=args.sample_rate,
        chunk_size=args.chunk_size,
        overlap_size=args.overlap_size,
        save_path=args.save_path
    )
    
    # List devices if requested
    if args.list_devices:
        mic_streamer.list_audio_devices()
        return
    
    # Test recording
    try:
        mic_streamer.test_recording(args.duration)
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    finally:
        del mic_streamer


if __name__ == "__main__":
    main()

"""
Usage examples:

1. List available audio devices:
python -m scripts.microphone_input --list_devices

2. Test recording with default device:
python -m scripts.microphone_input --duration 5

3. Test recording with specific device:
python -m scripts.microphone_input --device 1 --duration 10

4. Custom configuration:
python -m scripts.microphone_input --sample_rate 16000 --chunk_size 8000 --overlap_size 800 --duration 5
"""
