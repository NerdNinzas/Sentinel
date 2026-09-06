#!/bin/bash
# One-shot dev stack: backend :8000, frontend :3000, ngrok tunnel.
cd "$(dirname "$0")"
mkdir -p .logs
lsof -ti:8000 -sTCP:LISTEN | xargs -r kill; lsof -ti:3000 -sTCP:LISTEN | xargs -r kill; pkill -x ngrok 2>/dev/null; sleep 1
(cd backend && nohup uv run uvicorn main:app --port 8000 > ../.logs/backend.log 2>&1 &)
(cd frontend && nohup pnpm dev --port 3000 > ../.logs/frontend.log 2>&1 &)
nohup ngrok http --url=evaluatingly-unparcelling-andree.ngrok-free.dev 8000 --log stdout > .logs/ngrok.log 2>&1 &
echo "waiting for services…"
for i in $(seq 1 60); do curl -sf localhost:8000/health >/dev/null && curl -sf localhost:3000 >/dev/null && break; sleep 1; done
echo "backend : $(curl -s localhost:8000/health)"
echo "frontend: http://localhost:3000"
echo "tunnel  : https://evaluatingly-unparcelling-andree.ngrok-free.dev"
