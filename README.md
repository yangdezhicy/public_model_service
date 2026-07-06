# Public Model Service（完全免费本地模型版）

这是一套给 **Japan Travel Guide** 前端使用的免费 AI 模型服务。

默认方案：

- **不调用 OpenAI**
- **不需要 OpenAI API Key**
- **不产生第三方 API 调用费用**
- 使用你自己服务器上的 **Ollama + 开源模型**

> 注意：这里的“完全免费”指没有 OpenAI / DeepSeek / OpenRouter 等第三方 API 调用费；但会消耗你自己服务器的 CPU / 内存 / 磁盘 / 电费。

---

## 1. 默认模型

默认配置：

```env
MODEL_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
MODEL_NAME=qwen2.5:1.5b
```

`qwen2.5:1.5b` 比较轻量，适合普通服务器先跑通。如果你的服务器配置较高，可以改成：

```env
MODEL_NAME=qwen2.5:3b
```

或者：

```env
MODEL_NAME=llama3.2:3b
```

---

## 2. 部署到你的服务器

你的服务器对外地址：

```text
http://115.159.221.212:1217
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
docker compose exec ollama ollama pull qwen2.5:1.5b
```

检查模型是否存在：

```bash
docker compose exec ollama ollama list
```

---

## 3. 健康检查

```bash
curl http://115.159.221.212:1217/api/health
```

正常返回类似：

```json
{
  "ok": true,
  "service": "free-japan-travel-ai",
  "provider": "ollama",
  "model": "qwen2.5:1.5b",
  "configured": true,
  "free": true
}
```

---

## 4. 测试普通对话

```bash
curl -X POST http://115.159.221.212:1217/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "帮我规划东京3日游"}],
    "knowledge": "【东京景点】浅草寺、涩谷、上野公园"
  }'
```

---

## 5. 测试流式输出

```bash
curl -N -X POST http://115.159.221.212:1217/api/chat/stream \
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
VITE_API_BASE_URL=http://115.159.221.212:1217
```

所以只要当前模型服务正常启动，前端 AI 小助手就会使用这套免费的本地模型服务。

---

## 7. 如果模型回答慢怎么办

本地免费模型速度取决于服务器配置。

建议：

1. 先用 `qwen2.5:1.5b` 跑通；
2. 如果速度可以，再试 `qwen2.5:3b`；
3. 如果内存不足或很慢，换更小模型；
4. 如果你希望更强效果，需要更高配置服务器或 GPU。

---

## 8. 常见问题

### 8.1 返回 model not found

说明 Ollama 里还没有拉模型，执行：

```bash
docker compose exec ollama ollama pull qwen2.5:1.5b
```

### 8.2 前端请求失败

确认服务是否可访问：

```bash
curl http://115.159.221.212:1217/api/health
```

确认服务器安全组 / 防火墙是否开放 `1217` 端口。

### 8.3 想换模型

修改 `.env`：

```env
MODEL_NAME=qwen2.5:3b
```

拉取新模型：

```bash
docker compose exec ollama ollama pull qwen2.5:3b
docker compose restart public-japan-travel-ai
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

这个错误通常不是 FastAPI 版本不存在，而是服务器 Docker 构建时访问不到 PyPI，导致 pip 没拿到任何包列表。

本仓库 Dockerfile 已默认使用阿里云 PyPI 镜像：

```dockerfile
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ARG PIP_TRUSTED_HOST=mirrors.aliyun.com
```

请在服务器上拉最新代码后重新构建：

```bash
cd /www/wwwroot/public_model_service
git pull
docker compose build --no-cache
docker compose up -d
```

如果阿里云镜像仍然失败，可以切换清华源构建：

```bash
docker compose build --no-cache \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  --build-arg PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

docker compose up -d
```

也可以临时测试容器内网络：

```bash
docker run --rm python:3.11-slim python -m pip index versions fastapi -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
```

如果仍失败，优先检查：

1. 服务器 DNS 是否正常；
2. 宝塔/系统防火墙是否限制容器访问外网；
3. Docker 是否能访问外网；
4. 是否配置了不可用的 pip 源。
