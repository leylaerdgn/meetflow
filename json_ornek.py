import json

def analyze_meeting(json_string: str):
    print("JSON verisi parse ediliyor...\n")
    
    try:
        # 1. json.loads() ile string formatındaki JSON verisini Python objesine (dict/list) çeviriyoruz.
        parsed_data = json.loads(json_string)
        
        # 2. Artık normal bir Python sözlüğü (dictionary) gibi verilere erişebiliriz.
        metadata = parsed_data.get("meeting_metadata", {})
        topic = metadata.get("topic", "Konu belirtilmemiş")
        date = metadata.get("date", "Tarih yok")
        
        print(f"--- {topic.upper()} ---")
        print(f"Tarih: {date}\n")
        
        # 3. Listeler içinde döngü kurabiliriz
        decisions = parsed_data.get("decisions", [])
        print("Kararlar:")
        for decision in decisions:
            print(f" - {decision}")
            
        # 4. Liste içindeki sözlüklere (objelere) erişim
        action_items = parsed_data.get("tasks", [])
        print("\nGörevler (Tasks):")
        for item in action_items:
            title = item.get("title", "Görev yok")
            assignee = item.get("assignee", "Bilinmiyor")
            print(f" -> [ ] {title} (Sorumlu: {assignee})")
            
        return parsed_data

    except json.JSONDecodeError as e:
        print(f"Hata: Geçersiz JSON formatı! Detay: {e}")
        return None

# Test için örnek bir JSON metni
ornek_json_metni = """
{
  "meeting_metadata": {
    "topic": "Mobil Uygulama Geliştirme Süreci",
    "date": "2023-11-20"
  },
  "decisions": [
    "Giriş ekranı tasarımı cuma gününe kadar bitirilecek."
  ],
  "tasks": [
    {
      "title": "Taslakları hazırlamak",
      "assignee": "Leyla",
      "deadline": "Cuma"
    }
  ]
}
"""

# Fonksiyonumuzu çağırıyoruz
if __name__ == "__main__":
    analyze_meeting(ornek_json_metni)