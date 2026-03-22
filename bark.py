import logging

import httpx

logger = logging.getLogger(__name__)

LEVELS = {
    1: {
        "title": "消息提醒",
        "body": "你有一条新消息待查看",
        "level": "active",
    },
    2: {
        "title": "重要提醒",
        "body": "你有一条重要消息，请尽快查看",
        "level": "timeSensitive",
        "sound": "multiwayinvitation",
    },
    3: {
        "title": "紧急通知",
        "body": "有紧急事项需要你立即处理！",
        "level": "critical",
        "volume": 10,
        "call": "1",
        "sound": "alarm",
    },
}

LEVEL_LABELS = {
    1: "📢 普通",
    2: "⚡ 优先",
    3: "🚨 紧急",
}


async def push(bark_server: str, bark_key: str, level: int) -> bool:
    params = LEVELS.get(level, LEVELS[1])
    url = f"{bark_server.rstrip('/')}/{bark_key}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=params)
            return resp.status_code == 200
    except Exception as e:
        logger.error(f"Bark 推送异常: {e}")
        return False
