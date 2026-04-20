import os
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Yerel modüller
from prompt import SYSTEM_PROMPT
from models import MeetingDecoderOutput
import database

# .env dosyasını yüklüyoruz
load_dotenv()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

app = FastAPI(title="Meeting Decoder API")

@app.on_event("startup")
def on_startup():
    """Uygulama başladığında veritabanını başlatır."""
    database.init_db()

# Toplantı metnini tutacağımız geçici bellek içi veritabanı (ID -> Transcript)
meetings_db = {}

class MeetingInput(BaseModel):
    transcript: str

class TaskStatusUpdate(BaseModel):
    status: str

def analyze_meeting(transcript_text: str) -> MeetingDecoderOutput:
    print("LLM'e istek gönderiliyor...")
    
    max_retries = 3
    retry_delay = 5  # Başlangıçta 5 saniye bekle
    
    for attempt in range(max_retries):
        try:
            # Google GenAI SDK'sı ile güncel Gemini 2.5 Flash modelini çağırıyoruz
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"Toplantı Metni:\n{transcript_text}",
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.1,
                    response_mime_type="application/json"
                )
            )
            break  # İstek başarılı olursa döngüden çık
        except Exception as e:
            if "503" in str(e) and attempt < max_retries - 1:
                print(f"Sunucu meşgul (503). {retry_delay} saniye sonra tekrar deneniyor... (Deneme {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 2  # Bekleme süresini katla (5s, 10s...)
            else:
                raise e  # 503 dışındaki hataları veya max deneme aşımını direkt fırlat
    
    # LLM'den dönen raw string'i alıyoruz
    raw_content = response.text.strip()
    
    # Model kuralı çiğneyip başına/sonuna markdown (```json) eklerse temizliyoruz
    if raw_content.startswith("```json"):
        raw_content = raw_content[7:-3].strip()
    elif raw_content.startswith("```"):
        raw_content = raw_content[3:-3].strip()
        
    print("Yanıt alındı, Pydantic ile doğrulanıyor...")
    
    # JSON string'ini MeetingDecoderOutput modeline dönüştürerek doğruluyoruz (Parsing)
    parsed_data = MeetingDecoderOutput.model_validate_json(raw_content)
    
    return parsed_data

@app.post("/meetings")
def create_meeting(meeting: MeetingInput):
    meeting_id = len(meetings_db) + 1
    meetings_db[meeting_id] = meeting.transcript
    return {"id": meeting_id, "message": "Transcript başarıyla alındı"}

@app.get("/meetings")
def get_meetings():
    return [{"id": k, "transcript": v} for k, v in meetings_db.items()]

@app.post("/meetings/{meeting_id}/analyze")
def analyze_meeting_endpoint(meeting_id: int):
    if meeting_id not in meetings_db:
        raise HTTPException(status_code=404, detail="Toplantı bulunamadı")
        
    transcript = meetings_db[meeting_id]
    try:
        result = analyze_meeting(transcript)
        # Analiz sonucunu veritabanına kaydetmek için database modülünü kullan
        database.save_analysis_results(meeting_id, result.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks")
def get_all_tasks():
    """Veritabanındaki tüm görevleri listeler."""
    return database.get_all_tasks_from_db()

@app.put("/tasks/{task_id}")
def update_task_status(task_id: int, task_update: TaskStatusUpdate):
    """Bir görevin durumunu günceller."""
    allowed_statuses = {"todo", "doing", "done"}
    if task_update.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Geçersiz statü. İzin verilen değerler: {', '.join(allowed_statuses)}"
        )
    
    updated_task = database.update_task_status_in_db(task_id, task_update.status)
    if updated_task is None:
        raise HTTPException(status_code=404, detail="Görev bulunamadı")

    # Yanıta dinamik olarak 'completed' alanını ekle
    updated_task["completed"] = updated_task["status"] == "done"
    return updated_task
