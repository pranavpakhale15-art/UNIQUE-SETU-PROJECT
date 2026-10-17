import React from "react";
import { useLang } from "@/lib/i18n/LanguageContext";
import { LANGS } from "@/lib/i18n/translations";
import { Globe } from "lucide-react";

const LABELS = { mr: "मराठी", en: "English", hi: "हिन्दी" };

export default function LanguageSwitcher({ compact = false }) {
  const { lang, setLang } = useLang();
  return (
    <div className="flex items-center gap-1">
      {!compact && <Globe className="w-4 h-4 text-muted-foreground mr-1" />}
      <div className="inline-flex rounded-lg border border-border bg-card/60 p-0.5">
        {LANGS.map((l) => (
          <button
            key={l}
            onClick={() => setLang(l)}
            className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
              lang === l
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
            aria-pressed={lang === l}
          >
            {LABELS[l]}
          </button>
        ))}
      </div>
    </div>
  );
}