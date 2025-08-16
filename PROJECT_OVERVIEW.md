# 项目概览 | Project Overview

## 🎯 项目简介

**Efficient Speech Codec (ESC)** 是一个基于跨尺度残差向量量化Transformer的高效语音编解码器。本项目在原始研究基础上，扩展了实时语音处理、麦克风输入和流式传输功能。

## 🚀 核心功能

### 原始ESC功能
- **高效压缩**: 在1.5-9 kbps比特率下实现高质量语音编解码
- **多比特率支持**: 支持1.5, 3, 4.5, 6, 7.5, 9 kbps比特率
- **轻量化模型**: 仅30MB模型大小
- **高质量重建**: 与Descript音频编解码器相当的重建质量

### 🆕 新增功能
- **实时语音处理**: 基于队列的实时音频编解码管道
- **麦克风输入**: 支持从麦克风实时录制和处理音频
- **流式传输**: 低延迟音频流处理
- **音频保存**: 处理后的音频自动保存为WAV格式
- **性能监控**: 实时性能统计和队列状态监控
- **可配置参数**: 灵活的编码质量和性能配置

## 📁 项目架构

```
efficient-speech-codec/
│
├── 🔬 core/                     # 核心ESC实现
│   ├── esc/                     # ESC模型代码
│   ├── scripts/                 # 训练和评估脚本
│   └── configs/                 # 模型配置文件
│
├── 🎤 voice_processing/          # 实时语音处理
│   ├── voice_process.py         # 核心语音处理模块
│   ├── simple_voice_test.py     # 简单使用示例
│   └── test_voice_process.py    # 综合测试框架
│
├── 🧪 testing/                  # 测试套件
│   ├── test_streaming.py        # 流式传输测试
│   ├── test_microphone.py       # 麦克风输入测试
│   ├── test_audio_save.py       # 音频保存测试
│   └── test_*.py               # 其他专项测试
│
├── 📚 documentation/            # 文档
│   ├── README.md               # 主要文档
│   ├── VOICE_PROCESS_TEST_REPORT.md
│   ├── STREAMING_README.md
│   ├── MICROPHONE_USAGE.md
│   └── NUM_STREAMS_USAGE.md
│
├── 🎵 assets/                   # 资源文件
│   ├── data/                   # 示例音频
│   ├── model/                  # 预训练模型
│   └── output/                 # 输出结果
│
└── 🔧 setup/                    # 安装配置
    ├── requirements.txt         # Python依赖
    ├── install.sh              # 自动安装脚本
    └── example.ipynb           # Jupyter示例
```

## 🔄 工作流程

### 1. 基础音频编解码
```
音频文件 → ESC编码器 → 压缩数据 → ESC解码器 → 重建音频
```

### 2. 实时语音处理
```
麦克风 → 音频捕获 → 音频块 → 编码队列 → ESC处理 → 解码队列 → 输出音频
```

### 3. 流式传输
```
发送端: 音频输入 → 编码 → 数据包 → 传输队列
接收端: 传输队列 → 数据包重组 → 解码 → 音频输出
```

## 📊 技术参数

### 音频参数
- **采样率**: 4096 Hz (自动重采样)
- **声道**: 单声道 (立体声自动转换)
- **位深**: 16-bit PCM
- **块大小**: 1024样本 (250ms @ 4096Hz)
- **编码周期**: 5秒
- **数据包大小**: 2088字节

### 性能参数
- **延迟**: < 500ms (实时处理)
- **比特率**: 1.5-9 kbps (可配置)
- **质量**: 接近原始音频质量
- **内存**: 低内存占用，队列管理
- **CPU**: 支持CPU和GPU加速

## 🎛️ 配置选项

### VoiceProcessor参数
```python
VoiceProcessor(
    model_path="model/esc9kbps_base_adversarial",  # 模型路径
    device="cpu",                                  # 计算设备
    num_streams=6                                  # 编码流数量(1-9)
)
```

### num_streams影响
| 数值 | 质量 | 性能 | 适用场景 |
|------|------|------|----------|
| 1-2  | 基础 | 最快 | 实时应用，资源受限 |
| 3-4  | 良好 | 较快 | 平衡应用 |
| 5-6  | 优秀 | 中等 | 推荐设置 |
| 7-9  | 最佳 | 较慢 | 高质量要求 |

## 🧩 核心组件

### 1. VoiceProcessor
- **功能**: 核心语音处理引擎
- **特性**: 多线程、队列管理、实时处理
- **接口**: 简单易用的Python API

### 2. AudioTester
- **功能**: 综合测试框架
- **特性**: 麦克风输入、文件处理、性能分析
- **用途**: 功能验证和性能测试

### 3. 流式处理组件
- **sender.py**: 音频发送端
- **receiver.py**: 音频接收端
- **stream_compress.py**: 流式压缩

### 4. 测试组件
- **test_*.py**: 各种专项测试
- **monitoring**: 实时性能监控
- **validation**: 结果验证

## 🔧 开发指南

### 环境搭建
```bash
# 自动安装
./install.sh

# 手动安装
conda create -n esc python=3.10
conda activate esc
pip install -r requirements.txt
```

### 快速开始
```bash
# 基础测试
python simple_voice_test.py

# 麦克风测试  
python test_microphone.py

# 流式测试
python test_streaming.py
```

### 自定义开发
```python
# 集成到您的项目
from voice_process import VoiceProcessor

processor = VoiceProcessor()
# 您的代码...
```

## 📈 性能指标

### 编解码质量
- **PESQ分数**: > 3.0
- **Mel距离**: 最小化
- **SI-SDR**: 高信噪比
- **比特率利用率**: 优化

### 实时性能
- **处理延迟**: < 250ms
- **吞吐量**: 实时处理
- **资源占用**: 低CPU/内存
- **稳定性**: 长时间稳定运行

## 🎯 应用场景

### 1. 实时通信
- 语音通话
- 视频会议
- 实时聊天

### 2. 音频处理
- 音频压缩
- 语音增强
- 音质优化

### 3. 研究开发
- 语音编解码研究
- 算法性能分析
- 原型验证

### 4. 产品集成
- 嵌入式系统
- 移动应用
- 服务器端处理

## 🤝 贡献指南

1. **Fork** 项目仓库
2. **创建** 功能分支
3. **提交** 您的更改
4. **测试** 确保功能正常
5. **提交** Pull Request

## 📞 支持与反馈

- **Issues**: 在GitHub上提交问题
- **文档**: 查看详细文档
- **示例**: 参考provided examples
- **社区**: 参与开源社区讨论

---

**Efficient Speech Codec** - 让高质量语音处理变得简单高效！
