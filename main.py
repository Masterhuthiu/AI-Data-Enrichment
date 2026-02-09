import os
import time
import google.generativeai as genai
from fastapi import FastAPI, BackgroundTasks
from pymongo import MongoClient
from typing import Optional

app = FastAPI(title='JHipster AI Service')

# Cấu hình AI & Database
try:
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel('gemma-3-27b-it')
    
    # Thêm timeout để không treo App nếu DB lỗi
    client = MongoClient(os.getenv('MONGO_URI'), serverSelectionTimeoutMS=5000)
    db = client.sample_mflix
    col = db.movies
    print("✅ Kết nối DB và AI thành công")
except Exception as e:
    print(f"❌ Lỗi cấu hình ban đầu: {e}")

def background_translate(query: dict):
    print(f"🚀 Bắt đầu dịch với filter: {query}")
    # Giới hạn 10 phim mỗi lần gọi để tránh quá tải API Key miễn phí
    movies = list(col.find(query).limit(10))
    
    for movie in movies:
        try:
            plot = movie.get('fullplot')
            title = movie.get('title', 'Unknown')
            
            if not plot:
                continue
            
            # Tách prompt ra để an toàn cho Python 3.9
            prompt = f"Dịch tóm tắt phim sau sang tiếng Việt tự nhiên: {plot}"
            response = model.generate_content(prompt)
            
            # SỬA LỖI: Bỏ dấu gạch chéo ngược ở $set
            col.update_one(
                {'_id': movie['_id']}, 
                {'$set': {
                    'fullplot_vi': response.text, 
                    'translated_by': 'gemma-3-27b-it'
                }}
            )
            print(f"✅ Đã dịch xong: {title}")
            time.sleep(1) # Nghỉ 1 giây giữa mỗi phim
            
        except Exception as e:
            print(f"❌ Lỗi khi dịch phim {movie.get('_id')}: {e}")

@app.post('/translate/filter')
async def translate(background_tasks: BackgroundTasks, year: Optional[int] = None):
    # SỬA LỖI: Bỏ dấu gạch chéo ngược ở $exists
    query = {
        'fullplot': {'$exists': True}, 
        'fullplot_vi': {'$exists': False}
    }
    
    if year:
        query['year'] = year
        
    background_tasks.add_task(background_translate, query)
    return {
        'status': 'started',
        'filter_applied': str(query)
    }

@app.get('/')
def health():
    return {'status': 'ok', 'service': 'translator'}