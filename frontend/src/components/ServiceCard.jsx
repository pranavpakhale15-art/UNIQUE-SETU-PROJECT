import React from "react";
import { Link } from "react-router-dom";
import { useLang } from "@/lib/i18n/LanguageContext";
import { FileText, ArrowUpRight } from "lucide-react";
import ServiceThumbnail from "@/components/ServiceThumbnail";

export default function ServiceCard({ service }) {
  const { loc, t } = useLang();
  const name = loc(service, "name");
  const desc = loc(service, "description");
  const docCount = service.checklist?.length || 0;
  return (
    <Link
      to={`/services/${service.service_slug}`}
      className="group relative block overflow-hidden rounded-2xl border border-border/80 bg-card hover:-translate-y-1 hover:border-primary/25 hover:shadow-xl hover:shadow-primary/[0.07] transition-all duration-300"
    >
      <div className="absolute inset-x-0 top-0 h-1 origin-left scale-x-0 bg-gradient-to-r from-accent to-orange-300 transition-transform duration-300 group-hover:scale-x-100" />
      <ServiceThumbnail service={service} className="aspect-[16/10] w-full" />
      <div className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="w-11 h-11 rounded-xl bg-secondary text-primary flex items-center justify-center shrink-0 transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
            <FileText className="w-5 h-5" />
          </div>
          <span className="flex h-8 w-8 items-center justify-center rounded-full border border-border text-muted-foreground transition-all group-hover:border-primary group-hover:bg-primary group-hover:text-primary-foreground">
            <ArrowUpRight className="w-4 h-4" />
          </span>
        </div>
        <h3 className="mt-4 font-heading text-lg font-semibold text-foreground leading-snug">{name}</h3>
        <p className="mt-2 min-h-10 text-sm leading-relaxed text-muted-foreground line-clamp-2">{desc}</p>
        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-accent/10 font-semibold" style={{ color: "hsl(var(--accent))" }}>
            {service.category}
          </span>
          <span className="rounded-full bg-secondary px-2.5 py-1 text-muted-foreground">{docCount} {t("service.requiredDocs")}</span>
        </div>
      </div>
    </Link>
  );
}
