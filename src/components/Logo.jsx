import React from "react";
import { useLang } from "@/lib/i18n/LanguageContext";
import { Link } from "react-router-dom";

// Monogram placeholder logo — replace with the original logo asset when available.
export default function Logo({ size = "md", to = "/" }) {
  const { t } = useLang();
  const dim = size === "sm" ? "w-9 h-9" : size === "lg" ? "w-14 h-14" : "w-11 h-11";
  const text = size === "sm" ? "text-sm" : size === "lg" ? "text-lg" : "text-base";
  return (
    <Link to={to} className="flex items-center gap-2.5 group">
      <div className={`${dim} rounded-xl bg-gradient-to-br from-amber-500 via-orange-600 to-rose-700 flex items-center justify-center shadow-sm ring-1 ring-amber-700/20 shrink-0`}>
        <span className="text-white font-bold text-lg leading-none">यु</span>
      </div>
      <div className="flex flex-col leading-tight">
        <span className={`font-heading font-bold ${text} text-foreground tracking-tight`}>
          {t("common.appName")}
        </span>
        <span className="text-[11px] text-muted-foreground font-medium hidden sm:block">
          {t("common.tagline")}
        </span>
      </div>
    </Link>
  );
}