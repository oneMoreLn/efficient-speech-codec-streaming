# 麦克风流式传输功能使用说明

## 功能概述

本功能实现了从麦克风实时采集音频数据，并通过ESC（Efficient Speech Codec）进行编码和流式传输的能力。

## 主要特性

- **16kHz采样率**：固定采样率确保音频质量
- **低延迟**：实时音频处理和传输
- **可配置速率限制**：支持带宽控制
- **设备选择**：可选择特定的音频输入设备
- **性能监控**：实时统计传输性能
- **优雅中断**：支持Ctrl+C优雅停止

## 安装依赖

### 1. 系统依赖
```bash
# Ubuntu/Debian
sudo apt-get install -y portaudio19-dev

# CentOS/RHEL
sudo yum install portaudio-devel

# macOS
brew install portaudio
```

### 2. Python依赖
```bash
# 推荐使用conda
conda run -n esc conda install -c conda-forge pyaudio

# 或者使用pip（需要先安装系统依赖）
conda run -n esc pip install pyaudio
```

## 使用方法

### 1. 列出音频设备
```bash
python -m scripts.sender --list_devices --model_path ./model/esc9kbps_base_adversarial
```

### 2. 基本麦克风流式传输
```bash
# 启动接收端
python -m scripts.receiver --model_path ./model/esc9kbps_base_adversarial --port 8999

# 启动发送端（麦克风）
python -m scripts.sender --microphone --model_path ./model/esc9kbps_base_adversarial --port 8999
```

### 3. 指定音频设备
```bash
python -m scripts.sender --microphone --mic_device 1 --model_path ./model/esc9kbps_base_adversarial --port 8999
```

### 4. 带速率限制的传输
```bash
python -m scripts.sender --microphone --enable_rate_limit --rate_limit_bps 3000 --model_path ./model/esc9kbps_base_adversarial --port 8999
```

### 5. 完整参数示例
```bash
python -m scripts.sender \\
    --microphone \\
    --mic_device 0 \\
    --enable_rate_limit \\
    --rate_limit_bps 9000 \\
    --model_path ./model/esc9kbps_base_adversarial \\
    --host localhost \\
    --port 8999
```

## 命令行参数说明

### 发送端参数
- `--microphone`: 启用麦克风输入模式
- `--mic_device`: 指定麦克风设备ID（默认使用系统默认设备）
- `--list_devices`: 列出所有可用的音频输入设备
- `--enable_rate_limit`: 启用速率限制
- `--rate_limit_bps`: 设置速率限制（bps，默认3000）
- `--model_path`: ESC模型路径
- `--host`: 服务器地址（默认localhost）
- `--port`: 服务器端口（默认8999）

### 接收端参数
- `--model_path`: ESC模型路径
- `--port`: 监听端口（默认8999）
- `--save_path`: 音频保存路径（可选）

## 性能监控

程序会实时显示以下统计信息：
- 处理的音频块数量
- 传输数据量
- 编码时间
- 传输时间
- 解码时间
- 平均传输速率

## 故障排除

### 1. PyAudio导入错误
```bash
# 确保安装了系统依赖
sudo apt-get install -y portaudio19-dev

# 重新安装PyAudio
conda run -n esc conda install -c conda-forge pyaudio
```

### 2. 音频设备问题
- 使用`--list_devices`查看可用设备
- 在虚拟环境中可能没有音频设备，这是正常的
- 在有音频硬件的系统上测试

### 3. 权限问题
```bash
# 确保用户有音频设备权限
sudo usermod -a -G audio $USER
```

### 4. 速率限制问题
- 检查网络带宽是否足够
- 调整`--rate_limit_bps`参数
- 监控CPU使用率

## 技术原理

### 音频采集流程
1. **初始化**：配置PyAudio，设置16kHz采样率
2. **音频采集**：从麦克风实时读取音频数据
3. **数据处理**：转换为PyTorch张量格式
4. **编码**：使用ESC模型进行音频编码
5. **传输**：通过Socket发送编码数据
6. **速率控制**：根据配置限制传输速率

### 关键组件
- **MicrophoneStreamer**: 麦克风音频采集类
- **AudioStreamingSender**: 音频流发送器
- **性能统计**: 实时监控传输性能
- **速率限制**: 可配置的带宽控制

## 测试脚本

使用提供的测试脚本：
```bash
python test_microphone.py
```

该脚本会：
1. 检查依赖安装
2. 列出音频设备
3. 执行多种配置的测试
4. 生成测试报告

## 注意事项

1. **环境要求**：需要有音频硬件的系统
2. **权限**：确保有音频设备访问权限
3. **网络**：确保网络连接正常
4. **资源**：实时音频处理需要较多CPU资源
5. **延迟**：网络延迟会影响实时性

## 最佳实践

1. **设备选择**：使用质量好的麦克风设备
2. **网络环境**：在稳定的网络环境中使用
3. **性能优化**：根据系统性能调整参数
4. **错误处理**：监控日志输出，及时处理错误
5. **资源管理**：合理设置速率限制，避免资源耗尽

## 开发者信息

- 支持的音频格式：16kHz单声道PCM
- 编码器：ESC（Efficient Speech Codec）
- 传输协议：TCP Socket
- 依赖库：PyAudio, PyTorch, NumPy

如有问题，请查看日志输出或联系开发者。
