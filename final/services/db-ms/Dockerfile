FROM python:3-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir

COPY app.py .

RUN mkdir -p /data

EXPOSE 6000

CMD ["python", "app.py"]
