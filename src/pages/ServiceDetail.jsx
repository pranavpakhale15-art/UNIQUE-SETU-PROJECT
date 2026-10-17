import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useAuth } from "@/lib/AuthContext";
import { useLang } from "@/lib/i18n/LanguageContext";
import { getService } from "@/api/backendClient";
import { Button } from "@/components/ui/button";
import { ArrowLeft, CheckCircle2, Circle, FileText, Info } from "lucide-react";

export default function ServiceDetail() {
  const { slug } = useParams();
  const { user, isAuthenticated } = useAuth();
  const { t, loc } = useLang();
  const [service, setService] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        setService(await getService(slug));
      } catch (e) {
        if (e.status !== 404) setError(e.message || "Unable to load service");
      } finally {
        setLoading(false);
      }
    })();
  }, [slug]);

  if (loading) {
    return <div className="max-w-4xl mx-auto px-4 py-20 text-center text-muted-foreground">{t("common.loading")}</div>;
  }
  if (!service) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <p role={error ? "alert" : undefined} className={error ? "text-destructive" : "text-muted-foreground"}>{error || "404"}</p>
        <Button asChild variant="link"><Link to="/">{t("service.backToServices")}</Link></Button>
      </div>
    );
  }

  const name = loc(service, "name");
  const desc = loc(service, "description");

  return (
    <div className="max-w-4xl mx-auto px-4 py-10">
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-6">
        <ArrowLeft className="w-4 h-4" />{t("service.backToServices")}
      </Link>

      <div className="flex items-start gap-4">
        <div className="w-14 h-14 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
          <FileText className="w-7 h-7" />
        </div>
        <div>
          <span className="inline-block text-xs font-medium px-2 py-0.5 rounded-full bg-accent/10 mb-2" style={{ color: "hsl(var(--accent))" }}>
            {service.category}
          </span>
          <h1 className="font-heading font-bold text-2xl md:text-3xl text-foreground">{name}</h1>
        </div>
      </div>

      <p className="mt-5 text-muted-foreground leading-relaxed">{desc}</p>

      <div className="mt-4 flex items-start gap-2 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-sm">
        <Info className="w-4 h-4 mt-0.5 shrink-0" />
        <span>{t("home.disclaimer")}</span>
      </div>

      <div className="mt-8">
        <h2 className="font-heading font-semibold text-lg text-foreground mb-4">{t("service.requiredDocs")}</h2>
        <ul className="space-y-2">
          {service.checklist?.map((item, i) => (
            <li key={item.id || i} className="flex items-start gap-3 p-3 rounded-lg border border-border bg-card">
              {item.required ? (
                <CheckCircle2 className="w-5 h-5 text-green-600 shrink-0 mt-0.5" />
              ) : (
                <Circle className="w-5 h-5 text-muted-foreground shrink-0 mt-0.5" />
              )}
              <div>
                <p className="text-foreground font-medium">{loc(item, "label")}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {item.required ? t("common.required") : t("common.optional")}
                </p>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {(!isAuthenticated || user?.role === "customer") && <div className="mt-8">
        <Button asChild size="lg">
          <Link to={isAuthenticated
            ? `/applications/new?service=${service.service_slug}`
            : `/login?returnTo=${encodeURIComponent(`/services/${encodeURIComponent(slug)}`)}`}>
            {isAuthenticated ? t("common.applyNow") : t("common.loginToApply")}
          </Link>
        </Button>
      </div>}
    </div>
  );
}