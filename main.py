import os
import time
import sqlite3
import json
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv
from prompt import SYSTEM_PROMPT
from models import MeetingDecoderOutput

# .env dosyasını yüklüyoruz
load_dotenv()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

app = FastAPI(title="Meeting Decoder API")

# Toplantı metnini tutacağımız geçici bellek içi veritabanı (ID -> Transcript)
meetings_db = {}

class MeetingInput(BaseModel):
    transcript: str

class TaskStatusUpdate(BaseModel):
    status: str


def init_db():
    conn = sqlite3.connect("meetings.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS meetings (
        id INTEGER PRIMARY KEY,
        transcript TEXT,
        analysis TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id INTEGER,
        title TEXT,
        assignee TEXT,
        deadline TEXT,
        status TEXT DEFAULT 'todo' CHECK(status IN ('todo', 'doing', 'done'))
    )
    """)

    conn.commit()
    conn.close()

def save_to_db(meeting_id, transcript, analysis):
    conn = sqlite3.connect("meetings.db")
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO meetings (id, transcript, analysis)
    VALUES (?, ?, ?)
    """, (meeting_id, transcript, json.dumps(analysis)))

    # Analiz sonucundaki görevleri tasks tablosuna ekleyelim
    for task_item in analysis.get("tasks", []):
        cursor.execute("""
        INSERT INTO tasks (meeting_id, title, assignee, deadline, status)
        VALUES (?, ?, ?, ?, ?)
        """, (meeting_id, task_item.get("title"), task_item.get("assignee"), task_item.get("deadline"), task_item.get("status", "todo")))

    conn.commit()
    conn.close()

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
        # Pydantic V2 uyumluluğu için dict() yerine model_dump() kullanıldı
        save_to_db(meeting_id, transcript, result.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks")
def get_all_tasks():
    conn = sqlite3.connect("meetings.db")
    # Bu, cursor'un sözlük benzeri satırlar döndürmesini sağlar
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT id, meeting_id, title, assignee, deadline, status FROM tasks")
    tasks = cursor.fetchall()

    conn.close()

    # Satır nesnelerini sözlüklere dönüştür
    return [dict(task) for task in tasks]

@app.put("/tasks/{task_id}")
def update_task_status(task_id: int, task_update: TaskStatusUpdate):
    allowed_statuses = {"todo", "doing", "done"}
    if task_update.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Geçersiz statü. İzin verilen değerler: {', '.join(allowed_statuses)}"
        )

    conn = sqlite3.connect("meetings.db")
    conn.row_factory = sqlite3.Row  # Yanıt için sözlük benzeri satırlar al
    cursor = conn.cursor()

    # Görevin var olup olmadığını kontrol et
    cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    if task is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Görev bulunamadı")

    # Statüyü güncelle ve güncellenmiş görevi geri al
    cursor.execute("UPDATE tasks SET status = ? WHERE id = ?", (task_update.status, task_id))
    
    cursor.execute("SELECT id, title, status FROM tasks WHERE id = ?", (task_id,))
    updated_task = cursor.fetchone()
    
    conn.commit()
    conn.close()

    # Yanıt modelini oluştur
    response_data = dict(updated_task)
    response_data["completed"] = response_data["status"] == "done"

    return response_data

init_db()
    
