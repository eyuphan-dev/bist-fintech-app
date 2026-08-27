/**
 * Piyasa yönü rengi — tek doğruluk kaynağı.
 *
 * BULUNAN HATA: uygulamada 20 ayrı yerde `deger >= 0 ? yeşil : kırmızı` yazıyordu.
 * Bu, DEĞİŞİM OLMAYAN durumu (tam 0.00%) yeşil gösteriyordu. Liderlik
 * tablosunda 10 satırın 9'unun yeşil "+0.00%" görünmesinin sebebi buydu:
 * ortada kazanç yokken ekran kazanç varmış gibi görünüyor, yeşil rengin
 * "yükseliş" anlamı da böylece değersizleşiyordu.
 *
 * Doğrusu üç durumlu: pozitif → yeşil, negatif → kırmızı, sıfır/bilinmiyor → nötr.
 */

export const UP = "#10B981";
export const DOWN = "#F43F5E";
/** Değişim yok ya da veri yok. Yeşil DEĞİL — kazanç iddiasında bulunmaz. */
export const FLAT = "#8A99AD";

/** Sayısal değişime göre hex renk döner. null/undefined/0 → nötr. */
export function marketColor(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return FLAT;
  if (value > 0) return UP;
  if (value < 0) return DOWN;
  return FLAT;
}

/** Tailwind metin sınıfı karşılığı. */
export function marketTextClass(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "text-[#8A99AD]";
  if (value > 0) return "text-[#10B981]";
  if (value < 0) return "text-[#F43F5E]";
  return "text-[#8A99AD]";
}

/** Rozet/etiket için arka plan + metin sınıfı karşılığı. */
export function marketBadgeClass(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "bg-[#8A99AD]/10 text-[#8A99AD]";
  if (value > 0) return "bg-[#10B981]/10 text-[#10B981]";
  if (value < 0) return "bg-[#F43F5E]/10 text-[#F43F5E]";
  return "bg-[#8A99AD]/10 text-[#8A99AD]";
}

/** İşaretli yüzde metni: +1,25% / -0,80% / 0,00% */
export function formatPct(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const isaret = value > 0 ? "+" : "";
  return `${isaret}${value.toFixed(digits)}%`;
}
