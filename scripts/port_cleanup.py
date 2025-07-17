#!/usr/bin/env python3
"""
端口清理工具 - 用于清理被占用的端口
"""

import socket
import subprocess
import sys
import time
import signal
import os

def check_port_available(host, port):
    """检查端口是否可用"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex((host, port))
        sock.close()
        return result != 0  # 如果连接失败，说明端口可用
    except:
        return True

def find_process_using_port(port):
    """找到占用端口的进程"""
    try:
        # 使用netstat查找占用端口的进程
        result = subprocess.run(['netstat', '-tlnp'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        for line in lines:
            if f':{port}' in line and 'LISTEN' in line:
                parts = line.split()
                if len(parts) >= 7:
                    process_info = parts[6]
                    if '/' in process_info:
                        pid = process_info.split('/')[0]
                        if pid.isdigit():
                            return int(pid)
    except:
        pass
    
    # 备用方法：使用lsof
    try:
        result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().split('\n')[0])
    except:
        pass
    
    return None

def kill_process_using_port(port):
    """杀死占用端口的进程"""
    pid = find_process_using_port(port)
    if pid:
        try:
            print(f"Found process {pid} using port {port}")
            os.kill(pid, signal.SIGTERM)
            time.sleep(1)
            
            # 检查进程是否还活着
            try:
                os.kill(pid, 0)
                print(f"Process {pid} still alive, using SIGKILL")
                os.kill(pid, signal.SIGKILL)
                time.sleep(1)
            except OSError:
                pass
            
            print(f"Process {pid} terminated")
            return True
        except OSError as e:
            print(f"Failed to kill process {pid}: {e}")
            return False
    return False

def wait_for_port_available(host, port, timeout=10):
    """等待端口变为可用"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if check_port_available(host, port):
            return True
        time.sleep(0.5)
    return False

def cleanup_port(host, port):
    """清理端口"""
    if check_port_available(host, port):
        print(f"Port {port} is already available")
        return True
    
    print(f"Port {port} is in use, attempting to free it...")
    
    # 尝试杀死占用端口的进程
    if kill_process_using_port(port):
        # 等待端口释放
        if wait_for_port_available(host, port):
            print(f"Port {port} is now available")
            return True
        else:
            print(f"Port {port} is still not available after cleanup")
            return False
    else:
        print(f"Could not find or kill process using port {port}")
        return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python port_cleanup.py <port>")
        sys.exit(1)
    
    port = int(sys.argv[1])
    host = "localhost"
    
    success = cleanup_port(host, port)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
