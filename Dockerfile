FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
# Đảm bảo pip và các gói được cài đúng quyền hệ thống
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8080
# Sử dụng python -m để an toàn hơn
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]