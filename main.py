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
except Exception as e:
    print(f"Lỗi cấu hình: {e}")

def background_translate(query: dict):
    movies = list(col.find(query).limit(10))
    for movie in movies:
        try:
            plot = movie.get('fullplot')
            if not plot: continue
            
            response = model.generate_content(f"Dịch sang tiếng Việt: {plot}")
            col.update_one(
                {'_id': movie['_id']}, 
                {'\$set': {'fullplot_vi': response.text, 'translated_by': 'gemma-3-27b-it'}}
            )
            print(f"✅ Đã dịch: {movie.get('title')}")
            time.sleep(1)
        except Exception as e:
            print(f"❌ Lỗi: {e}")

@app.post('/translate/filter')
async def translate(background_tasks: BackgroundTasks, year: Optional[int] = None):
    query = {'fullplot': {'\$exists': True}, 'fullplot_vi': {'\$exists': False}}
    if year: query['year'] = year
    background_tasks.add_task(background_translate, query)
    return {'status': 'started'}

@app.get('/')
def health():
    return {'status': 'ok'}