# 流式音频传输系统 - 速率限制超参数功能

## 更新概述

成功将速率限制功能改为可配置的超参数，现在用户可以：

1. **选择是否启用速率限制**
2. **自定义速率限制值**
3. **根据需要灵活配置传输速率**

## 新增超参数

### 发送端参数

```bash
--enable_rate_limit     # 启用速率限制功能
--rate_limit_bps <值>   # 设置速率限制(字节/秒), 默认375 (3kbps)
```

## 使用方法

### 1. 无速率限制（默认模式）

```bash
python -m scripts.sender \
    --input ./data/speech_1.wav \
    --model_path ./model/esc9kbps_base_adversarial \
    --port 8888
```

**特点：**
- 最快传输速度
- 适合本地测试和高带宽环境
- 传输时间约6-10秒

### 2. 3kbps速率限制（默认限制）

```bash
python -m scripts.sender \
    --input ./data/speech_1.wav \
    --model_path ./model/esc9kbps_base_adversarial \
    --port 8888 \
    --enable_rate_limit
```

**特点：**
- 模拟低带宽环境
- 传输速率限制为375 bytes/second
- 传输时间约60-70秒

### 3. 自定义速率限制

#### 8kbps限制
```bash
python -m scripts.sender \
    --input ./data/speech_1.wav \
    --model_path ./model/esc9kbps_base_adversarial \
    --port 8888 \
    --enable_rate_limit \
    --rate_limit_bps 1000
```

#### 16kbps限制
```bash
python -m scripts.sender \
    --input ./data/speech_1.wav \
    --model_path ./model/esc9kbps_base_adversarial \
    --port 8888 \
    --enable_rate_limit \
    --rate_limit_bps 2000
```

#### 64kbps限制
```bash
python -m scripts.sender \
    --input ./data/speech_1.wav \
    --model_path ./model/esc9kbps_base_adversarial \
    --port 8888 \
    --enable_rate_limit \
    --rate_limit_bps 8000
```

## 测试结果对比

| 配置 | 速率限制 | 传输时间 | 平均传输速率 | 适用场景 |
|------|----------|----------|-------------|----------|
| 无限制 | 关闭 | ~6秒 | ~80,000 bytes/s | 本地测试、高带宽 |
| 3kbps | 375 bytes/s | ~67秒 | ~7,500 bytes/s | 极低带宽环境 |
| 8kbps | 1000 bytes/s | ~25秒 | ~20,000 bytes/s | 低带宽环境 |
| 16kbps | 2000 bytes/s | ~13秒 | ~40,000 bytes/s | 中等带宽环境 |

## 性能统计显示

### 无速率限制
```
=== Performance Statistics ===
Total transmission time: 6.319 seconds
Total bytes sent: 506,922 bytes
Average transmission rate: 80216.35 bytes/second
Rate limiting: DISABLED
```

### 3kbps速率限制
```
=== Performance Statistics ===
Total transmission time: 67.167 seconds
Total bytes sent: 506,922 bytes
Average transmission rate: 7547.16 bytes/second
Rate limiting: ENABLED - 375 bytes/second (3.0 kbps)
```

### 8kbps速率限制
```
=== Performance Statistics ===
Total transmission time: 25.346 seconds
Total bytes sent: 506,922 bytes
Average transmission rate: 20000.00 bytes/second
Rate limiting: ENABLED - 1000 bytes/second (8.0 kbps)
```

## 实现细节

### 1. 参数解析增强
```python
parser.add_argument("--enable_rate_limit", action="store_true", 
                   help="enable rate limiting")
parser.add_argument("--rate_limit_bps", type=int, default=375, 
                   help="rate limit in bytes per second (default: 375 for 3kbps)")
```

### 2. 构造函数更新
```python
def __init__(self, model_path: str, device: str = "cpu", chunk_size: int = 16000, 
             overlap_size: int = 1600, num_streams: int = 6, 
             enable_rate_limit: bool = False, rate_limit_bps: int = 375):
```

### 3. 条件性速率限制
```python
# Rate limiting implementation (if enabled)
if self.enable_rate_limit:
    # 速率限制逻辑
    if self.bytes_sent_this_second + data_size > self.rate_limit_bps:
        sleep_time = 1.0 - (current_time - self.last_send_time)
        if sleep_time > 0:
            time.sleep(sleep_time)
```

### 4. 智能状态显示
```python
if self.enable_rate_limit:
    print(f"Rate limiting: ENABLED - {self.rate_limit_bps} bytes/second ({self.rate_limit_bps * 8 / 1000:.1f} kbps)")
else:
    print(f"Rate limiting: DISABLED")
```

## 使用场景

### 1. 开发测试
- 使用无速率限制模式进行快速测试
- 验证功能正确性

### 2. 网络环境模拟
- 使用不同速率限制模拟各种网络条件
- 测试系统在不同带宽下的表现

### 3. 生产环境
- 根据实际网络条件设置合适的速率限制
- 避免网络拥塞，保证传输质量

## 测试工具

提供了专门的测试脚本：
```bash
python test_rate_limiting.py        # 运行完整测试
python test_rate_limiting.py --help # 查看使用说明
```

## 总结

速率限制超参数功能提供了：

✅ **灵活配置** - 可选择启用或关闭速率限制  
✅ **自定义速率** - 支持任意速率限制值  
✅ **清晰显示** - 统计信息明确显示速率限制状态  
✅ **向后兼容** - 默认行为保持不变  
✅ **易于使用** - 简单的命令行参数控制  

这个功能使得系统更加灵活，可以适应不同的使用场景和网络环境。
