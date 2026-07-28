# 🚀 BIST Finans Platformu - Modül Geliştirme ve Özellik Yol Haritası

---

## ⚠️ AI (Cursor / Claude) İÇİN ÖNCELİKLİ DENETİM VE KONTROL TALİMATI

> **GÖREV BAŞLAMADAN ÖNCE DİKKAT:**
> 1. **Kod Tabanı Taraması (Codebase Audit):** Aşağıdaki maddelerden herhangi birini uygulamaya geçmeden önce `frontend/` ve `backend/` dizinlerini detaylıca tara.
> 2. **Çakışma ve Mevcut Özellik Kontrolü:** Eğer listelenen özellik projemizde **zaten varsa**, **farklı bir yöntemle yazılmışsa** veya **kısmen mevcutsa** doğrudan üstüne yazma!
> 3. **Karşılaştırma ve Onay İste:** Kullanıcıya şu şekilde bilgi ver ve onay iste:
>    - *"Bu özellik [dosya_adı.tsx/py] içinde zaten mevcut. Mevcut yapı [X] şeklinde çalışıyor. Önerilen yeni yapı [Y] imkanı sunacak."*
>    - *"Sizce mevcut yapı kalsın mı, yoksa yeni yapıyla değiştirelim mi? Ya da şu alternatif geliştirmeyi mi yapalım?"*
> 4. **Faizsiz Finans (Katılım) Kuralı:** Kodun, veritabanı modellerinin, UI metinlerinin ve AI prompt'larının hiçbir yerinde "faiz", "interest", "mevduat" kelimesi veya mantığı kullanılmamalıdır. Tüm hesaplamalar reel ticaret, kâr payı, temettü ve değer artışı esasına dayanmalıdır.

---

## 📋 GELİŞTİRİLECEK 7 ANA MODÜL

### 1️⃣ 🏷️ Katılım Endeksi Rozeti & Filtresi (BIST KATLM)
* **Backend:**
  * `Stock` modeline `is_katilim_compliant` (Boolean) alanı ekle/kontrol et.
  * Hisselerin Katılım Endeksi'ne uygunluk durumunu filtreleyen API parametresi ekle (`/api/stocks?katilim_only=true`).
* **Frontend:**
  * Hisse Detay ve Arama sonuçlarında Katılım Endeksi'ne uygun hisselerin yanına yeşil **"🌱 Katılım"** etiketi/badge'i koy.
  * Hisse Listesi ve Filtreleme sayfasına **"Sadece Katılım Hisselerini Göster"** toggle düğmesi ekle.

---

### 2️⃣ 🚀 Halka Arz (IPO) Takvimi & Detay Kartı
* **Backend & Frontend (`/halka-arz` Sayfası):**
  * Aktif, yaklaşan ve tamamlanan halka arzları listeleyen bir takvim/dashboard ekranı oluştur.
  * **Veri Alanları:** Şirket Adı, Halka Arz Fiyatı, Talep Toplama Tarihleri, Dağıtım Yöntemi (Eşit/Oransal), Toplam Lot Sayısı ve **Katılım Endeksi'ne Uygunluk Durumu** (Evet/Hayır).
  * Mobil uyumlu, tıklanınca detayları gösteren şık kart tasarımları uygula.

---

### 3️⃣ 🎯 Aracı Kurum Hedef Fiyatları & Konsensüs
* **Backend:**
  * Hisse bazlı aracı kurum (İş Yatırım, Garanti, Ak Yatırım vb.) hedef fiyat raporlarını ve tavsiyelerini tutan endpoint oluştur (`/api/stocks/{symbol}/target-prices`).
* **Frontend:**
  * Hisse Detay sayfasına **"Aracı Kurum Konsensüsü"** kartı ekle.
  * **Gösterilecekler:** Ortalama Hedef Fiyat, Potansiyel Getiri Oranı (`+%XX`), Al / Tut / Sat tavsiye dağılım çubuğu (Progress bar).

---

### 4️⃣ 🗺️ Sektörel BIST Isı Haritası (Market Heatmap)
* **Frontend (`/heatmap` veya Dashboard Widget):**
  * BIST 100 / BIST 30 hisselerini sektörlerine göre (Banka, Otomotiv, Teknoloji, Gıda vb.) gruplayan interaktif **Treemap / Heatmap** bileşeni ekle.
  * Günlük yüzde değişimine göre renk ölçeği uygula (Koyu Yeşil = Yüksek Yükseliş, Kırmızı = Düşüş).
  * Kutucuk boyutları hisselerin piyasa değerine veya işlem hacmine göre ölçeklensin.

---

### 5️⃣ 📅 Bilanço & KAP Haber Takvimi
* **Backend & Frontend:**
  * Şirketlerin çeyreklik bilanço açıklama tarihlerini ve önemli KAP duyurularını gösteren takvim görünümü (`/kalendar` veya `/kap`).
  * Kullanıcının takip ettiği hisselere ait KAP haberlerini öne çıkaran filtreleme seçeneği ekle.

---

### 6️⃣ 📊 Topluluk Duygu Durumu (Sentiment & Beklenti Anketi)
* **Backend:**
  * Hisse bazlı kullanıcı oylama sistemi oluştur (`/api/stocks/{symbol}/vote`). Kullanıcılar haftalık/günlük beklenti oyu verebilsin (Yükselir / Düşer).
* **Frontend:**
  * Hisse detay sayfasına **"Topluluk Beklentisi"** widget'ı ekle.
  * Canlı oy oranını gösteren görsel çubuk: *"%68 Yükselir / %32 Düşer"* ve kullanıcının tek tıkla oy kullanabileceği butonlar.

---

### 7️⃣ 🔔 Kişiye Özel Bildirim & Alarm Sistemi
* **Backend:**
  * `StockNotificationPreference` (Fiyat limitleri, % değişim tetikleyicileri, KAP haber ve AI sinyal tercihleri) ve `Notification` (Sistem içi bildirim geçmişi) modellerini/endpoint'lerini oluştur.
* **Frontend:**
  * **Hisse Detay Sayfası:** Başlığın yanına **"🔔 Bildirim Oluştur"** butonu ekle. Tıklayınca açılan modal üzerinden Fiyat Alt/Üst Limiti, KAP ve AI Sinyal bildirim ayarlarını yaptır.
  * **Navbar:** En üste bildirim zili (`Bell`) ikonu koy. Okunmamış bildirim sayısını kırmızı badge ile göster. Tıklanınca son bildirimleri listeleyen dropdown menü aç.

---

## 🛠️ UYGULAMA ADIMLARI
1. Önce koddaki mevcut durumu tara ve kullanıcıya kısa bir durum özeti sun.
2. Kullanıcı onay verdikten sonra modülleri sırasıyla ve test ederek geliştir.
3. Tamamlanan her adımın ardından değişiklikleri master branch'e commit/push et.