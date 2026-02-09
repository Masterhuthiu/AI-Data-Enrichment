import os
import time
from typing import Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from pymongo import MongoClient
from bson import ObjectId
import google.generativeai as genai
from dotenv import load_dotenv

# Load biến môi trường từ file .env
load_dotenv()

app = FastAPI(
    title="JHipster AI Translation Service",
    description="Microservice dịch tóm tắt phim bằng Gemma-3-27b-it"
)

# =====================
# CONFIG & AI SETUP
# =====================
API_KEY = os.getenv("GEMINI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

if not API_KEY or not MONGO_URI:
    raise ValueError("Thiếu GEMINI_API_KEY hoặc MONGO_URI trong môi trường!")

genai.configure(api_key=API_KEY)
# Sử dụng model gemma-3-27b-it như yêu cầu
model = genai.GenerativeModel("gemma-3-27b-it")

client = MongoClient(MONGO_URI)
db = client.sample_mflix
col = db.movies

# =====================
# CORE LOGIC (WORKER)
# =====================
def background_translate(query: dict):
    """Hàm chạy ngầm để quét và dịch phim theo lô"""
    cursor = col.find(query, no_cursor_timeout=True).batch_size(50)
    print(f"🚀 Bắt đầu tiến trình dịch cho query: {query}")
    
    try:
        for movie in cursor:
            try:
                original_text = movie.get('fullplot')
                if not original_text:
                    continue

                prompt = f"Dịch sang tiếng Việt tự nhiên, phong cách phê bình điện ảnh:\n{original_text}"
                response = model.generate_content(prompt)
                vi_text = response.text.strip()

                col.update_one(
                    {"_id": movie["_id"]},
                    {"$set": {
                        "fullplot_vi": vi_text,
                        "translated_by": "gemma-3-27b-it",
                        "translated_at": time.time()
                    }}
                )
                # Sleep nhẹ để tránh chạm ngưỡng Rate Limit của Google
                time.sleep(0.3) 
            except Exception as e:
                print(f"❌ Lỗi tại ID {movie['_id']}: {e}")
                time.sleep(2) # Đợi lâu hơn nếu gặp lỗi (thường là rate limit)
    finally:
        cursor.close()
        print("✅ Hoàn thành tiến trình chạy ngầm.")

# =====================
# ENDPOINTS
# =====================

@app.get("/")
def health_check():
    return {"status": "running", "model": "gemma-3-27b-it"}

@app.post("/translate/filter")
async def translate_by_filter(
    background_tasks: BackgroundTasks, 
    year: Optional[int] = None, 
    genre: Optional[str] = None
):
    """Dịch có chọn lọc theo năm hoặc thể loại"""
    query = {
        "fullplot": {"$exists": True}, 
        "fullplot_vi": {"$exists": False}
    }
    if year:
        query["year"] = year
    if genre:
        query["genres"] = genre

    # Đẩy vào hàng đợi chạy ngầm
    background_tasks