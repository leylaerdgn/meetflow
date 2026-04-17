import os
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv
from prompt import SYSTEM_PROMPT
from models import MeetingDecoderOutput

# .env dosyasını yüklüyoruz
load_dotenv()

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def decode_meeting(transcript_text: str) -> MeetingDecoderOutput:
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

if __name__ == "__main__":
    transcript_path = "sample_transcript.txt"
    
    if not os.path.exists(transcript_path):
        print(f"Hata: '{transcript_path}' bulunamadı. Lütfen test için metni oluşturun.")
    else:
        with open(transcript_path, "r", encoding="utf-8") as f:
            transcript = f.read()
            
        try:
            result = decode_meeting(transcript)
            
            print("\n--- ÇÖZÜMLENEN TOPLANTI BİLGİLERİ ---")
            print(f"Konu  : {result.meeting_metadata.topic}")
            print(f"Tarih : {result.meeting_metadata.date}")
            print("\nKararlar:")
            for d in result.decisions: print(f" - {d}")
            print("\nAksiyonlar:")
            for a in result.action_items: print(f" - [ ] {a.task} (Sorumlu: {a.assignee}, Tarih: {a.deadline})")
            print("\nBelirsizlikler:")
            for am in result.ambiguities: print(f" - {am}")
                
            print("\nRiskli Aksiyonlar:")
            for r in result.risky_action_items: print(f" - {r.task} (Neden: {', '.join(r.reason)})")
                
            print("\nAtanmamış Görevler:")
            for u in result.unassigned_tasks: print(f" - {u}")
                
            print("\nTekrarlanan Konular:")
            for rt in result.repeated_topics: print(f" - {rt.topic} ({rt.count} kez)")
                
            print("\nÇelişkili Durumlar:")
            for dc in result.decision_conflicts: print(f" - {dc}")
                
            print("\nKonu Durumları:")
            print(f" - Açık Konular: {', '.join(result.open_topics) if result.open_topics else 'Yok'}")
            print(f" - Kapalı Konular: {', '.join(result.closed_topics) if result.closed_topics else 'Yok'}")
                
            print("\nÖncelikler (High/Medium/Low):")
            print(f" - High  : {', '.join(result.priorities.high) if result.priorities.high else 'Yok'}")
            print(f" - Medium: {', '.join(result.priorities.medium) if result.priorities.medium else 'Yok'}")
            print(f" - Low   : {', '.join(result.priorities.low) if result.priorities.low else 'Yok'}")
                
            print("\nİş Yükü Dağılımı:")
            for w in result.workload_distribution: print(f" - {w.assignee}: {w.task_count} görev")

        except Exception as e:
            print(f"\nBir hata oluştu: {e}")