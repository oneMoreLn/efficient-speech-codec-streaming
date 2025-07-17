#!/bin/bash

# 启动音频流式传输演示脚本
# 使用socket进行实时音频压缩传输

echo "=== 音频流式传输演示 ==="
echo

# 设置端口
PORT=8888

# 检查必要的文件
if [ ! -f "data/speech_1.wav" ]; then
    echo "错误: 找不到输入音频文件 data/speech_1.wav"
    exit 1
fi

if [ ! -d "model/esc9kbps_base_adversarial" ]; then
    echo "错误: 找不到模型文件夹 model/esc9kbps_base_adversarial"
    exit 1
fi

# 创建输出目录
mkdir -p output/streaming_demo

# 清理端口
echo "0. 清理端口 $PORT..."
python scripts/port_cleanup.py $PORT

echo "1. 启动接收端..."
# 在后台启动接收端
python -m scripts.receiver \
    --host localhost \
    --port $PORT \
    --save_path ./output/streaming_demo \
    --model_path ./model/esc9kbps_base_adversarial \
    --device cpu \
    --save_chunks &

# 保存接收端进程ID
RECEIVER_PID=$!

# 等待接收端启动
sleep 3

echo "2. 启动发送端..."
# 启动发送端
python -m scripts.sender \
    --input ./data/speech_1.wav \
    --host localhost \
    --port $PORT \
    --model_path ./model/esc9kbps_base_adversarial \
    --num_streams 6 \
    --device cpu \
    --chunk_size 16000 \
    --overlap_size 1600

echo "3. 传输完成，等待接收端处理..."
# 等待接收端处理完成
wait $RECEIVER_PID

echo "4. 演示完成！"
echo "输出文件保存在: ./output/streaming_demo/"
echo "包含完整重建音频和分块文件"

# 显示输出文件
echo
echo "生成的文件:"
ls -la ./output/streaming_demo/
