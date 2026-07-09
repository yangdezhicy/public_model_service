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

你的服务器配置是 **CPU 4 核、内存 4GB、系统盘 40GB**。这个配置可以运行本地免费模型。当前默认使用 `qwen2.5:1.5b` 提升回答准确性，并通过单并发、低温度和上下文限制控制内存；如果服务器仍然 OOM，可临时降回 `qwen2.5:0.5b`。

```env
MODEL_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
MODEL_NAME=qwen2.5:1.5b
MODEL_TEMPERATURE=0.2
MODEL_MAX_TOKENS=1000
OLLAMA_NUM_CTX=4096
OLLAMA_NUM_THREAD=3
MAX_CONCURRENT_REQUESTS=1
```

这套方案的目标是：

- 优先保证 4G 内存服务器能稳定运行；
- 控制上下文长度和输出长度，降低内存占用；
- 使用 3 个推理线程，给 4 核 CPU 预留 1 核给系统、Docker 和 Web 服务；
- 单并发生成，避免多个请求同时挤爆内存；
- 40GB 系统盘足够存放当前服务和 `qwen2.5:1.5b`，但不建议同时下载太多大模型；
- 保持中文旅游问答可用，适合作为当前阶段的免费 AI 小助手。

如果后续服务器升级到 8G 或以上，可以再尝试：

```env
MODEL_NAME=qwen2.5:1.5b
MODEL_MAX_TOKENS=1200
```

如果服务器有更高内存或 GPU，再考虑 `qwen2.5:3b`、`llama3.2:3b` 等更大模型。

---

## 2. 部署到你的服务器

你的服务器对外地址建议保持为 Nginx HTTPS 代理地址：

```text
https://www.yangdezhi.com.cn
```

当前 Docker Compose 不再直接占用公网端口，而是只把 AI 服务映射到宿主机本地端口：

```text
宿主机 127.0.0.1:15326 -> 容器内部 8000
Nginx 对外使用 https://www.yangdezhi.com.cn/api -> proxy_pass http://127.0.0.1:15326
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
# 先测 Docker 映射出来的本机内网端口
curl http://127.0.0.1:15326/api/health

# 再测 Nginx 对外 HTTPS 代理地址
curl -k https://www.yangdezhi.com.cn/api/health
```

正常返回类似：

```json
{
  "ok": true,
  "service": "free-japan-travel-ai",
  "provider": "ollama",
  "model": "qwen2.5:1.5b",
  "configured": true,
  "free": true,
  "num_ctx": 4096,
  "max_tokens": 1000,
  "num_thread": 3,
  "max_concurrent_requests": 1
}
```

---

## 4. 测试普通对话

```bash
curl -k -X POST https://www.yangdezhi.com.cn/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "帮我规划东京3日游"}],
    "knowledge": "【东京景点】浅草寺、涩谷、上野公园"
  }'
```

---

## 5. 测试流式输出

```bash
curl -k -N -X POST https://www.yangdezhi.com.cn/api/chat/stream \
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
VITE_API_BASE_URL=https://www.yangdezhi.com.cn
```

所以只要当前模型服务正常启动，前端 AI 小助手就会使用这套免费的本地模型服务。

---

## 7. 如果模型回答慢怎么办

本地免费模型速度取决于服务器 CPU、内存和当前负载。你的服务器是 4 核 CPU / 4GB 内存 / 40GB 系统盘，当前默认用 `qwen2.5:1.5b` 换取更准确的回答；如负载偏高，可按下面方式降级。

建议：

1. 默认使用 `qwen2.5:1.5b`，回答明显比 0.5B 更稳定；
2. 保持 `MAX_CONCURRENT_REQUESTS=1`，不要多并发；
3. 如果回答仍然慢，可以把 `MODEL_MAX_TOKENS` 从 `1000` 降到 `700`；
4. 如果出现内存不足，建议增加 2G swap；
5. 如果仍然 OOM，再把 `MODEL_NAME` 降为 `qwen2.5:0.5b`，并把 `OLLAMA_NUM_CTX` 降为 `2048`；
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
docker compose exec ollama ollama pull qwen2.5:1.5b
```

### 8.2 前端请求失败

确认服务是否可访问：

```bash
curl -k https://www.yangdezhi.com.cn/api/health
```

确认服务器安全组 / 防火墙是否开放 `443` 端口，并确认宝塔/Nginx 已将 `/api` 反向代理到 `http://127.0.0.1:15326`。

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

### 8.4 解决 HTTPS 网页下的“Mixed Content”错误

如果你的旅游网站是通过 `https://` 访问的，而 AI 服务是 `http://`，浏览器会拦截请求。

**解决方法 A：使用域名 + Nginx（推荐）**

1.  为 AI 服务配置一个子域名（如 `api.yourdomain.com`）。
2.  在服务器上安装 Nginx 并配置 SSL 证书。
3.  在 Nginx 中配置反向代理：
    ```nginx
    server {
        listen 443 ssl;
        server_name www.yangdezhi.com.cn;
        # SSL 证书配置...
        location /api/ {
            proxy_pass http://127.0.0.1:15326;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
    ```

**解决方法 B：临时在浏览器中放行**

在浏览器地址栏右侧点击“不安全内容”图标，选择“允许”或“加载不安全的脚本”。

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
curl http://127.0.0.1:15326/api/health
```
