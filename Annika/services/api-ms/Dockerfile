# Base image, subject to change
FROM python:3

WORKDIR /app

# For dependency installation (flask and requests(?))
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py .

EXPOSE 5000

CMD ["python", "app.py"]