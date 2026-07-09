# Public Model Service（LangChain + SiliconFlow 版）

这是一套给 **Japan Travel Guide** 前端使用的 AI 模型服务。当前版本默认使用 **LangChain + SiliconFlow OpenAI-compatible API**，不再依赖本机 Ollama 推理，因此不会持续占用服务器 CPU / 内存跑本地模型。

前端 API 契约保持不变：

```text
https://www.yangdezhi.com.cn/api/health
https://www.yangdezhi.com.cn/api/chat
https://www.yangdezhi.com.cn/api/chat/stream
```

## 1. 默认方案

```env
MODEL_PROVIDER=siliconflow
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
OPENAI_API_KEY=你的_SiliconFlow_API_Key
MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
MODEL_TEMPERATURE=0.2
MODEL_MAX_TOKENS=900
MAX_CONCURRENT_REQUESTS=2
```

如果 SiliconFlow 控制台提供了其他免费模型，也可以把 `MODEL_NAME` 改成控制台显示的模型名。

## 2. 部署到服务器

```bash
git clone https://github.com/yangdezhicy/public_model_service.git
cd public_model_service
cp .env.example .env
vim .env
```

请至少填写：

```env
OPENAI_API_KEY=你的_SiliconFlow_API_Key
```

然后启动：

```bash
docker compose up -d --build
```

当前 Docker Compose 只启动 `public-japan-travel-ai` 一个容器，不再启动 Ollama。

## 3. 如果之前跑过 Ollama

切换到 SiliconFlow 后，可以停止旧 Ollama 容器释放资源：

```bash
cd /www/wwwroot/public_model_service
docker compose stop ollama 2>/dev/null || true
docker rm public-japan-travel-ollama 2>/dev/null || true
```

如果你确定不再本地跑模型，也可以后续清理旧模型数据卷，但清理前建议先确认没有其他项目依赖 Ollama。

## 4. 健康检查

先测本机端口：

```bash
curl http://127.0.0.1:15326/api/health
```

正常返回类似：

```json
{
  "ok": true,
  "service": "japan-travel-ai",
  "provider": "siliconflow",
  "model": "Qwen/Qwen2.5-7B-Instruct",
  "configured": true,
  "base_url": "https://api.siliconflow.cn/v1"
}
```

再测域名代理：

```bash
curl https://www.yangdezhi.com.cn/api/health
```

## 5. 测试普通对话

```bash
curl -X POST https://www.yangdezhi.com.cn/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "帮我规划东京3日游"}],
    "knowledge": "【东京景点】浅草寺、涩谷、上野公园"
  }'
```

正常会返回：

```json
{
  "ok": true,
  "reply": "...",
  "provider": "siliconflow",
  "model": "Qwen/Qwen2.5-7B-Instruct"
}
```

## 6. 测试流式输出

```bash
curl -N -X POST https://www.yangdezhi.com.cn/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "帮我规划东京3日游"}],
    "knowledge": "【东京景点】浅草寺、涩谷、上野公园"
  }'
```

如果看到一段段输出：

```text
data: {"delta":"..."}

data: {"done":true}
```

说明 LangChain + SiliconFlow 流式接口正常。

## 7. Nginx 反向代理建议

`www.yangdezhi.com.cn` 的 443 站点中建议配置：

```nginx
location ^~ /api/ {
    proxy_pass http://127.0.0.1:15326;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
    send_timeout 300s;
}
```

保存后执行：

```bash
nginx -t && nginx -s reload
```

## 8. 常见问题

### 8.1 health 显示 configured=false

说明 `.env` 中没有配置 `OPENAI_API_KEY`，或容器没有读取到最新 `.env`。修改后执行：

```bash
docker compose up -d --build
```

### 8.2 模型调用失败

先看后端日志：

```bash
docker compose logs -f public-japan-travel-ai
```

常见原因包括 API Key 错误、SiliconFlow 账户额度不足、模型名不存在、网络访问 SiliconFlow 失败。

### 8.3 报 `'ascii' codec can't encode characters`

这个错误通常说明 `.env` 里的 `OPENAI_API_KEY` 仍然是中文占位符，或者密钥中混入了中文、空格等非法字符。请确认配置类似：

```env
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
```

不要写成：

```env
OPENAI_API_KEY=你的_SiliconFlow_API_Key
OPENAI_API_KEY=请填写你的_SiliconFlow_API_Key
```

修改后重新启动：

```bash
docker compose up -d --build
```

### 8.4 想换模型

在 `.env` 修改：

```env
MODEL_NAME=SiliconFlow 控制台中的模型名
```

然后重启：

```bash
docker compose restart public-japan-travel-ai
```
