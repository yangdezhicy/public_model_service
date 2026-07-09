FROM python:3.11-slim

ENV LANG=C.UTF-8
ENV PYTHONIOENCODING=utf-8

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py ./

EXPOSE 8000
CMD ["python", "main.py"]
