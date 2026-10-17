import React from "react";
import { Link } from "react-router-dom";
import { useLang } from "@/lib/i18n/LanguageContext";
import { FileText, ChevronRight } from "lucide-react";

export default function ServiceCard({ service }) {
  const { loc, t } = useLang();
  const name = loc(service, "name");
  const desc = loc(service, "description");
  const docCount = service.checklist?.length || 0;
  return (
    <Link
      to={`/services/${service.service_slug}`}
      className="group block rounded-xl border border-border bg-card p-5 hover:border-primary/40 hover:shadow-md transition-all duration-200"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="w-10 h-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
          <FileText className="w-5 h-5" />
        </div>
        <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
      </div>
      <h3 className="mt-3 font-heading font-semibold text-foreground leading-snug">{name}</h3>
      <p className="mt-1 text-sm text-muted-foreground line-clamp-2">{desc}</p>
      <div className="mt-3 flex items-center gap-3 text-xs">
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-accent/10 text-accent-foreground font-medium" style={{ color: "hsl(var(--accent))" }}>
          {service.category}
        </span>
        <span className="text-muted-foreground">{docCount} {t("service.requiredDocs")}</span>
      </div>
    </Link>
  );
}