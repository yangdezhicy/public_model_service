import json
import os
from typing import Dict, List, Optional

import requests
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # noqa: BLE001
    pass


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


SERVICE_NAME = os.environ.get("SERVICE_NAME") or "public-japan-travel-ai"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
MODEL_NAME = os.environ.get("MODEL_NAME") or "gpt-4o-mini"
MODEL_PROVIDER = os.environ.get("MODEL_PROVIDER") or "openai-compatible"
MODEL_TEMPERATURE = float(os.environ.get("MODEL_TEMPERATURE") or "0.4")
MODEL_MAX_TOKENS = int(os.environ.get("MODEL_MAX_TOKENS") or "3000")
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT") or "60")
STREAM_TIMEOUT = int(os.environ.get("STREAM_TIMEOUT") or "90")
CORS_ALLOW_ORIGINS = _split_csv(os.environ.get("CORS_ALLOW_ORIGINS") or "*")
EXTRA_HEADERS_RAW = os.environ.get("OPENAI_EXTRA_HEADERS") or "{}"

try:
    OPENAI_EXTRA_HEADERS: Dict[str, str] = json.loads(EXTRA_HEADERS_RAW)
    if not isinstance(OPENAI_EXTRA_HEADERS, dict):
        OPENAI_EXTRA_HEADERS = {}
except Exception:  # noqa: BLE001
    OPENAI_EXTRA_HEADERS = {}

SYSTEM_PROMPT = (
    "你是『日本旅游 AI 小助手』，服务于一个中文日本旅游攻略网站。\n"
    "你必须始终使用简体中文回答。\n"
    "优先依据调用方提供的【站内资料】回答；涉及价格、地址、营业时间、店铺、景点等具体信息时，禁止编造。\n"
    "如果资料不足，可以补充常识，但必须明确区分『资料已给出』和『通用建议』。\n"
    "你的回答应条理清晰、可执行、适合真实出行决策。"
)

app = FastAPI(title="Public Japan Travel AI Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    knowledge: Optional[str] = ""


@app.get("/")
def index_handler():
    return {
        "service": SERVICE_NAME,
        "status": "ok",
        "provider": MODEL_PROVIDER,
        "model": MODEL_NAME,
        "openai_base_url": OPENAI_BASE_URL,
    }


@app.get("/api/health")
def health_handler():
    return {
        "ok": True,
        "service": SERVICE_NAME,
        "provider": MODEL_PROVIDER,
        "model": MODEL_NAME,
        "configured": bool(OPENAI_API_KEY and OPENAI_BASE_URL),
    }


def _build_system_prompt(knowledge: str) -> str:
    if knowledge:
        return SYSTEM_PROMPT + "\n\n【站内资料】\n" + knowledge
    return SYSTEM_PROMPT


def _build_payload(req: ChatRequest) -> dict:
    history = [m for m in req.messages if m.role in ("user", "assistant")][-12:]
    payload_messages = [{"role": "system", "content": _build_system_prompt(req.knowledge or "")}]
    for msg in history:
        payload_messages.append({"role": msg.role, "content": msg.content})
    return {
        "model": MODEL_NAME,
        "messages": payload_messages,
        "temperature": MODEL_TEMPERATURE,
        "max_tokens": MODEL_MAX_TOKENS,
    }


def _base_headers() -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    for key, value in OPENAI_EXTRA_HEADERS.items():
        headers[str(key)] = str(value)
    return headers


@app.post("/api/chat")
def chat_handler(req: ChatRequest):
    if not OPENAI_API_KEY or not OPENAI_BASE_URL:
        return {"ok": False, "error": "模型服务未配置", "reply": ""}

    payload = _build_payload(req)
    try:
        resp = requests.post(
            OPENAI_BASE_URL + "/chat/completions",
            headers=_base_headers(),
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not reply:
            return {"ok": False, "error": "空响应", "reply": ""}
        return {"ok": True, "reply": reply}
    except requests.exceptions.RequestException as exc:
        return {"ok": False, "error": "模型调用失败: " + str(exc), "reply": ""}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "服务异常: " + str(exc), "reply": ""}


@app.post("/api/chat/stream")
def chat_stream_handler(req: ChatRequest):
    def event_stream():
        if not OPENAI_API_KEY or not OPENAI_BASE_URL:
            yield "data: " + json.dumps({"error": "模型服务未配置"}, ensure_ascii=False) + "\n\n"
            yield "data: " + json.dumps({"done": True}) + "\n\n"
            return

        payload = _build_payload(req)
        payload["stream"] = True
        try:
            with requests.post(
                OPENAI_BASE_URL + "/chat/completions",
                headers={**_base_headers(), "Accept": "text/event-stream"},
                json=payload,
                timeout=STREAM_TIMEOUT,
                stream=True,
            ) as resp:
                resp.raise_for_status()
                resp.encoding = "utf-8"
                got_any = False
                for raw in resp.iter_lines(decode_unicode=True):
                    if not raw:
                        continue
                    line = raw.strip()
                    if not line.startswith("data:"):
                        continue
                    chunk = line[len("data:"):].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        obj = json.loads(chunk)
                    except Exception:  # noqa: BLE001
                        continue
                    delta = (obj.get("choices", [{}])[0].get("delta", {}) or {}).get("content", "")
                    if delta:
                        got_any = True
                        yield "data: " + json.dumps({"delta": delta}, ensure_ascii=False) + "\n\n"
                if not got_any:
                    yield "data: " + json.dumps({"error": "空响应"}, ensure_ascii=False) + "\n\n"
        except requests.exceptions.RequestException as exc:
            yield "data: " + json.dumps({"error": "模型调用失败: " + str(exc)}, ensure_ascii=False) + "\n\n"
        except Exception as exc:  # noqa: BLE001
            yield "data: " + json.dumps({"error": "服务异常: " + str(exc)}, ensure_ascii=False) + "\n\n"
        yield "data: " + json.dumps({"done": True}) + "\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
