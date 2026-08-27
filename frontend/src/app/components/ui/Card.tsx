"use client";

import React from "react";

/**
 * Ortak kart bileşeni.
 *
 * NEDEN VAR: `bg-[#151921] border border-[#242B35] rounded-*` kalıbı 107 yerde
 * tekrarlanıyordu ve köşe yuvarlaklığı üç farklı değerde (lg/xl/2xl) kuralsız
 * dağılmıştı. Tutarsızlık, göz için renk hatasından daha çok "amatör" okunur.
 *
 * GÖLGE YOK. Bu projede box-shadow kullanılmaz — derinlik, yüzey renginin bir
 * ton açılmasıyla verilir (--surface-raised).
 *
 * HOVER SADECE TIKLANABİLİRDE: `interactive` yalnızca kart gerçekten bir yere
 * götürüyor ya da bir işlem tetikliyorsa verilmelidir. Bilgi gösteren kartta
 * hover, kullanıcıya "buraya tıklarsam bir şey olur mu?" diye yanlış bir
 * beklenti yaratır.
 */

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Kart tıklanabilirse hover tepkisi verir. Sadece bilgi gösteriyorsa false. */
  interactive?: boolean;
  /** İç dolgu. Yoğun tablolarda "none" kullanılıp dolgu içeride verilir. */
  padding?: "none" | "sm" | "md" | "lg";
  /** Vurgulu kenarlık (ör. seçili durum) — marka renginde. */
  highlighted?: boolean;
}

const PADDING = {
  none: "",
  sm: "p-3",
  md: "p-4",
  lg: "p-4 sm:p-5",
};

export default function Card({
  interactive = false,
  padding = "md",
  highlighted = false,
  className = "",
  children,
  ...rest
}: CardProps) {
  return (
    <div
      className={[
        "bg-[var(--surface)] rounded-[var(--radius-card)] border",
        highlighted ? "border-[var(--brand-line)]" : "border-[var(--line)]",
        interactive
          ? "transition-colors duration-150 hover:border-[var(--line-strong)] hover:bg-[var(--surface-raised)] cursor-pointer"
          : "",
        PADDING[padding],
        className,
      ].join(" ")}
      {...rest}
    >
      {children}
    </div>
  );
}

/** Kart başlığı — ikon + başlık + sağda isteğe bağlı eylem alanı. */
export function CardHeader({
  icon: Icon,
  title,
  action,
  className = "",
}: {
  icon?: React.ElementType;
  title: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex items-center justify-between gap-2 mb-3 ${className}`}>
      <div className="flex items-center gap-2 min-w-0">
        {Icon && <Icon className="w-4 h-4 text-[var(--brand)] shrink-0" />}
        <h3 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wide truncate">
          {title}
        </h3>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
