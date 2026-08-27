"use client";

import React from "react";

/**
 * Ortak buton bileşeni.
 *
 * NEDEN VAR: aynı buton stili uygulamada 16 ayrı yerde elle kopyalanmıştı.
 * Tek bir hover rengini değiştirmek 16 dosyaya girmeyi gerektiriyordu — tam da
 * bu projenin "sabit iki yerde tanımlanırsa zamanla sapar" ilkesine aykırı
 * durum (bkz. komisyon oranı hatası).
 *
 * GÖLGE YOK: bu projede box-shadow kasıtlı olarak kullanılmaz. Derinlik hissi
 * yüzey renginin bir ton açılmasıyla verilir. Gölge, kurumsal bir terminal
 * yerine tüketici uygulaması görünümü yaratıyor.
 *
 * DOKUNMA HEDEFİ: tüm boyutlar en az 44px yüksekliğe ulaşır (tasarım sistemi
 * kuralı). `sm` bile mobilde parmakla rahat basılabilir olmalıdır.
 */

type Variant = "primary" | "secondary" | "ghost" | "buy" | "sell" | "danger";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  fullWidth?: boolean;
  /** Metnin solunda gösterilecek lucide ikonu. */
  icon?: React.ElementType;
}

const VARIANTS: Record<Variant, string> = {
  // Marka rengi MAVİ — gezinme ve genel eylemler. Yeşil bilerek kullanılmaz;
  // o renk yalnızca piyasa yükselişine ayrılmıştır.
  primary:
    "bg-[var(--brand)] text-white hover:bg-[var(--brand-hover)] active:bg-[var(--brand-active)] border border-transparent",
  secondary:
    "bg-[var(--surface)] text-[var(--text-primary)] border border-[var(--line)] hover:border-[var(--line-strong)] hover:bg-[var(--surface-raised)]",
  ghost:
    "bg-transparent text-[var(--text-secondary)] border border-transparent hover:text-[var(--text-primary)] hover:bg-[var(--surface-raised)]",
  // AL/SAT butonları piyasa yönü rengini kullanır — bu bir marka tercihi değil,
  // borsa arayüzlerinde yerleşik bir sözleşmedir (al=yeşil, sat=kırmızı).
  buy: "bg-[var(--up)] text-[#0B0E14] hover:brightness-110 active:brightness-95 border border-transparent",
  sell: "bg-[var(--down)] text-white hover:brightness-110 active:brightness-95 border border-transparent",
  danger:
    "bg-transparent text-[var(--down)] border border-[var(--down)]/40 hover:bg-[var(--down)]/10",
};

const SIZES: Record<Size, string> = {
  sm: "min-h-[44px] px-3 text-xs",
  md: "min-h-[44px] px-4 text-sm",
  lg: "min-h-[48px] px-5 text-sm",
};

export default function Button({
  variant = "primary",
  size = "md",
  fullWidth = false,
  icon: Icon,
  className = "",
  children,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      disabled={disabled}
      className={[
        "inline-flex items-center justify-center gap-2 font-semibold",
        "rounded-[var(--radius-control)]",
        // Geçiş yalnızca renk üzerinde — konum/boyut animasyonu yok ki
        // yoğun veri ekranında dikkat dağıtmasın.
        "transition-colors duration-150",
        // Basma geri bildirimi: dokunmatikte "işlem oldu" hissi için minik tık.
        "active:scale-[0.98]",
        // Klavye erişilebilirliği — odak halkası marka renginde.
        "outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)]",
        "disabled:opacity-45 disabled:cursor-not-allowed disabled:active:scale-100",
        VARIANTS[variant],
        SIZES[size],
        fullWidth ? "w-full" : "",
        className,
      ].join(" ")}
      {...rest}
    >
      {Icon && <Icon className="w-4 h-4 shrink-0" />}
      {children}
    </button>
  );
}
