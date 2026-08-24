from datetime import datetime, timedelta
from sqlalchemy import text, inspect
from database import engine, Base, SessionLocal, IS_SQLITE
import models

# ---------------------------------------------------------------------------
# BİST Hisse Kataloğu + Katılım Endeksi (XKTUM) Uygunluk Bilgileri
#
# NOT: Aşağıdaki is_katilim_compliant / purification_rate / non_compliance_reason
# alanları bu simülasyon platformu için temsili örnek veridir; resmi BİST Katılım
# Tüm (XKTUM) endeksinin güncel, canlı bileşen listesiyle birebir örtüşmeyebilir.
# Gerçek yatırım kararları için resmi kaynaklara (BİST, KAP, danışman kuruluşlar)
# başvurulmalıdır — bu veriler yatırım tavsiyesi değildir.
# ---------------------------------------------------------------------------
INITIAL_STOCKS = [
    # --- Orijinal 26 Katılım Finans ağırlıklı küçük/orta ölçek hisse ---
    {"symbol": "ALBRK", "company_name": "Albaraka Türk Katılım Bankası A.Ş.", "sector": "Bankacılık", "is_katilim_compliant": True, "purification_rate": 0.10, "non_compliance_reason": None},
    {"symbol": "BAHKM", "company_name": "Bahadır Kimya Sanayi ve Ticaret A.Ş.", "sector": "Kimya", "is_katilim_compliant": True, "purification_rate": 1.20, "non_compliance_reason": None},
    {"symbol": "BEGYO", "company_name": "Batı Ege Gayrimenkul Yatırım Ortaklığı A.Ş.", "sector": "GYO", "is_katilim_compliant": True, "purification_rate": 2.80, "non_compliance_reason": None},
    {"symbol": "BIMAS", "company_name": "BİM Birleşik Mağazalar A.Ş.", "sector": "Perakende", "is_katilim_compliant": True, "purification_rate": 1.40, "non_compliance_reason": None},
    {"symbol": "BINBN", "company_name": "Bin Ulaşım ve Akıllı Şehir Teknolojileri A.Ş.", "sector": "Teknoloji", "is_katilim_compliant": True, "purification_rate": 1.60, "non_compliance_reason": None},
    {"symbol": "BORSK", "company_name": "Bor Şeker A.Ş.", "sector": "Gıda", "is_katilim_compliant": True, "purification_rate": 0.90, "non_compliance_reason": None},
    {"symbol": "BOSSA", "company_name": "Bossa Ticaret ve Sanayi İşletmeleri T.A.Ş.", "sector": "Tekstil", "is_katilim_compliant": True, "purification_rate": 2.30, "non_compliance_reason": None},
    {"symbol": "CELHA", "company_name": "Çelik Halat ve Tel Sanayii A.Ş.", "sector": "Demir-Çelik", "is_katilim_compliant": True, "purification_rate": 1.10, "non_compliance_reason": None},
    {"symbol": "COSMO", "company_name": "Cosmos Yatırım Holding A.Ş.", "sector": "Holding", "is_katilim_compliant": True, "purification_rate": 3.00, "non_compliance_reason": None},
    {"symbol": "DARDL", "company_name": "Dardanel Önentaş Gıda Sanayi A.Ş.", "sector": "Gıda", "is_katilim_compliant": True, "purification_rate": 0.70, "non_compliance_reason": None},
    {"symbol": "DOFRB", "company_name": "Dof Robotik Sanayi A.Ş.", "sector": "Teknoloji", "is_katilim_compliant": True, "purification_rate": 1.90, "non_compliance_reason": None},
    {"symbol": "EBEBK", "company_name": "Ebebek Mağazacılık A.Ş.", "sector": "Perakende", "is_katilim_compliant": True, "purification_rate": 0.50, "non_compliance_reason": None},
    {"symbol": "EKSUN", "company_name": "Eksun Gıda Tarım Sanayi ve Ticaret A.Ş.", "sector": "Gıda", "is_katilim_compliant": True, "purification_rate": 1.30, "non_compliance_reason": None},
    {"symbol": "ESCOM", "company_name": "Escort Teknoloji Yatırım A.Ş.", "sector": "Teknoloji", "is_katilim_compliant": True, "purification_rate": 2.10, "non_compliance_reason": None},
    {"symbol": "FZLGY", "company_name": "Fuzul Gayrimenkul Yatırım Ortaklığı A.Ş.", "sector": "GYO", "is_katilim_compliant": True, "purification_rate": 2.60, "non_compliance_reason": None},
    {"symbol": "GUNDG", "company_name": "Gündoğdu Gıda Süt Ürünleri Sanayi ve Dış Ticaret A.Ş.", "sector": "Gıda", "is_katilim_compliant": True, "purification_rate": 0.80, "non_compliance_reason": None},
    {"symbol": "IZFAS", "company_name": "İzmir Fırça Sanayi ve Ticaret A.Ş.", "sector": "Sanayi", "is_katilim_compliant": True, "purification_rate": 1.00, "non_compliance_reason": None},
    {"symbol": "IZINV", "company_name": "İz Yatırım Holding A.Ş.", "sector": "Holding", "is_katilim_compliant": True, "purification_rate": 2.40, "non_compliance_reason": None},
    {"symbol": "KRGYO", "company_name": "Körfez Gayrimenkul Yatırım Ortaklığı A.Ş.", "sector": "GYO", "is_katilim_compliant": True, "purification_rate": 3.20, "non_compliance_reason": None},
    {"symbol": "KTLEV", "company_name": "Katılımevim Tasarruf Finansman A.Ş.", "sector": "Finansal Kiralama", "is_katilim_compliant": True, "purification_rate": 0.40, "non_compliance_reason": None},
    {"symbol": "KZBGY", "company_name": "Kızılbük Gayırmenkul Yatırım Ortaklığı A.Ş.", "sector": "GYO", "is_katilim_compliant": True, "purification_rate": 2.90, "non_compliance_reason": None},
    {"symbol": "LXGYO", "company_name": "Luxera Gayrimenkul Yatırım Ortaklığı A.Ş.", "sector": "GYO", "is_katilim_compliant": True, "purification_rate": 2.20, "non_compliance_reason": None},
    {"symbol": "MCARD", "company_name": "Metropal Kurumsal Hizmetler A.Ş.", "sector": "Hizmetler", "is_katilim_compliant": True, "purification_rate": 1.50, "non_compliance_reason": None},
    {"symbol": "MPARK", "company_name": "MLP Sağlık Hizmetleri A.Ş. (Medical Park)", "sector": "Sağlık", "is_katilim_compliant": True, "purification_rate": 1.80, "non_compliance_reason": None},
    {"symbol": "PENGD", "company_name": "Penguen Gıda Sanayi A.Ş.", "sector": "Gıda", "is_katilim_compliant": True, "purification_rate": 0.60, "non_compliance_reason": None},
    {"symbol": "YUNSA", "company_name": "Yünsa Yünlü Sanayi ve Ticaret A.Ş.", "sector": "Tekstil", "is_katilim_compliant": True, "purification_rate": 1.70, "non_compliance_reason": None},

    # --- BIST 100 / BIST Tüm ağırlıklı büyük ölçek hisseler ---
    {"symbol": "THYAO", "company_name": "Türk Hava Yolları A.O.", "sector": "Ulaştırma", "is_katilim_compliant": True, "purification_rate": 2.10, "non_compliance_reason": None},
    {"symbol": "EREGL", "company_name": "Ereğli Demir ve Çelik Fabrikaları T.A.Ş.", "sector": "Demir-Çelik", "is_katilim_compliant": True, "purification_rate": 1.80, "non_compliance_reason": None},
    {"symbol": "TUPRS", "company_name": "Türkiye Petrol Rafinerileri A.Ş.", "sector": "Enerji", "is_katilim_compliant": True, "purification_rate": 3.40, "non_compliance_reason": None},
    {"symbol": "ASELS", "company_name": "Aselsan Elektronik Sanayi ve Ticaret A.Ş.", "sector": "Savunma", "is_katilim_compliant": True, "purification_rate": 1.20, "non_compliance_reason": None},
    {"symbol": "SISE", "company_name": "Türkiye Şişe ve Cam Fabrikaları A.Ş.", "sector": "Sanayi", "is_katilim_compliant": True, "purification_rate": 2.50, "non_compliance_reason": None},
    {"symbol": "KCHOL", "company_name": "Koç Holding A.Ş.", "sector": "Holding", "is_katilim_compliant": False, "purification_rate": 0.00,
     "non_compliance_reason": "Grup bünyesindeki bankacılık/finans iştirakleri nedeniyle faiz geliri oranı Katılım Endeksi eşik değerini aşmaktadır."},
    {"symbol": "SAHOL", "company_name": "Hacı Ömer Sabancı Holding A.Ş.", "sector": "Holding", "is_katilim_compliant": False, "purification_rate": 0.00,
     "non_compliance_reason": "Grup bünyesindeki bankacılık faaliyetleri (Akbank) nedeniyle faiz geliri oranı kriterleri karşılamamaktadır."},
    {"symbol": "GARAN", "company_name": "Türkiye Garanti Bankası A.Ş.", "sector": "Bankacılık", "is_katilim_compliant": False, "purification_rate": 0.00,
     "non_compliance_reason": "Faiz bazlı mevduat bankacılığı faaliyeti yürütmektedir."},
    {"symbol": "AKBNK", "company_name": "Akbank T.A.Ş.", "sector": "Bankacılık", "is_katilim_compliant": False, "purification_rate": 0.00,
     "non_compliance_reason": "Faiz bazlı mevduat bankacılığı faaliyeti yürütmektedir."},
    {"symbol": "FROTO", "company_name": "Ford Otomotiv Sanayi A.Ş.", "sector": "Otomotiv", "is_katilim_compliant": True, "purification_rate": 1.50, "non_compliance_reason": None},
    {"symbol": "TOASO", "company_name": "Tofaş Türk Otomobil Fabrikası A.Ş.", "sector": "Otomotiv", "is_katilim_compliant": True, "purification_rate": 1.70, "non_compliance_reason": None},
    {"symbol": "SASA", "company_name": "Sasa Polyester Sanayi A.Ş.", "sector": "Kimya", "is_katilim_compliant": True, "purification_rate": 0.90, "non_compliance_reason": None},
    {"symbol": "HEKTS", "company_name": "Hektaş Ticaret T.A.Ş.", "sector": "Kimya", "is_katilim_compliant": True, "purification_rate": 0.60, "non_compliance_reason": None},
    {"symbol": "ENKAI", "company_name": "Enka İnşaat ve Sanayi A.Ş.", "sector": "İnşaat", "is_katilim_compliant": True, "purification_rate": 4.20, "non_compliance_reason": None},
    {"symbol": "PETKM", "company_name": "Petkim Petrokimya Holding A.Ş.", "sector": "Kimya", "is_katilim_compliant": True, "purification_rate": 2.00, "non_compliance_reason": None},
    {"symbol": "OYAKC", "company_name": "Oyak Çimento A.Ş.", "sector": "İnşaat", "is_katilim_compliant": True, "purification_rate": 1.10, "non_compliance_reason": None},
    {"symbol": "MGROS", "company_name": "Migros Ticaret A.Ş.", "sector": "Perakende", "is_katilim_compliant": False, "purification_rate": 0.00,
     "non_compliance_reason": "Toplam faizli borç / piyasa değeri oranı Katılım Endeksi eşik değerini aşmaktadır."},

    # --- BIST 100 / BIST Tüm geniş kapsam (2026-08-23'te eklendi) --------------
    # Katalog 43 hisseden 165'e çıkarıldı. Bu satırların şirket adı ve sektörü
    # UYDURULMADI: her sembol yfinance'e sorulup gerçekten veri dönenler
    # alındı, ad kaynaktan geldi, sektör ise yfinance "industry" alanından
    # açık bir eşleme tablosuyla mevcut Türkçe sözlüğe çevrildi.
    #
    # katilim_status = BELIRSIZ: bu hisseler için elle küratörlü katılım
    # uygunluğu verisi YOK. "Uygun değil" olarak işaretlemek yanlış bilgi
    # vermek olurdu; gerçek bilanço oranlarıyla ayrıca hesaplanacaklar.
    {"symbol": "ADEL", "company_name": "Adel Kalemcilik Ticaret ve Sanayi A.Ş.", "sector": "Sanayi", "katilim_status": "BELIRSIZ"},
    {"symbol": "AEFES", "company_name": "Anadolu Efes Biracilik ve Malt Sanayii A.Ş.", "sector": "Gıda", "katilim_status": "BELIRSIZ"},
    {"symbol": "AGHOL", "company_name": "AG Anadolu Grubu Holding A.Ş.", "sector": "Holding", "katilim_status": "BELIRSIZ"},
    {"symbol": "AGROT", "company_name": "AGROTECH TEKNOLOJI", "sector": "Holding", "katilim_status": "BELIRSIZ"},
    {"symbol": "AHGAZ", "company_name": "Ahlatci Dogal Gaz Dagitim Enerji ve Yatirim A.Ş.", "sector": "Enerji", "katilim_status": "BELIRSIZ"},
    {"symbol": "AKCNS", "company_name": "Akçansa Çimento Sanayi ve Ticaret A.Ş.", "sector": "İnşaat", "katilim_status": "BELIRSIZ"},
    {"symbol": "AKFGY", "company_name": "Akfen Gayrimenkul Yatirim Ortakligi A.Ş.", "sector": "GYO", "katilim_status": "BELIRSIZ"},
    {"symbol": "AKFYE", "company_name": "Akfen Yenilenebilir Enerji A.Ş.", "sector": "Enerji", "katilim_status": "BELIRSIZ"},
    {"symbol": "AKSA", "company_name": "Aksa Akrilik Kimya Sanayii A.Ş.", "sector": "Tekstil", "katilim_status": "BELIRSIZ"},
    {"symbol": "AKSEN", "company_name": "Aksa Enerji Üretim A.Ş.", "sector": "Enerji", "katilim_status": "BELIRSIZ"},
    {"symbol": "AKSGY", "company_name": "Akis Gayrimenkul Yatirim Ortakligi A.Ş.", "sector": "GYO", "katilim_status": "BELIRSIZ"},
    {"symbol": "ALARK", "company_name": "Alarko Holding A.Ş.", "sector": "Holding", "katilim_status": "BELIRSIZ"},
    {"symbol": "ALCTL", "company_name": "Alcatel Lucent Teletas Telekomünikasyon A.Ş.", "sector": "Teknoloji", "katilim_status": "BELIRSIZ"},
    {"symbol": "ALFAS", "company_name": "Alfa Solar Enerji Sanayi ve Ticaret A.Ş.", "sector": "Enerji", "katilim_status": "BELIRSIZ"},
    {"symbol": "ALTNY", "company_name": "ALTINAY SAVUNMA", "sector": "Savunma", "katilim_status": "BELIRSIZ"},
    {"symbol": "ANHYT", "company_name": "Anadolu Hayat Emeklilik A.Ş.", "sector": "Sigorta", "katilim_status": "BELIRSIZ"},
    {"symbol": "ANSGR", "company_name": "Anadolu Anonim Türk Sigorta Sirketi", "sector": "Sigorta", "katilim_status": "BELIRSIZ"},
    {"symbol": "ARCLK", "company_name": "Arçelik A.Ş.", "sector": "Sanayi", "katilim_status": "BELIRSIZ"},
    {"symbol": "ARDYZ", "company_name": "Ard Grup Bilisim Teknolojileri A.Ş.", "sector": "Teknoloji", "katilim_status": "BELIRSIZ"},
    {"symbol": "ARENA", "company_name": "Arena Bilgisayar Sanayi ve Ticaret A.Ş.", "sector": "Perakende", "katilim_status": "BELIRSIZ"},
    {"symbol": "ASTOR", "company_name": "Astor Enerji A.Ş.", "sector": "Sanayi", "katilim_status": "BELIRSIZ"},
    {"symbol": "AYDEM", "company_name": "Aydem Yenilenebilir Enerji A.Ş.", "sector": "Enerji", "katilim_status": "BELIRSIZ"},
    {"symbol": "AYGAZ", "company_name": "Aygaz A.Ş.", "sector": "Enerji", "katilim_status": "BELIRSIZ"},
    {"symbol": "BASGZ", "company_name": "Baskent Dogalgaz Dagitim Gayrimenkul Yatirim Ortakligi A.Ş.", "sector": "Enerji", "katilim_status": "BELIRSIZ"},
    {"symbol": "BERA", "company_name": "Bera Holding A.Ş.", "sector": "Holding", "katilim_status": "BELIRSIZ"},
    {"symbol": "BIENY", "company_name": "Bien Yapi Urunleri Sanayi Turizm ve Ticaret A.Ş.", "sector": "İnşaat", "katilim_status": "BELIRSIZ"},
    {"symbol": "BIOEN", "company_name": "Biotrend Cevre ve Enerji Yatirimlari A.Ş.", "sector": "Enerji", "katilim_status": "BELIRSIZ"},
    {"symbol": "BRISA", "company_name": "Brisa Bridgestone Sabanci Lastik Sanayi ve Ticaret A.Ş.", "sector": "Otomotiv", "katilim_status": "BELIRSIZ"},
    {"symbol": "BRSAN", "company_name": "Borusan Birlesik Boru Fabrikalari Sanayi ve Ticaret A.Ş.", "sector": "Demir-Çelik", "katilim_status": "BELIRSIZ"},
    {"symbol": "BRYAT", "company_name": "Borusan Yatirim ve Pazarlama A.Ş.", "sector": "Demir-Çelik", "katilim_status": "BELIRSIZ"},
    {"symbol": "BUCIM", "company_name": "Bursa Cimento Fabrikasi A.Ş.", "sector": "İnşaat", "katilim_status": "BELIRSIZ"},
    {"symbol": "CANTE", "company_name": "Çan2 Termik A.Ş.", "sector": "Enerji", "katilim_status": "BELIRSIZ"},
    {"symbol": "CCOLA", "company_name": "Coca-Cola Içecek A.Ş.", "sector": "Gıda", "katilim_status": "BELIRSIZ"},
    {"symbol": "CIMSA", "company_name": "Çimsa Çimento Sanayi ve Ticaret A.Ş.", "sector": "İnşaat", "katilim_status": "BELIRSIZ"},
    {"symbol": "CLEBI", "company_name": "Çelebi Hava Servisi A.Ş.", "sector": "Ulaştırma", "katilim_status": "BELIRSIZ"},
    {"symbol": "CVKMD", "company_name": "CVK Maden Isletmeleri Sanayi ve Ticaret A.Ş.", "sector": "Madencilik", "katilim_status": "BELIRSIZ"},
    {"symbol": "CWENE", "company_name": "CW Enerji Mühendislik Ticaret ve Sanayi A.Ş.", "sector": "Enerji", "katilim_status": "BELIRSIZ"},
    {"symbol": "DEVA", "company_name": "Deva Holding A.Ş.", "sector": "Sağlık", "katilim_status": "BELIRSIZ"},
    {"symbol": "DOAS", "company_name": "Dogus Otomotiv Servis ve Ticaret A.Ş.", "sector": "Otomotiv", "katilim_status": "BELIRSIZ"},
    {"symbol": "DOHOL", "company_name": "Dogan Sirketler Grubu Holding A.Ş.", "sector": "Holding", "katilim_status": "BELIRSIZ"},
    {"symbol": "ECILC", "company_name": "EIS Eczacibasi Ilaç, Sinai ve Finansal Yatirimlar Sanayi ve Ticaret A.Ş.", "sector": "Sağlık", "katilim_status": "BELIRSIZ"},
    {"symbol": "ECZYT", "company_name": "Eczacibasi Yatirim Holding Ortakligi A.Ş.", "sector": "Holding", "katilim_status": "BELIRSIZ"},
    {"symbol": "EGEEN", "company_name": "Ege Endüstri ve Ticaret A.Ş.", "sector": "Otomotiv", "katilim_status": "BELIRSIZ"},
    {"symbol": "EGGUB", "company_name": "Ege Gübre Sanayii A.Ş.", "sector": "Ulaştırma", "katilim_status": "BELIRSIZ"},
    {"symbol": "ENERY", "company_name": "Enerya Enerji A.Ş.", "sector": "Enerji", "katilim_status": "BELIRSIZ"},
    {"symbol": "ENJSA", "company_name": "Enerjisa Enerji A.Ş.", "sector": "Enerji", "katilim_status": "BELIRSIZ"},
    {"symbol": "EUPWR", "company_name": "Europower Enerji ve Otomasyon Teknolojileri Sanayi Ticaret A.Ş.", "sector": "Sanayi", "katilim_status": "BELIRSIZ"},
    {"symbol": "FENER", "company_name": "Fenerbahçe Futbol A.Ş.", "sector": "Medya", "katilim_status": "BELIRSIZ"},
    {"symbol": "GENIL", "company_name": "Gen Ilac Ve Saglik Urunleri Sanayi Ve Ticaret A.Ş.", "sector": "Sağlık", "katilim_status": "BELIRSIZ"},
    {"symbol": "GESAN", "company_name": "Girisim Elektrik Sanayi Taahhüt ve Ticaret A.Ş.", "sector": "İnşaat", "katilim_status": "BELIRSIZ"},
    {"symbol": "GLYHO", "company_name": "Global Yatirim Holding A.Ş.", "sector": "Holding", "katilim_status": "BELIRSIZ"},
    {"symbol": "GUBRF", "company_name": "Gübre Fabrikalari Türk A.Ş.", "sector": "Kimya", "katilim_status": "BELIRSIZ"},
    {"symbol": "GWIND", "company_name": "Galata Wind Enerji A.Ş.", "sector": "Enerji", "katilim_status": "BELIRSIZ"},
    {"symbol": "HALKB", "company_name": "Türkiye Halk Bankasi A.Ş.", "sector": "Bankacılık", "katilim_status": "BELIRSIZ"},
    {"symbol": "HATSN", "company_name": "Hat-San Gemi Insaa Bakim Onarim Deniz Nakliyat Sanayi ve Ticaret A.Ş.", "sector": "Savunma", "katilim_status": "BELIRSIZ"},
    {"symbol": "HLGYO", "company_name": "Halk Gayrimenkul Yatirim Ortakligi A.S", "sector": "GYO", "katilim_status": "BELIRSIZ"},
    {"symbol": "HRKET", "company_name": "Hareket Proje Tasimaciligi Ve Yuk Muhendisligi A.Ş.", "sector": "İnşaat", "katilim_status": "BELIRSIZ"},
    {"symbol": "INVEO", "company_name": "Inveo Yatirim Holding A.Ş.", "sector": "Aracı Kurum", "katilim_status": "BELIRSIZ"},
    {"symbol": "ISCTR", "company_name": "Türkiye Is Bankasi A.Ş.", "sector": "Bankacılık", "katilim_status": "BELIRSIZ"},
    {"symbol": "ISDMR", "company_name": "Iskenderun Demir ve Çelik A.Ş.", "sector": "Demir-Çelik", "katilim_status": "BELIRSIZ"},
    {"symbol": "ISGYO", "company_name": "Is Gayrimenkul Yatirim Ortakligi A.Ş.", "sector": "GYO", "katilim_status": "BELIRSIZ"},
    {"symbol": "ISMEN", "company_name": "Is Yatirim Menkul Degerler A.Ş.", "sector": "Aracı Kurum", "katilim_status": "BELIRSIZ"},
    {"symbol": "IZMDC", "company_name": "Izmir Demir Çelik Sanayi A.Ş.", "sector": "Demir-Çelik", "katilim_status": "BELIRSIZ"},
    {"symbol": "JANTS", "company_name": "Jantsa Jant Sanayi ve Ticaret A.Ş.", "sector": "Otomotiv", "katilim_status": "BELIRSIZ"},
    {"symbol": "KARSN", "company_name": "Karsan Otomotiv Sanayii ve Ticaret A.Ş.", "sector": "Sanayi", "katilim_status": "BELIRSIZ"},
    {"symbol": "KARTN", "company_name": "Kartonsan Karton Sanayi ve Ticaret A.Ş.", "sector": "Sanayi", "katilim_status": "BELIRSIZ"},
    {"symbol": "KCAER", "company_name": "Kocaer Celik Sanayi ve Ticaret A.Ş.", "sector": "Demir-Çelik", "katilim_status": "BELIRSIZ"},
    {"symbol": "KLKIM", "company_name": "Kalekim Kimyevi Maddeler Sanayi Ve Ticaret A.Ş.", "sector": "Kimya", "katilim_status": "BELIRSIZ"},
    {"symbol": "KLSER", "company_name": "Kaleseramik Canakkale Kalebodur Seramik Sanayi A.Ş.", "sector": "İnşaat", "katilim_status": "BELIRSIZ"},
    {"symbol": "KMPUR", "company_name": "Kimteks Poliüretan Sanayi ve Ticaret A.Ş.", "sector": "Kimya", "katilim_status": "BELIRSIZ"},
    {"symbol": "KONTR", "company_name": "Kontrolmatik Teknoloji Enerji Ve Muhendislik A.Ş.", "sector": "Holding", "katilim_status": "BELIRSIZ"},
    {"symbol": "KONYA", "company_name": "Konya Çimento Sanayii A.Ş.", "sector": "İnşaat", "katilim_status": "BELIRSIZ"},
    {"symbol": "KRDMD", "company_name": "Kardemir Karabük Demir Çelik Sanayi Ve Ticaret A.Ş.", "sector": "Demir-Çelik", "katilim_status": "BELIRSIZ"},
    {"symbol": "LMKDC", "company_name": "LIMAK DOGU ANADOLU", "sector": "İnşaat", "katilim_status": "BELIRSIZ"},
    {"symbol": "LOGO", "company_name": "Logo Yazilim Sanayi ve Ticaret A.Ş.", "sector": "Teknoloji", "katilim_status": "BELIRSIZ"},
    {"symbol": "MAGEN", "company_name": "Margün Enerji Üretim Sanayi ve Ticaret A.Ş.", "sector": "Enerji", "katilim_status": "BELIRSIZ"},
    {"symbol": "MAVI", "company_name": "Mavi Giyim Sanayi ve Ticaret A.Ş.", "sector": "Perakende", "katilim_status": "BELIRSIZ"},
    {"symbol": "MIATK", "company_name": "MIA Teknoloji A.Ş.", "sector": "Teknoloji", "katilim_status": "BELIRSIZ"},
    {"symbol": "NETAS", "company_name": "Netas Telekomünikasyon A.Ş.", "sector": "Teknoloji", "katilim_status": "BELIRSIZ"},
    {"symbol": "NTHOL", "company_name": "Net Holding A.Ş.", "sector": "Turizm", "katilim_status": "BELIRSIZ"},
    {"symbol": "OBAMS", "company_name": "OBA MAKARNACILIK", "sector": "Gıda", "katilim_status": "BELIRSIZ"},
    {"symbol": "ODAS", "company_name": "Odas Elektrik Üretim Sanayi Ticaret A.Ş.", "sector": "Enerji", "katilim_status": "BELIRSIZ"},
    {"symbol": "OTKAR", "company_name": "Otokar Otomotiv ve Savunma Sanayi A.Ş.", "sector": "Otomotiv", "katilim_status": "BELIRSIZ"},
    {"symbol": "PAPIL", "company_name": "Papilon Savunma Teknoloji ve Ticaret A.Ş.", "sector": "İnşaat", "katilim_status": "BELIRSIZ"},
    {"symbol": "PARSN", "company_name": "Parsan Makina Parçalari Sanayii A.Ş.", "sector": "Otomotiv", "katilim_status": "BELIRSIZ"},
    {"symbol": "PEKGY", "company_name": "Peker Gayrimenkul Yatirim Ortakligi A.Ş.", "sector": "GYO", "katilim_status": "BELIRSIZ"},
    {"symbol": "PGSUS", "company_name": "Pegasus Hava Tasimaciligi A.Ş.", "sector": "Ulaştırma", "katilim_status": "BELIRSIZ"},
    {"symbol": "PRKME", "company_name": "Park Elektrik Üretim Madencilik Sanayi ve Ticaret A.Ş.", "sector": "Madencilik", "katilim_status": "BELIRSIZ"},
    {"symbol": "PSGYO", "company_name": "Pasifik Gayrimenkul Yatirim Ortakligi A.Ş.", "sector": "GYO", "katilim_status": "BELIRSIZ"},
    {"symbol": "QUAGR", "company_name": "QUA Granite Hayal Yapi ve Ürünleri Sanayi Ticaret A.Ş.", "sector": "İnşaat", "katilim_status": "BELIRSIZ"},
    {"symbol": "REEDR", "company_name": "Reeder Teknoloji Sanayi ve Ticaret A.Ş.", "sector": "Perakende", "katilim_status": "BELIRSIZ"},
    {"symbol": "SARKY", "company_name": "Sarkuysan Elektrolitik Bakir Sanayi ve Ticaret A.Ş.", "sector": "Madencilik", "katilim_status": "BELIRSIZ"},
    {"symbol": "SDTTR", "company_name": "SDT Uzay ve Savunma Teknolojileri A.Ş.", "sector": "Savunma", "katilim_status": "BELIRSIZ"},
    {"symbol": "SELEC", "company_name": "Selçuk Ecza Deposu Ticaret ve Sanayi A.Ş.", "sector": "Sağlık", "katilim_status": "BELIRSIZ"},
    {"symbol": "SKBNK", "company_name": "Sekerbank T.A.S.", "sector": "Bankacılık", "katilim_status": "BELIRSIZ"},
    {"symbol": "SMRTG", "company_name": "Smart Günes Enerjisi Teknolojileri Arastirma ve Gelistirme Üretim Sanayi ve Ticaret A.Ş.", "sector": "Enerji", "katilim_status": "BELIRSIZ"},
    {"symbol": "SNGYO", "company_name": "Sinpas Gayrimenkul Yatirim Ortakligi A.Ş.", "sector": "GYO", "katilim_status": "BELIRSIZ"},
    {"symbol": "SOKM", "company_name": "Sok Marketler Ticaret A.Ş.", "sector": "Perakende", "katilim_status": "BELIRSIZ"},
    {"symbol": "TABGD", "company_name": "TAB GIDA", "sector": "Gıda", "katilim_status": "BELIRSIZ"},
    {"symbol": "TATGD", "company_name": "Tat Gida Sanayi A.Ş.", "sector": "Gıda", "katilim_status": "BELIRSIZ"},
    {"symbol": "TAVHL", "company_name": "TAV Havalimanlari Holding A.Ş.", "sector": "Ulaştırma", "katilim_status": "BELIRSIZ"},
    {"symbol": "TCELL", "company_name": "Turkcell Iletisim Hizmetleri A.Ş.", "sector": "Telekomünikasyon", "katilim_status": "BELIRSIZ"},
    {"symbol": "TKFEN", "company_name": "Tekfen Holding A.Ş.", "sector": "Kimya", "katilim_status": "BELIRSIZ"},
    {"symbol": "TMSN", "company_name": "Tümosan Motor ve Traktör Sanayi A.Ş.", "sector": "Sanayi", "katilim_status": "BELIRSIZ"},
    {"symbol": "TRGYO", "company_name": "Torunlar Gayrimenkul Yatirim Ortakligi A.Ş.", "sector": "GYO", "katilim_status": "BELIRSIZ"},
    {"symbol": "TSKB", "company_name": "Türkiye Sinai Kalkinma Bankasi A.Ş.", "sector": "Bankacılık", "katilim_status": "BELIRSIZ"},
    {"symbol": "TTKOM", "company_name": "Türk Telekomünikasyon A.Ş.", "sector": "Telekomünikasyon", "katilim_status": "BELIRSIZ"},
    {"symbol": "TTRAK", "company_name": "Türk Traktör ve Ziraat Makineleri A.Ş.", "sector": "Sanayi", "katilim_status": "BELIRSIZ"},
    {"symbol": "TUCLK", "company_name": "Tugçelik Alüminyum Ve Metal Mamulleri Sanayi Ve Ticaret A.Ş.", "sector": "Sanayi", "katilim_status": "BELIRSIZ"},
    {"symbol": "TUKAS", "company_name": "Tukas Gida Sanayi ve Ticaret A.Ş.", "sector": "Gıda", "katilim_status": "BELIRSIZ"},
    {"symbol": "TURSG", "company_name": "Türkiye Sigorta A.Ş.", "sector": "Sigorta", "katilim_status": "BELIRSIZ"},
    {"symbol": "ULKER", "company_name": "Ülker Bisküvi Sanayi A.Ş.", "sector": "Gıda", "katilim_status": "BELIRSIZ"},
    {"symbol": "ULUUN", "company_name": "Ulusoy Un Sanayi ve Ticaret A.Ş.", "sector": "Gıda", "katilim_status": "BELIRSIZ"},
    {"symbol": "USAK", "company_name": "Usak Seramik Sanayi A.Ş.", "sector": "İnşaat", "katilim_status": "BELIRSIZ"},
    {"symbol": "VAKBN", "company_name": "Türkiye Vakiflar Bankasi Türk A.O.", "sector": "Bankacılık", "katilim_status": "BELIRSIZ"},
    {"symbol": "VAKKO", "company_name": "Vakko Tekstil ve Hazir Giyim Sanayi Isletmeleri A.Ş.", "sector": "Tekstil", "katilim_status": "BELIRSIZ"},
    {"symbol": "VESBE", "company_name": "Vestel Beyaz Esya Sanayi ve Ticaret A.Ş.", "sector": "Sanayi", "katilim_status": "BELIRSIZ"},
    {"symbol": "VESTL", "company_name": "Vestel Elektronik Sanayi ve Ticaret A.Ş.", "sector": "Sanayi", "katilim_status": "BELIRSIZ"},
    {"symbol": "YEOTK", "company_name": "Yeo Teknoloji Enerji Ve Endustri A.Ş.", "sector": "İnşaat", "katilim_status": "BELIRSIZ"},
    {"symbol": "YKBNK", "company_name": "Yapi ve Kredi Bankasi A.Ş.", "sector": "Bankacılık", "katilim_status": "BELIRSIZ"},
    {"symbol": "YYLGD", "company_name": "Yayla Agro Gida Sanayi ve Ticaret A.Ş.", "sector": "Gıda", "katilim_status": "BELIRSIZ"},
    {"symbol": "ZOREN", "company_name": "Zorlu Enerji Elektrik Üretim A.Ş.", "sector": "Enerji", "katilim_status": "BELIRSIZ"},
]

# Var olan tablolara sonradan eklenen kolonlar (SQLite ALTER TABLE ADD COLUMN destekler;
# create_all() zaten var olan tabloları güncellemediği için elle taşınır)
MIGRATIONS = {
    "users": {
        "baseline_value": "NUMERIC(15, 2) DEFAULT 100000.00",
    },
    "watchlist": {
        "target_price": "NUMERIC(10, 2)",
        "note": "VARCHAR(280)",
        "updated_at": "TIMESTAMP",
    },
    "stocks": {
        "is_katilim_compliant": "INTEGER DEFAULT 0",
        "purification_rate": "NUMERIC(5, 2) DEFAULT 0.00",
        "non_compliance_reason": "TEXT",
        "sector": "TEXT",
        "previous_close": "NUMERIC(10, 2)",
        "open_price": "NUMERIC(10, 2)",
        "day_high": "NUMERIC(10, 2)",
        "day_low": "NUMERIC(10, 2)",
        "katilim_status": "VARCHAR(12) DEFAULT 'BELIRSIZ'",
        "katilim_debt_ratio": "NUMERIC(6, 2)",
        "katilim_asset_ratio": "NUMERIC(6, 2)",
        "katilim_checked_at": "TIMESTAMP",
        "katilim_detail": "TEXT",
    },
    "index_history": {
        # Gun ici tazeleme: doviz/altin artik 15 dakikada bir guncelleniyor.
        "updated_at": "TIMESTAMP",
        "source": "VARCHAR(20)",
        "change_1d_pct": "NUMERIC(6, 2)",
    },
    "financial_statements": {
        "long_term_debt": "NUMERIC(20, 2)",
        "current_debt": "NUMERIC(20, 2)",
        "cash_and_equivalents": "NUMERIC(20, 2)",
        "short_term_investments": "NUMERIC(20, 2)",
    },
    "company_analysis": {
        # Temettü alanları (portföy temettü geliri projeksiyonu için).
        # DİKKAT: bu alanlar MEVCUT company_analysis bloğunun içine yazılmalıdır —
        # sözlüğe ikinci bir "company_analysis" anahtarı eklenirse Python yinelenen
        # anahtarı sessizce ezer (sonraki kazanır) ve migration hiç çalışmaz.
        "fifty_two_week_high": "NUMERIC(12, 2)",
        "fifty_two_week_low": "NUMERIC(12, 2)",
        "market_cap": "NUMERIC(20, 2)",
        "average_volume": "BIGINT",
        "dividend_yield": "NUMERIC(6, 2)",
        "dividend_rate": "NUMERIC(10, 2)",
        "last_dividend_date": "DATE",
        "ev_ebitda": "NUMERIC(10, 2)",
        "roe": "NUMERIC(6, 2)",
        "gross_margin": "NUMERIC(6, 2)",
        "net_margin": "NUMERIC(6, 2)",
        "fx_exposure_text": "TEXT",
        "interest_sensitivity_text": "TEXT",
        "altman_z_score": "NUMERIC(6, 2)",
        "altman_zone": "TEXT",
        "debt_to_equity": "NUMERIC(8, 2)",
        "net_fx_position": "TEXT",
        "target_mean_price": "NUMERIC(10, 2)",
        "target_high_price": "NUMERIC(10, 2)",
        "target_low_price": "NUMERIC(10, 2)",
        "target_upside_pct": "NUMERIC(6, 2)",
        "number_of_analysts": "INTEGER",
        "recommendation_key": "TEXT",
        "analyst_buy_count": "INTEGER",
        "analyst_hold_count": "INTEGER",
        "analyst_sell_count": "INTEGER",
        "next_earnings_date": "DATE",
    },
    "user_bots": {
        "time_frame": "TEXT DEFAULT '1D'",
        "started_at": "TEXT",
        "ends_at": "TEXT",
        "baseline_value": "NUMERIC(15, 2) DEFAULT 100000.00",
        "performance_reset_at": "TEXT",
    },
    "portfolios": {
        "opened_at": "TEXT",
        "updated_at": "TEXT",
    },
    "bot_logs": {
        # İşlem anındaki bot zaman dilimi ('1D'/'1W'/'1M') — oturum bazlı
        # işlem günlüğü için sonradan eklendi, eski kayıtlarda NULL kalır.
        "time_frame": "VARCHAR(5)",
    },
}


def run_migrations():
    """
    Var olan tablolara eksik kolonları ekler. Tablo henüz yoksa create_all zaten doğru
    şemayla oluşturacaktır. SQLAlchemy inspector kullanıldığı için hem SQLite hem
    Postgres'te çalışır — Postgres'te (production) tablo daha önce create_all ile
    oluşturulmuş olsa bile, sonradan models.py'a eklenen yeni kolonlar create_all
    tarafından EKLENMEZ (create_all yalnızca eksik TABLOLARI oluşturur, var olan
    tablolara kolon eklemez); bu yüzden bu fonksiyon her ortamda çalıştırılmalıdır.
    """
    inspector = inspect(engine)
    with engine.connect() as conn:
        for table_name, column_defs in MIGRATIONS.items():
            if not inspector.has_table(table_name):
                continue
            existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
            for column_name, ddl in column_defs.items():
                if column_name not in existing_columns:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))
                    print(f"'{table_name}' tablosuna '{column_name}' kolonu eklendi.")
        conn.commit()


                                                                    # noqa: E302
# Sorgu planında fark yaratan, model tanımlarında bulunmayan ek indeksler.
# (ad, tablo, kolonlar) — CREATE INDEX IF NOT EXISTS ile idempotent uygulanır.
PERFORMANCE_INDEXES = [
    # stock_prices en büyük tablo (50k+ satır) ve EN SIK sorgu şu desende:
    #   filter_by(stock_id=X).order_by(recorded_at.desc()).first()
    # stock_id'de indeks YOKTU; yalnızca recorded_at vardı. Bileşik indeks hem
    # filtreyi hem sıralamayı tek geçişte karşılar. Bu sorgu her sayfa
    # yüklemesinde her hisse için çalıştığı için etkisi doğrudan hissedilir.
    ("ix_stock_prices_stock_recorded", "stock_prices", "stock_id, recorded_at DESC"),
    # KAP bildirimleri artık canlı çekim yerine bu tablodan sembole göre
    # servis ediliyor (bkz. get_kap_disclosures) — sembol indekslenmeliydi.
    ("ix_kap_notifications_symbol_date", "kap_notifications", "symbol, publish_date DESC"),
    # index_history: sembol + tarih ile sorgulanıyor (benchmark, döviz/altın).
    ("ix_index_history_symbol_date", "index_history", "symbol, trade_date DESC"),
]


def create_performance_indexes():
    """
    Model tanımlarında olmayan ama sorgu planında fark yaratan indeksleri oluşturur.

    create_all() yalnızca model üzerinde tanımlı indeksleri kurar; buradakiler
    bileşik (composite) ve sıralama yönü belirtilen indeksler olduğu için ayrı
    ele alınır. IF NOT EXISTS sayesinde her açılışta güvenle çalışır.
    """
    inspector = inspect(engine)
    with engine.connect() as conn:
        for name, table, columns in PERFORMANCE_INDEXES:
            if not inspector.has_table(table):
                continue
            try:
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})"))
            except Exception as e:
                # Tek bir indeksin başarısız olması açılışı engellememeli.
                print(f"[Index] '{name}' oluşturulamadı: {e}")
        conn.commit()


def migrate_volume_to_bigint():
    """
    stock_prices.volume ve stock_prices_daily.volume kolonlarını BIGINT'e yükseltir.

    Neden gerekli: BIST'te yüksek hacimli hisselerde günlük lot adedi Postgres
    integer (int4) üst sınırını (2.147.483.647) aşıyor ve günlük geçmiş tazeleme
    "psycopg2.errors.NumericValueOutOfRange: integer out of range" ile patlıyordu.

    Yalnızca Postgres'te çalışır: SQLite'ın INTEGER'ı zaten 64 bittir, orada
    yapılacak bir şey yoktur. Kolon tipi değişikliği MIGRATIONS sözlüğüyle
    yapılamaz (o yalnızca eksik kolon EKLER), bu yüzden ayrı ele alınır.
    """
    if engine.dialect.name != "postgresql":
        return

    inspector = inspect(engine)
    with engine.connect() as conn:
        for table_name in ("stock_prices", "stock_prices_daily"):
            if not inspector.has_table(table_name):
                continue
            for col in inspector.get_columns(table_name):
                if col["name"] != "volume":
                    continue
                # Zaten BIGINT ise dokunma (idempotent olmalı: her açılışta çalışıyor).
                if "BIGINT" in str(col["type"]).upper():
                    continue
                conn.execute(text(
                    f"ALTER TABLE {table_name} ALTER COLUMN volume TYPE BIGINT"
                ))
                print(f"'{table_name}.volume' kolonu BIGINT'e yükseltildi.")
        conn.commit()


def migrate_portfolios_table():
    """
    'portfolios' tablosunu is_bot_portfolio kolonu ve (user_id, stock_id, is_bot_portfolio)
    UNIQUE kısıtıyla yeniden oluşturur. SQLite'ta var olan bir UNIQUE kısıtını ALTER TABLE
    ile değiştirmek mümkün olmadığından, tablo yeniden inşa edilir (rebuild) ve veriler
    is_bot_portfolio=0 (kullanıcı manuel pozisyonu) varsayımıyla taşınır.
    """
    with engine.connect() as conn:
        existing_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(portfolios)"))}
        if not existing_columns:
            return  # Tablo henüz yok; create_all doğru şemayla oluşturacak
        if "is_bot_portfolio" in existing_columns:
            return  # Zaten migrate edilmiş

        conn.execute(text("""
            CREATE TABLE portfolios_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                stock_id INTEGER NOT NULL,
                quantity REAL NOT NULL,
                average_cost REAL NOT NULL,
                is_bot_portfolio INTEGER DEFAULT 0 NOT NULL,
                UNIQUE(user_id, stock_id, is_bot_portfolio),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(stock_id) REFERENCES stocks(id)
            )
        """))
        conn.execute(text("""
            INSERT INTO portfolios_new (id, user_id, stock_id, quantity, average_cost, is_bot_portfolio)
            SELECT id, user_id, stock_id, quantity, average_cost, 0 FROM portfolios
        """))
        conn.execute(text("DROP TABLE portfolios"))
        conn.execute(text("ALTER TABLE portfolios_new RENAME TO portfolios"))
        conn.commit()
        print("'portfolios' tablosu is_bot_portfolio kolonu ile yeniden oluşturuldu.")


BOT_TIME_FRAME_DURATIONS = {
    "1D": timedelta(days=1),
    "1W": timedelta(weeks=1),
    "1M": timedelta(days=30),
}


def seed_user_bots(db):
    """Bot olmayan (is_bot=False) her kullanıcı için kişisel AI botu kaydı oluşturur."""
    users = db.query(models.User).filter_by(is_bot=False).all()
    created = 0
    now = datetime.utcnow()
    for user in users:
        exists = db.query(models.UserBot).filter_by(user_id=user.id).first()
        if not exists:
            db.add(models.UserBot(
                user_id=user.id,
                bot_name=f"{user.username} — Kişisel AI Bot",
                virtual_balance=100000.00,
                is_active=True,
                risk_profile="normal",
                time_frame="1D",
                started_at=now,
                ends_at=now + BOT_TIME_FRAME_DURATIONS["1D"],
            ))
            created += 1
    db.commit()
    if created:
        print(f"{created} kullanıcı için kişisel AI Bot kaydı oluşturuldu.")


def backfill_portfolio_timestamps(db):
    """Migration sonrası opened_at/updated_at boş kalan mevcut portfolios satırlarını doldurur."""
    now = datetime.utcnow()
    rows = db.query(models.Portfolio).filter(models.Portfolio.opened_at.is_(None)).all()
    for row in rows:
        row.opened_at = now
        row.updated_at = now
    if rows:
        db.commit()
        print(f"{len(rows)} portföy pozisyonu için tarih (opened_at/updated_at) bilgisi dolduruldu.")


def backfill_user_bot_durations(db):
    """Migration sonrası started_at/ends_at boş kalan mevcut user_bots satırlarını doldurur."""
    now = datetime.utcnow()
    bots = db.query(models.UserBot).filter(models.UserBot.started_at.is_(None)).all()
    for ub in bots:
        tf = ub.time_frame or "1D"
        ub.started_at = now
        ub.ends_at = now + BOT_TIME_FRAME_DURATIONS.get(tf, BOT_TIME_FRAME_DURATIONS["1D"])
    if bots:
        db.commit()
        print(f"{len(bots)} kişisel bot için süre (started_at/ends_at) bilgisi dolduruldu.")


def init_database():
    print("Veritabanı tabloları oluşturuluyor...")
    if IS_SQLITE:
        # UNIQUE kısıtı değişikliği gerektiren bu tam tablo yeniden inşası (rebuild)
        # yalnızca SQLite'a özgü bir sorunu (ALTER TABLE ile UNIQUE eklenememesi) çözer;
        # Postgres'teki portfolios tablosu zaten doğru şemayla oluşturulmuştur.
        migrate_portfolios_table()
    # run_migrations() hem SQLite hem Postgres'te çalışır: create_all() yalnızca EKSİK
    # TABLOLARI oluşturur, var olan bir tabloya sonradan eklenen kolonları eklemez —
    # bu yüzden production'daki (Postgres) var olan tablolar için de gereklidir.
    run_migrations()
    # Kolon TİPİ değişiklikleri run_migrations kapsamında değildir (o yalnızca
    # eksik kolon ekler), bu yüzden ayrı çağrılır.
    migrate_volume_to_bigint()
    Base.metadata.create_all(bind=engine)
    # Indeksler tablolar olustuktan SONRA kurulmali.
    create_performance_indexes()

    db = SessionLocal()
    try:
        # 1. Seed / güncelle stocks (katılım endeksi bilgileri dahil)
        eklenen = guncellenen = 0
        for stock_data in INITIAL_STOCKS:
            # Tohum listesi iki tür satır içerir:
            #  - KÜRATÖRLÜ: is_katilim_compliant / purification_rate elle girilmiş.
            #  - KAPSAM: yalnızca sembol/ad/sektör; katılım durumu BELİRSİZ.
            # Bu yüzden alanlar .get() ile okunur.
            kuratorlu = "is_katilim_compliant" in stock_data
            durum = stock_data.get(
                "katilim_status",
                ("UYGUN" if stock_data.get("is_katilim_compliant") else "UYGUN_DEGIL") if kuratorlu else "BELIRSIZ",
            )

            exists = db.query(models.Stock).filter_by(symbol=stock_data["symbol"]).first()
            if not exists:
                db.add(models.Stock(
                    symbol=stock_data["symbol"],
                    company_name=stock_data["company_name"],
                    is_active=True,
                    sector=stock_data["sector"],
                    is_katilim_compliant=bool(stock_data.get("is_katilim_compliant", False)),
                    purification_rate=stock_data.get("purification_rate", 0.00),
                    non_compliance_reason=stock_data.get("non_compliance_reason"),
                    katilim_status=durum,
                ))
                eklenen += 1
            else:
                exists.company_name = stock_data["company_name"]
                exists.is_active = True
                exists.sector = stock_data["sector"]
                # Katılım alanları YALNIZCA küratörlü satırlardan güncellenir.
                # Aksi halde her uygulama açılışında, sonradan gerçek bilanço
                # oranlarıyla hesaplanmış bir durum "BELİRSİZ"e geri ezilirdi.
                if kuratorlu:
                    exists.is_katilim_compliant = stock_data["is_katilim_compliant"]
                    exists.purification_rate = stock_data["purification_rate"]
                    exists.non_compliance_reason = stock_data["non_compliance_reason"]
                    exists.katilim_status = durum
                elif not exists.katilim_status:
                    exists.katilim_status = "BELIRSIZ"
                guncellenen += 1
        print(f"Hisse kataloğu: {eklenen} eklendi, {guncellenen} güncellendi (toplam {len(INITIAL_STOCKS)}).")

        # 2. Seed AI Bot User (paylaşımlı demo bot — geriye dönük uyumluluk için korunur)
        bot_username = "yapay_zeka_trader"
        bot_exists = db.query(models.User).filter_by(username=bot_username).first()
        if not bot_exists:
            bot = models.User(
                username=bot_username,
                email="bot@borsasim.com",
                password_hash="pbkdf2:sha256:bot_dummy_password",
                virtual_balance=100000.00,
                is_bot=True
            )
            db.add(bot)
            print(f"Yapay Zeka Trader bot kullanıcısı oluşturuldu! (Başlangıç Bakiyesi: 100.000 TL)")

        db.commit()

        # 3. Seed TEFAS Katılım fonları (boş liste ile başlamasın diye)
        from tefas_client import seed_katilim_funds
        seed_katilim_funds(db)

        # 4. Her kullanıcı için kişisel AI Bot kaydı oluştur (yoksa)
        seed_user_bots(db)

        # 5. Migration sonrası eksik süre bilgilerini doldur
        backfill_user_bot_durations(db)

        # 6. Migration sonrası eksik portföy tarih bilgilerini doldur
        backfill_portfolio_timestamps(db)

        print("Veritabanı başarıyla ilklendirildi.")
    except Exception as e:
        print(f"Veritabanı ilklendirilirken hata oluştu: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_database()
