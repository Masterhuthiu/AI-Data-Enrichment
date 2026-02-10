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

# --- Cấu hình Consul ---
CONSUL_HOST = os.getenv('CONSUL_HOST', 'consul-server')
CONSUL_PORT = int(os.getenv('CONSUL_PORT', 8500))
SERVICE_NAME = 'translator-service'
SERVICE_ID = f"{SERVICE_NAME}-{socket.gethostname()}"
SERVICE_PORT = 8080

# --- Cấu hình AI & Database ---
try:
    # Sử dụng API Key từ Secret
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    # Sử dụng model gemma-3-27b-it như bạn yêu cầu
    model = genai.GenerativeModel('gemma-3-27b-it')
    
    client = MongoClient(os.getenv('MONGO_URI'), serverSelectionTimeoutMS=5000)
    db = client.sample_mflix
    col = db.movies
    print("✅ Kết nối MongoDB thành công")
except Exception as e:
    print(f"❌ Lỗi cấu hình: {e}")

# --- Logic Dịch thuật (Chạy ngầm) ---
def translate_movie_task(movie_id: str):
    try:
        # 1. Tìm phim trong DB
        movie = col.find_one({"_id": ObjectId(movie_id)})
        if not movie:
            print(f"❌ Không tìm thấy phim ID: {movie_id}")
            return

        plot_to_translate = movie.get('fullplot') or movie.get('plot')
        if not plot_to_translate:
            print(f"⚠️ Phim {movie.get('title')} không có nội dung để dịch")
            return

        print(f"🌐 Đang dịch phim: {movie.get('title')}...")

        # 2. Gọi AI dịch
        prompt = f"Dịch nội dung phim sau đây sang tiếng Việt một cách tự nhiên: {plot_to_translate}"
        response = model.generate_content(prompt)
        translated_text = response.text

        # 3. Cập nhật lại vào MongoDB
        col.update_one(
            {"_id": ObjectId(movie_id)},
            {"$set": {"fullplot_vi": translated_text}}
        )
        print(f"✅ Đã dịch xong và lưu vào DB: {movie.get('title')}")

    except Exception as e:
        print(f"❌ Lỗi trong quá trình dịch: {e}")

# --- Consul Events ---
@app.on_event("startup")
async def register_to_consul():
    try:
        c = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)
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

# --- Endpoints ---

@app.get('/')
def health():
    return {'status': 'ok', 'service': 'translator'}

# Endpoint bạn đang cần gọi đây:
@app.post('/translate/id/{movie_id}')
async def translate_by_id(movie_id: str, background_tasks: BackgroundTasks):
    # Kiểm tra ID hợp lệ
    if not ObjectId.is_valid(movie_id):
        raise HTTPException(status_code=400, detail="ID không đúng định dạng ObjectId")
    
    # Thêm tác vụ dịch vào background để không làm treo API
    background_tasks.add_task(translate_movie_task, movie_id)
    
    return {
        "message": "Đã tiếp nhận yêu cầu dịch",
        "movie_id": movie_id,
        "status": "processing"
    }

@app.post('/translate/filter')
async def translate_by_filter(year: int, background_tasks: BackgroundTasks):
    movies = col.find({"year": year, "fullplot_vi": {"$exists": False}})
    count = 0
    for m in movies:
        background_tasks.add_task(translate_movie_task, str(m['_id']))
        count += 1
    
    return {"message": f"Đang dịch {count} bộ phim của năm {year}"}