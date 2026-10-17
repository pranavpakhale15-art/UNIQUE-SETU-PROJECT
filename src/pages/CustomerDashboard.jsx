import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useLang } from "@/lib/i18n/LanguageContext";
import StatusBadge from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Plus, FileText, ChevronRight } from "lucide-react";
import { listApplications, listServices } from "@/api/backendClient";
import ServiceCard from "@/components/ServiceCard";

export default function CustomerDashboard() {
  const { t, loc, lang } = useLang();
  const [apps, setApps] = useState([]);
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const [applicationsPage, servicesPage] = await Promise.all([
          listApplications(),
          listServices(lang),
        ]);
        setApps(applicationsPage.items || []);
        setServices(servicesPage.items || []);
      } catch (e) {
        setError(e.message || "Unable to load your customer dashboard");
      } finally {
        setLoading(false);
      }
    })();
  }, [lang]);

  return (
    <div className="max-w-5xl mx-auto px-4 py-10">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="font-heading font-bold text-2xl md:text-3xl text-foreground">{t("dashboard.title")}</h1>
          <p className="text-muted-foreground text-sm mt-1">{t("dashboard.subtitle")}</p>
        </div>
        <Button asChild>
          <Link to="/applications/new"><Plus className="w-4 h-4 mr-1.5" />{t("dashboard.newApplication")}</Link>
        </Button>
      </div>

      {loading ? (
        <div className="text-center py-16 text-muted-foreground">{t("common.loading")}</div>
      ) : error ? (
        <div role="alert" className="text-center py-16 text-destructive">{error}</div>
      ) : (
        <>
          <section aria-labelledby="applications-heading" className="mb-12">
            <h2 id="applications-heading" className="font-heading font-semibold text-xl mb-4">{t("dashboard.title")}</h2>
            {apps.length === 0 ? (
              <div className="text-center py-10 rounded-xl border border-dashed border-border">
                <FileText className="w-10 h-10 text-muted-foreground/40 mx-auto mb-3" />
                <p className="text-muted-foreground">{t("dashboard.noApplications")}</p>
              </div>
            ) : (
              <div className="space-y-3">
                {apps.map((a) => (
                  <Link
                    key={a.id}
                    to={`/applications/${a.id}`}
                    className="block rounded-xl border border-border bg-card p-4 hover:border-primary/40 hover:shadow-sm transition-all"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-10 h-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
                          <FileText className="w-5 h-5" />
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium text-foreground truncate">{loc(a, "service_name")}</p>
                          <p className="text-xs text-muted-foreground">{a.application_id || a.id.slice(-8)}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <StatusBadge status={a.status} />
                        <ChevronRight className="w-4 h-4 text-muted-foreground" />
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </section>
          <section aria-labelledby="services-heading">
            <div className="flex items-center justify-between gap-3 mb-4">
              <div>
                <h2 id="services-heading" className="font-heading font-semibold text-xl">{t("home.servicesTitle")}</h2>
                <p className="text-sm text-muted-foreground mt-1">{services.length} {t("home.servicesCount")}</p>
              </div>
              <Button asChild variant="outline">
                <Link to="/applications/new"><Plus className="w-4 h-4 mr-1.5" />{t("dashboard.newApplication")}</Link>
              </Button>
            </div>
            {services.length === 0 ? (
              <div className="text-center py-10 rounded-xl border border-dashed border-border text-muted-foreground">
                {t("home.servicesUnavailable")}
              </div>
            ) : (
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {services.map((service) => <ServiceCard key={service.id} service={service} />)}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}