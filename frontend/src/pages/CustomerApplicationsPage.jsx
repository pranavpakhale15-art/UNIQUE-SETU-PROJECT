import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FileText, ArrowUpRight } from "lucide-react";
import StatusBadge from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { listApplications, listCompletedWork } from "@/api/backendClient";
import { useLang } from "@/lib/i18n/LanguageContext";

export default function CustomerApplicationsPage() {
  const { loc } = useLang();
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([listApplications(), listCompletedWork()]).then(([activePage, completedPage]) => {
      if (!active) return;
      const activeItems = (activePage.items || []).map((item) => ({ ...item, history_group: "Application history" }));
      const completedItems = (completedPage.items || []).map((item) => ({ ...item, history_group: "Completed applications" }));
      const unique = new Map([...activeItems, ...completedItems].map((item) => [item.id || item._id, item]));
      setApplications([...unique.values()].sort((a, b) => new Date(b.submitted_at || b.completed_at || b.created_at || 0) - new Date(a.submitted_at || a.completed_at || a.created_at || 0)));
    }).catch((loadError) => {
      if (active) setError(loadError.message || "Unable to load application history.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  return (
    <main className="mx-auto max-w-5xl px-4 py-10">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div><p className="text-xs font-semibold uppercase tracking-wide text-primary">Customer account</p><h1 className="mt-1 font-heading text-2xl font-bold md:text-3xl">My Applications / History</h1><p className="mt-1 text-sm text-muted-foreground">Review ongoing, completed and past application records.</p></div>
        <Button asChild><Link to="/services">New Application</Link></Button>
      </div>
      {error && <p role="alert" className="mb-4 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
      {loading ? <p className="py-16 text-center text-muted-foreground">Loading application history…</p> : applications.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border p-12 text-center"><FileText className="mx-auto mb-3 h-9 w-9 text-muted-foreground/50" /><p className="text-sm text-muted-foreground">No applications yet.</p><Button asChild className="mt-4"><Link to="/services">Browse services</Link></Button></div>
      ) : <div className="space-y-3">{applications.map((application) => {
        const id = application.id || application._id;
        return <article key={id} className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border bg-card p-4">
          <div className="min-w-0"><p className="truncate font-medium">{loc(application, "service_name") || application.service?.name?.en || application.service_name_en || application.application_number}</p><p className="mt-1 text-xs text-muted-foreground">{application.application_number || application.application_id || id} · {application.submitted_at ? new Date(application.submitted_at).toLocaleDateString() : application.completed_at ? `Completed ${new Date(application.completed_at).toLocaleDateString()}` : "Draft"}</p></div>
          <div className="flex items-center gap-3"><StatusBadge status={application.status || "Completed by Shop"} /><Button asChild size="sm" variant="outline"><Link to={`/applications/${id}`}>View details <ArrowUpRight className="ml-1 h-4 w-4" /></Link></Button></div>
        </article>;
      })}</div>}
    </main>
  );
}
