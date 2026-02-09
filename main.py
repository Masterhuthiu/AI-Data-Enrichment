Chắc chắn là nên chỉnh lại một chút để bản code này hoạt động bền bỉ và chuyên nghiệp hơn, đặc biệt là sau khi chúng ta đã rút ra kinh nghiệm từ các lỗi cú pháp và lỗi logic vừa rồi.

Dưới đây là phiên bản "hoàn hảo" đã được tinh chỉnh để:

Sửa lỗi cú pháp f-string (phù hợp với Python 3.9).

Thêm xử lý lỗi kết nối MongoDB (để tránh App bị treo khi khởi động).

Thêm giới hạn (Limit) để tránh làm "cháy" API Key miễn phí nếu database quá lớn.

Hãy dùng lệnh này để ghi đè lại file main.py chuẩn nhất:

Bash
cat <<EOF > main.py
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
    
    client = MongoClient(os.getenv('MONGO_URI'), serverSelectionTimeoutMS=5000)
    db = client.sample_mflix
    col = db.movies
    print("✅ Kết nối MongoDB và Gemini thành công!")
except Exception as e:
    print(f"❌ Lỗi cấu hình hệ thống: {e}")

def background_translate(query: dict):
    print(f"🚀 Bắt đầu tiến trình dịch chạy ngầm...")
    # Thêm limit(10) để bảo vệ API Key khỏi bị tràn (Rate Limit)
    movies = list(col.find(query).limit(10))
    
    count = 0
    for movie in movies:
        try:
            title = movie.get('title', 'Unknown')
            original_plot = movie.get('fullplot')
            
            if not original_plot:
                continue

            # Prompt tối ưu cho Gemma-3
            prompt = f"Dịch tóm tắt phim sau sang tiếng Việt tự nhiên: {original_plot}"
            response = model.generate_content(prompt)
            
            col.update_one(
                {'_id': movie['_id']}, 
                {'\$set': {
                    'fullplot_vi': response.text, 
                    'translated_by': 'gemma-3-27b-it',
                    'updated_at': time.time()
                }}
            )
            print(f"✅ Đã dịch xong: {title}")
            count += 1
            time.sleep(1)  # Nghỉ 1 giây để tránh lỗi 429 (Too Many Requests)
            
        except Exception as e:
            print(f"❌ Lỗi khi dịch phim {movie.get('title')}: {e}")
            
    print(f"🏁 Hoàn thành! Đã dịch thành công {count} phim.")

@app.post('/translate/filter')
async def translate(background_tasks: BackgroundTasks, year: Optional[int] = None):
    # Logic tìm phim chưa có bản dịch tiếng Việt
    query = {
        'fullplot': {'\$exists': True}, 
        'fullplot_vi': {'\$exists': False}
    }
    if year:
        query['year'] = year
        
    background_tasks.add_task(background_translate, query)
    return {
        'status': 'started', 
        'message': f'Tiến trình dịch phim năm {year if year else "tất cả"} đã bắt đầu.',
        'filter': str(query)
    }

@app.get('/')
def health():
    return {'status': 'ok', 'model': 'gemma-3-27b-it'}