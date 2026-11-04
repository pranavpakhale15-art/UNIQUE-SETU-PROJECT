import React from "react";
import { useLang } from "@/lib/i18n/LanguageContext";
import { Link } from "react-router-dom";

export default function Logo({ size = "md", to = "/" }) {
  const { t } = useLang();
  const dim = size === "sm" ? "w-9 h-9" : size === "lg" ? "w-14 h-14" : "w-11 h-11";
  const text = size === "sm" ? "text-sm" : size === "lg" ? "text-lg" : "text-base";
  return (
    <Link to={to} className="flex items-center gap-2.5 group">
      <img
        src={`${import.meta.env.BASE_URL}logo.png`}
        alt={t("common.appName")}
        className={`${dim} rounded-xl object-cover shadow-md shadow-orange-900/10 ring-1 ring-amber-700/20 shrink-0 transition-transform duration-300 group-hover:scale-105`}
      />
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
