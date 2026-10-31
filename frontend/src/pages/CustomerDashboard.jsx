import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useLang } from "@/lib/i18n/LanguageContext";
import StatusBadge from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { FileText, Plus, ArrowRight } from "lucide-react";
import { listApplications, listUnreadDocumentNotifications } from "@/api/backendClient";

const TERMINAL_STATUSES = new Set(["Completed by Shop", "Rejected by Shop", "Cancelled"]);
const PROGRESS_STATUSES = [
  "Draft", "Submitted by Customer", "Received by Shop", "Documents Under Review",
  "Documents Incomplete", "Correction Requested", "Ready for Processing", "In Progress",
  "Submitted to Government Authority", "Awaiting Government Decision", "Approved by Authority",
  "Rejected by Authority",
];

function progressFor(status) {
  const index = Math.max(0, PROGRESS_STATUSES.indexOf(status));
  return Math.round(((index + 1) / PROGRESS_STATUSES.length) * 100);
}

export default function CustomerDashboard() {
  const { t, loc } = useLang();
  const [applications, setApplications] = useState([]);
  const [unreadDocuments, setUnreadDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([listApplications(), listUnreadDocumentNotifications()]).then(([applicationPage, notifications]) => {
      if (!active) return;
      setApplications((applicationPage.items || []).filter((item) => !TERMINAL_STATUSES.has(item.status)));
      setUnreadDocuments(notifications.items || []);
    }).catch((loadError) => {
      if (active) setError(loadError.message || "Unable to load your dashboard.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const handleRead = (event) => {
      const readId = event.detail?.notificationId;
      if (readId) setUnreadDocuments((current) => current.filter((item) => (item.id || item._id) !== readId));
    };
    const handleReadAll = () => setUnreadDocuments([]);
    const refreshOnFocus = () => {
      if (document.visibilityState !== "visible") return;
      listUnreadDocumentNotifications().then((result) => setUnreadDocuments(result.items || [])).catch(() => {});
    };
    window.addEventListener("setu:notification-read", handleRead);
    window.addEventListener("setu:notifications-read-all", handleReadAll);
    document.addEventListener("visibilitychange", refreshOnFocus);
    return () => {
      window.removeEventListener("setu:notification-read", handleRead);
      window.removeEventListener("setu:notifications-read-all", handleReadAll);
      document.removeEventListener("visibilitychange", refreshOnFocus);
    };
  }, []);

  return (
    <main className="mx-auto max-w-5xl px-4 py-10">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div><p className="text-xs font-semibold uppercase tracking-wide text-primary">Customer dashboard</p><h1 className="mt-1 font-heading text-2xl font-bold md:text-3xl">Ongoing Applications</h1><p className="mt-1 text-sm text-muted-foreground">Track applications that are in progress or need your attention.</p></div>
        <Button asChild><Link to="/services"><Plus className="mr-2 h-4 w-4" />New Application</Link></Button>
      </div>
      {error && <p role="alert" className="mb-5 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
      {unreadDocuments.length > 0 && (
        <section aria-labelledby="unread-documents-heading" className="mb-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <h2 id="unread-documents-heading" className="font-heading font-semibold text-foreground">New documents from the owner</h2>
          <ul className="mt-2 space-y-2">
            {unreadDocuments.map((notification) => (
              <li key={notification.id || notification._id} className="flex flex-wrap items-center justify-between gap-3 text-sm">
                <p>{notification.message || notification.title}</p>
                <Button asChild size="sm" variant="outline"><Link to={`/applications/${notification.related_application_id}?notificationId=${encodeURIComponent(notification.id || notification._id)}${notification.related_document_id ? `&documentId=${encodeURIComponent(notification.related_document_id)}` : ""}`}>{notification.related_document_id ? "View document" : "Read message"} <ArrowRight className="ml-1 h-4 w-4" /></Link></Button>
              </li>
            ))}
          </ul>
        </section>
      )}
      {loading ? <p className="py-16 text-center text-muted-foreground">{t("common.loading")}</p> : applications.length === 0 ? (
        <section className="rounded-xl border border-dashed border-border p-12 text-center">
          <FileText className="mx-auto mb-3 h-10 w-10 text-muted-foreground/50" />
          <p className="text-muted-foreground">No ongoing applications need your attention.</p>
          <Button asChild className="mt-4"><Link to="/services">Browse services</Link></Button>
        </section>
      ) : <section aria-label="Ongoing applications" className="space-y-3">
        {applications.map((application) => {
          const id = application.id || application._id;
          const progress = progressFor(application.status);
          return (
            <article key={id} className="rounded-xl border border-border bg-card p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"><FileText className="h-5 w-5" /></div>
                  <div className="min-w-0">
                    <p className="truncate font-medium">{loc(application, "service_name") || application.service?.name?.en || application.service_name_en || "Service application"}</p>
                    <p className="mt-1 text-xs text-muted-foreground">Application ID: {application.application_number || application.application_id || id}</p>
                    <p className="mt-1 text-xs text-muted-foreground">Submitted: {application.submitted_at ? new Date(application.submitted_at).toLocaleDateString() : "Draft — not submitted"}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3"><StatusBadge status={application.status} /><Button asChild size="sm" variant="outline"><Link to={`/applications/${id}`}>View Details</Link></Button></div>
              </div>
              <div className="mt-4" aria-label={`Application progress ${progress}%`}>
                <div className="mb-1 flex justify-between text-xs text-muted-foreground"><span>Progress</span><span>{progress}%</span></div>
                <div className="h-2 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary transition-all" style={{ width: `${progress}%` }} /></div>
              </div>
            </article>
          );
        })}
      </section>}
    </main>
  );
}
