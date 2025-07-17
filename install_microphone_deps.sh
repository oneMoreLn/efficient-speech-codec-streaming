#!/bin/bash
# 麦克风流式传输依赖安装脚本

echo "=== 安装麦克风流式传输依赖 ==="

# 检查conda环境
if ! command -v conda &> /dev/null; then
    echo "❌ conda 未安装或不在PATH中"
    exit 1
fi

# 检查esc环境
if ! conda env list | grep -q "esc"; then
    echo "❌ conda环境 'esc' 不存在"
    echo "请先创建conda环境: conda create -n esc python=3.10"
    exit 1
fi

echo "✅ 找到conda环境: esc"

# 激活环境并安装依赖
echo "正在安装PyAudio..."
conda run -n esc pip install pyaudio

echo "正在安装其他音频处理依赖..."
conda run -n esc pip install numpy torch torchaudio

echo "检查安装结果..."
conda run -n esc python -c "
import pyaudio
import numpy as np
import torch
import torchaudio
print('✅ 所有依赖已成功安装')
print(f'PyAudio版本: {pyaudio.__version__}')
print(f'NumPy版本: {np.__version__}')
print(f'PyTorch版本: {torch.__version__}')
print(f'TorchAudio版本: {torchaudio.__version__}')
"

if [ $? -eq 0 ]; then
    echo "🎉 依赖安装完成！"
    echo
    echo "使用说明:"
    echo "1. 测试麦克风功能: python test_microphone.py"
    echo "2. 显示使用说明: python test_microphone.py --help"
    echo "3. 列出音频设备: python -m scripts.sender --list_devices --model_path ./model/esc9kbps_base_adversarial"
    echo "4. 开始麦克风流式传输: python -m scripts.sender --microphone --model_path ./model/esc9kbps_base_adversarial"
else
    echo "❌ 依赖安装失败"
fi
