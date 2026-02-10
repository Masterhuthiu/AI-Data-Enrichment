import os
import time
import socket
import consul
import google.generativeai as genai
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pymongo import MongoClient
from bson import ObjectId
from typing import Optional

app = FastAPI(title='JHipster AI Service')

# Cấu hình Consul
CONSUL_HOST = os.getenv('CONSUL_HOST', 'consul-server')
CONSUL_PORT = int(os.getenv('CONSUL_PORT', 8500))
SERVICE_NAME = 'translator-service'
SERVICE_ID = f"{SERVICE_NAME}-{socket.gethostname()}"
SERVICE_PORT = 8080

# Cấu hình AI & Database
try:
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel('gemma-3-27b-it')
    client = MongoClient(os.getenv('MONGO_URI'), serverSelectionTimeoutMS=5000)
    db = client.sample_mflix
    col = db.movies
except Exception as e:
    print(f"❌ Lỗi cấu hình: {e}")

@app.on_event("startup")
async def register_to_consul():
    try:
        c = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)
        # Lấy IP của chính Pod này trong mạng nội bộ K8s
        ip_address = socket.gethostbyname(socket.gethostname())
        
        c.agent.service.register(
            name=SERVICE_NAME,
            service_id=SERVICE_ID,
            address=ip_address,
            port=SERVICE_PORT,
            check=consul.Check.http(f"http://{ip_address}:{SERVICE_PORT}/", interval="10s")
        )
        print(f"✅ Đã đăng ký với Consul: {SERVICE_ID}")
    except Exception as e:
        print(f"❌ Không thể đăng ký Consul: {e}")

@app.on_event("shutdown")
async def deregister_from_consul():
    try:
        c = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)
        c.agent.service.deregister(SERVICE_ID)
        print(f"👋 Đã hủy đăng ký khỏi Consul")
    except Exception as e:
        print(f"❌ Lỗi khi hủy đăng ký Consul: {e}")

# ... Giữ nguyên các hàm translate và endpoints cũ ...
@app.get('/')
def health():
    return {'status': 'ok', 'service': 'translator'}