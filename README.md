# Efficient Speech Coding with Cross-Scale Residual Vector Quantized Transformers

This is the code repository for the neural speech codec presented in the EMNLP 2024 paper **ESC: Efficient Speech Coding with Cross-Scale Residual Vector Quantized Transformers** [[paper](https://arxiv.org/abs/2404.19441)]

- Our neural speech codec ESC, within only 30MB, efficiently compresses 16kHz speech at bitrates of 1.5, 3, 4.5, 6, 7.5, and 9kbps, while maintaining comparative reconstruction quality to Descript's audio codec. 
- We provide pretrained model checkpoints [[download](#model-checkpoints)] for different ESC variants and DAC models, as well as a demo webpage [[link](https://efficient-speech-codec.notion.site/)] including multilingual speech samples.
- **NEW**: Real-time voice processing pipeline with microphone input/output support and streaming capabilities.

![An illustration of ESC Architecture](assets/architecture.png)

## 🆕 New Features

### Real-time Voice Processing
We've added a comprehensive voice processing pipeline that supports:

- **🎤 Microphone Input**: Real-time audio capture from microphone
- **🔄 Voice Processing**: Queue-based audio encoding/decoding with ESC codec
- **📡 Streaming Support**: Real-time audio streaming with configurable parameters
- **💾 Audio Saving**: Save processed audio to WAV files
- **⚡ Low Latency**: Optimized for real-time applications

#### Quick Start - Voice Processing
```python
from voice_process import VoiceProcessor

# Create voice processor with custom settings
processor = VoiceProcessor(
    model_path="model/esc9kbps_base_adversarial",
    device="cpu", 
    num_streams=6  # Configure quality vs. performance
)

# Start processing
processor.start_workers()

# Add audio data (numpy array, float32, 4096Hz)
processor.voice_send_queue.put(audio_data)

# Get processed audio
processed_audio = processor.voice_recv_queue.get()

# Stop processing
processor.stop_workers()
```

#### Voice Processing Examples
```bash
# Run simple voice processing test
python simple_voice_test.py

# Test different num_streams parameters  
python simple_voice_test.py streams

# Process audio file
python simple_voice_test.py input.wav output.wav

# Comprehensive voice processing tests
python test_voice_process.py --help
```

#### Streaming Audio Tests
```bash
# Test real-time streaming
python test_streaming.py

# Test with microphone input
python test_microphone.py

# Performance analysis
python test_streaming_stats.py
```
## 📁 Project Structure

```
├── esc/                          # Core ESC codec implementation
├── scripts/                      # Training and evaluation scripts
├── configs/                      # Model configuration files
├── model/                        # Pre-trained model checkpoints
├── data/                         # Sample audio files
├── output/                       # Generated output files
├── voice_process.py              # 🆕 Real-time voice processing module
├── test_voice_process.py         # 🆕 Comprehensive voice tests
├── simple_voice_test.py          # 🆕 Simple usage examples
├── test_microphone.py            # 🆕 Microphone input tests
├── test_streaming.py             # 🆕 Streaming performance tests
└── requirements.txt              # Python dependencies
```

## Usage

### Environment Setup
```bash
conda create -n esc python=3.10
conda activate esc

pip install -r requirements.txt

# For microphone support (optional)
pip install pyaudio
# On Ubuntu/Debian: sudo apt-get install portaudio19-dev
# On macOS: brew install portaudio
# On Windows: pip install pipwin && pipwin install pyaudio
```

### 🎤 Real-time Voice Processing

#### Basic Voice Processing
```python
from voice_process import VoiceProcessor
import numpy as np

# Initialize processor
processor = VoiceProcessor(
    model_path="model/esc9kbps_base_adversarial",
    device="cpu",
    num_streams=6  # Quality setting: 1(fast) to 9(best quality)
)

# Start processing workers
processor.start_workers()

# Process audio chunks (4096Hz, float32)
audio_chunk = np.random.randn(1024).astype(np.float32)  # 250ms @ 4096Hz
processor.voice_send_queue.put(audio_chunk)

# Get processed results
if not processor.voice_recv_queue.empty():
    processed_chunk = processor.voice_recv_queue.get()
    print(f"Processed {len(processed_chunk)} samples")

processor.stop_workers()
```

#### File Processing
```bash
# Process single audio file
python simple_voice_test.py input.wav output.wav

# Run quality comparison tests
python simple_voice_test.py streams
```

#### Microphone Input
```python
from test_voice_process import AudioTester

# Test with microphone input
tester = AudioTester()
result = tester.test_microphone_input(
    duration=5.0,  # Record for 5 seconds
    device_index=None  # Use default microphone
)
print(f"Processed {result['input_samples']} -> {result['output_samples']} samples")
```

### 🔧 Compress and de-compress audio
```ruby
python -m scripts.compress  --input /path/to/input.wav --save_path /path/to/output --model_path /path/to/model --num_streams 6 --device cpu 
```
This will create `.pth`(code) and `.wav`(reconstructed audio) files under the specified `save_path`. Our codec supports `num_streams` from 1 to 6, corresponding to bitrates 1.5 ~ 9.0 kbps. For programmatic usage, you can compress audio tensors using `torchaudio` as follows: 

```python
import torchaudio, torch
from esc import ESC
model = ESC(**config)
model.load_state_dict(torch.load("model.pth", map_location="cpu"),)
x, _ = torchaudio.load("input.wav")
# Enc. (@ num_streams*1.5 kbps)
codes, f_shape = model.encode(x, num_streams=6)
# Dec.
recon_x = model.decode(codes, f_shape)
```
For more details, see the `example.ipynb` notebook.

### 🎯 Training

We provide developmental training and evaluation datasets available on [Hugging Face](https://huggingface.co/datasets/Tracygu/dnscustom/tree/main). For custom training, set the `train_data_path` in `exp.yaml` to the parent directory containing `.wav` audio segments. Run the following to start training:

```ruby
WANDB_API_KEY=your_API_key
accelerate launch main.py --exp_name esc9kbps --config_path ./configs/9kbps_esc_base.yaml --wandb_project efficient-speech-codec --lr 1.0e-4 --num_epochs 80 --num_pretraining_epochs 15 --num_devices 4 --dropout_rate 0.75 --save_path /path/to/output --seed 53
```

We use `accelerate` library to handle distributed training and `wandb` library for monitoring. To enable adversarial training with the same discriminator in DAC, include the `--adv_training` flag. 

Training a base ESC model on 4 RTX4090 GPUs takes ~16 hours for 250k steps on 3-second speech clips with a batch size of 36. Detailed experiment configurations can be found in the `configs/` folder. For complete experiments presented in the paper, refer to `scripts_all.sh`.  

### 📊 Evaluation

```ruby
CUDA_VISIBLE_DEVICES=0
python -m scripts.test --eval_folder_path path/to/data --batch_size 12 --model_path /path/to/model --device cuda
```
This will run codec evaluation across all available bandwidth on the specified test set folder. We provide four metrics for reporting: `PESQ`, `Mel-Distance`, `SI-SDR` and `Bitrate-Utilization-Rate`. Evaluation statistics will be saved under `model_path` by default.  

## 📚 Documentation

For detailed information about the new voice processing features:

- **[Voice Processing Guide](VOICE_PROCESS_TEST_REPORT.md)**: Comprehensive testing framework documentation
- **[Streaming Guide](STREAMING_README.md)**: Real-time streaming implementation details  
- **[Microphone Usage](MICROPHONE_USAGE.md)**: Microphone input setup and usage
- **[num_streams Parameter](NUM_STREAMS_USAGE.md)**: Quality vs. performance configuration
- **[Performance Report](STREAMING_PERFORMANCE_REPORT.md)**: Streaming performance analysis

## 📦 Model Checkpoints
You can download the pre-trained model checkpoints below:

| Codec  | Checkpoint                                      | #Param. |
|--------|-------------------------------------------------|----------|
| ESC-Base           | [Download](https://drive.google.com/file/d/1OF1ab3az6nKOY8owSUhUH0ksYHFmR1bc/view?usp=sharing) | 8.39M    |
| ESC-Base(adv)      | [Download](https://drive.google.com/file/d/1_g1dFYhY7qXKWkcq8_Q6I-kv8tQW_SF7/view?usp=sharing) | 8.39M    |
| ESC-Large          | [Download](https://drive.google.com/file/d/180Q4zctqeNnDmRvoMsVQ-3iCB5FriJbN/view?usp=sharing) | 15.58M   |
| DAC-Tiny(adv)      | [Download](https://drive.google.com/file/d/1ED-B_S7ftsb8CqoFGTNkWUIrMKrk-iiu/view?usp=sharing) | 8.17M    |
| DAC-Tiny           | [Download](https://drive.google.com/file/d/1jk8zPYBYmxgsiSzrgoQynF6hnzoiIuX8/view?usp=sharing) | 8.17M    |
| DAC-Base(adv)      | [Download](https://drive.google.com/file/d/1moy0FX-aPlx54MajBRuE-zjYeNlJUjI6/view?usp=sharing) | 74.31M   |

## � Quick Start Examples

### 1. Basic Audio Compression
```bash
# Compress audio file
python -m scripts.compress --input data/speech_1.wav --save_path output --model_path model/esc9kbps_base_adversarial --num_streams 6 --device cpu
```

### 2. Real-time Voice Processing
```bash
# Quick test
python simple_voice_test.py

# Test with your own audio file  
python simple_voice_test.py path/to/your/audio.wav output/processed.wav

# Test different quality settings
python simple_voice_test.py streams
```

### 3. Microphone Recording
```bash
# Test microphone input (requires pyaudio)
python test_microphone.py

# Comprehensive voice processing tests
python test_voice_process.py --source microphone --duration 10
```

### 4. Streaming Tests
```bash
# Test streaming performance
python test_streaming.py

# Analyze streaming statistics
python test_streaming_stats.py
```

## 🐛 Troubleshooting

### Common Issues

1. **PyAudio Installation Issues**:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install portaudio19-dev python3-pyaudio
   
   # macOS
   brew install portaudio
   pip install pyaudio
   
   # Windows
   pip install pipwin
   pipwin install pyaudio
   ```

2. **CUDA/GPU Issues**:
   ```python
   # Use CPU if GPU issues occur
   processor = VoiceProcessor(device="cpu")
   ```

3. **Audio Format Issues**:
   - Ensure audio is 16-bit PCM WAV format
   - Sample rate will be automatically resampled to 4096Hz

## 🔧 Configuration

### VoiceProcessor Parameters
- `model_path`: Path to ESC model directory (default: "model/esc9kbps_base_adversarial")
- `device`: Computing device "cpu" or "cuda" (default: "cpu")  
- `num_streams`: Encoding quality 1-9 (default: 6, balance of quality and performance)

### Audio Parameters
- **Sample Rate**: 4096 Hz (automatically resampled)
- **Channels**: Mono (stereo converted automatically)
- **Chunk Size**: 1024 samples (250ms @ 4096Hz)
- **Encoding Period**: 5 seconds
- **Packet Size**: 2088 bytes

## �📈 Results

![Performance Evaluation](assets/results.png)
We provide a comprehensive performance comparison of ESC with Descript's audio codec (DAC) at different scales of model sizes (w/ and w/o adversarial trainings).

## Reference
If you find our work useful or relevant to your research, please kindly cite our paper:
```bibtex
@article{gu2024esc,
        title={ESC: Efficient Speech Coding with Cross-Scale Residual Vector Quantized Transformers},
        author={Gu, Yuzhe and Diao, Enmao},
        journal={arXiv preprint arXiv:2404.19441},
        year={2024}
}
```