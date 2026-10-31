import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useLang } from "@/lib/i18n/LanguageContext";
import { getApplicationTask } from "@/api/backendClient";
import StatusBadge from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";

function localizedLabel(item, language) {
  const labels = item?.label && typeof item.label === "object" ? item.label : {};
  return labels[language] || labels.en || labels.mr || labels.hi || item?.label || item?.name || "Application detail";
}

export default function TaskDetail() {
  const { id } = useParams();
  const { lang, loc } = useLang();
  const [task, setTask] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const result = await getApplicationTask(id);
        if (active) setTask(result);
      } catch (loadError) {
        if (active) setError(loadError.message || "Unable to load this task");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [id]);

  if (loading) {
    return <div className="max-w-3xl mx-auto px-4 py-20 text-center text-muted-foreground">Loading task…</div>;
  }
  if (!task) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-20 text-center">
        <p role={error ? "alert" : undefined} className={error ? "text-destructive" : "text-muted-foreground"}>{error || "Task not found"}</p>
        <Button asChild variant="link"><Link to="/workspace">Back to workspace</Link></Button>
      </div>
    );
  }

  const application = task.application;
  const customer = task.customer;

  return (
    <div className="max-w-3xl mx-auto px-4 py-10">
      <Link to="/workspace" className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" />Back to workspace
      </Link>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">Task details</p>
          <h1 className="mt-1 font-heading text-2xl font-bold text-foreground">{task.title}</h1>
          {task.description && <p className="mt-2 text-sm text-muted-foreground">{task.description}</p>}
        </div>
        <StatusBadge status={task.status} />
      </div>

      <section className="mb-6 rounded-xl border border-border bg-card p-5">
        <h2 className="mb-3 font-heading font-semibold">Task information</h2>
        <dl className="grid gap-3 sm:grid-cols-2">
          <div><dt className="text-xs text-muted-foreground">Priority</dt><dd className="mt-1 text-sm">{task.priority || "normal"}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Due date</dt><dd className="mt-1 text-sm">{task.due_date ? new Date(task.due_date).toLocaleString() : "No due date"}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Task status</dt><dd className="mt-1 text-sm">{task.status}</dd></div>
        </dl>
      </section>

      {application ? (
        <>
          <section className="mb-6 rounded-xl border border-border bg-card p-5">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-heading font-semibold">Application and customer</h2>
              <StatusBadge status={application.status} />
            </div>
            <p className="text-sm font-medium">{loc(application, "service_name") || application.application_number}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {application.application_number}
              {application.submitted_at ? ` · Submitted ${new Date(application.submitted_at).toLocaleString()}` : " · Not submitted"}
            </p>
            <dl className="mt-4 grid gap-3 sm:grid-cols-2">
              <div><dt className="text-xs text-muted-foreground">Customer name</dt><dd className="mt-1 text-sm">{customer?.full_name || "—"}</dd></div>
              <div><dt className="text-xs text-muted-foreground">Mobile number</dt><dd className="mt-1 text-sm">{customer?.mobile_number || "—"}</dd></div>
              {customer?.email && <div><dt className="text-xs text-muted-foreground">Email</dt><dd className="mt-1 break-words text-sm">{customer.email}</dd></div>}
            </dl>
            <Button asChild variant="outline" size="sm" className="mt-4">
              <Link to={`/applications/${application.id}`}>Open full application and documents</Link>
            </Button>
          </section>

          {(application.form_requirements_snapshot || []).length > 0 && (
            <section className="mb-6 rounded-xl border border-border bg-card p-5">
              <h2 className="mb-3 font-heading font-semibold">Application details</h2>
              <dl className="grid gap-3 sm:grid-cols-2">
                {application.form_requirements_snapshot.map((item) => (
                  <div key={item.id || item.item_id} className="rounded-lg bg-muted/30 p-3">
                    <dt className="text-xs text-muted-foreground">{localizedLabel(item, lang)}</dt>
                    <dd className="mt-1 break-words text-sm">{application.application_data?.[item.id || item.item_id] || "—"}</dd>
                  </div>
                ))}
              </dl>
            </section>
          )}

          <section className="rounded-xl border border-border bg-card p-5">
            <h2 className="mb-3 font-heading font-semibold">Submitted documents</h2>
            {(task.documents || []).length === 0 ? (
              <p className="text-sm text-muted-foreground">No submitted documents are available for this application.</p>
            ) : (
              <ul className="space-y-2">
                {task.documents.map((document) => (
                  <li key={document.id} className="rounded-lg bg-muted/30 p-3 text-sm">
                    <p className="font-medium">{document.file_name || "Physical document"}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {document.verification_status || document.submission_method}
                      {document.created_at ? ` · ${new Date(document.created_at).toLocaleString()}` : ""}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      ) : (
        <p className="rounded-xl border border-border bg-muted/20 p-5 text-sm text-muted-foreground">
          Application details are not available to this account under the current assignment.
        </p>
      )}
    </div>
  );
}
