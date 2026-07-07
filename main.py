import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import BoundedSemaphore
from typing import Dict, List


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

SERVICE_NAME = os.environ.get('SERVICE_NAME') or 'free-japan-travel-ai'
MODEL_PROVIDER = (os.environ.get('MODEL_PROVIDER') or 'ollama').lower()
MODEL_NAME = os.environ.get('MODEL_NAME') or 'qwen2.5:0.5b'
MODEL_TEMPERATURE = float(os.environ.get('MODEL_TEMPERATURE') or '0.35')
MODEL_MAX_TOKENS = int(os.environ.get('MODEL_MAX_TOKENS') or '800')
OLLAMA_NUM_CTX = int(os.environ.get('OLLAMA_NUM_CTX') or '2048')
OLLAMA_NUM_THREAD = int(os.environ.get('OLLAMA_NUM_THREAD') or '3')
MAX_CONCURRENT_REQUESTS = int(os.environ.get('MAX_CONCURRENT_REQUESTS') or '1')
REQUEST_TIMEOUT = int(os.environ.get('REQUEST_TIMEOUT') or '120')
STREAM_TIMEOUT = int(os.environ.get('STREAM_TIMEOUT') or '180')
PORT = int(os.environ.get('PORT') or '8000')
CORS_ALLOW_ORIGINS = _split_csv(os.environ.get('CORS_ALLOW_ORIGINS') or '*')
OLLAMA_BASE_URL = (os.environ.get('OLLAMA_BASE_URL') or 'http://ollama:11434').rstrip('/')
OPENAI_BASE_URL = (os.environ.get('OPENAI_BASE_URL') or 'https://api.openai.com/v1').rstrip('/')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY') or ''
MODEL_SEMAPHORE = BoundedSemaphore(max(1, MAX_CONCURRENT_REQUESTS))

SYSTEM_PROMPT = (
    '你是「日本旅游 AI 小助手」，服务于一个中文日本旅游攻略网站。\n'
    '你必须始终使用简体中文回答。\n'
    '优先依据调用方提供的【站内资料】回答；涉及价格、地址、营业时间、店铺、景点等具体信息时，禁止编造。\n'
    '如果资料不足，可以补充常识，但必须明确区分「资料已给出」和「通用建议」。\n'
    '你的回答应条理清晰、可执行、适合真实出行决策。'
)


def _json_bytes(data: Dict) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode('utf-8')


def _history(payload: Dict) -> List[Dict[str, str]]:
    knowledge = payload.get('knowledge') or ''
    system_prompt = SYSTEM_PROMPT + ('\n\n【站内资料】\n' + knowledge if knowledge else '')
    messages = [{'role': 'system', 'content': system_prompt}]
    for msg in (payload.get('messages') or [])[-12:]:
        role = msg.get('role')
        content = msg.get('content')
        if role in ('user', 'assistant') and isinstance(content, str):
            messages.append({'role': role, 'content': content})
    return messages


def _post_json(url: str, payload: Dict, headers: Dict[str, str] | None = None, timeout: int = 120) -> Dict:
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=body,
        headers={'Content-Type': 'application/json', **(headers or {})},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read().decode('utf-8')
        return json.loads(data)


def _call_ollama(payload: Dict) -> str:
    with MODEL_SEMAPHORE:
        data = _post_json(
            OLLAMA_BASE_URL + '/api/chat',
            {
                'model': MODEL_NAME,
                'messages': _history(payload),
                'stream': False,
                'options': {
                    'temperature': MODEL_TEMPERATURE,
                    'num_predict': MODEL_MAX_TOKENS,
                    'num_ctx': OLLAMA_NUM_CTX,
                    'num_thread': OLLAMA_NUM_THREAD,
                },
            },
            timeout=REQUEST_TIMEOUT,
        )
    return (data.get('message') or {}).get('content') or ''


def _call_openai(payload: Dict) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError('OpenAI-compatible 模式未配置 OPENAI_API_KEY')
    with MODEL_SEMAPHORE:
        data = _post_json(
            OPENAI_BASE_URL + '/chat/completions',
            {
                'model': MODEL_NAME,
                'messages': _history(payload),
                'temperature': MODEL_TEMPERATURE,
                'max_tokens': MODEL_MAX_TOKENS,
            },
            headers={'Authorization': 'Bearer ' + OPENAI_API_KEY},
            timeout=REQUEST_TIMEOUT,
        )
    return data.get('choices', [{}])[0].get('message', {}).get('content') or ''


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
                'configured': True if MODEL_PROVIDER == 'ollama' else bool(OPENAI_API_KEY),
                'free': MODEL_PROVIDER == 'ollama',
                'num_ctx': OLLAMA_NUM_CTX,
                'max_tokens': MODEL_MAX_TOKENS,
                'num_thread': OLLAMA_NUM_THREAD,
                'max_concurrent_requests': MAX_CONCURRENT_REQUESTS,
            }))
            return
        self._send(404, _json_bytes({'ok': False, 'error': 'Not found'}))

    def _read_payload(self) -> Dict:
        length = int(self.headers.get('Content-Length') or '0')
        raw = self.rfile.read(length).decode('utf-8') if length else '{}'
        return json.loads(raw or '{}')

    def do_POST(self) -> None:
        if self.path == '/api/chat':
            try:
                payload = self._read_payload()
                reply = _call_ollama(payload) if MODEL_PROVIDER == 'ollama' else _call_openai(payload)
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
            if MODEL_PROVIDER == 'ollama':
                self._stream_ollama(payload)
            else:
                reply = _call_openai(payload)
                self._write_sse({'delta': reply})
            self._write_sse({'done': True})
        except Exception as exc:  # noqa: BLE001
            try:
                self._write_sse({'error': '模型调用失败: ' + str(exc)})
                self._write_sse({'done': True})
            except Exception:  # noqa: BLE001
                pass

    def _write_sse(self, data: Dict) -> None:
        chunk = ('data: ' + json.dumps(data, ensure_ascii=False) + '\n\n').encode('utf-8')
        self.wfile.write(chunk)
        self.wfile.flush()

    def _stream_ollama(self, payload: Dict) -> None:
        body = json.dumps({
            'model': MODEL_NAME,
            'messages': _history(payload),
            'stream': True,
            'options': {
                'temperature': MODEL_TEMPERATURE,
                'num_predict': MODEL_MAX_TOKENS,
                'num_ctx': OLLAMA_NUM_CTX,
                'num_thread': OLLAMA_NUM_THREAD,
            },
        }, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            OLLAMA_BASE_URL + '/api/chat',
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with MODEL_SEMAPHORE:
            with urllib.request.urlopen(req, timeout=STREAM_TIMEOUT) as resp:
                for raw in resp:
                    if not raw.strip():
                        continue
                    obj = json.loads(raw.decode('utf-8'))
                    delta = (obj.get('message') or {}).get('content') or ''
                    if delta:
                        self._write_sse({'delta': delta})
                    if obj.get('done'):
                        break

    def log_message(self, fmt: str, *args) -> None:
        print('%s - - [%s] %s' % (self.address_string(), self.log_date_time_string(), fmt % args))


if __name__ == '__main__':
    print(f'{SERVICE_NAME} listening on 0.0.0.0:{PORT}, provider={MODEL_PROVIDER}, model={MODEL_NAME}')
    ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
