# Base image, subject to change
FROM python:3

WORKDIR /app

# Dependency installation
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py .

RUN mkdir -p /data

EXPOSE 6000

CMD ["python", "app.py"]