import uiautomation as automation
import json
import os
import time
import sqlite3
import win32api
import win32con
import win32gui
import hashlib
import aiohttp
import asyncio
import signal
import sys
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse
from loguru import logger
from flask import Flask, request, jsonify
from flask_cors import CORS
import psutil
from dotenv import load_dotenv

def get_application_path():
    """获取应用程序路径"""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的程序
        return os.path.dirname(sys.executable)
    else:
        # 如果是开发环境
        return os.path.dirname(os.path.abspath(__file__))

# 加载环境变量
env_path = os.path.join(get_application_path(), '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
    logger.info(f"已加载环境变量配置文件: {env_path}")
    # 打印当前环境变量值，用于调试
    db_name = os.getenv('DB_NAME')
    logger.info(f"当前DB_NAME环境变量值: {db_name}")
else:
    logger.warning(f"未找到环境变量配置文件: {env_path}")

class WeChatPaymentAPI:
    """微信支付API类"""
    
    def __init__(self, db_name: str = None):
        # 从环境变量获取配置，如果环境变量不存在则使用默认值
        self.db_name = db_name or os.getenv('DB_NAME', 'wxpayments.db')
        # 确保数据库文件路径是绝对路径
        if not os.path.isabs(self.db_name):
            self.db_name = os.path.join(get_application_path(), self.db_name)
        self.app = Flask(__name__)
        self._setup_cors()
        self._setup_routes()
        self.server = None
        
    def _setup_cors(self):
        """配置CORS"""
        CORS(self.app, resources={
            r"/api/*": {
                "origins": "*",
                "methods": ["GET", "POST", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization"],
                "expose_headers": ["Content-Type", "Authorization"],
                "supports_credentials": True
            }
        })
        
    def _setup_routes(self):
        """设置路由"""
        self.app.route('/api/payment/check', methods=['GET'])(self.check_payment)
        self.app.route('/api/payment/list', methods=['GET'])(self.get_payment_list)
        self.app.route('/api/service/status', methods=['GET'])(self.check_service_status)
        
    def get_db_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn
        
    def check_payment(self):
        """检查支付状态API"""
        try:
            create_time = request.args.get('create_time')
            message = request.args.get('message')
            wechat_id = request.args.get('wechat_id')

            if not create_time:
                return jsonify({
                    'code': 400,
                    'message': '缺少必要参数 create_time'
                }), 400

            create_time = datetime.strptime(create_time, '%Y-%m-%d %H:%M:%S')
            end_time = create_time + timedelta(minutes=10)

            conn = self.get_db_connection()
            cursor = conn.cursor()

            query = '''
            SELECT * FROM payments 
            WHERE timestamp BETWEEN ? AND ?
            '''
            params = [create_time.strftime('%Y-%m-%d %H:%M:%S'), 
                     end_time.strftime('%Y-%m-%d %H:%M:%S')]

            if message:
                query += ' AND message LIKE ?'
                params.append(f'%{message}%')
            if wechat_id:
                query += ' AND sender LIKE ?'
                params.append(f'%{wechat_id}%')

            cursor.execute(query, params)
            result = cursor.fetchone()

            if result:
                payment_data = dict(result)
                return jsonify({
                    'code': 200,
                    'message': '支付成功',
                    'data': {
                        'amount': payment_data['amount'],
                        'sender': payment_data['sender'],
                        'timestamp': payment_data['timestamp'],
                        'message': payment_data['message'],
                        'remark': payment_data['remark']
                    }
                })
            else:
                return jsonify({
                    'code': 404,
                    'message': '未找到支付记录'
                })

        except Exception as e:
            return jsonify({
                'code': 500,
                'message': f'服务器错误: {str(e)}'
            }), 500
        finally:
            conn.close()
            
    def get_payment_list(self):
        """获取支付记录列表API"""
        try:
            wechat_id = request.args.get('wechat_id')
            message = request.args.get('message')
            start_time = request.args.get('start_time')
            end_time = request.args.get('end_time')
            page = int(request.args.get('page', 1))
            page_size = int(request.args.get('page_size', 20))

            offset = (page - 1) * page_size

            conn = self.get_db_connection()
            cursor = conn.cursor()

            query = 'SELECT * FROM payments WHERE 1=1'
            count_query = 'SELECT COUNT(*) as total FROM payments WHERE 1=1'
            params = []

            if wechat_id:
                query += ' AND sender LIKE ?'
                count_query += ' AND sender LIKE ?'
                params.append(f'%{wechat_id}%')
            if message:
                query += ' AND message LIKE ?'
                count_query += ' AND message LIKE ?'
                params.append(f'%{message}%')
            if start_time:
                query += ' AND timestamp >= ?'
                count_query += ' AND timestamp >= ?'
                params.append(start_time)
            if end_time:
                query += ' AND timestamp <= ?'
                count_query += ' AND timestamp <= ?'
                params.append(end_time)

            query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
            params.extend([page_size, offset])

            cursor.execute(count_query, params[:-2])
            total = cursor.fetchone()['total']

            cursor.execute(query, params)
            results = cursor.fetchall()

            payments = []
            for row in results:
                payment = dict(row)
                payments.append({
                    'amount': payment['amount'],
                    'sender': payment['sender'],
                    'timestamp': payment['timestamp'],
                    'message': payment['message'],
                    'notify_status': payment['notify_status']
                })

            return jsonify({
                'code': 200,
                'message': 'success',
                'data': {
                    'total': total,
                    'page': page,
                    'page_size': page_size,
                    'list': payments
                }
            })

        except Exception as e:
            return jsonify({
                'code': 500,
                'message': f'服务器错误: {str(e)}'
            }), 500
        finally:
            conn.close()
            
    def check_service_status(self):
        """检查微信支付监控服务状态"""
        try:
            # 检查当前进程
            current_pid = os.getpid()
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if proc.info['pid'] == current_pid:
                    return jsonify({
                        'code': 200,
                        'message': '服务进程存在',
                        'data': {
                            'status': 'process_exists',
                            'pid': current_pid
                        }
                    })
        except Exception as e:
            logger.error(f"检查服务状态时出错: {str(e)}")
            pass

        return jsonify({
            'code': 404,
            'message': '服务未运行',
            'data': {
                'status': 'stopped'
            }
        })
        
    def run(self, host: str = None, port: int = None, debug: bool = None):
        """运行API服务"""
        host = host or os.getenv('API_HOST', '0.0.0.0')
        port = port or int(os.getenv('API_PORT', '5000'))
        debug = debug if debug is not None else os.getenv('API_DEBUG', 'false').lower() == 'true'
        
        from werkzeug.serving import make_server
        self.server = make_server(host, port, self.app)
        self.server.serve_forever()
        
    def shutdown(self):
        """关闭API服务"""
        if self.server:
            self.server.shutdown()

class WeChatPaymentMonitor:
    """微信支付监控类"""
    
    def __init__(self, db_name: str = None):
        # 从环境变量获取配置，如果环境变量不存在则使用默认值
        self.db_name = db_name or os.getenv('DB_NAME', 'wxpayments.db')
        self.max_scroll_count = int(os.getenv('MAX_SCROLL_COUNT', '50'))
        self.first_run_limit = int(os.getenv('FIRST_RUN_LIMIT', '1000'))
        self.normal_run_limit = int(os.getenv('NORMAL_RUN_LIMIT', '10'))
        self.scroll_wheel_value = int(os.getenv('SCROLL_WHEEL_VALUE', '2000'))
        self.scroll_interval = float(os.getenv('SCROLL_INTERVAL', '0.1'))
        self.check_interval = int(os.getenv('CHECK_INTERVAL', '5'))
        # 运行标志
        self.running = True
        # 窗口引用
        self.wechat_window = self.get_wechat_window()
        self.payment_list = self.get_payment_list()
        
        # 配置日志
        self._setup_logger()
        # 注册信号处理器
        self._setup_signal_handlers()
            
    def _setup_logger(self):
        """配置日志"""
        logger.remove()
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="INFO",
            colorize=True
        )
        
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        if sys.platform == 'win32':
            # Windows平台使用特殊处理
            def handler(sig, hook=None):
                logger.info("正在退出，请稍候...")
                self.running = False
                self.wechat_window = None
                self.payment_list = None
                # 强制退出程序
                os._exit(0)
                return True
            win32api.SetConsoleCtrlHandler(handler, True)
        else:
            # Unix平台使用标准信号处理
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """信号处理函数"""
        logger.info("正在退出，请稍候...")
        self.running = False
        self.wechat_window = None
        self.payment_list = None
        # 强制退出程序
        os._exit(0)
        
    def get_wechat_window(self) -> Optional[automation.WindowControl]:
        """获取微信窗口"""
        try:
            window = automation.WindowControl(searchDepth=1, ClassName='ChatWnd')
            if window.Exists():
                self.wechat_window = window
                return window
            else:
                self.wechat_window = None
                logger.error("微信窗口不存在")
                self.running = False
                # 强制退出程序
                os._exit(0)
                return None
        except Exception as e:
            self.wechat_window = None
            logger.error(f"获取微信窗口失败: {str(e)}")
            self.running = False
            # 强制退出程序
            os._exit(0)
            return None
            
    def get_payment_list(self) -> Optional[automation.ListControl]:
        """获取支付消息列表"""
        try:
            list_control = self.wechat_window.ListControl(searchDepth=10, Name="消息")
            if list_control.Exists():
                self.payment_list = list_control
                return list_control
            else:
                self.payment_list = None
                logger.error("支付消息列表不存在")
                self.running = False
                return None
        except Exception as e:
            self.payment_list = None
            logger.error(f"获取支付消息列表失败: {str(e)}")
            self.running = False
            return None

    def check_windows(self) -> bool:
        """检查窗口状态"""
        if not self.wechat_window or not self.wechat_window.Exists():
            logger.error("微信支付消息窗口已关闭")
            self.running = False
            return False
            
        if not self.payment_list or not self.payment_list.Exists():
            logger.error("支付消息列表已关闭")
            self.running = False
            return False
            
        return True

    def get_all_text_controls(self, control: automation.Control) -> List[automation.Control]:
        """递归获取所有文本控件"""
        text_controls = []
        
        if control.ControlTypeName == 'TextControl':
            text_controls.append(control)
        
        for child in control.GetChildren():
            text_controls.extend(self.get_all_text_controls(child))
        
        return text_controls
        
    def extract_payment_info(self, list_item: automation.Control) -> Optional[Dict[str, str]]:
        """提取支付信息"""
        try:
            text_controls = self.get_all_text_controls(list_item)
            controls_dict = {}
            
            key_mapping = {
                "收款金额": "amount",
                "来自": "sender",
                "付款方留言": "message",
                "到账时间": "timestamp",
                "备注": "remark"
            }
            
            for i, control in enumerate(text_controls):
                name = control.Name
                if name in key_mapping:
                    if i + 1 < len(text_controls):
                        next_control = text_controls[i + 1]
                        if next_control.ControlTypeName == 'TextControl':
                            value = next_control.Name
                            if key_mapping[name] == "amount":
                                value = value.replace("￥", "")
                            controls_dict[key_mapping[name]] = value

            if all(key in controls_dict for key in ["amount", "sender", "timestamp"]):
                return controls_dict
            return None
            
        except Exception as e:
            logger.error(f"提取支付信息时出错: {str(e)}")
            return None
            
    def scroll_to_load_more(self, list_control: automation.ListControl):
        """滚动加载更多支付记录"""
        logger.info("开始滚动加载更多支付记录...")
        scroll_count = 0
        last_height = 0
        no_change_count = 0
        
        try:
            # 确保微信窗口处于活动状态
            if not self.wechat_window.Exists():
                logger.error("微信窗口不存在")
                return
                
            # 激活微信窗口
            try:
                # 使用多种方法尝试激活窗口
                self.wechat_window.SetFocus()
                self.wechat_window.SetTopmost(True)
                self.wechat_window.ShowWindow(win32con.SW_RESTORE)  # 如果窗口最小化，恢复它
                self.wechat_window.SetTopmost(False)
                
                # 使用 win32gui 发送激活消息
                hwnd = self.wechat_window.NativeWindowHandle
                if hwnd:
                    win32gui.SetForegroundWindow(hwnd)
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, 
                                        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
                    win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, 
                                        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
                
                time.sleep(0.5)  # 等待窗口激活
            except Exception as e:
                logger.error(f"激活窗口时出错: {str(e)}")
                return
            
            rect = list_control.BoundingRectangle
            center_x = (rect.left + rect.right) // 2
            center_y = (rect.top + rect.bottom) // 2
            
            # 保存当前鼠标位置
            original_pos = win32api.GetCursorPos()
            
            # 移动鼠标到列表中心
            win32api.SetCursorPos((center_x, center_y))
            time.sleep(0.1)  # 等待鼠标移动完成
            
            while scroll_count < self.max_scroll_count:
                # 再次检查窗口是否仍然存在
                if not self.wechat_window.Exists():
                    logger.error("微信窗口已关闭")
                    break
                    
                current_height = list_control.BoundingRectangle.height
                
                if current_height == last_height:
                    no_change_count += 1
                    if no_change_count >= 3:
                        break
                else:
                    no_change_count = 0
                    
                # 执行滚动
                win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, center_x, center_y, self.scroll_wheel_value, 0)
                time.sleep(self.scroll_interval)
                
                last_height = current_height
                scroll_count += 1
                
                if scroll_count % 10 == 0:
                    logger.info(f"已滚动 {scroll_count} 次...")
                    
            logger.info(f"滚动完成，共滚动 {scroll_count} 次")
            
        except Exception as e:
            logger.error(f"滚动加载更多记录时出错: {str(e)}")
        finally:
            # 恢复鼠标位置
            try:
                win32api.SetCursorPos(original_pos)
            except:
                pass
        
    def get_all_payment_records(self, is_first_run: bool = False) -> List[Dict[str, str]]:
        """获取所有支付记录"""
        start_time = time.time()
        payments = []
        new_payments = []
        
        if not hasattr(self, 'previous_records'):
            self.previous_records = []
        
        try:
            list_items = [item for item in self.payment_list.GetChildren() 
                         if item.ControlTypeName == 'ListItemControl']
            
            if is_first_run:
                self.scroll_to_load_more(self.payment_list)
                list_items = [item for item in self.payment_list.GetChildren() 
                             if item.ControlTypeName == 'ListItemControl']
                list_items = list_items[-self.first_run_limit:]
            else:
                list_items = list_items[-self.normal_run_limit:]
        
            for item in list_items:
                info = self.extract_payment_info(item)
                if info:
                    payments.append(info)
            
            # 只返回新的记录
            if not is_first_run:
                new_payments = [p for p in payments if p not in self.previous_records]
            else:
                new_payments = payments
                
            self.previous_records = payments
                    
            return new_payments
            
        except Exception as e:
            logger.error(f"获取支付记录时出错: {str(e)}")
            return []
        finally:
            end_time = time.time()
            elapsed_time = end_time - start_time
            if len(new_payments) > 0:
                logger.info(f"获取支付记录耗时: {elapsed_time:.2f} 秒，获取到 {len(new_payments)} 条新记录")

class PaymentNotifier:
    """支付通知类"""
    
    def __init__(self, notify_url: str, notify_key: str, db_name: str = None, max_retry: int = 7, concurrency: int = 10):
        self.notify_url = notify_url
        self.notify_key = notify_key
        self.db_name = db_name or os.getenv('DB_NAME', 'wxpayments.db')
        self.max_retry = max_retry
        self.concurrency = concurrency  # 增加并发数
        self.running = True
        self.task_counter = 0
        self.loader_interval = 1  # 加载器检查间隔（秒）
        
        # 重试时间间隔配置（单位：秒）
        self.retry_intervals = [0, 10, 60, 120, 3600, 7200, 21600, 54000]
        
        # 创建通知队列
        self.notify_queue = asyncio.Queue()
        
        # 初始化数据库
        self._init_database()
        
    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # 创建完整的表结构
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount TEXT NOT NULL,
            sender TEXT NOT NULL,
            message TEXT,
            timestamp TEXT NOT NULL,
            remark TEXT,
            created_at TEXT NOT NULL,
            notify_status INTEGER DEFAULT 0,
            notify_retry_count INTEGER DEFAULT 0,
            notify_url TEXT,
            notify_response TEXT,
            notify_time TEXT,
            next_retry_time TEXT,
            UNIQUE(amount, sender, timestamp)
        )
        ''')
        
        conn.commit()
        conn.close()
        
    async def task_loader(self):
        """定期加载待处理通知的任务加载器"""
        while self.running:
            try:
                await self.load_pending_notifications()
                await asyncio.sleep(self.loader_interval)
            except Exception as e:
                logger.error(f"任务加载器异常: {str(e)}")
                await asyncio.sleep(self.loader_interval)

    async def load_pending_notifications(self):
        """加载待处理的通知记录到队列"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            current_time = datetime.now()
            # 获取所有未通知或通知失败的记录，并且重试时间已到
            cursor.execute('''
            SELECT amount, sender, message, timestamp, remark, notify_retry_count, notify_time
            FROM payments
            WHERE (notify_status = 0 OR notify_status = 2)
            AND notify_retry_count < ?
            AND (
                next_retry_time IS NULL 
                OR datetime(next_retry_time) <= datetime(?)
            )
            ORDER BY created_at ASC
            LIMIT ?
            ''', (self.max_retry, current_time.strftime('%Y-%m-%d %H:%M:%S'), self.concurrency * 2))
            
            pending_payments = cursor.fetchall()
            count = 0
            
            for payment in pending_payments:
                payment_dict = {
                    'amount': payment[0],
                    'sender': payment[1],
                    'message': payment[2],
                    'timestamp': payment[3],
                    'remark': payment[4]
                }
                # 添加到通知队列
                await self.schedule_task(payment_dict, payment[5])
                count += 1
                
            if count > 0:
                logger.info(f"已加载 {count} 条待处理的通知记录")
                    
        except Exception as e:
            logger.error(f"加载待处理通知时出错: {str(e)}")
        finally:
            conn.close()

    async def process_new_payment(self, payment_data: Dict[str, str]):
        """处理新的支付记录"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # 检查是否已存在该支付记录
            cursor.execute('''
            SELECT id FROM payments 
            WHERE amount = ? AND sender = ? AND timestamp = ?
            ''', (payment_data['amount'], payment_data['sender'], payment_data['timestamp']))
            
            if not cursor.fetchone():
                # 如果不存在，插入新记录
                cursor.execute('''
                INSERT INTO payments (
                    amount, sender, message, timestamp, remark, 
                    created_at, notify_status, notify_retry_count, next_retry_time
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?)
                ''', (
                    payment_data['amount'],
                    payment_data['sender'],
                    payment_data.get('message', ''),
                    payment_data['timestamp'],
                    payment_data.get('remark', ''),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
                conn.commit() 
                logger.info(f"新支付记录已添加到数据库: {payment_data['amount']} - {payment_data['sender']} - {payment_data['timestamp']}")
                
        except Exception as e:
            logger.error(f"处理新支付记录时出错: {str(e)}")
        finally:
            conn.close()

    async def schedule_task(self, payment_data: Dict[str, str], retry_count: int = 0):
        """调度通知任务"""
        if retry_count >= self.max_retry:
            return

        # 直接添加到队列
        await self.notify_queue.put((payment_data, retry_count))
        logger.info(f"任务已调度: {payment_data['amount']} - {payment_data['sender']} - {payment_data['timestamp']} - 第{retry_count + 1}次支付通知")

    async def notify_worker(self):
        """通知工作协程"""
        async with aiohttp.ClientSession() as session:
            while self.running:
                try:
                    if self.notify_queue.empty():
                        await asyncio.sleep(1)
                        continue
                    
                    payment_data, retry_count = await self.notify_queue.get()
                    
                    try:
                        sign_str = f"{payment_data['amount']}{payment_data['sender']}{payment_data['timestamp']}{self.notify_key}"
                        sign = hashlib.md5(sign_str.encode()).hexdigest()
                        
                        notify_data = {
                            'amount': payment_data['amount'],
                            'sender': payment_data['sender'],
                            'timestamp': payment_data['timestamp'],
                            'message': payment_data.get('message', ''),
                            'remark': payment_data.get('remark', ''),
                            'sign': sign
                        }
                        
                        headers = {
                            'Content-Type': 'application/x-www-form-urlencoded'
                        }
                        
                        async with session.post(self.notify_url, data=notify_data, headers=headers, timeout=10) as response:
                            response_text = await response.text()
                            if response.status == 200 and response_text == "success":
                                await self.update_notify_status(
                                    payment_data,
                                    notify_status=1,
                                    retry_count=retry_count,
                                    response_text=response_text
                                )
                                logger.success(f"通知成功: {self.notify_url} => {payment_data['amount']} - {payment_data['sender']} - {payment_data['timestamp']}")
                            else:
                                raise Exception(f"HTTP {response.status}")
                                
                    except Exception as e:
                        # 更新通知状态
                        await self.update_notify_status(
                            payment_data,
                            notify_status=2,
                            retry_count=retry_count+1,
                            response_text=f"第{retry_count + 1 }次尝试失败: {str(e)}"
                        )
                        
                        logger.error(f"通知处理异常: {str(e)}")
                except Exception as e:
                    logger.error(f"通知工作协程异常: {str(e)}")
                    await asyncio.sleep(0.1)
                    
    async def update_notify_status(self, payment_data: Dict[str, str], notify_status: int, retry_count: int, response_text: str = ""):
        """更新通知状态"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # 计算下次重试时间
            next_retry_time = None
            if self.retry_intervals[retry_count]:
                next_retry_time = datetime.now() + timedelta(seconds=self.retry_intervals[retry_count])
            
            cursor.execute('''
            UPDATE payments 
            SET notify_status = ?,
                notify_url = ?,
                notify_response = ?,
                notify_time = ?,
                notify_retry_count = ?,
                next_retry_time = ?
            WHERE amount = ? AND sender = ? AND timestamp = ?
            ''', (
                notify_status,
                self.notify_url,
                response_text,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                retry_count,
                next_retry_time.strftime('%Y-%m-%d %H:%M:%S') if next_retry_time else None,
                payment_data['amount'],
                payment_data['sender'],
                payment_data['timestamp']
            ))
            
            conn.commit()
        except Exception as e:
            logger.error(f"更新通知状态失败: {str(e)}")
        finally:
            conn.close()
            
    async def start(self):
        """启动通知系统"""
        # 启动任务加载器
        loader_task = asyncio.create_task(self.task_loader())
        
        # 启动通知工作协程
        workers = []
        for _ in range(self.concurrency):
            worker = asyncio.create_task(self.notify_worker())
            workers.append(worker)
            
        return loader_task, workers
        
    async def stop(self, loader_task: asyncio.Task, workers: List[asyncio.Task]):
        """停止通知系统"""
        if not workers:
            return
            
        try:
            self.running = False
            loader_task.cancel()
            for worker in workers:
                worker.cancel()
            await asyncio.gather(loader_task, *workers, return_exceptions=True)
        except Exception as e:
            logger.error(f"停止通知系统时出错: {str(e)}")

async def main():
    """主函数"""
    # 创建支付监控实例
    monitor = WeChatPaymentMonitor()
    
    # 创建支付通知实例
    notify_url = os.getenv('NOTIFY_URL')
    notify_key = os.getenv('NOTIFY_KEY')
    
    if not notify_url or not notify_key:
        logger.warning("未配置通知URL或密钥，通知功能将被禁用")
        notify_url = ""
        notify_key = ""
        
    notifier = PaymentNotifier(notify_url, notify_key)
    
    # 创建API实例
    api = WeChatPaymentAPI()
    
    # 启动API服务（在新线程中运行）
    import threading
    api_thread = threading.Thread(target=api.run, daemon=True)
    api_thread.start()
    
    # 存储异步任务
    loader_task = None
    worker_tasks = []
    
    try:
        # 启动通知服务
        loader_task, worker_tasks = await notifier.start()
        
        # 主循环
        is_first_run = True
        while monitor.running:
            try:
                if not monitor.check_windows():
                    logger.error("窗口检查失败，程序将退出")
                    break
                    
                payments = monitor.get_all_payment_records(is_first_run)
                if payments:
                    for payment in payments:
                        await notifier.process_new_payment(payment)
                is_first_run = False
                
                await asyncio.sleep(monitor.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"主循环发生错误: {str(e)}")
                if "窗口" in str(e) or "不存在" in str(e):
                    logger.error("检测到窗口异常，程序将退出")
                    break
                await asyncio.sleep(1)
                
    except KeyboardInterrupt:
        logger.info("正在停止服务...")
    except Exception as e:
        logger.error(f"发生错误: {str(e)}")
    finally:
        # 设置运行标志为False
        monitor.running = False
        
        # 关闭API服务
        api.shutdown()
        
        # 停止通知服务
        if loader_task and worker_tasks:
            await notifier.stop(loader_task, worker_tasks)
            
        # 取消所有异步任务
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
            
        # 等待所有任务完成
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
        logger.info("服务已停止")
        # 强制退出程序
        os._exit(0)

if __name__ == '__main__':
    try:
        # # 设置事件循环策略
        # if sys.platform == 'win32':
        #     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        # 运行主函数
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序异常退出: {str(e)}")
    finally:
        # 确保程序完全退出
        os._exit(0)