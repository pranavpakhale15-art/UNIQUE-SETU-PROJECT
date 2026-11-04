import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/lib/AuthContext";
import { useLang } from "@/lib/i18n/LanguageContext";
import { usePublishedServices, useServiceCategories } from "@/lib/serviceQueries";
import ServiceCard from "@/components/ServiceCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search, FileCheck2, ClipboardList, UploadCloud, LineChart, ShieldCheck, ArrowRight, CheckCircle2, Sparkles } from "lucide-react";

export default function Home() {
  const { user, isAuthenticated } = useAuth();
  const { t, loc } = useLang();
  const servicesQuery = usePublishedServices();
  const categoriesQuery = useServiceCategories();
  const services = servicesQuery.data?.items || [];
  const categories = categoriesQuery.data || [];
  const loading = servicesQuery.isLoading || categoriesQuery.isLoading;
  const error = servicesQuery.error?.message || categoriesQuery.error?.message || "";
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return services;
    return services.filter((service) => {
      const category = categories.find((item) => item.id === service.section_id);
      return [service.name_mr, service.name_en, service.name_hi, service.category, loc(category || {}, "name")]
        .some((value) => String(value || "").toLowerCase().includes(term));
    });
  }, [categories, loc, query, services]);

  const serviceGroups = useMemo(() => {
    const used = new Set();
    const groups = categories.map((category) => {
      const items = filtered.filter((service) => service.section_id === category.id);
      items.forEach((service) => used.add(service.id));
      return {
        id: category.id,
        label: loc(category, "name") || category.slug,
        to: `/services/category/section-${category.id}`,
        items,
      };
    }).filter((group) => group.items.length);
    const legacy = new Map();
    filtered.filter((service) => !service.section_id || !used.has(service.id)).forEach((service) => {
      const label = service.category || "Other services";
      if (!legacy.has(label)) legacy.set(label, []);
      legacy.get(label).push(service);
    });
    legacy.forEach((items, label) => groups.push({
      id: `legacy-${label}`,
      label,
      to: `/services/category/legacy-${encodeURIComponent(label)}`,
      items,
    }));
    return groups;
  }, [categories, filtered, loc]);

  const steps = [
    { icon: ClipboardList, title: t("home.step1Title"), desc: t("home.step1Desc") },
    { icon: FileCheck2, title: t("home.step2Title"), desc: t("home.step2Desc") },
    { icon: UploadCloud, title: t("home.step3Title"), desc: t("home.step3Desc") },
    { icon: LineChart, title: t("home.step4Title"), desc: t("home.step4Desc") },
  ];

  return (
    <div className="overflow-hidden">
      {/* Hero */}
      <section className="relative isolate overflow-hidden border-b border-border/70 bg-[linear-gradient(135deg,hsl(var(--background))_0%,hsl(var(--secondary))_55%,hsl(var(--background))_100%)]">
        <div className="hero-grid absolute inset-0 opacity-50" />
        <div className="absolute -left-24 top-12 h-72 w-72 rounded-full bg-accent/10 blur-3xl" />
        <div className="absolute -right-20 bottom-0 h-96 w-96 rounded-full bg-primary/10 blur-3xl" />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 py-16 md:py-24 lg:py-28 grid items-center gap-14 lg:grid-cols-[1.08fr_0.92fr]">
          <div>
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-accent/20 bg-accent/10 text-xs font-semibold tracking-wide" style={{ color: "hsl(var(--accent))" }}>
              <ShieldCheck className="w-3.5 h-3.5" />
              {t("common.tagline")}
            </div>
            <h1 className="mt-6 font-heading font-bold text-4xl sm:text-5xl lg:text-[3.75rem] text-foreground tracking-[-0.04em] leading-[1.08]">
              {t("home.heroTitle")}
            </h1>
            <p className="mt-5 text-base md:text-lg text-muted-foreground max-w-2xl leading-relaxed">
              {t("home.heroSubtitle")}
            </p>
            <div className="mt-8 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
              <Button asChild size="lg" className="h-12 px-6 shadow-lg shadow-primary/15">
                <a href="#services">{t("home.heroCta")}<ArrowRight className="w-4 h-4 ml-1" /></a>
              </Button>
              <Button asChild size="lg" variant="outline" className="h-12 px-6 bg-background/70 backdrop-blur-sm">
                <Link to={isAuthenticated ? (user?.role === "customer" ? "/dashboard" : "/workspace") : "/register"}>{t("home.heroCta2")}</Link>
              </Button>
            </div>
            <div className="mt-7 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-emerald-600" />{t("home.step2Title")}</span>
              <span className="inline-flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-emerald-600" />{t("home.step4Title")}</span>
            </div>
          </div>

          <div className="relative mx-auto w-full max-w-lg lg:mx-0 lg:ml-auto">
            <div className="absolute -inset-5 rounded-[2rem] bg-gradient-to-br from-accent/20 via-transparent to-primary/15 blur-2xl" />
            <div className="relative rounded-[1.75rem] border border-white/80 bg-card/90 p-3 shadow-2xl shadow-primary/10 backdrop-blur-xl">
              <div className="rounded-[1.35rem] border border-border/70 bg-background p-5 sm:p-7">
                <div className="flex items-center justify-between gap-4 border-b border-border/70 pb-5">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent">{t("home.howItWorksTitle")}</p>
                    <p className="mt-1 font-heading text-xl font-bold text-foreground">{t("common.appName")}</p>
                  </div>
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg shadow-primary/20">
                    <Sparkles className="h-5 w-5" />
                  </div>
                </div>
                <div className="mt-5 space-y-3">
                  {steps.map((step, i) => (
                    <div key={step.title} className="group flex items-center gap-4 rounded-xl border border-border/70 bg-card p-3.5 transition-all hover:-translate-y-0.5 hover:border-primary/25 hover:shadow-md">
                      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${i === 0 ? "bg-accent text-white" : "bg-secondary text-primary"}`}>
                        <step.icon className="h-[18px] w-[18px]" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-medium text-muted-foreground">0{i + 1}</p>
                        <p className="truncate text-sm font-semibold text-foreground">{step.title}</p>
                      </div>
                      {i === 0 ? <ArrowRight className="h-4 w-4 text-accent" /> : <div className="h-2 w-2 rounded-full bg-border" />}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="max-w-7xl mx-auto px-4 sm:px-6 py-20 md:py-24">
        <div className="max-w-2xl mb-12">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-accent">{t("common.tagline")}</p>
          <h2 className="mt-3 font-heading font-bold text-3xl md:text-4xl tracking-tight text-foreground">{t("home.howItWorksTitle")}</h2>
        </div>
        <div className="relative grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="absolute left-[12%] right-[12%] top-7 hidden h-px bg-gradient-to-r from-transparent via-border to-transparent lg:block" />
          {steps.map((s, i) => (
            <div key={i} className="group relative rounded-2xl border border-border/80 bg-card p-6 transition-all duration-300 hover:-translate-y-1 hover:border-primary/20 hover:shadow-xl hover:shadow-primary/[0.06]">
              <div className="relative z-10 w-14 h-14 rounded-2xl bg-secondary text-primary flex items-center justify-center ring-8 ring-background transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                <s.icon className="w-5 h-5" />
              </div>
              <div className="absolute top-6 right-6 text-4xl font-bold text-primary/[0.07]">0{i + 1}</div>
              <h3 className="mt-6 font-heading text-lg font-semibold text-foreground">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Services */}
      <section id="services" className="border-y border-border/70 bg-secondary/45">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-20 md:py-24">
          <div className="mb-10 grid items-end gap-6 md:grid-cols-[1fr_auto]">
            <div className="max-w-2xl">
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-accent">{t("common.appName")}</p>
              <h2 className="mt-3 font-heading font-bold text-3xl md:text-4xl tracking-tight text-foreground">{t("home.servicesTitle")}</h2>
              <p className="mt-3 text-muted-foreground">{t("home.servicesSubtitle")}</p>
            </div>
            <div className="relative w-full md:w-80">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("common.search")}
                className="pl-11 h-12 rounded-xl border-border bg-card shadow-sm"
              />
            </div>
          </div>
        {loading ? (
          <div className="rounded-2xl border border-border bg-card text-center py-16 text-muted-foreground">{t("common.loading")}</div>
        ) : error ? (
          <div role="alert" className="rounded-2xl border border-destructive/20 bg-destructive/5 text-center py-16 text-destructive">{error}</div>
        ) : serviceGroups.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border bg-card/60 text-center py-16 text-muted-foreground">
            {query ? t("home.noServicesMatch") : t("home.servicesUnavailable")}
          </div>
        ) : (
          <div className="space-y-10">
            {serviceGroups.map((group) => (
              <section key={group.id} aria-labelledby={`home-category-${group.id}`}>
                <div className="mb-4 flex items-center justify-between gap-3">
                  <h3 id={`home-category-${group.id}`} className="font-heading text-lg font-semibold text-foreground">{group.label}</h3>
                  <Link to={group.to} className="shrink-0 text-sm font-medium text-primary hover:underline">View category</Link>
                </div>
                <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                  {group.items.map((service) => <ServiceCard key={service.id} service={service} />)}
                </div>
              </section>
            ))}
          </div>
        )}
        </div>
      </section>
    </div>
  );
}
