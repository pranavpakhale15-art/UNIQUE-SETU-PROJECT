import React, { useEffect, useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/lib/AuthContext";
import { useLang } from "@/lib/i18n/LanguageContext";
import { listServices } from "@/api/backendClient";
import ServiceCard from "@/components/ServiceCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search, FileCheck2, ClipboardList, UploadCloud, LineChart, ShieldCheck, ArrowRight } from "lucide-react";

export default function Home() {
  const { user, isAuthenticated } = useAuth();
  const { t, loc } = useLang();
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const page = await listServices();
        setServices(page.items || []);
      } catch (e) {
        setError(e.message || "Unable to load services");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const filtered = useMemo(() => {
    if (!query.trim()) return services;
    const q = query.toLowerCase();
    return services.filter((s) =>
      [s.name_mr, s.name_en, s.name_hi, s.category].some((v) => (v || "").toLowerCase().includes(q))
    );
  }, [services, query]);

  const steps = [
    { icon: ClipboardList, title: t("home.step1Title"), desc: t("home.step1Desc") },
    { icon: FileCheck2, title: t("home.step2Title"), desc: t("home.step2Desc") },
    { icon: UploadCloud, title: t("home.step3Title"), desc: t("home.step3Desc") },
    { icon: LineChart, title: t("home.step4Title"), desc: t("home.step4Desc") },
  ];

  return (
    <div>
      {/* Hero */}
      <section className="relative overflow-hidden border-b border-border bg-gradient-to-b from-primary/[0.04] to-background">
        <div className="absolute inset-0 opacity-[0.04]" style={{ backgroundImage: "radial-gradient(hsl(var(--primary)) 1px, transparent 1px)", backgroundSize: "24px 24px" }} />
        <div className="relative max-w-6xl mx-auto px-4 py-16 md:py-24 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent/10 text-xs font-medium" style={{ color: "hsl(var(--accent))" }}>
            <ShieldCheck className="w-3.5 h-3.5" />
            {t("common.tagline")}
          </div>
          <h1 className="mt-5 font-heading font-bold text-3xl md:text-5xl text-foreground tracking-tight max-w-3xl mx-auto leading-tight">
            {t("home.heroTitle")}
          </h1>
          <p className="mt-4 text-base md:text-lg text-muted-foreground max-w-2xl mx-auto">
            {t("home.heroSubtitle")}
          </p>
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Button asChild size="lg" className="w-full sm:w-auto">
              <a href="#services">{t("home.heroCta")}<ArrowRight className="w-4 h-4 ml-2" /></a>
            </Button>
            <Button asChild size="lg" variant="outline" className="w-full sm:w-auto">
              <Link to={isAuthenticated ? (user?.role === "customer" ? "/dashboard" : "/workspace") : "/register"}>{t("home.heroCta2")}</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="max-w-6xl mx-auto px-4 py-16">
        <div className="text-center mb-10">
          <h2 className="font-heading font-bold text-2xl md:text-3xl text-foreground">{t("home.howItWorksTitle")}</h2>
        </div>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((s, i) => (
            <div key={i} className="relative rounded-xl border border-border bg-card p-6">
              <div className="w-11 h-11 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
                <s.icon className="w-5 h-5" />
              </div>
              <div className="absolute top-6 right-6 text-4xl font-bold text-primary/10">{i + 1}</div>
              <h3 className="mt-4 font-heading font-semibold text-foreground">{s.title}</h3>
              <p className="mt-1.5 text-sm text-muted-foreground">{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Services */}
      <section id="services" className="max-w-6xl mx-auto px-4 py-16 bg-card/30">
        <div className="text-center mb-8">
          <h2 className="font-heading font-bold text-2xl md:text-3xl text-foreground">{t("home.servicesTitle")}</h2>
          <p className="mt-2 text-muted-foreground">{t("home.servicesSubtitle")}</p>
        </div>
        <div className="max-w-md mx-auto mb-8 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("common.search")}
            className="pl-10 h-11"
          />
        </div>
        {loading ? (
          <div className="text-center py-12 text-muted-foreground">{t("common.loading")}</div>
        ) : error ? (
          <div role="alert" className="text-center py-12 text-destructive">{error}</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            {query ? t("home.noServicesMatch") : t("home.servicesUnavailable")}
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((s) => <ServiceCard key={s.id} service={s} />)}
          </div>
        )}
      </section>
    </div>
  );
}