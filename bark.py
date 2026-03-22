"""
Bark 推送模块 — 封装 Bark API 调用

Bark 通知级别：
  - active:        普通通知
  - timeSensitive: 时效性通知，可突破专注/勿扰模式
  - critical:      紧急通知，可绕过静音，最大音量响铃
"""

import logging

import httpx

logger = logging.getLogger(__name__)

# 三级通知参数配置
# 每个级别对应不同的 Bark API 参数
LEVELS = {
    # 级别 1：普通通知
    1: {
        "title": "消息提醒",
        "body": "你有一条新消息待查看",
        "level": "active",
    },
    # 级别 2：优先通知 — 突破专注模式
    2: {
        "title": "重要提醒",
        "body": "你有一条重要消息，请尽快查看",
        "level": "timeSensitive",
        "sound": "multiwayinvitation",
    },
    # 级别 3：紧急通知 — 绕过静音，最大音量，持续响铃
    3: {
        "title": "紧急通知",
        "body": "有紧急事项需要你立即处理！",
        "level": "critical",
        "volume": 10,       # 音量最大（0-10）
        "call": "1",         # 持续响铃（类似来电）
        "sound": "alarm",    # 闹钟铃声
    },
}

# 通知级别的中文标签（用于界面展示）
LEVEL_LABELS = {
    1: "📢 普通",
    2: "⚡ 优先",
    3: "🚨 紧急",
}


async def push(bark_server: str, bark_key: str, level: int) -> bool:
    """
    向指定 Bark 设备发送推送通知

    参数:
        bark_server: Bark 服务器地址（如 https://api.day.app）
        bark_key:    设备的 Bark Key
        level:       通知级别（1=普通, 2=优先, 3=紧急）

    返回:
        True 推送成功，False 推送失败
    """
    params = LEVELS.get(level, LEVELS[1])
    url = f"{bark_server.rstrip('/')}/{bark_key}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=params)
            return resp.status_code == 200
    except Exception as e:
        logger.error(f"Bark 推送异常: {e}")
        return False
