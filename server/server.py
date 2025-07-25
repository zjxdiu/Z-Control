import configparser
import os
import sys
import json
from functools import wraps

import requests
from flask import Flask, render_template, request, Response, jsonify, abort

template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
app = Flask(__name__, template_folder=template_dir)

# 当前版本：v12-server / 20250714-1824
# --- 配置加载 ---
def load_config():
    """仅加载服务端和安全相关的配置"""
    try:
        config = configparser.ConfigParser()
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_path, 'config.ini')
        if not os.path.exists(config_path):
            raise FileNotFoundError("配置文件 config.ini 未找到！")
        config.read(config_path, encoding='utf-8')
        return config
    except Exception as e:
        print(f"FATAL: 加载配置失败: {e}", file=sys.stderr)
        sys.exit(1)

config = load_config()
SERVER_PORT = config.getint('Server', 'port', fallback=5000)
ALLOWED_IPS_STR = config.get('Server', 'allowed_ips', fallback='127.0.0.1')
ALLOWED_IPS = [ip.strip() for ip in ALLOWED_IPS_STR.split(',')]

# 客户端列表文件的路径
CLIENTS_FILE = os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__))), 'clients.json')

# --- 客户端列表持久化 ---
def load_clients():
    """从 clients.json 加载客户端列表"""
    if not os.path.exists(CLIENTS_FILE):
        return []
    try:
        with open(CLIENTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"WARN: 读取客户端列表文件失败: {e}，将使用空列表。")
        return []

def save_clients(clients):
    """将客户端列表保存到 clients.json"""
    try:
        with open(CLIENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(clients, f, indent=4, ensure_ascii=False)
        return True
    except IOError as e:
        print(f"ERROR: 保存客户端列表文件失败: {e}")
        return False

# --- 安全认证装饰器 ---
def require_allowed_ip(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.headers.get('X-Forwarded-For'):
            client_ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
        else:
            client_ip = request.remote_addr
        if client_ip in ALLOWED_IPS:
            return f(*args, **kwargs)
        else:
            print(f"WARN: 拒绝了来自非法IP {client_ip} 的访问。")
            abort(403)
    return decorated_function

# --- 与客户端通信的辅助函数 (已重构) ---
def send_request_to_client(client_info, endpoint, method='POST', json_data=None, timeout=10):
    """
    根据传入的客户端信息动态发送请求。
    client_info: dict, 包含 'host', 'port', 'apiKey'
    """
    if not all(k in client_info for k in ['host', 'port', 'apiKey']):
        return None, (jsonify({"error": "无效的客户端配置信息。"}), 400)

    url = f"http://{client_info['host']}:{client_info['port']}{endpoint}"
    headers = {'X-API-Key': client_info['apiKey']}
    
    try:
        if method.upper() == 'POST':
            response = requests.post(url, headers=headers, json=json_data, timeout=timeout)
        else:
            response = requests.get(url, headers=headers, timeout=timeout)
        
        response.raise_for_status()
        return response, None
        
    except requests.exceptions.RequestException as e:
        error_message = f"与客户端 {client_info['host']}:{client_info['port']} 通信失败: {e}"
        print(f"ERROR: {error_message}")
        return None, (jsonify({"error": error_message}), 500)

# --- Web 页面路由 ---
@app.route('/')
@require_allowed_ip
def index():
    return render_template('index.html')

# --- 客户端管理 API ---
@app.route('/api/clients', methods=['GET'])
@require_allowed_ip
def get_clients():
    """获取所有已保存的客户端"""
    return jsonify(load_clients())

@app.route('/api/clients', methods=['POST'])
@require_allowed_ip
def save_clients_route():
    """保存整个客户端列表"""
    clients_data = request.get_json()
    if not isinstance(clients_data, list):
        return jsonify({"error": "请求体必须是一个列表。"}), 400
    if save_clients(clients_data):
        return jsonify({"message": "客户端列表已成功保存。"}), 200
    else:
        return jsonify({"error": "保存客户端列表到服务器失败。"}), 500

# --- 后端功能 API (已重构为接收客户端信息) ---
def client_action_handler(endpoint, method='POST', timeout=10, needs_payload=False, custom_logic=None):
    """通用的客户端操作处理函数，减少重复代码"""
    data = request.get_json()
    if not data or 'client' not in data:
        return jsonify({"error": "请求中缺少 'client' 信息。"}), 400
    
    client_info = data['client']
    payload = data.get('payload') if needs_payload else None

    response, error = send_request_to_client(client_info, endpoint, method=method, json_data=payload, timeout=timeout)
    
    if error:
        return error
    
    if custom_logic:
        return custom_logic(response)
    else:
        # 默认处理方式
        if 'application/json' in response.headers.get('Content-Type', ''):
             return jsonify(response.json())
        elif 'image/' in response.headers.get('Content-Type', ''):
             return Response(response.content, status=response.status_code, mimetype=response.headers['Content-Type'])
        else:
             return Response(response.text, status=response.status_code, mimetype=response.headers['Content-Type'])

@app.route('/api/check_client_status', methods=['POST'])
@require_allowed_ip
def check_client_status():
    data = request.get_json()
    if not data or 'client' not in data:
        return jsonify({"error": "请求中缺少 'client' 信息。"}), 400

    response, error = send_request_to_client(data['client'], '/api/status', method='GET', timeout=3)
    if error:
        return jsonify({"status": "offline", "error": error[0].get_json().get('error', '未知错误')})
    return jsonify({"status": "online", "client_info": response.json()})

@app.route('/api/get_screenshot', methods=['POST'])
@require_allowed_ip
def get_screenshot():
    return client_action_handler('/api/screenshot', timeout=15)

@app.route('/api/get_tasklist', methods=['POST'])
@require_allowed_ip
def get_tasklist():
    # 进程排序的自定义逻辑
    def sort_tasklist(response):
        try:
            raw_text = response.text
            lines = raw_text.strip().split('\n')
            if len(lines) < 2: return Response(raw_text, status=200, mimetype='text/plain')
            
            header_lines, process_lines = lines[:2], lines[2:]
            
            def sort_key(line):
                try: return line[33:].lower()
                except IndexError: return line.lower()

            sorted_process_lines = sorted(process_lines, key=sort_key)
            sorted_text = "\n".join(header_lines + sorted_process_lines)
            return Response(sorted_text, status=200, mimetype='text/plain; charset=utf-8')
        except Exception as e:
            print(f"ERROR: 排序进程列表时出错: {e}")
            return Response(response.text, status=200, mimetype='text/plain; charset=utf-8')

    return client_action_handler('/api/tasklist', custom_logic=sort_tasklist)


@app.route('/api/delay_shutdown', methods=['POST'])
@require_allowed_ip
def delay_shutdown():
    return client_action_handler('/api/shutdown', needs_payload=True)


if __name__ == '__main__':
    print("--- 服务端程序启动 ---")
    print(f"监听地址: 0.0.0.0:{SERVER_PORT}")
    print(f"允许访问的IP: {', '.join(ALLOWED_IPS)}")
    print(f"客户端配置将通过Web界面动态管理。")
    print(f"Web控制界面已在 http://<你的IP>:{SERVER_PORT} 上可用")

    try:
        from waitress import serve
        serve(app, host='0.0.0.0', port=SERVER_PORT)
    except ImportError:
        print("\nWARN: 未安装 waitress，使用Flask自带的开发服务器。建议安装: pip install waitress\n")
        app.run(host='0.0.0.0', port=SERVER_PORT, debug=False)
