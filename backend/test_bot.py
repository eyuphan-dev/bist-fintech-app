from database import SessionLocal
from bot import run_ai_bot_simulation

def main():
    print("Manüel Bot Simülasyonu Başlatılıyor...")
    db = SessionLocal()
    try:
        run_ai_bot_simulation(db)
        print("Bot Simülasyonu başarıyla tamamlandı.")
    except Exception as e:
        print(f"Hata: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
