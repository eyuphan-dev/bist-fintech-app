"use client";

import React from "react";
import { X, Target, NotebookText, Lightbulb } from "lucide-react";

interface CalculatorHelpModalProps {
  title: string;
  purpose: string;
  howTo: string;
  example?: string;
  onClose: () => void;
}

/**
 * Hesaplayıcı widget'ları (Temettü, DCA vb.) için ortak kullanım kılavuzu modalı.
 * "Ne İşe Yarar? / Nasıl Kullanılır? / Örnek" yapısını paylaşır. Backdrop
 * tıklaması ve X ikonuyla kapanır, mobilde dokunmaya uygundur.
 */
export default function CalculatorHelpModal({ title, purpose, howTo, example, onClose }: CalculatorHelpModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md bg-[#151921] border border-[#242B35] rounded-2xl overflow-hidden max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="bg-[#F59E0B]/10 border-b border-[#F59E0B]/20 px-5 py-4 flex items-center justify-between shrink-0">
          <h2 className="text-sm font-bold text-white pr-2">{title}</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition shrink-0" title="Kapat">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4 overflow-y-auto">
          <div className="bg-[#0B0E14] border border-[#242B35] rounded-xl p-3 flex items-start gap-2.5">
            <Target className="w-4 h-4 text-[#F59E0B] shrink-0 mt-0.5" />
            <div>
              <h4 className="text-xs font-bold text-white">Ne İşe Yarar?</h4>
              <p className="text-[11px] text-gray-400 leading-relaxed mt-0.5">{purpose}</p>
            </div>
          </div>

          <div className="bg-[#0B0E14] border border-[#242B35] rounded-xl p-3 flex items-start gap-2.5">
            <NotebookText className="w-4 h-4 text-[#F59E0B] shrink-0 mt-0.5" />
            <div>
              <h4 className="text-xs font-bold text-white">Nasıl Kullanılır?</h4>
              <p className="text-[11px] text-gray-400 leading-relaxed mt-0.5">{howTo}</p>
            </div>
          </div>

          {example && (
            <div className="bg-[#0B0E14] border border-[#242B35] rounded-xl p-3 flex items-start gap-2.5">
              <Lightbulb className="w-4 h-4 text-[#F59E0B] shrink-0 mt-0.5" />
              <div>
                <h4 className="text-xs font-bold text-white">Örnek</h4>
                <p className="text-[11px] text-gray-400 leading-relaxed mt-0.5">{example}</p>
              </div>
            </div>
          )}

          <p className="text-[10px] text-gray-600 text-center pt-1">
            💡 Hesaplamalar teorik formüllere dayanır. Yatırım tavsiyesi değildir.
          </p>
        </div>
      </div>
    </div>
  );
}
