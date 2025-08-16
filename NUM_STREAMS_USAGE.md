# VoiceProcessor num_streams 参数使用指南

## 📖 概述

`num_streams` 参数控制ESC编码器使用的并行流数量，影响音频编码的质量和复杂度。

## 🔧 参数配置

### 基本用法

```python
from voice_process import VoiceProcessor

# 使用默认参数 (num_streams=6)
processor = VoiceProcessor()

# 自定义num_streams参数
processor = VoiceProcessor(num_streams=3)

# 完整参数配置
processor = VoiceProcessor(
    model_path="model/esc9kbps_base_adversarial",
    device="cpu", 
    num_streams=9
)
```

## 📊 参数影响

| num_streams | 质量 | 计算复杂度 | 推荐场景 |
|-------------|------|------------|----------|
| 1           | 基础 | 最低       | 快速测试、资源受限 |
| 3           | 良好 | 较低       | 实时应用 |
| 6 (默认)    | 优秀 | 中等       | 平衡质量与性能 |
| 9           | 最佳 | 最高       | 高质量要求 |

## 🧪 测试不同参数

### 快速测试
```bash
# 测试不同num_streams参数的效果
python simple_voice_test.py streams
```

### 音频文件处理对比
```python
import wave
import numpy as np
from voice_process import VoiceProcessor

def compare_num_streams(input_file):
    """比较不同num_streams参数的处理效果"""
    
    for num_streams in [1, 3, 6, 9]:
        print(f"\\n🔄 测试 num_streams = {num_streams}")
        
        # 创建处理器
        processor = VoiceProcessor(num_streams=num_streams)
        processor.start_workers()
        
        try:
            # 加载音频文件
            with wave.open(input_file, 'rb') as wav:
                audio_data = np.frombuffer(wav.readframes(-1), dtype=np.int16)
                audio_float = audio_data.astype(np.float32) / 32768.0
            
            # 处理音频（简化示例）
            # 实际使用中需要按块处理并收集结果
            print(f"  📊 输入: {len(audio_float)} 样本")
            print(f"  ⚙️  使用 {num_streams} 个编码流")
            
        finally:
            processor.stop_workers()

# 使用示例
# compare_num_streams("data/speech_1.wav")
```

## ⚡ 性能建议

1. **实时应用**: 使用 `num_streams=3` 或 `num_streams=6`
2. **离线处理**: 可以使用更高的值如 `num_streams=9`
3. **资源受限**: 使用 `num_streams=1`
4. **默认选择**: `num_streams=6` 提供良好的质量与性能平衡

## 🔍 故障排除

如果遇到问题：

1. **内存不足**: 降低 `num_streams` 值
2. **处理过慢**: 使用较小的 `num_streams` 值
3. **质量不满意**: 增加 `num_streams` 值

## 📝 更新日志

- **2024-01**: 添加 `num_streams` 可配置参数
- 默认值设为 6，提供质量与性能的平衡
- 支持 1-9 的参数范围
- 添加测试脚本验证不同参数效果
