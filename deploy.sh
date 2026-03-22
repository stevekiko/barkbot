#!/bin/bash
set -e

cd /root/barkbot

echo "🔔 BarkBot 一键部署"
echo "===================="

# Check .env
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  已创建 .env 文件，请先编辑配置："
    echo "    nano /root/barkbot/.env"
    echo ""
    echo "配置完成后重新运行: bash deploy.sh"
    exit 1
fi

# Create data dir
mkdir -p data

# Build and start
echo "📦 构建镜像..."
docker compose up -d --build

echo ""
echo "✅ 部署完成！"
echo ""
echo "常用命令："
echo "  cd /root/barkbot"
echo "  查看日志:  docker compose logs -f"
echo "  重启:      docker compose restart"
echo "  停止:      docker compose down"
echo "  更新重部署: docker compose up -d --build"
