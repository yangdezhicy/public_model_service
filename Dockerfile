FROM python:3.11-slim

ENV LANG=C.UTF-8
ENV PYTHONIOENCODING=utf-8

WORKDIR /app
COPY requirements.txt ./
# 使用国内清华源镜像，避免服务器网络问题导致下载失败
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
COPY main.py ./

EXPOSE 8000
CMD ["python", "main.py"]
