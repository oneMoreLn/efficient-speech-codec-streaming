"""
Audio Streaming Sender - Encodes audio and sends compressed bitstream via socket
"""

from esc.models import make_model
from scripts.utils import read_yaml
import torch
import torchaudio
import argparse
import warnings
import time
import socket
import pickle
import threading
import queue
import json
import os
from typing import Iterator, Tuple, Optional

warnings.filterwarnings("ignore")

def parse_args():
    parser = argparse.ArgumentParser(description="Audio Streaming Sender")
    parser.add_argument("--input", type=str, help="input 16kHz mono audio file to encode (optional if using microphone)")
    parser.add_argument("--microphone", action="store_true", help="use microphone input instead of file")
    parser.add_argument("--mic_device", type=int, help="microphone device index")
    parser.add_argument("--mic_save_path", type=str, help="path to save recorded microphone audio")
    parser.add_argument("--list_devices", action="store_true", help="list available audio devices and exit")
    parser.add_argument("--host", type=str, default="localhost", help="receiver host address")
    parser.add_argument("--port", type=int, default=8888, help="receiver port number")
    
    parser.add_argument("--model_path", type=str, required=True, help="folder contains model configuration and checkpoint")
    parser.add_argument("--num_streams", type=int, default=6, help="number of transmitted streams in encoding")
    
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--chunk_size", type=int, default=16000, help="chunk size in samples (default: 1 second at 16kHz)")
    parser.add_argument("--overlap_size", type=int, default=1600, help="overlap size in samples (default: 0.1 second at 16kHz)")
    parser.add_argument("--realtime", action="store_true", help="simulate real-time streaming")
    parser.add_argument("--buffer_size", type=int, default=4096, help="socket buffer size")
    parser.add_argument("--enable_rate_limit", action="store_true", help="enable 3kbps rate limiting")
    parser.add_argument("--rate_limit_bps", type=int, default=375, help="rate limit in bytes per second (default: 375 for 3kbps)")
    
    return parser.parse_args()

class AudioStreamingSender:
    def __init__(self, model_path: str, device: str = "cpu", chunk_size: int = 16000, 
                 overlap_size: int = 1600, num_streams: int = 6, enable_rate_limit: bool = False,
                 rate_limit_bps: int = 375):
        """
        Initialize audio streaming sender
        
        Args:
            model_path: Path to model configuration and checkpoint
            device: Device to run the model on
            chunk_size: Size of each audio chunk in samples
            overlap_size: Overlap between chunks in samples
            num_streams: Number of streams for encoding
            enable_rate_limit: Whether to enable rate limiting
            rate_limit_bps: Rate limit in bytes per second (default: 375 for 3kbps)
        """
        self.device = device
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        self.hop_size = chunk_size - overlap_size
        self.num_streams = num_streams
        
        # Load model
        config = read_yaml(f"{model_path}/config.yaml")
        self.model = make_model(config['model'], config['model_name'])
        self.model.load_state_dict(
            torch.load(f"{model_path}/model.pth", map_location="cpu")["model_state_dict"]
        )
        self.model = self.model.to(device)
        self.model.eval()
        
        # Socket connection
        self.socket = None
        self.connected = False
        
        # Threading
        self.encode_queue = queue.Queue(maxsize=10)
        self.send_queue = queue.Queue(maxsize=10)
        self.stop_event = threading.Event()
        
        # Performance statistics
        self.stats = {
            'total_bytes_sent': 0,
            'total_encode_time': 0,
            'total_send_time': 0,
            'chunks_processed': 0,
            'encode_times': [],
            'send_times': [],
            'chunk_sizes': [],
            'start_time': None,
            'end_time': None
        }
        
        # Rate limiting configuration
        self.enable_rate_limit = enable_rate_limit
        self.rate_limit_bps = rate_limit_bps
        self.last_send_time = time.time()
        self.bytes_sent_this_second = 0
        
    def connect(self, host: str, port: int) -> bool:
        """Connect to receiver"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, port))
            self.connected = True
            print(f"Connected to receiver at {host}:{port}")
            return True
        except Exception as e:
            print(f"Failed to connect to receiver: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from receiver"""
        if self.socket:
            self.socket.close()
            self.connected = False
            print("Disconnected from receiver")
    
    def send_metadata(self, sample_rate: int, total_chunks: int):
        """Send metadata about the audio stream"""
        metadata = {
            "sample_rate": sample_rate,
            "chunk_size": self.chunk_size,
            "overlap_size": self.overlap_size,
            "num_streams": self.num_streams,
            "total_chunks": total_chunks
        }
        
        # Send metadata length first
        metadata_bytes = json.dumps(metadata).encode('utf-8')
        metadata_length = len(metadata_bytes)
        self.socket.sendall(metadata_length.to_bytes(4, byteorder='big'))
        
        # Send metadata
        self.socket.sendall(metadata_bytes)
        print(f"Sent metadata: {metadata}")
    
    def encode_chunk(self, chunk: torch.Tensor) -> Tuple[torch.Tensor, tuple]:
        """Encode a single audio chunk"""
        with torch.no_grad():
            chunk = chunk.to(self.device)
            codes, size = self.model.encode(chunk, num_streams=self.num_streams)
            return codes, size
    
    def serialize_codes(self, codes: torch.Tensor, size: tuple, chunk_idx: int) -> bytes:
        """Serialize codes and metadata for transmission"""
        data = {
            "chunk_idx": chunk_idx,
            "codes": codes.cpu().numpy(),
            "size": size,
            "timestamp": time.time()
        }
        return pickle.dumps(data)
    
    def encoding_worker(self):
        """Worker thread for encoding audio chunks"""
        while not self.stop_event.is_set():
            try:
                chunk_data = self.encode_queue.get(timeout=1.0)
                if chunk_data is None:  # Poison pill
                    break
                
                chunk, chunk_idx = chunk_data
                
                # Measure encoding time
                encode_start = time.time()
                codes, size = self.encode_chunk(chunk)
                encode_end = time.time()
                encode_time = encode_end - encode_start
                
                # Serialize data
                serialized_data = self.serialize_codes(codes, size, chunk_idx)
                
                # Update statistics
                self.stats['encode_times'].append(encode_time)
                self.stats['total_encode_time'] += encode_time
                self.stats['chunks_processed'] += 1
                
                self.send_queue.put(serialized_data)
                print(f"Encoded chunk {chunk_idx} in {encode_time:.4f}s")
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in encoding worker: {e}")
                break
    
    def sending_worker(self):
        """Worker thread for sending encoded data with optional rate limiting"""
        while not self.stop_event.is_set():
            try:
                data = self.send_queue.get(timeout=1.0)
                if data is None:  # Poison pill
                    break
                
                # Measure sending time
                send_start = time.time()
                
                # Rate limiting implementation (if enabled)
                if self.enable_rate_limit:
                    current_time = time.time()
                    if current_time - self.last_send_time >= 1.0:
                        # Reset for new second
                        self.last_send_time = current_time
                        self.bytes_sent_this_second = 0
                    
                    data_size = len(data) + 4  # Include length prefix
                    
                    # Check if we need to wait for rate limiting
                    if self.bytes_sent_this_second + data_size > self.rate_limit_bps:
                        sleep_time = 1.0 - (current_time - self.last_send_time)
                        if sleep_time > 0:
                            time.sleep(sleep_time)
                            self.last_send_time = time.time()
                            self.bytes_sent_this_second = 0
                
                # Send data length first
                data_length = len(data)
                self.socket.sendall(data_length.to_bytes(4, byteorder='big'))
                
                # Send data
                self.socket.sendall(data)
                
                send_end = time.time()
                send_time = send_end - send_start
                
                # Update statistics
                data_size = len(data) + 4  # Include length prefix
                self.stats['send_times'].append(send_time)
                self.stats['total_send_time'] += send_time
                self.stats['chunk_sizes'].append(data_size)
                self.stats['total_bytes_sent'] += data_size
                
                # Update rate limiting counter (if enabled)
                if self.enable_rate_limit:
                    self.bytes_sent_this_second += data_size
                
                rate_status = f" (rate limited)" if self.enable_rate_limit else ""
                print(f"Sent chunk data ({data_size} bytes) in {send_time:.4f}s{rate_status}")
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in sending worker: {e}")
                break
    
    def stream_audio_file(self, input_path: str, realtime: bool = False):
        """Stream audio file to receiver"""
        # Load audio file
        audio, sr = torchaudio.load(input_path)
        
        # Ensure mono audio
        if audio.shape[0] > 1:
            audio = audio.mean(dim=0, keepdim=True)
        
        # Calculate total chunks
        audio_length = audio.shape[1]
        total_chunks = int((audio_length + self.hop_size - 1) // self.hop_size)
        
        # Initialize statistics
        self.stats['start_time'] = time.time()
        
        # Send metadata
        self.send_metadata(sr, total_chunks)
        
        # Start worker threads
        encode_thread = threading.Thread(target=self.encoding_worker)
        send_thread = threading.Thread(target=self.sending_worker)
        
        encode_thread.start()
        send_thread.start()
        
        # Process audio in chunks
        start_idx = 0
        chunk_idx = 0
        
        try:
            while start_idx < audio_length:
                chunk_idx += 1
                
                # Extract chunk
                end_idx = min(start_idx + self.chunk_size, audio_length)
                chunk = audio[:, start_idx:end_idx]
                
                # Pad chunk if necessary
                if chunk.shape[1] < self.chunk_size:
                    pad_size = self.chunk_size - chunk.shape[1]
                    chunk = torch.nn.functional.pad(chunk, (0, pad_size))
                
                # Add to encoding queue
                self.encode_queue.put((chunk, chunk_idx))
                
                # Simulate real-time processing
                if realtime:
                    chunk_duration = self.chunk_size / sr
                    time.sleep(chunk_duration)
                
                # Move to next chunk
                start_idx += self.hop_size
                
                print(f"Queued chunk {chunk_idx}/{total_chunks}")
            
            # Wait for all chunks to be processed
            while not self.encode_queue.empty() or not self.send_queue.empty():
                time.sleep(0.1)
            
            # Send end signal
            end_signal = pickle.dumps({"end": True})
            data_length = len(end_signal)
            self.socket.sendall(data_length.to_bytes(4, byteorder='big'))
            self.socket.sendall(end_signal)
            
            # Finalize statistics
            self.stats['end_time'] = time.time()
            
            print(f"Streaming completed!")
            print(f"Sent {chunk_idx} chunks")
            self.print_performance_stats()
            
        except Exception as e:
            print(f"Error during streaming: {e}")
        finally:
            # Stop worker threads
            self.stop_event.set()
            self.encode_queue.put(None)  # Poison pill
            self.send_queue.put(None)   # Poison pill
            
            encode_thread.join()
            send_thread.join()
    
    def stream_microphone(self, device_index: Optional[int] = None, save_path: Optional[str] = None):
        """Stream audio from microphone"""
        try:
            # Import microphone module
            from scripts.microphone_input import MicrophoneStreamer
            
            # Initialize microphone streamer with save path
            mic_streamer = MicrophoneStreamer(
                sample_rate=16000,  # Fixed at 16kHz
                chunk_size=self.chunk_size,
                overlap_size=self.overlap_size,
                save_path=save_path
            )
            
            # Start recording
            if not mic_streamer.start_recording(device_index):
                return
            
            # Initialize statistics
            self.stats['start_time'] = time.time()
            
            # Send metadata (we don't know total chunks for microphone)
            self.send_metadata(16000, 0)  # total_chunks = 0 for continuous stream
            
            # Start worker threads
            encode_thread = threading.Thread(target=self.encoding_worker)
            send_thread = threading.Thread(target=self.sending_worker)
            
            encode_thread.start()
            send_thread.start()
            
            print("开始麦克风流式传输...")
            print("按 Ctrl+C 停止传输")
            
            try:
                # Process microphone chunks
                for chunk, chunk_idx in mic_streamer.stream_chunks():
                    # Add to encoding queue
                    self.encode_queue.put((chunk, chunk_idx))
                    print(f"Queued microphone chunk {chunk_idx}")
                    
                    # Check if we should stop
                    if self.stop_event.is_set():
                        break
                        
            except KeyboardInterrupt:
                print("\n麦克风流式传输被用户中断")
            finally:
                # Stop microphone
                mic_streamer.stop_recording()
                
                # Wait for queues to empty
                while not self.encode_queue.empty() or not self.send_queue.empty():
                    time.sleep(0.1)
                
                # Send end signal
                end_signal = pickle.dumps({"end": True})
                data_length = len(end_signal)
                self.socket.sendall(data_length.to_bytes(4, byteorder='big'))
                self.socket.sendall(end_signal)
                
                # Finalize statistics
                self.stats['end_time'] = time.time()
                
                print("麦克风流式传输完成!")
                self.print_performance_stats()
                
        except ImportError:
            print("错误: 需要安装 pyaudio 库")
            print("请运行: pip install pyaudio")
        except Exception as e:
            print(f"麦克风流式传输错误: {e}")
        finally:
            # Stop worker threads
            self.stop_event.set()
            self.encode_queue.put(None)  # Poison pill
            self.send_queue.put(None)   # Poison pill
            
            encode_thread.join()
            send_thread.join()
    
    def print_performance_stats(self):
        """Print detailed performance statistics"""
        if self.stats['start_time'] is None or self.stats['end_time'] is None:
            print("Performance statistics not available")
            return
        
        total_time = self.stats['end_time'] - self.stats['start_time']
        
        print("\n=== Performance Statistics ===")
        print(f"Total transmission time: {total_time:.3f} seconds")
        print(f"Total bytes sent: {self.stats['total_bytes_sent']:,} bytes")
        print(f"Average transmission rate: {self.stats['total_bytes_sent'] / total_time:.2f} bytes/second")
        
        if self.enable_rate_limit:
            print(f"Rate limiting: ENABLED - {self.rate_limit_bps} bytes/second ({self.rate_limit_bps * 8 / 1000:.1f} kbps)")
        else:
            print(f"Rate limiting: DISABLED")
        
        if self.stats['chunks_processed'] > 0:
            print(f"\nEncoding Performance:")
            print(f"  Total encoding time: {self.stats['total_encode_time']:.3f} seconds")
            print(f"  Average encoding time per chunk: {self.stats['total_encode_time'] / self.stats['chunks_processed']:.4f} seconds")
            print(f"  Min encoding time: {min(self.stats['encode_times']):.4f} seconds")
            print(f"  Max encoding time: {max(self.stats['encode_times']):.4f} seconds")
            
            print(f"\nTransmission Performance:")
            print(f"  Total sending time: {self.stats['total_send_time']:.3f} seconds")
            print(f"  Average sending time per chunk: {self.stats['total_send_time'] / len(self.stats['send_times']):.4f} seconds")
            print(f"  Min sending time: {min(self.stats['send_times']):.4f} seconds")
            print(f"  Max sending time: {max(self.stats['send_times']):.4f} seconds")
            
            print(f"\nChunk Size Statistics:")
            print(f"  Average chunk size: {sum(self.stats['chunk_sizes']) / len(self.stats['chunk_sizes']):.2f} bytes")
            print(f"  Min chunk size: {min(self.stats['chunk_sizes'])} bytes")
            print(f"  Max chunk size: {max(self.stats['chunk_sizes'])} bytes")
            
            # Calculate efficiency
            encoding_efficiency = (self.stats['total_encode_time'] / total_time) * 100
            sending_efficiency = (self.stats['total_send_time'] / total_time) * 100
            
            print(f"\nEfficiency Analysis:")
            print(f"  Encoding time ratio: {encoding_efficiency:.2f}% of total time")
            print(f"  Sending time ratio: {sending_efficiency:.2f}% of total time")
            print(f"  Idle time ratio: {100 - encoding_efficiency - sending_efficiency:.2f}% of total time")
            
        print("=" * 30)

def main():
    args = parse_args()
    
    # Handle device listing
    if args.list_devices:
        try:
            from scripts.microphone_input import MicrophoneStreamer
            mic_streamer = MicrophoneStreamer()
            mic_streamer.list_audio_devices()
            del mic_streamer
        except ImportError:
            print("错误: 需要安装 pyaudio 库来列出音频设备")
            print("请运行: pip install pyaudio")
        return
    
    # Validate input arguments
    if not args.microphone and not args.input:
        print("错误: 必须指定 --input 文件或使用 --microphone 选项")
        return
    
    if args.microphone and args.input:
        print("错误: 不能同时使用 --input 和 --microphone 选项")
        return
    
    # Initialize sender
    sender = AudioStreamingSender(
        model_path=args.model_path,
        device=args.device,
        chunk_size=args.chunk_size,
        overlap_size=args.overlap_size,
        num_streams=args.num_streams,
        enable_rate_limit=args.enable_rate_limit,
        rate_limit_bps=args.rate_limit_bps
    )
    
    try:
        # Connect to receiver
        if sender.connect(args.host, args.port):
            if args.microphone:
                # Stream from microphone
                sender.stream_microphone(args.mic_device, args.mic_save_path)
            else:
                # Stream from file
                sender.stream_audio_file(args.input, args.realtime)
        else:
            print("Failed to connect to receiver")
            return
            
    except KeyboardInterrupt:
        print("\nStreaming interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sender.disconnect()

if __name__ == "__main__":
    main()
