import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useLang } from "@/lib/i18n/LanguageContext";
import StatusBadge from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Plus, FileText, ChevronRight } from "lucide-react";
import { listApplications, listCompletedWork, listNotifications, listServices } from "@/api/backendClient";
import ServiceCard from "@/components/ServiceCard";

export default function CustomerDashboard() {
  const { t, loc, lang } = useLang();
  const [apps, setApps] = useState([]);
  const [completedApps, setCompletedApps] = useState([]);
  const [services, setServices] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notificationError, setNotificationError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const [applicationsPage, completedPage, servicesPage] = await Promise.all([
          listApplications(),
          listCompletedWork(),
          listServices(lang),
        ]);
        setApps(applicationsPage.items || []);
        setCompletedApps(completedPage.items || []);
        setServices(servicesPage.items || []);
        try {
          const notificationPage = await listNotifications();
          setNotifications(notificationPage.items || []);
          setNotificationError("");
        } catch (notificationLoadError) {
          setNotificationError(notificationLoadError.message || "Unable to load document notifications");
        }
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
          {notificationError && <p role="alert" className="mb-4 text-sm text-destructive">{notificationError}</p>}
          {notifications.filter((notification) => notification.event_type === "document.issued_available" && notification.related_application_id).length > 0 && (
            <section aria-labelledby="issued-documents-heading" className="mb-8 rounded-xl border border-green-200 bg-green-50 p-4">
              <h2 id="issued-documents-heading" className="font-heading font-semibold text-foreground mb-2">Documents available</h2>
              <ul className="space-y-2">
                {notifications.filter((notification) => notification.event_type === "document.issued_available" && notification.related_application_id).map((notification) => (
                  <li key={notification.id || notification._id} className="flex flex-wrap items-center justify-between gap-3 text-sm">
                    <p>{notification.message || notification.title}</p>
                    <Button asChild size="sm" variant="outline">
                      <Link to={`/applications/${notification.related_application_id}`}>View document</Link>
                    </Button>
                  </li>
                ))}
              </ul>
            </section>
          )}
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
          <section aria-labelledby="completed-applications-heading" className="mb-12">
            <h2 id="completed-applications-heading" className="font-heading font-semibold text-xl mb-4">Completed Tasks</h2>
            {completedApps.length === 0 ? (
              <div className="rounded-xl border border-dashed border-border p-6 text-sm text-muted-foreground">
                No applications have a final document shared with you yet.
              </div>
            ) : (
              <div className="space-y-3">
                {completedApps.map((application) => (
                  <Link
                    key={application.id}
                    to={`/applications/${application.id}`}
                    className="block rounded-xl border border-border bg-card p-4 transition-all hover:border-primary/40 hover:shadow-sm"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-medium text-foreground">{loc(application, "service_name") || application.application_number}</p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {application.application_number} · Final document shared {application.issued_document?.shared_at
                            ? new Date(application.issued_document.shared_at).toLocaleDateString()
                            : ""}
                        </p>
                        {application.issued_document?.file_name && (
                          <p className="mt-1 text-xs text-muted-foreground">Document: {application.issued_document.file_name}</p>
                        )}
                      </div>
                      <StatusBadge status={application.status} />
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