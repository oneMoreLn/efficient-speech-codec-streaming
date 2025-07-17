from esc.models import make_model
from utils import read_yaml
import torch
import os
import torchaudio
import argparse
import warnings
import time
from typing import Iterator, Tuple
warnings.filterwarnings("ignore")

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True, help="input 16kHz mono audio file to encode")
    parser.add_argument("--save_path", type=str, default="./output", help="folder to save codes and reconstructed audio")

    parser.add_argument("--model_path", type=str, required=True, help="folder contains model configuration and checkpoint")
    parser.add_argument("--num_streams", type=int, default=6, help="number of transmitted streams in encoding")

    parser.add_argument("--device", type=str, default="cpu")
    parser.add_argument("--streaming", action="store_true", help="enable streaming compression")
    parser.add_argument("--chunk_size", type=int, default=16000, help="chunk size in samples for streaming (default: 1 second at 16kHz)")
    parser.add_argument("--overlap_size", type=int, default=1600, help="overlap size in samples for streaming (default: 0.1 second at 16kHz)")
    
    return parser.parse_args()

def streaming_compress(args):
    """Streaming compression function"""
    print("Starting streaming compression...")
    
    # Load audio
    x, sr = torchaudio.load(args.input)
    if x.shape[0] > 1:
        x = x.mean(dim=0, keepdim=True)
    x = x.to(args.device)
    
    # Load model
    model = make_model(read_yaml(f"{args.model_path}/config.yaml")['model'], read_yaml(f"{args.model_path}/config.yaml")['model_name'])
    model.load_state_dict(
        torch.load(f"{args.model_path}/model.pth", map_location="cpu")["model_state_dict"],
    )
    model = model.to(args.device)
    model.eval()
    
    # Setup streaming parameters
    chunk_size = args.chunk_size
    overlap_size = args.overlap_size
    hop_size = chunk_size - overlap_size
    
    # Process audio in chunks
    audio_length = x.shape[1]
    start_idx = 0
    
    all_codes = []
    all_recon_chunks = []
    overlap_buffer = None
    chunk_idx = 0
    
    start_time = time.time()
    
    while start_idx < audio_length:
        chunk_idx += 1
        
        # Extract chunk
        end_idx = min(start_idx + chunk_size, audio_length)
        chunk = x[:, start_idx:end_idx]
        
        # Pad chunk if necessary
        if chunk.shape[1] < chunk_size:
            pad_size = chunk_size - chunk.shape[1]
            chunk = torch.nn.functional.pad(chunk, (0, pad_size))
        
        # Process chunk
        with torch.no_grad():
            codes, size = model.encode(chunk, num_streams=args.num_streams)
            recon_chunk = model.decode(codes, size)
        
        # Handle overlapping
        if overlap_buffer is not None:
            # Blend overlapping regions
            blended_overlap = (overlap_buffer + recon_chunk[:, :overlap_size]) / 2
            recon_chunk = torch.cat([blended_overlap, recon_chunk[:, overlap_size:]], dim=1)
        
        # Store overlap for next chunk
        if end_idx < audio_length:
            overlap_buffer = recon_chunk[:, -overlap_size:].clone()
            output_chunk = recon_chunk[:, :hop_size]
        else:
            # Last chunk, no overlap needed
            output_chunk = recon_chunk
            if overlap_buffer is not None:
                output_chunk = recon_chunk[:, :hop_size]
        
        # Store results
        all_codes.append(codes)
        all_recon_chunks.append(output_chunk)
        
        print(f"Processed chunk {chunk_idx}/{int(audio_length/hop_size)+1}")
        
        # Move to next chunk
        start_idx += hop_size
    
    # Concatenate all reconstructed chunks
    if all_recon_chunks:
        full_recon = torch.cat(all_recon_chunks, dim=1)
        
        # Trim to original length
        original_length = min(full_recon.shape[1], audio_length)
        full_recon = full_recon[:, :original_length]
        
        # Save results
        fname = args.input.split("/")[-1]
        if not os.path.exists(args.save_path): 
            os.makedirs(args.save_path)
        
        output_path = f"{args.save_path}/decoded_{args.num_streams*1.5}kbps_{fname}"
        torchaudio.save(output_path, full_recon, sr)
        
        codes_path = f"{args.save_path}/encoded_{args.num_streams*1.5}kbps_{fname.split('.')[0]}.pth"
        torch.save(all_codes, codes_path)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        print(f"Streaming compression completed!")
        print(f"Processed {chunk_idx} chunks in {processing_time:.2f} seconds")
        print(f"Average processing time per chunk: {processing_time/chunk_idx:.3f} seconds")
        print(f"Output saved to: {output_path}")
        print(f"Codes saved to: {codes_path}")
    
    else:
        print("No chunks were processed!")

def main(args):
    if args.streaming:
        streaming_compress(args)
    else:
        # Original batch compression
        x, sr = torchaudio.load(f"{args.input}")
        x = x.to(args.device)

        model = make_model(read_yaml(f"{args.model_path}/config.yaml")['model'], read_yaml(f"{args.model_path}/config.yaml")['model_name'])
        model.load_state_dict(
            torch.load(f"{args.model_path}/model.pth", map_location="cpu")["model_state_dict"],
        )
        model = model.to(args.device)

        codes, size = model.encode(x, num_streams=args.num_streams)
        recon_x = model.decode(codes, size)

        fname = args.input.split("/")[-1]
        if not os.path.exists(args.save_path): 
            os.makedirs(args.save_path)
        torchaudio.save(f"{args.save_path}/decoded_{args.num_streams*1.5}kbps_{fname}", recon_x, sr)
        torch.save(codes, f"{args.save_path}/encoded_{args.num_streams*1.5}kbps_{fname.split('.')[0]}.pth")
        print(f"compression outputs saved into {args.save_path}")

if __name__ == "__main__":
    args = parse_args()
    main(args)

"""
Usage examples:

1. Original batch compression:
python -m scripts.compress \
    --input ./data/speech_1.wav \
    --save_path ./output \
    --model_path ./model/esc9kbps_base_adversarial \
    --num_streams 6 \
    --device cpu 

2. Streaming compression:
python -m scripts.compress \
    --input ./data/speech_1.wav \
    --save_path ./output \
    --model_path ./model/esc9kbps_base_adversarial \
    --num_streams 6 \
    --device cpu \
    --streaming

3. Streaming with custom chunk size:
python -m scripts.compress \
    --input ./data/speech_1.wav \
    --save_path ./output \
    --model_path ./model/esc9kbps_base_adversarial \
    --num_streams 6 \
    --device cpu \
    --streaming \
    --chunk_size 8000 \
    --overlap_size 800

"""