import os
import sys
import logging
import configparser
import threading
from datetime import datetime
from functools import wraps
from io import BytesIO

from flask import Flask, request, jsonify, send_file, abort
from PIL import ImageGrab
import psutil

# --- 全局变量 ---
APP_VERSION = "1.0-silent" # silent为后台静默运行
shutdown_timer = None

# --- 初始化Flask应用 ---
app = Flask(__name__)

# --- 配置和日志 ---
def load_config():
    """加载配置文件"""
    try:
        config = configparser.ConfigParser()
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_path, 'config.ini')
        if not os.path.exists(config_path):
            raise FileNotFoundError("配置文件 config.ini 未找到！")
        # 修正问题1：明确使用UTF-8编码读取
        config.read(config_path, encoding='utf-8')
        return config
    except Exception as e:
        logging.error(f"加载配置失败: {e}")
        sys.exit(1)

def setup_logging():
    """设置日志记录"""
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_filename = os.path.join(log_dir, f"{datetime.now().strftime('%Y%m%d')}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

# --- 加载配置 ---
config = load_config()
CLIENT_PORT = config.getint('Client', 'port', fallback=5001)
API_KEY = config.get('Security', 'api_key', fallback=None)

# 在日志设置之后再执行检查，确保能记录错误
setup_logging()

if not API_KEY or API_KEY == 'ChangeMeToARandomSecretKey-ABC123!@#':
    logging.error("安全警告：API Key未设置或使用了默认值，请修改config.ini！")
    sys.exit(1)

# --- 认证装饰器 ---
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.headers.get('X-API-Key') and request.headers.get('X-API-Key') == API_KEY:
            return f(*args, **kwargs)
        else:
            logging.warning(f"拒绝了来自 {request.remote_addr} 的未授权访问。")
            abort(401)
    return decorated_function

# --- 核心功能函数 ---
def execute_shutdown(delay_seconds):
    """使用系统命令执行关机。"""
    try:
        if sys.platform == "win32":
            if delay_seconds == -1:
                os.system('shutdown /a')
                logging.info("已发送取消关机命令。")
                return {"status": "shutdown_cancelled", "message": "关机计划已取消。"}
            else:
                os.system('shutdown /a') 
                command = f'shutdown /s /t {delay_seconds}'
                os.system(command)
                logging.info(f"已设置关机计划，延迟 {delay_seconds} 秒。")
                if delay_seconds == 0:
                     return {"status": "shutdown_immediate", "message": "立即关机指令已发送。"}
                return {"status": "shutdown_scheduled", "delay": delay_seconds, "message": f"关机计划已设置，将在 {delay_seconds} 秒后执行。"}
        else: # For Linux/macOS
            if delay_seconds == -1:
                os.system('sudo shutdown -c')
                logging.info("已发送取消关机命令。")
                return {"status": "shutdown_cancelled", "message": "关机计划已取消。"}
            else:
                 delay_minutes = max(1, round(delay_seconds / 60))
                 os.system(f'sudo shutdown -h +{delay_minutes}')
                 logging.info(f"已设置关机计划，延迟 {delay_minutes} 分钟。")
                 return {"status": "shutdown_scheduled", "delay": delay_seconds, "message": f"关机计划已设置，将在约 {delay_minutes} 分钟后执行。"}

    except Exception as e:
        logging.error(f"执行关机命令失败: {e}")
        return {"status": "error", "message": str(e)}

# --- API 端点 (Endpoints) ---

@app.route('/api/status', methods=['GET'])
@require_api_key
def get_status():
    return jsonify({"status": "ok", "version": APP_VERSION})

@app.route('/api/screenshot', methods=['POST'])
@require_api_key
def api_screenshot():
    logging.info(f"收到来自 {request.remote_addr} 的截图请求。")
    try:
        screenshot = ImageGrab.grab()
        img_buffer = BytesIO()
        screenshot.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        logging.info("截图成功。")
        return send_file(img_buffer, mimetype='image/png')
    except Exception as e:
        logging.error(f"截图失败: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/tasklist', methods=['POST'])
@require_api_key
def api_tasklist():
    logging.info(f"收到来自 {request.remote_addr} 的进程列表请求。")
    try:
        proc_list = []
        for proc in psutil.process_iter(['pid', 'name', 'username']):
            try:
                if proc.info['username'] is not None:
                    proc_list.append(
                        f"{proc.info['pid']:<8} {proc.info.get('username', 'N/A'):<25} {proc.info.get('name', 'N/A')}"
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        header = f"{'PID':<8} {'USERNAME':<25} {'PROCESS NAME'}\n" + "-"*60 + "\n"
        response_text = header + "\n".join(proc_list)
        logging.info("获取进程列表成功。")
        return response_text, 200, {'Content-Type': 'text/plain; charset=utf-8'}
    except Exception as e:
        logging.error(f"获取进程列表失败: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/shutdown', methods=['POST'])
@require_api_key
def api_shutdown():
    logging.info(f"收到来自 {request.remote_addr} 的关机请求。")
    data = request.get_json()
    if not data or 'delay' not in data:
        return jsonify({"error": "缺少 'delay' 参数。"}), 400
    
    try:
        delay = int(data['delay'])
        result = execute_shutdown(delay)
        return jsonify(result)
    except ValueError:
        return jsonify({"error": "'delay' 必须是整数。"}), 400
    except Exception as e:
        logging.error(f"处理关机请求失败: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    logging.info(f"--- 客户端程序启动 (v{APP_VERSION}) ---")
    logging.info(f"监听地址: 0.0.0.0:{CLIENT_PORT}")
    logging.info("等待服务端指令...")
    try:
        from waitress import serve
        serve(app, host='0.0.0.0', port=CLIENT_PORT)
    except ImportError:
        logging.warning("未安装 waitress，使用Flask自带的开发服务器。建议安装: pip install waitress")
        app.run(host='0.0.0.0', port=CLIENT_PORT)
