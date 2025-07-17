"""
Audio Streaming Receiver - Receives compressed bitstream via socket and decodes to audio
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
import numpy as np
from typing import Optional, List

warnings.filterwarnings("ignore")

def parse_args():
    parser = argparse.ArgumentParser(description="Audio Streaming Receiver")
    parser.add_argument("--host", type=str, default="localhost", help="host address to bind")
    parser.add_argument("--port", type=int, default=8888, help="port number to bind")
    parser.add_argument("--save_path", type=str, default="./output", help="folder to save reconstructed audio")
    
    parser.add_argument("--model_path", type=str, required=True, help="folder contains model configuration and checkpoint")
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--buffer_size", type=int, default=4096, help="socket buffer size")
    parser.add_argument("--save_chunks", action="store_true", help="save individual chunks")
    
    return parser.parse_args()

class AudioStreamingReceiver:
    def __init__(self, model_path: str, device: str = "cpu", save_path: str = "./output"):
        """
        Initialize audio streaming receiver
        
        Args:
            model_path: Path to model configuration and checkpoint
            device: Device to run the model on
            save_path: Path to save reconstructed audio
        """
        self.device = device
        self.save_path = save_path
        
        # Load model
        config = read_yaml(f"{model_path}/config.yaml")
        self.model = make_model(config['model'], config['model_name'])
        self.model.load_state_dict(
            torch.load(f"{model_path}/model.pth", map_location="cpu")["model_state_dict"]
        )
        self.model = self.model.to(device)
        self.model.eval()
        
        # Socket connection
        self.server_socket = None
        self.client_socket = None
        self.connected = False
        
        # Stream metadata
        self.sample_rate = 16000
        self.chunk_size = 16000
        self.overlap_size = 1600
        self.num_streams = 6
        self.total_chunks = 0
        self.hop_size = 0
        
        # Threading
        self.receive_queue = queue.Queue(maxsize=20)
        self.decode_queue = queue.Queue(maxsize=20)
        self.stop_event = threading.Event()
        
        # Audio reconstruction
        self.reconstructed_chunks = []
        self.overlap_buffer = None
        self.received_chunks = 0
        
        # Performance statistics
        self.stats = {
            'total_bytes_received': 0,
            'total_receive_time': 0,
            'total_decode_time': 0,
            'chunks_processed': 0,
            'receive_times': [],
            'decode_times': [],
            'chunk_sizes': [],
            'start_time': None,
            'end_time': None
        }
        
        # Create output directory
        os.makedirs(save_path, exist_ok=True)
    
    def start_server(self, host: str, port: int) -> bool:
        """Start server and wait for connection"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            self.server_socket.bind((host, port))
            self.server_socket.listen(1)
            print(f"Server listening on {host}:{port}")
            
            self.client_socket, addr = self.server_socket.accept()
            self.connected = True
            print(f"Connected to sender at {addr}")
            return True
            
        except Exception as e:
            print(f"Failed to start server: {e}")
            return False
    
    def stop_server(self):
        """Stop server and close connections"""
        if self.client_socket:
            self.client_socket.close()
        if self.server_socket:
            self.server_socket.close()
        self.connected = False
        print("Server stopped")
    
    def receive_data(self, size: int) -> bytes:
        """Receive exact amount of data"""
        data = b''
        while len(data) < size:
            chunk = self.client_socket.recv(size - len(data))
            if not chunk:
                raise ConnectionError("Connection closed")
            data += chunk
        return data
    
    def receive_metadata(self) -> dict:
        """Receive metadata about the audio stream"""
        # Receive metadata length
        length_bytes = self.receive_data(4)
        metadata_length = int.from_bytes(length_bytes, byteorder='big')
        
        # Receive metadata
        metadata_bytes = self.receive_data(metadata_length)
        metadata = json.loads(metadata_bytes.decode('utf-8'))
        
        # Update stream parameters
        self.sample_rate = metadata['sample_rate']
        self.chunk_size = metadata['chunk_size']
        self.overlap_size = metadata['overlap_size']
        self.num_streams = metadata['num_streams']
        self.total_chunks = metadata['total_chunks']
        self.hop_size = self.chunk_size - self.overlap_size
        
        print(f"Received metadata: {metadata}")
        return metadata
    
    def deserialize_codes(self, data: bytes) -> Optional[dict]:
        """Deserialize received codes and metadata"""
        try:
            return pickle.loads(data)
        except Exception as e:
            print(f"Error deserializing data: {e}")
            return None
    
    def decode_chunk(self, codes: torch.Tensor, size: tuple) -> torch.Tensor:
        """Decode a single audio chunk"""
        with torch.no_grad():
            codes = codes.to(self.device)
            recon_chunk = self.model.decode(codes, size)
            return recon_chunk
    
    def process_chunk(self, chunk_data: dict) -> Optional[torch.Tensor]:
        """Process received chunk data"""
        try:
            chunk_idx = chunk_data['chunk_idx']
            codes = torch.from_numpy(chunk_data['codes'])
            size = chunk_data['size']
            timestamp = chunk_data['timestamp']
            
            # Decode chunk
            recon_chunk = self.decode_chunk(codes, size)
            
            # Handle overlapping
            if self.overlap_buffer is not None:
                # Blend overlapping regions
                blended_overlap = (self.overlap_buffer + recon_chunk[:, :self.overlap_size]) / 2
                recon_chunk = torch.cat([blended_overlap, recon_chunk[:, self.overlap_size:]], dim=1)
            
            # Store overlap for next chunk
            if chunk_idx < self.total_chunks:
                self.overlap_buffer = recon_chunk[:, -self.overlap_size:].clone()
                output_chunk = recon_chunk[:, :self.hop_size]
            else:
                # Last chunk, no overlap needed
                output_chunk = recon_chunk
                if self.overlap_buffer is not None:
                    output_chunk = recon_chunk[:, :self.hop_size]
            
            print(f"Decoded chunk {chunk_idx}/{self.total_chunks}")
            return output_chunk
            
        except Exception as e:
            print(f"Error processing chunk: {e}")
            return None
    
    def receiving_worker(self):
        """Worker thread for receiving data"""
        while not self.stop_event.is_set():
            try:
                # Measure receive time
                receive_start = time.time()
                
                # Receive data length
                length_bytes = self.receive_data(4)
                data_length = int.from_bytes(length_bytes, byteorder='big')
                
                # Receive data
                data = self.receive_data(data_length)
                
                receive_end = time.time()
                receive_time = receive_end - receive_start
                
                # Update statistics
                data_size = data_length + 4  # Include length prefix
                self.stats['receive_times'].append(receive_time)
                self.stats['total_receive_time'] += receive_time
                self.stats['chunk_sizes'].append(data_size)
                self.stats['total_bytes_received'] += data_size
                
                # Deserialize data
                chunk_data = self.deserialize_codes(data)
                if chunk_data is None:
                    continue
                
                # Check for end signal
                if chunk_data.get('end', False):
                    print("Received end signal")
                    self.decode_queue.put(None)  # Signal decoding worker to stop
                    break
                
                # Add to decode queue
                self.decode_queue.put(chunk_data)
                
                print(f"Received chunk data ({data_size} bytes) in {receive_time:.4f}s")
                
            except Exception as e:
                print(f"Error in receiving worker: {e}")
                break
    
    def decoding_worker(self):
        """Worker thread for decoding chunks"""
        while not self.stop_event.is_set():
            try:
                chunk_data = self.decode_queue.get(timeout=1.0)
                if chunk_data is None:  # Poison pill
                    break
                
                # Measure decode time
                decode_start = time.time()
                
                # Process chunk
                output_chunk = self.process_chunk(chunk_data)
                
                decode_end = time.time()
                decode_time = decode_end - decode_start
                
                # Update statistics
                self.stats['decode_times'].append(decode_time)
                self.stats['total_decode_time'] += decode_time
                self.stats['chunks_processed'] += 1
                
                if output_chunk is not None:
                    self.reconstructed_chunks.append(output_chunk)
                    self.received_chunks += 1
                    
                    chunk_idx = chunk_data.get('chunk_idx', 0)
                    print(f"Decoded chunk {chunk_idx} in {decode_time:.4f}s")
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in decoding worker: {e}")
                break
    
    def save_audio(self, chunks: List[torch.Tensor], filename: str):
        """Save reconstructed audio chunks to file"""
        if not chunks:
            print("No chunks to save")
            return
        
        # Concatenate all chunks
        full_audio = torch.cat(chunks, dim=1)
        
        # Save to file
        output_path = os.path.join(self.save_path, filename)
        torchaudio.save(output_path, full_audio, self.sample_rate)
        print(f"Saved reconstructed audio to: {output_path}")
    
    def save_individual_chunks(self, chunks: List[torch.Tensor], base_filename: str):
        """Save individual chunks"""
        for i, chunk in enumerate(chunks):
            filename = f"{base_filename}_chunk_{i+1}.wav"
            output_path = os.path.join(self.save_path, filename)
            torchaudio.save(output_path, chunk, self.sample_rate)
        print(f"Saved {len(chunks)} individual chunks")
    
    def receive_stream(self, save_chunks: bool = False):
        """Main function to receive and process audio stream"""
        try:
            # Initialize statistics
            self.stats['start_time'] = time.time()
            
            # Receive metadata
            metadata = self.receive_metadata()
            
            # Start worker threads
            receive_thread = threading.Thread(target=self.receiving_worker)
            decode_thread = threading.Thread(target=self.decoding_worker)
            
            receive_thread.start()
            decode_thread.start()
            
            # Wait for streaming to complete
            receive_thread.join()
            decode_thread.join()
            
            # Finalize statistics
            self.stats['end_time'] = time.time()
            
            # Save reconstructed audio
            if self.reconstructed_chunks:
                timestamp = int(time.time())
                filename = f"received_audio_{self.num_streams*1.5}kbps_{timestamp}.wav"
                self.save_audio(self.reconstructed_chunks, filename)
                
                if save_chunks:
                    base_filename = f"received_{self.num_streams*1.5}kbps_{timestamp}"
                    self.save_individual_chunks(self.reconstructed_chunks, base_filename)
                
                print(f"Received and decoded {self.received_chunks} chunks")
                self.print_performance_stats()
            else:
                print("No audio data received")
                
        except Exception as e:
            print(f"Error during stream reception: {e}")
        finally:
            self.stop_event.set()
    
    def print_performance_stats(self):
        """Print detailed performance statistics"""
        if self.stats['start_time'] is None or self.stats['end_time'] is None:
            print("Performance statistics not available")
            return
        
        total_time = self.stats['end_time'] - self.stats['start_time']
        
        print("\n=== Receiver Performance Statistics ===")
        print(f"Total reception time: {total_time:.3f} seconds")
        print(f"Total bytes received: {self.stats['total_bytes_received']:,} bytes")
        print(f"Average reception rate: {self.stats['total_bytes_received'] / total_time:.2f} bytes/second")
        
        if self.stats['chunks_processed'] > 0:
            print(f"\nReception Performance:")
            print(f"  Total reception time: {self.stats['total_receive_time']:.3f} seconds")
            print(f"  Average reception time per chunk: {self.stats['total_receive_time'] / len(self.stats['receive_times']):.4f} seconds")
            print(f"  Min reception time: {min(self.stats['receive_times']):.4f} seconds")
            print(f"  Max reception time: {max(self.stats['receive_times']):.4f} seconds")
            
            print(f"\nDecoding Performance:")
            print(f"  Total decoding time: {self.stats['total_decode_time']:.3f} seconds")
            print(f"  Average decoding time per chunk: {self.stats['total_decode_time'] / self.stats['chunks_processed']:.4f} seconds")
            print(f"  Min decoding time: {min(self.stats['decode_times']):.4f} seconds")
            print(f"  Max decoding time: {max(self.stats['decode_times']):.4f} seconds")
            
            print(f"\nChunk Size Statistics:")
            print(f"  Average chunk size: {sum(self.stats['chunk_sizes']) / len(self.stats['chunk_sizes']):.2f} bytes")
            print(f"  Min chunk size: {min(self.stats['chunk_sizes'])} bytes")
            print(f"  Max chunk size: {max(self.stats['chunk_sizes'])} bytes")
            
            # Calculate efficiency
            receive_efficiency = (self.stats['total_receive_time'] / total_time) * 100
            decode_efficiency = (self.stats['total_decode_time'] / total_time) * 100
            
            print(f"\nEfficiency Analysis:")
            print(f"  Reception time ratio: {receive_efficiency:.2f}% of total time")
            print(f"  Decoding time ratio: {decode_efficiency:.2f}% of total time")
            print(f"  Idle time ratio: {100 - receive_efficiency - decode_efficiency:.2f}% of total time")
            
        print("=" * 38)

def main():
    args = parse_args()
    
    # Initialize receiver
    receiver = AudioStreamingReceiver(
        model_path=args.model_path,
        device=args.device,
        save_path=args.save_path
    )
    
    try:
        # Start server
        if receiver.start_server(args.host, args.port):
            # Receive stream
            receiver.receive_stream(args.save_chunks)
        else:
            print("Failed to start server")
            return
            
    except KeyboardInterrupt:
        print("\nServer interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        receiver.stop_server()

if __name__ == "__main__":
    main()

"""
Usage examples:

1. Basic receiver:
python -m scripts.receiver \
    --host localhost \
    --port 8888 \
    --save_path ./output/received \
    --model_path ./model/esc9kbps_base_adversarial \
    --device cpu

2. Save individual chunks:
python -m scripts.receiver \
    --host localhost \
    --port 8888 \
    --save_path ./output/received \
    --model_path ./model/esc9kbps_base_adversarial \
    --device cpu \
    --save_chunks

3. Start receiver first, then sender:
# Terminal 1:
python -m scripts.receiver --model_path ./model/esc9kbps_base_adversarial

# Terminal 2:
python -m scripts.sender --input ./data/speech_1.wav --model_path ./model/esc9kbps_base_adversarial
"""
