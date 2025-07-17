# 音频流式传输功能

本项目新增了基于socket的音频流式传输功能，支持实时音频压缩和传输。

## 文件说明

### 1. `scripts/sender.py` - 发送端
负责音频编码和发送压缩后的比特流。

**主要功能：**
- 加载音频文件并分块处理
- 使用ESC模型进行音频压缩编码
- 通过socket发送压缩数据流
- 支持实时和非实时模式
- 多线程处理：编码线程 + 发送线程

### 2. `scripts/receiver.py` - 接收端
负责接收压缩比特流并解码为音频。

**主要功能：**
- 启动socket服务器等待连接
- 接收压缩数据流
- 使用ESC模型进行音频解码
- 处理音频块的重叠拼接
- 保存完整重建音频和分块文件
- 多线程处理：接收线程 + 解码线程

### 3. `scripts/compress.py` - 改进的压缩脚本
在原有批处理功能基础上，增加了流式压缩选项。

**新增功能：**
- `--streaming` 参数启用流式压缩
- `--chunk_size` 设置分块大小
- `--overlap_size` 设置重叠大小
- 支持音频块的重叠处理和拼接

### 4. `scripts/demo_streaming.sh` - 演示脚本
一键启动完整的流式传输演示。

## 使用方法

### 方法1：使用演示脚本（推荐）

```bash
# 一键启动完整演示
./scripts/demo_streaming.sh
```

### 方法2：分别启动发送端和接收端

**步骤1：启动接收端**
```bash
python -m scripts.receiver \
    --host localhost \
    --port 8888 \
    --save_path ./output/received \
    --model_path ./model/esc9kbps_base_adversarial \
    --device cpu \
    --save_chunks
```

**步骤2：启动发送端**
```bash
python -m scripts.sender \
    --input ./data/speech_1.wav \
    --host localhost \
    --port 8888 \
    --model_path ./model/esc9kbps_base_adversarial \
    --num_streams 6 \
    --device cpu \
    --realtime
```

### 方法3：使用改进的compress脚本

```bash
# 流式压缩（本地处理）
python -m scripts.compress \
    --input ./data/speech_1.wav \
    --save_path ./output \
    --model_path ./model/esc9kbps_base_adversarial \
    --num_streams 6 \
    --device cpu \
    --streaming \
    --chunk_size 16000 \
    --overlap_size 1600
```

## 参数说明

### 通用参数
- `--model_path`: 模型文件夹路径
- `--device`: 运行设备 (cpu/cuda)
- `--num_streams`: 传输流数量 (影响压缩率)
- `--chunk_size`: 音频块大小 (样本数，默认16000=1秒@16kHz)
- `--overlap_size`: 重叠大小 (样本数，默认1600=0.1秒@16kHz)

### 发送端参数
- `--input`: 输入音频文件路径
- `--host`: 接收端地址
- `--port`: 端口号
- `--realtime`: 启用实时模式
- `--buffer_size`: socket缓冲区大小

### 接收端参数
- `--host`: 绑定地址
- `--port`: 绑定端口
- `--save_path`: 输出文件夹
- `--save_chunks`: 保存单独的音频块

## 技术特点

### 1. 流式处理
- 音频按块处理，支持长音频文件
- 内存使用效率高
- 支持实时流式传输

### 2. 重叠拼接
- 音频块间使用重叠处理
- 减少块边界的人工痕迹
- 提高音质连续性

### 3. 多线程架构
- 编码/解码与网络传输并行
- 提高处理效率
- 支持实时性能

### 4. 错误处理
- 网络连接异常处理
- 数据序列化/反序列化错误处理
- 优雅的中断处理

## 性能优化建议

1. **网络环境**：局域网环境下性能最佳
2. **硬件配置**：GPU加速可显著提升编码/解码速度
3. **参数调优**：
   - 较大的chunk_size可减少网络开销
   - 较小的overlap_size可减少计算开销
   - 根据网络带宽调整buffer_size

## 故障排除

1. **连接失败**：检查端口是否被占用
2. **音质问题**：调整overlap_size和chunk_size
3. **延迟问题**：使用--realtime参数或调整chunk_size
4. **内存不足**：减小chunk_size或队列大小

## 扩展功能

该架构支持以下扩展：
- 多客户端广播
- 音频格式转换
- 动态码率调整
- 网络自适应传输
- 音频效果处理
