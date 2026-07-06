# Public Model Service（自有服务器可部署版）

这是给 **Japan Travel Guide** 前端配套的公共可用模型服务，目标是：
- 不依赖 Aime / 内部 llmproxy；
- 可部署到你自己的云服务器 / VPS / Docker 主机；
- 兼容 **OpenAI-compatible** 模型接口；
- 保留现有前端所需的两个接口：
  - `POST /api/chat`
  - `POST /api/chat/stream`

> 也就是说，只要你的模型供应商支持 OpenAI 风格的 `/chat/completions`，这套服务就能直接接入。

---

## 1. 支持什么模型平台

这套服务默认支持所有 **OpenAI-compatible** 平台，例如：
- OpenAI
- OpenRouter
- DeepSeek
- 火山方舟（若你有公网可用 endpoint）
- Kimi / GLM / SiliconFlow / 其他兼容 OpenAI 协议的平台

核心只需要 3 个参数：
- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `MODEL_NAME`

---

## 2. 目录说明

- `main.py`：FastAPI 服务主程序
- `requirements.txt`：Python 依赖
- `.env.example`：环境变量示例
- `Dockerfile`：Docker 镜像构建文件
- `docker-compose.yml`：Docker Compose 启动方式

---

## 3. 本地/服务器部署方式

### 方式 A：直接 Python 运行

```bash
cd public_model_service
cp .env.example .env
# 按需修改 .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

启动后默认监听：

```bash
http://0.0.0.0:8000
```

可用接口：
- `GET /api/health`
- `POST /api/chat`
- `POST /api/chat/stream`

---

### 方式 B：Docker 部署（推荐）

```bash
cd public_model_service
cp .env.example .env
# 修改 .env
docker compose up -d --build
```

查看日志：

```bash
docker compose logs -f
```

---

## 4. 环境变量配置

### OpenAI 官方

```env
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-xxxxxxxx
MODEL_NAME=gpt-4o-mini
```

### DeepSeek

```env
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_API_KEY=sk-xxxxxxxx
MODEL_NAME=deepseek-chat
```

### OpenRouter

```env
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_API_KEY=sk-or-xxxxxxxx
MODEL_NAME=openai/gpt-4o-mini
OPENAI_EXTRA_HEADERS={"HTTP-Referer":"https://your-site.com","X-Title":"Japan Travel Guide"}
```

### 其他兼容平台

```env
OPENAI_BASE_URL=https://your-provider.com/v1
OPENAI_API_KEY=your-key
MODEL_NAME=your-model-name
```

---

## 5. 前端如何改成用你自己的服务器

`react-app` 已经支持通过环境变量覆盖 AI 后端地址。

在前端项目根目录创建：

```env
VITE_API_BASE_URL=http://你的服务器IP或域名:8000
```

例如：

```env
VITE_API_BASE_URL=https://ai.yourdomain.com
```

然后重新构建前端：

```bash
cd react-app
npm install
npm run build
```

---

## 6. 反向代理（建议）

如果你要公网访问，建议在服务器前面加 Nginx / Caddy，并配 HTTPS。

例如把：
- `https://ai.yourdomain.com` → 转发到 `http://127.0.0.1:8000`

这样前端就可以安全调用。

---

## 7. 安全建议

1. **不要把 `.env` 提交到 GitHub**。
2. 建议限制 `CORS_ALLOW_ORIGINS`，不要长期使用 `*`。
3. 如果你的服务会被公网访问，建议增加：
   - 请求频控
   - 鉴权（如 API Token / JWT）
   - 日志脱敏
   - 异常告警
4. 如果前端只给自己用，可仅开放给指定域名。

---

## 8. 健康检查与测试

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
```

普通对话：

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "帮我规划东京3日游"}],
    "knowledge": "【东京景点】浅草寺、涩谷、上野公园"
  }'
```

流式对话：

```bash
curl -N -X POST http://127.0.0.1:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "帮我规划东京3日游"}],
    "knowledge": "【东京景点】浅草寺、涩谷、上野公园"
  }'
```

---

## 9. 与当前项目的关系

- `react-app`：前端
- `public_model_service`：你自己的公网/私有云模型服务
- 前端只需要配置 `VITE_API_BASE_URL` 指向你的服务即可

这样你就可以把整套系统完整部署到自己的服务器，而不依赖当前 Aime 内部模型代理。
