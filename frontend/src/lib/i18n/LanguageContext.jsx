import React, { createContext, useContext, useState, useCallback, useMemo } from "react";
import { translations, DEFAULT_LANG, LANGS } from "./translations";

const LanguageContext = createContext();

const STORAGE_KEY = "usk_lang";

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return LANGS.includes(saved) ? saved : DEFAULT_LANG;
    } catch {
      return DEFAULT_LANG;
    }
  });

  const setLang = useCallback((next) => {
    setLangState(next);
    try { localStorage.setItem(STORAGE_KEY, next); } catch { /* ignore */ }
  }, []);

  const t = useCallback((key) => {
    const parts = key.split(".");
    let val = translations[lang];
    for (const p of parts) {
      val = val?.[p];
      if (val === undefined) break;
    }
    if (val === undefined) {
      // fall back to default lang (Marathi)
      let fb = translations[DEFAULT_LANG];
      for (const p of parts) {
        fb = fb?.[p];
        if (fb === undefined) break;
      }
      return fb ?? key;
    }
    return val;
  }, [lang]);

  // Localized field picker: given a record and a base field name, returns the value for current lang
  const loc = useCallback((record, base) => {
    if (!record) return "";
    const key = `${base}_${lang}`;
    const fbKey = `${base}_mr`;
    const localized = record[base];
    if (localized && typeof localized === "object") {
      return localized[lang] || localized[DEFAULT_LANG] || Object.values(localized).find(Boolean) || "";
    }
    return record[key] || record[fbKey] || localized || "";
  }, [lang]);

  const value = useMemo(() => ({ lang, setLang, t, loc }), [lang, setLang, t, loc]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLang() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLang must be used within LanguageProvider");
  return ctx;
}