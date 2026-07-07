# Public Model Service（完全免费本地模型版）

这是一套给 **Japan Travel Guide** 前端使用的免费 AI 模型服务。

默认方案：

- **不调用 OpenAI**
- **不需要 OpenAI API Key**
- **不产生第三方 API 调用费用**
- 使用你自己服务器上的 **Ollama + 开源模型**

> 注意：这里的“完全免费”指没有 OpenAI / DeepSeek / OpenRouter 等第三方 API 调用费；但会消耗你自己服务器的 CPU / 内存 / 磁盘 / 电费。

---

## 1. 默认模型（4 核 CPU / 4GB 内存 / 40GB 系统盘方案）

你的服务器配置是 **CPU 4 核、内存 4GB、系统盘 40GB**。这个配置可以运行本地免费模型，但不适合直接跑 3B/7B 级别模型；推荐先用 0.5B 小模型保证稳定在线。

```env
MODEL_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
MODEL_NAME=qwen2.5:0.5b
MODEL_TEMPERATURE=0.35
MODEL_MAX_TOKENS=800
OLLAMA_NUM_CTX=2048
OLLAMA_NUM_THREAD=3
MAX_CONCURRENT_REQUESTS=1
```

这套方案的目标是：

- 优先保证 4G 内存服务器能稳定运行；
- 控制上下文长度和输出长度，降低内存占用；
- 使用 3 个推理线程，给 4 核 CPU 预留 1 核给系统、Docker 和 Web 服务；
- 单并发生成，避免多个请求同时挤爆内存；
- 40GB 系统盘足够存放当前服务和 `qwen2.5:0.5b`，但不建议同时下载太多大模型；
- 保持中文旅游问答可用，适合作为当前阶段的免费 AI 小助手。

如果后续服务器升级到 8G 或以上，可以再尝试：

```env
MODEL_NAME=qwen2.5:1.5b
MODEL_MAX_TOKENS=1200
```

如果服务器有更高内存或 GPU，再考虑 `qwen2.5:3b`、`llama3.2:3b` 等更大模型。

---

## 2. 部署到你的服务器

你的服务器对外地址：

```text
http://115.159.221.212:8888
```

在服务器执行：

```bash
git clone https://github.com/yangdezhicy/public_model_service.git
cd public_model_service
cp .env.example .env
docker compose up -d --build
```

首次启动后，需要拉取免费模型：

```bash
docker compose exec ollama ollama pull qwen2.5:0.5b
```

检查模型是否存在：

```bash
docker compose exec ollama ollama list
```

---

## 3. 健康检查

```bash
curl http://115.159.221.212:8888/api/health
```

正常返回类似：

```json
{
  "ok": true,
  "service": "free-japan-travel-ai",
  "provider": "ollama",
  "model": "qwen2.5:0.5b",
  "configured": true,
  "free": true,
  "num_ctx": 2048,
  "max_tokens": 800,
  "num_thread": 3,
  "max_concurrent_requests": 1
}
```

---

## 4. 测试普通对话

```bash
curl -X POST http://115.159.221.212:8888/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "帮我规划东京3日游"}],
    "knowledge": "【东京景点】浅草寺、涩谷、上野公园"
  }'
```

---

## 5. 测试流式输出

```bash
curl -N -X POST http://115.159.221.212:8888/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "帮我规划东京3日游"}],
    "knowledge": "【东京景点】浅草寺、涩谷、上野公园"
  }'
```

如果看到一段段：

```text
data: {"delta":"..."}
```

说明流式接口正常。

---

## 6. 前端接入

你的页面仓库 `Japan-Travel-Guide` 已经配置为默认请求：

```env
VITE_API_BASE_URL=http://115.159.221.212:8888
```

所以只要当前模型服务正常启动，前端 AI 小助手就会使用这套免费的本地模型服务。

---

## 7. 如果模型回答慢怎么办

本地免费模型速度取决于服务器 CPU、内存和当前负载。你的服务器是 4 核 CPU / 4GB 内存 / 40GB 系统盘，建议先不要追求大模型参数量，先保证稳定可用。

建议：

1. 默认使用 `qwen2.5:0.5b`；
2. 保持 `MAX_CONCURRENT_REQUESTS=1`，不要多并发；
3. 如果回答仍然慢，可以把 `MODEL_MAX_TOKENS` 从 `800` 降到 `500`；
4. 如果出现内存不足，建议增加 2G swap；
5. 如果未来升级到 8G 内存，再尝试 `qwen2.5:1.5b`；
6. 40GB 系统盘不要同时保留多个大模型，避免磁盘被模型文件占满。

4GB 内存服务器可选增加 swap：

```bash
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

---

## 8. 常见问题

### 8.1 返回 model not found

说明 Ollama 里还没有拉模型，执行：

```bash
docker compose exec ollama ollama pull qwen2.5:0.5b
```

### 8.2 前端请求失败

确认服务是否可访问：

```bash
curl http://115.159.221.212:8888/api/health
```

确认服务器安全组 / 防火墙是否开放 `8888` 端口。

### 8.3 想换模型

4GB 内存服务器不建议直接换大模型。如果你已经确认内存余量充足，可以修改 `.env`：

```env
MODEL_NAME=qwen2.5:1.5b
MODEL_MAX_TOKENS=1200
```

拉取新模型并重启服务：

```bash
docker compose exec ollama ollama pull qwen2.5:1.5b
docker compose restart public-japan-travel-ai
```

如果出现卡顿、超时或容器重启，把 `.env` 改回：

```env
MODEL_NAME=qwen2.5:0.5b
MODEL_MAX_TOKENS=800
OLLAMA_NUM_CTX=2048
OLLAMA_NUM_THREAD=3
MAX_CONCURRENT_REQUESTS=1
```

---

## 9. 可选：以后切回付费模型

如果以后想切回 OpenAI-compatible，只需要改 `.env`：

```env
MODEL_PROVIDER=openai-compatible
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-xxxx
MODEL_NAME=gpt-4o-mini
```

然后重启：

```bash
docker compose restart public-japan-travel-ai
```

---

## 10. Docker 构建时报 `Could not find a version that satisfies the requirement fastapi==0.115.0`

这个错误通常是旧版本镜像还在执行 `pip install`，但当前最新版本已经移除了 FastAPI / requests / pydantic 依赖，Docker 构建不会再安装任何 pip 包。

请在服务器上拉最新代码后重新构建：

```bash
cd /www/wwwroot/public_model_service
git pull
docker compose build --no-cache
docker compose up -d
```

如果仍然看到 `fastapi==0.115.0`，说明服务器目录里的代码不是最新版本，或者宝塔使用了旧缓存。请确认 `Dockerfile` 内容应类似：

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY main.py ./
EXPOSE 8000
CMD ["python", "main.py"]
```

---

## 11. 彻底解决 pip / FastAPI 安装失败

如果你曾遇到：

```text
Could not find a version that satisfies the requirement fastapi==0.115.0
```

最新版本已经彻底移除了 FastAPI / requests / pydantic 依赖，服务改为 Python 标准库实现：

- 不执行 `pip install`
- 不依赖 PyPI
- 不会再因为 FastAPI 下载失败导致 Docker 构建失败

请在服务器重新拉代码并无缓存构建：

```bash
cd /www/wwwroot/public_model_service
git pull
docker compose build --no-cache
docker compose up -d
```

然后检查：

```bash
curl http://127.0.0.1:8888/api/health
```
