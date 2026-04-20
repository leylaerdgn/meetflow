import sqlite3
import json
from typing import List, Dict, Any

DB_NAME = "meetings.db"

def get_db_conn():
    """Yeni bir veritabanı bağlantısı açar ve ayarlar."""
    conn = sqlite3.connect(DB_NAME)
    # Foreign Key kısıtlamalarını aktif et (SQLite'ta varsayılan olarak kapalıdır)
    conn.execute("PRAGMA foreign_keys = ON")
    # Sorgu sonuçlarına sütun adlarıyla erişim sağlar
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    # Veritabanı bağlantısını oluştur (dosya yoksa otomatik yaratılır)
    conn = get_db_conn()
    cursor = conn.cursor()

    # SQL şemasını çalıştır
    cursor.executescript("""
    -- 1. Toplantılar Tablosu
    CREATE TABLE IF NOT EXISTS meetings (
        id INTEGER PRIMARY KEY, -- main.py'deki ID ile tutarlılık için AUTOINCREMENT kaldırıldı
        topic TEXT,
        meeting_date TEXT,
        raw_output_json TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    -- 2. Görevler (Aksiyon Maddeleri) Tablosu
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id INTEGER NOT NULL,
        title TEXT,
        assignee TEXT,
        deadline TEXT,
        status TEXT DEFAULT 'todo' CHECK(status IN ('todo', 'doing', 'done'))
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
        title TEXT NOT NULL,
        reasons TEXT NOT NULL,
        FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
    );

    -- 6. Atanmamış Görevler Tablosu
    CREATE TABLE IF NOT EXISTS unassigned_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        FOREIGN KEY (meeting_id) REFERENCES meetings (id) ON DELETE CASCADE
    );
    """)

    # Değişiklikleri kaydet ve bağlantıyı kapat
    conn.commit()
    conn.close()
    print("Veritabanı ve tablolar başarıyla oluşturuldu (meetings.db).")

def save_analysis_results(meeting_id: int, result: Dict[str, Any]):
    """Analiz sonucunu normalize edilmiş tablolara kaydeder."""
    conn = get_db_conn()
    cursor = conn.cursor()
    try:
        # Tüm işlemleri bir transaction içinde güvenle yap
        cursor.execute("BEGIN")

        # 1. Ana toplantı verisini kaydet/güncelle
        metadata = result.get("meeting_metadata", {})
        cursor.execute("""
            INSERT INTO meetings (id, topic, meeting_date, raw_output_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                topic=excluded.topic,
                meeting_date=excluded.meeting_date,
                raw_output_json=excluded.raw_output_json;
        """, (
            meeting_id,
            metadata.get("topic"),
            metadata.get("date"),
            json.dumps(result)
        ))

        # 2. Tekrar analiz durumunda eski verileri temizle
        cursor.execute("DELETE FROM tasks WHERE meeting_id = ?", (meeting_id,))
        cursor.execute("DELETE FROM decisions WHERE meeting_id = ?", (meeting_id,))
        cursor.execute("DELETE FROM ambiguities WHERE meeting_id = ?", (meeting_id,))
        cursor.execute("DELETE FROM risky_action_items WHERE meeting_id = ?", (meeting_id,))
        cursor.execute("DELETE FROM unassigned_tasks WHERE meeting_id = ?", (meeting_id,))

        # 3. Yeni görevleri (tasks) ekle
        for task in result.get("tasks", []):
            cursor.execute(
                "INSERT INTO tasks (meeting_id, title, assignee, deadline) VALUES (?, ?, ?, ?)",
                (meeting_id, task.get("title"), task.get("assignee"), task.get("deadline"))
            )

        # 4. Yeni kararları (decisions) ekle
        for decision in result.get("decisions", []):
            cursor.execute("INSERT INTO decisions (meeting_id, decision) VALUES (?, ?)", (meeting_id, decision))

        # 5. Yeni belirsizlikleri (ambiguities) ekle
        for ambiguity in result.get("ambiguities", []):
            cursor.execute("INSERT INTO ambiguities (meeting_id, ambiguity) VALUES (?, ?)", (meeting_id, ambiguity))

        # 6. Yeni riskli görevleri ekle
        for risky_task in result.get("risky_action_items", []):
            cursor.execute(
                "INSERT INTO risky_action_items (meeting_id, title, reasons) VALUES (?, ?, ?)",
                (meeting_id, risky_task.get("title"), json.dumps(risky_task.get("reasons", [])))
            )

        # 7. Yeni atanmamış görevleri ekle
        for unassigned_task_title in result.get("unassigned_tasks", []):
            cursor.execute(
                "INSERT INTO unassigned_tasks (meeting_id, title) VALUES (?, ?)", (meeting_id, unassigned_task_title)
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_all_tasks_from_db() -> List[Dict[str, Any]]:
    """Veritabanındaki tüm görevleri bir liste olarak döndürür."""
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, meeting_id, title, assignee, deadline, status FROM tasks")
    tasks = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tasks

def update_task_status_in_db(task_id: int, status: str) -> Dict[str, Any]:
    """Bir görevin durumunu günceller ve güncellenmiş görevi döndürür."""
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
    if cursor.rowcount == 0:
        conn.close()
        return None  # Güncellenecek görev bulunamadı

    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    updated_task = dict(cursor.fetchone())
    conn.commit()
    conn.close()
    return updated_task

if __name__ == "__main__":
    init_db()