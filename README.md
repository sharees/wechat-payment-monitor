# WeChat Payment Monitor

微信版本要求:3.9x

一个基于 Python 的微信赞助码支付监控工具，可以自动监控微信赞助码支付消息并发送通知。

通过监听微信支付窗口的消息内容实现支付回调 ,不会产生任何风控。安全无风险！

## 功能特点

- 🔍 自动监控微信支付消息
- 💰 支持赞赏码支付监控
- 📝 支持支付留言识别
- 🔔 支持自定义通知回调
- 📊 提供 Web API 接口
- 💾 本地 SQLite 数据库存储
- 🔄 支持失败重试机制
- 🎯 支持多线程并发处理

## 系统要求

- Windows 10 或更高版本
- Python 3.8 或更高版本
- 微信 PC 版

## 安装步骤

1. 克隆仓库：
```bash
git clone https://github.com/yourusername/wechat-payment-monitor.git
cd wechat-payment-monitor
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置环境变量：
创建 `.env` 文件并配置以下参数：
```env
# 数据库配置
DB_NAME=wxpayments.db

# API 配置
API_HOST=0.0.0.0
API_PORT=5000
API_DEBUG=false

# 通知配置
NOTIFY_URL=你的通知回调地址
NOTIFY_KEY=你的通知密钥

# 监控配置
MAX_SCROLL_COUNT=50
FIRST_RUN_LIMIT=1000
NORMAL_RUN_LIMIT=10
SCROLL_WHEEL_VALUE=2000
SCROLL_INTERVAL=0.1
CHECK_INTERVAL=5
```

## 使用方法

### 开发环境运行

1. 确保微信已登录并打开支付消息窗口
2. 运行程序：
```bash
python main.py
```

### 打包运行

1. 打包程序：
```bash
python build.py
```

2. 在 `dist` 目录下找到 `WeChatPay.exe`
3. 将 `.env` 文件复制到 `WeChatPay.exe` 同目录
4. 双击运行 `WeChatPay.exe`

## API 接口

### 检查支付状态
```
GET /api/payment/check
参数：
- create_time: 创建时间（必填）
- message: 支付留言
- wechat_id: 微信ID
```

### 获取支付记录
```
GET /api/payment/list
参数：
- wechat_id: 微信ID
- message: 支付留言
- start_time: 开始时间
- end_time: 结束时间
- page: 页码
- page_size: 每页数量
```

### 检查服务状态
```
GET /api/service/status
```

## 注意事项

1. 运行前请确保微信已登录并打开支付消息窗口
2. 程序需要管理员权限才能正常操作微信窗口
3. 建议使用虚拟环境运行程序
4. 请妥善保管 `.env` 文件中的密钥信息

## 常见问题

1. **程序无法启动**
   - 检查是否以管理员权限运行
   - 检查微信是否已登录
   - 检查支付消息窗口是否打开

2. **无法监控到支付消息**
   - 检查微信窗口是否被遮挡
   - 检查支付消息窗口是否正常显示
   - 检查环境变量配置是否正确

3. **通知回调失败**
   - 检查网络连接
   - 检查通知 URL 是否正确
   - 检查通知密钥是否正确

## 贡献指南

欢迎提交 Issue 和 Pull Request！

## 免责声明

本项目仅供个人学习和研究使用，禁止用于任何商业用途。使用本项目产生的任何后果由使用者自行承担。

### 使用限制

1. 本项目仅供个人测试和学习使用
2. 禁止用于任何商业用途
3. 禁止用于任何违法用途
4. 禁止用于任何可能对微信账号造成风险的行为

### 免责条款

1. 本项目不对使用者的任何行为负责
2. 使用者应当遵守相关法律法规
3. 使用者应当遵守微信的使用条款
4. 因使用本项目导致的任何损失由使用者自行承担
5. 因使用本项目导致的任何账号风险由使用者自行承担
6. 因使用本项目导致的任何法律风险由使用者自行承担


### 版权声明

本项目采用 MIT 许可证，但附加以下限制：

1. 禁止用于任何商业用途
2. 禁止用于任何违法用途
3. 禁止用于任何可能对微信账号造成风险的行为





