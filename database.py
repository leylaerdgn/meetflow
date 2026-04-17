import sqlite3

def init_db():
    # Veritabanı bağlantısını oluştur (dosya yoksa otomatik yaratılır)
    conn = sqlite3.connect('meetings.db')
    
    # Foreign Key kısıtlamalarını aktif et (SQLite'ta varsayılan olarak kapalıdır)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    # SQL şemasını çalıştır
    cursor.executescript("""
    -- 1. Toplantılar Tablosu
    CREATE TABLE IF NOT EXISTS meetings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT NOT NULL,
        meeting_date TEXT,
        raw_output_json TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- 2. Görevler (Aksiyon Maddeleri) Tablosu
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id INTEGER NOT NULL,
        task TEXT NOT NULL,
        assignee TEXT,
        deadline TEXT,
        is_risky BOOLEAN DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
    );

    -- 3. Kararlar Tablosu
    CREATE TABLE IF NOT EXISTS decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id INTEGER NOT NULL,
        decision TEXT NOT NULL,
        FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
    );

    -- 4. Belirsizlikler Tablosu
    CREATE TABLE IF NOT EXISTS ambiguities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id INTEGER NOT NULL,
        ambiguity TEXT NOT NULL,
        FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
    );

    -- 5. Riskli Görevler Tablosu
    CREATE TABLE IF NOT EXISTS risky_action_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id INTEGER NOT NULL,
        task TEXT NOT NULL,
        reasons TEXT NOT NULL,
        FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
    );

    -- 6. Atanmamış Görevler Tablosu
    CREATE TABLE IF NOT EXISTS unassigned_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id INTEGER NOT NULL,
        task TEXT NOT NULL,
        FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
    );
    """)

    # Değişiklikleri kaydet ve bağlantıyı kapat
    conn.commit()
    conn.close()
    print("Veritabanı ve tablolar başarıyla oluşturuldu (meetings.db).")

if __name__ == "__main__":
    init_db()