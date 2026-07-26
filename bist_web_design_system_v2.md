# BIST Web Uygulaması - UI/UX & Tasarım Sistem Rehberi (v2)
## "Anti-AI Blue" Obsidian & Amber Gold Mobil Uyumlu Arayüz Şartnamesi

Bu doküman; Midas Pro derin analiz kartları, Katılım Endeksi rozetleri, mobil alt gezinme barı, sayfa duyarlı akıllı yardım modalı, imzalı footer ve yasal onay kutusu dahil **sadece frontend ve tasarım sistemini kapsayan** teknik şartnamedir.

---

## İÇİNDEKİLER
1. [Tasarım Felsefesi ve Renk Paleti ("Anti-AI Blue")](#1-tasarım-felsefesi-ve-renk-paleti-anti-ai-blue)
2. [Tipografi, İkon ve Sayı Kuralları](#2-tipografi-ikon-ve-sayı-kuralları)
3. [Mobil Optimizasyon ve UX Standartları](#3-mobil-optimizasyon-ve-ux-standartları)
4. [Frontend Bileşenleri Şartnamesi (Next.js & TailwindCSS)](#4-frontend-bileşenleri-şartnamesi-nextjs--tailwindcss)
5. [Claude Sonnet 4.6 İçin Token Dostu Master UI Prompt](#5-claude-sonnet-46-için-token-dostu-master-ui-prompt)

---

## 1. Tasarım Felsefesi ve Renk Paleti ("Anti-AI Blue")

Piyasadaki jenerik elektrik mavisi (`#0066FF`), mor parlamalar ve neon glow efektleri yerine **Obsidyen Siyahı ve Sıcak Kehribar Gold** tonları kullanılmıştır:

| Eleman | Renk Kodu | Renk Tanımı | Kullanım Alanı |
| :--- | :--- | :--- | :--- |
| **Canvas / Arka Plan** | `#0B0E14` | Obsidyen Siyahı | Tüm sayfaların en arka planı |
| **Kart / Yüzey** | `#151921` | Koyu Kömür | Hisse kartları, grafik panelleri, tablo alanları |
| **Sınır / Çizgiler** | `#242B35` | Muted Slate | 1px inceliğindeki kart ve tablo kenarlıkları |
| **Yükseliş (Kâr)** | `#10B981` | Zümrüt Yeşili | Yükselen hisseler, pozitif getiriler, yeşil grafikler |
| **Düşüş (Zarar)** | `#F43F5E` | Koyu Gül Kırmızı | Düşen hisseler, negatif getiriler, kırmızı grafikler |
| **Vurgu (Accent)** | `#F59E0B` | Sıcak Kehribar Gold | **Bot vurguları**, kilit metrikler, aktif sekme çizgisi |
| **Birincil Metin** | `#F8FAFC` | Off-White | Fiyatlar, hisse kodları, ana başlıklar |
| **İkincil Metin** | `#8A99AD` | Muted Steel | Hisse adları, 15 dk gecikme uyarısı, ikincil etiketler |

---

## 2. Tipografi, İkon ve Sayı Kuralları

1. **Hizalanmış Sayılar (`tabular-nums`):** Hisse fiyatları ve finansal rakamlar canlı değişirken sağa sola kaymaması için zorunlu CSS:
   ```css
   .stock-price {
       font-family: 'Inter', sans-serif;
       font-variant-numeric: tabular-nums;
       font-weight: 600;
   }
   ```
2. **Yasaklı İkon ve Görseller:**
   * ❌ Sihirli değnek (🪄), ışıltı (✦), robot (🤖), beyin (🧠) ikonları **KESİNLİKLE YASAKTIR**.
   * ❌ Heavy Glassmorphism (cam efekti) ve okunabilirliği düşüren bulanıklıklar banned.
3. **İzin Verilen İkonlar:**
   * Yalnızca **Lucide-React** kütüphanesinden minimalist 1.5px ince çizgisel ikonlar ve canlı yeşil/kehribar **Canlı Durum Noktaları (Status Dots)**.

---

## 3. Mobil Optimizasyon ve UX Standartları

* **Mobil Bottom Navigation Bar (`md:hidden`):** Ekranın en altında sabit duran Midas tarzı alt gezinme barı (Home, BİST, Bot, Fonlar, Portföy).
* **Touch Target Sizes:** Tüm dokunulabilir butonlar, kartlar ve sekme yönlendirmeleri için minimum **44x44px** dokunma alanı.
* **Yatay Kaydırmalı Tablolar (Responsive Tables):** Midas Pro derin analiz tabloları küçük ekranlarda daralmaz; yumuşak kaydırma (`overflow-x-auto WebkitOverflowScrolling: touch`) ile mobil uyumlu çalışır.

---

## 4. Frontend Bileşenleri Şartnamesi (Next.js & TailwindCSS)

### 4.1. `MobileBottomNav.tsx`
* Sadece mobil cihazlarda (`md:hidden`) ekranın altında sabitlenen (`fixed bottom-0 left-0 right-0 z-50`) alt menü barı.
* Sayfa geçişlerinde aktif sekmeyi `#F59E0B` (Amber Gold) rengi ve 2px alt çizgi ile belirginleştirir.

### 4.2. `MidasProAnalysisTab.tsx`
* **Piotroski Skoru (0-9):** Görsel yeşil ilerleme çubuğu ve durumu (Örn: `8/9 - Çok Sağlam Bilanço`).
* **Çarpan Kıyaslama Tablosu:** Hissenin F/K, PD/DD, FD/FAVÖK değerlerini Sektör Ortalamasıyla yan yana gösterir.
* **Sektörel İskonto Rozeti:** Sektörüne göre ucuzsa `Sektörüne Göre %42 Ucuz` (Yeşil Rozet).
* **Makul Eder Fiyat Kartı:** Borsa Fiyatı vs Tahmini Eder Fiyat (`%+26.5 Potansiyel Prim`).
* **Marj Kartları:** ROE (Özkaynak Karlılığı), Brüt Kar Marjı, Net Kar Marjı % değerleri.
* **Döviz & Faiz Duyarlılığı:** Bilançodaki net döviz pozisyonuna göre etiketler (Örn: `🟢 Dolar Yükselişine Dayanıklı`).

### 4.3. `InsiderTrackerBadge.tsx` & `KatilimBadge.tsx`
* **Patron İşlem Uyarısı:** Son 30 günde patron/yönetim hisse topladıysa `🟢 Patron Hissede Alımda!` rozeti.
* **Katılım Endeksi Rozeti:** 
  * Katılım uyumluysa: `✓ KATILIM UYGUN` (Tıklandığında Arınma Oranı % popover'ı açılır).
  * Uygun değilse: `✕ UYGUN DEĞİL` (Sebebi görünür).

### 4.4. `DividendCalculatorWidget.tsx` & `DcaBacktestWidget.tsx`
* **Temettü Emekliliği:** "Aylık X TL hedef pasif gelir" girdisine göre gerekli lot sayısı ve hedef ilerleme çubuğu.
* **DCA Backtest:** "Her ay X TL yatırsaydım bugün kaç param olurdu?" geçmiş getiri simülasyon grafiği.

### 4.5. `CommunitySentimentGauge.tsx`
* Yorum analizlerinden üretilen topluluk duygu ibresi: `Topluluk Hissede Boğa (%78 Olumlu)`.

### 4.6. `OnboardingHelpModal.tsx` (Sayfa Duyarlı Akıllı Yardım)
* Ekranın sağ alt köşesinde sabitlemiş yüzen `?` butonu.
* İlk girişte `localStorage` kontrolüyle otomatik açılan karşılama modalı.
* `usePathname()` ile bulunulan sayfaya özel rehberlik:
  * `/`: Genel platform ve sanal portföy kurallarını anlatır.
  * `/hisse/[symbol]`: Piotroski, Makul Değer ve Katılım Endeksi'ni açıklar.
  * `/bot`: Yapay Zeka Quant Trader mantığını açıklar.
  * `/fonlar`: TEFAS yatırım fonlarını açıklar.

### 4.7. `Footer.tsx` (İmzalı Yasal Alt Bilgi)
* Gizlilik Sözleşmesi, KVKK, Kullanıcı Sözleşmesi ve YTD Sorumluluk Reddi bağlantıları.
* "Veriler en az 15 dakika gecikmelidir" uyarı bandı.
* **İmza Metni:** `Design by Eyüphan İpek Hazretleri (ks)`

### 4.8. `LegalDisclaimerModal.tsx` (Yasal Onay Kutusu)
Kullanıcı üye olurken veya ilk sanal alım-satımda işaretlemek zorunda olduğu ZORUNLU onay kutusu:
`[x] Kullanıcı Sözleşmesi, KVKK Aydınlatma Metni ve Sorumluluk Reddi Feragatnamesi'ni okudum, kabul ediyorum.`
*(İçeriğinde YTD beyanı, simülasyon vurgusu, 15 dk gecikme kabulü ve tazminat haklarından tam feragatname yer alır).*

### 4.9. `QuantBotDashboard.tsx`
* "Bot vs BİST 100" karşılaştırmalı performans çizgisel grafiği.
* Win Rate (%) kartı mevcuttur.
* Botun neden alıp sattığını belirten teknik gerekçe akışı (Live Log Feed).

---

## 5. Claude Sonnet 4.6 İçin Token Dostu Master UI Prompt

```text
SYSTEM DIRECTIVE: You are an elite UI/UX Frontend Architect. Output ONLY complete, production-ready React (Next.js App Router + TailwindCSS + Lucide-React) components. NO intro/outro text, NO verbose explanations. Write FULL implementations with zero placeholders.

[PROJECT DESIGN & MOBILE RULES]
- Colors: Obsidian Canvas `#0B0E14`, Surface `#151921`, Border `#242B35`, Positive `#10B981`, Negative `#F43F5E`, Accent `#F59E0B` (Amber Gold).
- Strict UI: NO blue/purple glows, NO magic/robot/star icons. Use `font-variant-numeric: tabular-nums` for prices.
- Mobile Touch UX: All touch targets MUST be >= 44x44px. Render fixed Bottom Nav (`md:hidden`). Smooth scroll tables (`overflow-x-auto`).

---

[TASK: FRONTEND COMPONENTS IMPLEMENTATION]
Generate complete Next.js React code files for:
1. `MobileBottomNav.tsx`: Fixed bottom nav (Home, BİST, Bot, Fonlar, Portföy) with active tab state.
2. `OnboardingHelpModal.tsx`: Floating `?` button (bottom-right). Route-aware explanations using `usePathname()`. Auto-opens on first visit (`localStorage`).
3. `Footer.tsx`: Legal links (Gizlilik, KVKK, YTD) + 15-min delay banner + Signature: "Design by Eyüphan İpek Hazretleri (ks)".
4. `MidasProAnalysisTab.tsx`: Piotroski Score bar, Sector P/E comparison table, Fair Value vs Price (% Potential), FX/Interest Sensitivity badges.
5. `InsiderTrackerBadge.tsx` & `KatilimBadge.tsx`: "🟢 Patron Hissede Alımda!" & `✓ KATILIM UYGUN` (with Arınma Oranı popover).
6. `DividendCalculatorWidget.tsx` & `DcaBacktestWidget.tsx`: Passive income lot target & monthly investment DCA calculator.
7. `CommunitySentimentGauge.tsx`: Aggregates comment sentiment -> "Topluluk Hissede Boğa (%78 Olumlu)".
8. `LegalDisclaimerModal.tsx`: Mandatory Registration/Trading Checkbox for full legal liability waiver & YTD.
9. `QuantBotDashboard.tsx`: Performance comparison chart (Bot vs BIST 100), Win Rate %, and live bot logs feed.
```
