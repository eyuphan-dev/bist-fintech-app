from database import SessionLocal
import models
from yfinance_client import fetch_historical_prices
from datetime import datetime

def populate_stock_history():
    db = SessionLocal()
    try:
        stocks = db.query(models.Stock).filter_by(is_active=True).all()
        print(f"{len(stocks)} aktif hisse için geçmiş fiyatlar indiriliyor...")
        
        for stock in stocks:
            print(f"{stock.symbol} geçmiş verileri çekiliyor...")
            history = fetch_historical_prices(stock.symbol, period="1mo", interval="1d")
            
            inserted_count = 0
            for data in history:
                # Check if this stock price for this exact time already exists
                exists = db.query(models.StockPrice).filter_by(
                    stock_id=stock.id,
                    recorded_at=data["recorded_at"]
                ).first()
                
                if not exists:
                    price_record = models.StockPrice(
                        stock_id=stock.id,
                        price=data["price"],
                        volume=data["volume"],
                        recorded_at=data["recorded_at"]
                    )
                    db.add(price_record)
                    inserted_count += 1
            
            db.commit()
            print(f"{stock.symbol} için {inserted_count} adet geçmiş fiyat kaydı eklendi.")
            
        print("Tüm hisselerin geçmiş fiyatları başarıyla dolduruldu!")
    except Exception as e:
        print(f"Hata oluştu: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    populate_stock_history()
