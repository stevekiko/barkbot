# 🔔 BarkBot

Telegram Bot，通过 [Bark](https://github.com/Finb/Bark) 向 iOS 设备推送通知。适用于远程团队管理场景，在 Telegram 群组中 @成员 即可一键推送 Bark 通知到对方手机。

## 功能特性

- **三级通知**
  - 📢 普通 — 标准通知提醒
  - ⚡ 优先 — 突破专注/勿扰模式（timeSensitive）
  - 🚨 紧急 — 绕过静音，最大音量持续响铃（critical）
- **群组交互** — 在群组中 @成员，弹出按钮选择通知级别
- **紧急通知二次确认** — 防止误触打扰他人休息，休息时段（22:00-08:00）额外提醒
- **管理面板** — 私聊 Bot 通过按钮管理成员（添加/修改/删除/测试推送）
- **管理员通知** — 每次紧急推送自动通知管理员，记录发送人、目标、群组、时间
- **群组白名单** — 可限制 Bot 只在指定群组生效
- **全局错误处理** — 异常不会导致 Bot 崩溃，自动通知管理员错误详情
- **Docker 一键部署** — 支持崩溃自动重启

## 项目结构

```
barkbot/
├── bot.py              # 入口，注册 handler 和全局错误处理
├── config.py           # 读取 .env 配置
├── database.py         # SQLite 数据库操作
├── bark.py             # Bark 推送 API 调用
├── handlers/
│   ├── start.py        # /start 命令和主菜单
│   ├── admin.py        # 成员管理（增删改查、测试推送）
│   └── notify.py       # 群组 @提醒 和推送回调
├── Dockerfile
├── docker-compose.yml
├── deploy.sh           # 一键部署脚本
├── requirements.txt
├── .env.example
└── .dockerignore
```

## 部署

### 前置条件

- 一台 Linux 服务器（装有 Docker 和 Docker Compose）
- 一个 Telegram Bot Token（通过 [@BotFather](https://t.me/BotFather) 创建）
- 你的 Telegram User ID（通过 [@userinfobot](https://t.me/userinfobot) 获取）

### 步骤

**1. 上传项目到服务器**

```bash
scp -r ./barkbot root@你的服务器IP:/root/barkbot
```

**2. 配置环境变量**

```bash
cd /root/barkbot
cp .env.example .env
nano .env
```

```env
# Telegram Bot Token
BOT_TOKEN=你的Bot Token

# 管理员 Telegram User ID（多个用逗号分隔）
ADMIN_IDS=123456789

# 允许的群组 ID（留空则不限制，多个用逗号分隔）
# 把 Bot 加入群组后发消息，查看日志获取群组 ID
ALLOWED_GROUPS=
```

**3. 一键启动**

```bash
bash deploy.sh
```

### 常用命令

```bash
cd /root/barkbot

# 查看日志
docker compose logs -f

# 重启
docker compose restart

# 停止
docker compose down

# 更新代码后重新部署
docker compose up -d --build
```

## 使用方法

### 管理面板（私聊 Bot）

1. 私聊 Bot 发送 `/start` 打开管理面板
2. 点击「➕ 添加成员」，按提示输入：
   - Telegram 用户名（不含 @）
   - 显示名称
   - Bark Key（在 Bark App 中获取）
3. 添加完成后可在「📋 成员列表」中管理

### 群组推送

1. 将 Bot 添加到群组
2. 在群组中 @已注册的成员，Bot 会弹出通知级别按钮
3. 点击按钮即可推送（紧急通知需二次确认）

### 获取群组 ID

将 Bot 加入群组后，在群里随便发条消息，通过 `docker compose logs -f` 查看日志中输出的群组 ID。

## Bark 通知级别详情

| 级别 | Bark level | 效果 | 参数 |
|------|-----------|------|------|
| 📢 普通 | active | 正常通知 | — |
| ⚡ 优先 | timeSensitive | 突破专注模式 | sound: multiwayinvitation |
| 🚨 紧急 | critical | 绕过静音，最大音量响铃 | volume: 10, call: 1, sound: alarm |

## 技术栈

- Python 3.11
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) 20.x
- [httpx](https://github.com/encode/httpx) — 异步 HTTP 请求
- SQLite — 数据存储
- Docker — 容器化部署
