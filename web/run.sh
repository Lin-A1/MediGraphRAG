#!/bin/bash

# 进入工作目录
cd "$(dirname "$0")/.."

# 定义颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== 医学试题生成系统启动！ ===${NC}"

# 启动后端API服务
echo -e "${YELLOW}正在启动后端API服务...${NC}"
uvicorn web.api.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo -e "${GREEN}后端API服务已启动 (PID: $BACKEND_PID)${NC}"

# 等待一下确保后端启动
sleep 2

# 启动前端服务
echo -e "${YELLOW}正在启动前端服务...${NC}"
cd web/frontend
npm install
npm run dev &
FRONTEND_PID=$!
echo -e "${GREEN}前端服务已启动 (PID: $FRONTEND_PID)${NC}"

# 注册清理函数
cleanup() {
    echo -e "${YELLOW}正在关闭服务...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo -e "${GREEN}服务已关闭${NC}"
    exit 0
}

# 捕获终止信号
trap cleanup SIGINT SIGTERM

echo -e "${GREEN}所有服务已启动${NC}"
echo -e "${YELLOW}后端API地址: http://localhost:8000${NC}"
echo -e "${YELLOW}前端页面地址: 请查看上方前端启动信息${NC}"
echo -e "${YELLOW}按 Ctrl+C 停止所有服务${NC}"

# 保持脚本运行
wait