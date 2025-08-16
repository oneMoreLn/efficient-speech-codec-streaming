#!/bin/bash

# ESC项目安装脚本
# Efficient Speech Codec Setup Script

set -e  # 遇到错误时退出

echo "🚀 开始安装 Efficient Speech Codec 环境..."

# 检查Python版本
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ 需要 Python 3.8 或更高版本，当前版本: $python_version"
    exit 1
fi

echo "✅ Python 版本检查通过: $python_version"

# 检查conda是否可用
if command -v conda &> /dev/null; then
    echo "🐍 使用 Conda 创建环境..."
    
    # 创建conda环境
    echo "📦 创建 conda 环境 'esc'..."
    conda create -n esc python=3.10 -y
    
    echo "🔄 激活环境..."
    eval "$(conda shell.bash hook)"
    conda activate esc
    
    echo "✅ Conda 环境 'esc' 创建完成"
else
    echo "🐍 Conda 不可用，使用 pip 和 venv..."
    
    # 创建虚拟环境
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
    source venv/bin/activate
    
    echo "✅ Python 虚拟环境创建完成"
fi

# 升级pip
echo "⬆️ 升级 pip..."
pip install --upgrade pip

# 安装核心依赖
echo "📦 安装核心依赖..."
pip install -r requirements.txt

# 检查是否需要安装PyAudio
echo ""
echo "🎤 是否需要麦克风支持? (y/N): "
read -r install_pyaudio

if [[ $install_pyaudio =~ ^[Yy]$ ]]; then
    echo "🎧 安装 PyAudio (麦克风支持)..."
    
    # 检测操作系统并安装相应依赖
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "🐧 检测到 Linux 系统"
        echo "请先安装系统依赖: sudo apt-get install portaudio19-dev python3-pyaudio"
        echo "然后运行: pip install pyaudio"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "🍎 检测到 macOS 系统"
        if command -v brew &> /dev/null; then
            echo "📦 使用 Homebrew 安装 portaudio..."
            brew install portaudio
            pip install pyaudio
        else
            echo "请先安装 Homebrew，然后运行: brew install portaudio && pip install pyaudio"
        fi
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        echo "🪟 检测到 Windows 系统"
        pip install pipwin
        pipwin install pyaudio
    else
        echo "⚠️ 未知操作系统，请手动安装 PyAudio"
        echo "参考: https://pyaudio.readthedocs.io/en/latest/installation.html"
    fi
else
    echo "⏭️ 跳过 PyAudio 安装（可稍后手动安装以支持麦克风功能）"
fi

# 检查模型文件
echo ""
echo "📁 检查模型文件..."
if [ -d "model/esc9kbps_base_adversarial" ]; then
    echo "✅ 找到预训练模型: model/esc9kbps_base_adversarial"
else
    echo "⚠️ 未找到预训练模型"
    echo "请下载模型文件到 model/ 目录"
    echo "参考 README.md 中的 Model Checkpoints 部分"
fi

# 创建输出目录
echo "📂 创建输出目录..."
mkdir -p output
mkdir -p output/test_streaming
mkdir -p output/test_microphone_save

# 运行快速测试
echo ""
echo "🧪 运行快速测试..."
python -c "
try:
    from voice_process import VoiceProcessor
    import torch
    print('✅ VoiceProcessor 导入成功')
    
    if torch.cuda.is_available():
        print(f'✅ CUDA 可用: {torch.cuda.get_device_name(0)}')
    else:
        print('ℹ️ CUDA 不可用，将使用 CPU')
        
    print('✅ 核心组件测试通过')
except Exception as e:
    print(f'❌ 测试失败: {e}')
    exit(1)
"

echo ""
echo "🎉 安装完成！"
echo ""
echo "📖 使用指南:"
echo "1. 基础测试: python simple_voice_test.py"
echo "2. 文件处理: python simple_voice_test.py input.wav output.wav"
echo "3. 质量测试: python simple_voice_test.py streams"
echo "4. 麦克风测试: python test_microphone.py"
echo "5. 流式测试: python test_streaming.py"
echo ""
echo "📚 详细文档请查看 README.md"

# 提示激活环境
if command -v conda &> /dev/null; then
    echo ""
    echo "🔄 要使用项目，请先激活环境:"
    echo "   conda activate esc"
else
    echo ""
    echo "🔄 要使用项目，请先激活环境:"
    echo "   source venv/bin/activate"
fi
