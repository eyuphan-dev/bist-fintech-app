/**
 * API'den gelen UTC ISO zaman damgasını, görüntüleyenin tarayıcı saat dilimine
 * değil, her zaman Türkiye (Europe/Istanbul) saatine göre biçimlendirir — bu bir
 * BİST uygulaması olduğu için emir/işlem saatleri her zaman piyasa saatiyle
 * (İstanbul) tutarlı gösterilmelidir.
 */
export function formatIstanbulDateTime(isoString: string): string {
  return new Intl.DateTimeFormat("tr-TR", {
    timeZone: "Europe/Istanbul",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(isoString));
}
