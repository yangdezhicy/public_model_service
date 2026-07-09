import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import BoundedSemaphore
from typing import Any, Dict, List, Tuple

from langchain_openai import ChatOpenAI


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(',') if item.strip()]


def _load_dotenv(path: str = '.env') -> None:
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-8') as file:
        for raw in file:
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

SERVICE_NAME = os.environ.get('SERVICE_NAME') or 'japan-travel-ai'
MODEL_PROVIDER = (os.environ.get('MODEL_PROVIDER') or 'siliconflow').lower()
MODEL_NAME = os.environ.get('MODEL_NAME') or 'Qwen/Qwen2.5-7B-Instruct'
MODEL_TEMPERATURE = float(os.environ.get('MODEL_TEMPERATURE') or '0.2')
MODEL_MAX_TOKENS = int(os.environ.get('MODEL_MAX_TOKENS') or '900')
MAX_CONCURRENT_REQUESTS = int(os.environ.get('MAX_CONCURRENT_REQUESTS') or '2')
REQUEST_TIMEOUT = int(os.environ.get('REQUEST_TIMEOUT') or '120')
HOST = os.environ.get('HOST') or '0.0.0.0'
PORT = int(os.environ.get('PORT') or '8000')
CORS_ALLOW_ORIGINS = _split_csv(os.environ.get('CORS_ALLOW_ORIGINS') or '*')
OPENAI_BASE_URL = (os.environ.get('OPENAI_BASE_URL') or 'https://api.siliconflow.cn/v1').rstrip('/')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY') or ''
MODEL_SEMAPHORE = BoundedSemaphore(max(1, MAX_CONCURRENT_REQUESTS))

SYSTEM_PROMPT = (
    '你是「日本旅游 AI 小助手」，服务于一个中文日本旅游攻略网站。你必须始终使用简体中文回答。\n'
    '回答优先级：1) 调用方提供的【站内资料】；2) 稳定通用旅行常识；3) 若资料不足，明确说“站内资料暂未覆盖”。\n'
    '涉及价格、地址、营业时间、店铺、票券、签证、退税、交通时，禁止编造精确数值；没有资料就给核验方式和保守建议。\n'
    '回答必须包含：结论先行、分点建议、注意事项；行程规划尽量按 Day 1/Day 2 输出；购物建议写清品类、预算、推荐地点、比价方法和“以门店实时价为准”。\n'
    '当用户询问小红书热门、日本便宜国内贵、奢侈品包包/中古包时，优先围绕 LV、Chanel 中古、Goyard、Celine、Loewe、Mikimoto/TASAKI、BAO BAO、PORTER、Onitsuka Tiger、Lululemon Outlet，并说明差价受汇率/退税/库存影响。\n'
    '不要输出英文，除非是地名/品牌/官方名称；不要声称自己可以实时联网查询。'
)


def _json_bytes(data: Dict[str, Any]) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode('utf-8')


def _compact_text(value: str, limit: int = 6500) -> str:
    compact = ' '.join(value.replace('\r', '\n').split())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + '\n【资料过长已截断：请优先使用以上高相关片段】'


def _history(payload: Dict[str, Any]) -> List[Tuple[str, str]]:
    knowledge = _compact_text(payload.get('knowledge') or '')
    system_prompt = SYSTEM_PROMPT + ('\n\n【站内资料】\n' + knowledge if knowledge else '')
    messages: List[Tuple[str, str]] = [('system', system_prompt)]
    for msg in (payload.get('messages') or [])[-6:]:
        role = msg.get('role')
        content = msg.get('content')
        if role in ('user', 'assistant') and isinstance(content, str):
            messages.append(('human' if role == 'user' else 'ai', content))
    return messages


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get('text') or item.get('content')
                if isinstance(text, str):
                    parts.append(text)
        return ''.join(parts)
    return str(content or '')


def _llm() -> ChatOpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError('SiliconFlow 模式未配置 OPENAI_API_KEY')
    return ChatOpenAI(
        model=MODEL_NAME,
        base_url=OPENAI_BASE_URL,
        api_key=OPENAI_API_KEY,
        temperature=MODEL_TEMPERATURE,
        max_tokens=MODEL_MAX_TOKENS,
        timeout=REQUEST_TIMEOUT,
    )


def _call_model(payload: Dict[str, Any]) -> str:
    if MODEL_PROVIDER not in ('siliconflow', 'openai-compatible', 'langchain'):
        raise RuntimeError('当前版本默认使用 LangChain + SiliconFlow，请将 MODEL_PROVIDER 配置为 siliconflow')
    with MODEL_SEMAPHORE:
        response = _llm().invoke(_history(payload))
    return _content_to_text(response.content)


def _stream_model(payload: Dict[str, Any], write_delta) -> None:
    if MODEL_PROVIDER not in ('siliconflow', 'openai-compatible', 'langchain'):
        raise RuntimeError('当前版本默认使用 LangChain + SiliconFlow，请将 MODEL_PROVIDER 配置为 siliconflow')
    with MODEL_SEMAPHORE:
        for chunk in _llm().stream(_history(payload)):
            delta = _content_to_text(chunk.content)
            if delta:
                write_delta(delta)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def _cors_origin(self) -> str:
        origin = self.headers.get('Origin') or '*'
        if '*' in CORS_ALLOW_ORIGINS or origin in CORS_ALLOW_ORIGINS:
            return origin if origin != 'null' else '*'
        return CORS_ALLOW_ORIGINS[0] if CORS_ALLOW_ORIGINS else '*'

    def _send(self, status: int, body: bytes, content_type: str = 'application/json; charset=utf-8') -> None:
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', self._cors_origin())
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self._send(204, b'')

    def do_GET(self) -> None:
        if self.path in ('/', '/api/health'):
            self._send(200, _json_bytes({
                'ok': True,
                'service': SERVICE_NAME,
                'provider': MODEL_PROVIDER,
                'model': MODEL_NAME,
                'configured': bool(OPENAI_API_KEY),
                'base_url': OPENAI_BASE_URL,
                'max_tokens': MODEL_MAX_TOKENS,
                'max_concurrent_requests': MAX_CONCURRENT_REQUESTS,
            }))
            return
        self._send(404, _json_bytes({'ok': False, 'error': 'Not found'}))

    def _read_payload(self) -> Dict[str, Any]:
        length = int(self.headers.get('Content-Length') or '0')
        raw = self.rfile.read(length).decode('utf-8') if length else '{}'
        return json.loads(raw or '{}')

    def do_POST(self) -> None:
        if self.path == '/api/chat':
            try:
                payload = self._read_payload()
                reply = _call_model(payload)
                self._send(200, _json_bytes({'ok': bool(reply), 'reply': reply, 'provider': MODEL_PROVIDER, 'model': MODEL_NAME, 'error': '' if reply else '空响应'}))
            except Exception as exc:  # noqa: BLE001
                self._send(200, _json_bytes({'ok': False, 'error': '模型调用失败: ' + str(exc), 'reply': ''}))
            return

        if self.path == '/api/chat/stream':
            self._handle_stream()
            return

        self._send(404, _json_bytes({'ok': False, 'error': 'Not found'}))

    def _handle_stream(self) -> None:
        try:
            payload = self._read_payload()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', self._cors_origin())
            self.end_headers()
            _stream_model(payload, lambda delta: self._write_sse({'delta': delta}))
            self._write_sse({'done': True})
        except Exception as exc:  # noqa: BLE001
            try:
                self._write_sse({'error': '模型调用失败: ' + str(exc)})
                self._write_sse({'done': True})
            except Exception:  # noqa: BLE001
                pass

    def _write_sse(self, data: Dict[str, Any]) -> None:
        chunk = ('data: ' + json.dumps(data, ensure_ascii=False) + '\n\n').encode('utf-8')
        self.wfile.write(chunk)
        self.wfile.flush()

    def log_message(self, fmt: str, *args) -> None:
        print('%s - - [%s] %s' % (self.address_string(), self.log_date_time_string(), fmt % args))


if __name__ == '__main__':
    print(f'{SERVICE_NAME} listening on {HOST}:{PORT}, provider={MODEL_PROVIDER}, model={MODEL_NAME}')
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
