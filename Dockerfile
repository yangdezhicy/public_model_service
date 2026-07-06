FROM python:3.11-slim

WORKDIR /app
COPY main.py ./

# 纯 Python 标准库实现：不依赖 FastAPI / requests / pydantic，不执行 pip install，避免服务器 PyPI 网络问题。
EXPOSE 8000
CMD ["python", "main.py"]
