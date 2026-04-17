from pathlib import Path
from main import decode_meeting

TEST_DIR = Path("sample_data")

def run_tests():
    for file_path in TEST_DIR.glob("*.txt"):
        print("\n" + "=" * 60)
        print(f"TEST DOSYASI: {file_path.name}")
        print("=" * 60)

        transcript = file_path.read_text(encoding="utf-8")

        try:
            result = decode_meeting(transcript)

            print("Konu:", result.meeting_metadata.topic)
            print("Tarih:", result.meeting_metadata.date)
            print("Kararlar:", result.decisions)
            print("Aksiyonlar:", result.action_items)
            print("Belirsizlikler:", result.ambiguities)

            if hasattr(result, "risky_action_items"):
                print("Riskli Aksiyonlar:", result.risky_action_items)

            if hasattr(result, "unassigned_tasks"):
                print("Atanmamış Görevler:", result.unassigned_tasks)

        except Exception as e:
            print("HATA:", e)

if __name__ == "__main__":
    run_tests()