from esc.models import make_model
from utils import read_yaml
import torch
import torchaudio
import argparse
import warnings
import os
import numpy as np
from typing import Iterator, Tuple, Optional
import time

warnings.filterwarnings("ignore")

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True, help="input 16kHz mono audio file to encode")
    parser.add_argument("--save_path", type=str, default="./output", help="folder to save codes and reconstructed audio")
    
    parser.add_argument("--model_path", type=str, required=True, help="folder contains model configuration and checkpoint")
    parser.add_argument("--num_streams", type=int, default=6, help="number of transmitted streams in encoding")
    
    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--chunk_size", type=int, default=16000, help="chunk size in samples (default: 1 second at 16kHz)")
    parser.add_argument("--overlap_size", type=int, default=1600, help="overlap size in samples (default: 0.1 second at 16kHz)")
    parser.add_argument("--realtime", action="store_true", help="simulate real-time processing")
    
    return parser.parse_args()

class StreamingAudioProcessor:
    def __init__(self, model_path: str, device: str = "cpu", chunk_size: int = 16000, overlap_size: int = 1600):
        """
        Initialize streaming audio processor
        
        Args:
            model_path: Path to model configuration and checkpoint
            device: Device to run the model on
            chunk_size: Size of each audio chunk in samples
            overlap_size: Overlap between chunks in samples
        """
        self.device = device
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        self.hop_size = chunk_size - overlap_size
        
        # Load model
        config = read_yaml(f"{model_path}/config.yaml")
        self.model = make_model(config['model'], config['model_name'])
        self.model.load_state_dict(
            torch.load(f"{model_path}/model.pth", map_location="cpu")["model_state_dict"]
        )
        self.model = self.model.to(device)
        self.model.eval()
        
        # Buffer for overlapping
        self.overlap_buffer = None
        self.output_buffer = []
        
    def process_chunk(self, chunk: torch.Tensor, num_streams: int = 6) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Process a single audio chunk
        
        Args:
            chunk: Audio chunk tensor of shape (1, chunk_size)
            num_streams: Number of streams for encoding
            
        Returns:
            Tuple of (encoded_codes, reconstructed_audio)
        """
        with torch.no_grad():
            # Ensure chunk is on the correct device
            chunk = chunk.to(self.device)
            
            # Encode the chunk
            codes, size = self.model.encode(chunk, num_streams=num_streams)
            
            # Decode the chunk
            recon_chunk = self.model.decode(codes, size)
            
            return codes, recon_chunk
    
    def stream_from_file(self, input_path: str, num_streams: int = 6) -> Iterator[Tuple[torch.Tensor, torch.Tensor]]:
        """
        Stream audio from file in chunks
        
        Args:
            input_path: Path to input audio file
            num_streams: Number of streams for encoding
            
        Yields:
            Tuple of (encoded_codes, reconstructed_audio_chunk)
        """
        # Load audio file
        audio, sr = torchaudio.load(input_path)
        
        # Ensure mono audio
        if audio.shape[0] > 1:
            audio = audio.mean(dim=0, keepdim=True)
        
        # Process audio in chunks
        audio_length = audio.shape[1]
        start_idx = 0
        
        while start_idx < audio_length:
            # Extract chunk
            end_idx = min(start_idx + self.chunk_size, audio_length)
            chunk = audio[:, start_idx:end_idx]
            
            # Pad chunk if necessary
            if chunk.shape[1] < self.chunk_size:
                pad_size = self.chunk_size - chunk.shape[1]
                chunk = torch.nn.functional.pad(chunk, (0, pad_size))
            
            # Process chunk
            codes, recon_chunk = self.process_chunk(chunk, num_streams)
            
            # Handle overlapping
            if self.overlap_buffer is not None:
                # Blend overlapping regions
                overlap_start = recon_chunk.shape[1] - self.overlap_size
                blended_overlap = (self.overlap_buffer + recon_chunk[:, :self.overlap_size]) / 2
                recon_chunk = torch.cat([blended_overlap, recon_chunk[:, self.overlap_size:]], dim=1)
            
            # Store overlap for next chunk
            if end_idx < audio_length:
                self.overlap_buffer = recon_chunk[:, -self.overlap_size:].clone()
                output_chunk = recon_chunk[:, :self.hop_size]
            else:
                # Last chunk, no overlap needed
                output_chunk = recon_chunk
                if self.overlap_buffer is not None:
                    output_chunk = recon_chunk[:, :self.hop_size]
            
            yield codes, output_chunk
            
            # Move to next chunk
            start_idx += self.hop_size
    
    def stream_realtime_simulation(self, input_path: str, num_streams: int = 6, 
                                 sample_rate: int = 16000) -> Iterator[Tuple[torch.Tensor, torch.Tensor]]:
        """
        Simulate real-time streaming processing
        
        Args:
            input_path: Path to input audio file
            num_streams: Number of streams for encoding
            sample_rate: Sample rate of audio
            
        Yields:
            Tuple of (encoded_codes, reconstructed_audio_chunk)
        """
        chunk_duration = self.chunk_size / sample_rate
        
        for codes, recon_chunk in self.stream_from_file(input_path, num_streams):
            # Simulate real-time processing delay
            time.sleep(chunk_duration)
            yield codes, recon_chunk
    
    def reset_buffers(self):
        """Reset internal buffers for new stream"""
        self.overlap_buffer = None
        self.output_buffer = []

def main(args):
    # Initialize streaming processor
    processor = StreamingAudioProcessor(
        model_path=args.model_path,
        device=args.device,
        chunk_size=args.chunk_size,
        overlap_size=args.overlap_size
    )
    
    # Create output directory
    if not os.path.exists(args.save_path):
        os.makedirs(args.save_path)
    
    # Get filename
    fname = os.path.basename(args.input)
    base_name = os.path.splitext(fname)[0]
    
    # Choose streaming method
    if args.realtime:
        print("Starting real-time simulation...")
        stream_iterator = processor.stream_realtime_simulation(args.input, args.num_streams)
    else:
        print("Starting batch streaming...")
        stream_iterator = processor.stream_from_file(args.input, args.num_streams)
    
    # Process stream
    all_codes = []
    all_recon_chunks = []
    
    chunk_idx = 0
    start_time = time.time()
    
    for codes, recon_chunk in stream_iterator:
        chunk_idx += 1
        
        # Store codes and reconstructed audio
        all_codes.append(codes)
        all_recon_chunks.append(recon_chunk)
        
        # Optional: Save individual chunks
        if args.realtime:
            chunk_path = f"{args.save_path}/chunk_{chunk_idx}_{args.num_streams*1.5}kbps_{base_name}.wav"
            torchaudio.save(chunk_path, recon_chunk, 16000)
            print(f"Processed chunk {chunk_idx}, saved to {chunk_path}")
    
    # Concatenate all reconstructed chunks
    if all_recon_chunks:
        full_recon = torch.cat(all_recon_chunks, dim=1)
        
        # Save full reconstructed audio
        output_path = f"{args.save_path}/decoded_{args.num_streams*1.5}kbps_{fname}"
        torchaudio.save(output_path, full_recon, 16000)
        
        # Save all codes
        codes_path = f"{args.save_path}/encoded_{args.num_streams*1.5}kbps_{base_name}.pth"
        torch.save(all_codes, codes_path)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        print(f"Streaming compression completed!")
        print(f"Processed {chunk_idx} chunks in {processing_time:.2f} seconds")
        print(f"Average processing time per chunk: {processing_time/chunk_idx:.3f} seconds")
        print(f"Full reconstructed audio saved to: {output_path}")
        print(f"Encoded codes saved to: {codes_path}")
    
    else:
        print("No chunks were processed!")

if __name__ == "__main__":
    args = parse_args()
    main(args)

"""
Usage examples:

1. Basic streaming compression:
python -m scripts.stream_compress \
    --input ./data/speech_1.wav \
    --save_path ./output/streaming \
    --model_path ./model/esc9kbps_base_adversarial \
    --num_streams 6 \
    --device cpu

2. Real-time simulation:
python -m scripts.stream_compress \
    --input ./data/speech_1.wav \
    --save_path ./output/streaming \
    --model_path ./model/esc9kbps_base_adversarial \
    --num_streams 6 \
    --device cpu \
    --realtime

3. Custom chunk size:
python -m scripts.stream_compress \
    --input ./data/speech_1.wav \
    --save_path ./output/streaming \
    --model_path ./model/esc9kbps_base_adversarial \
    --num_streams 6 \
    --device cpu \
    --chunk_size 8000 \
    --overlap_size 800

"""
