import React, { useCallback, useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useAuth } from "@/lib/AuthContext";
import { useLang } from "@/lib/i18n/LanguageContext";
import StatusBadge, { getStatusTranslationKey } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { ArrowLeft, FileText, Clock, MessageSquare, CheckCircle2, Circle, XCircle, AlertCircle, UploadCloud } from "lucide-react";
import {
  downloadApplicationDocument,
  getApplication,
  reviewApplicationDocument,
  submitApplication,
  updateApplicationOwnerFields,
  updateApplicationStatus,
  uploadApplicationDocument,
} from "@/api/backendClient";

const REVIEW_ICON = {
  pending: Clock,
  verified: CheckCircle2,
  rejected: XCircle,
  replacement_requested: AlertCircle,
  not_applicable: Circle,
};

const NEXT_STATUSES = {
  "Submitted by Customer": ["Received by Shop", "Documents Under Review", "Rejected by Shop", "Cancelled"],
  "Received by Shop": ["Documents Under Review", "Documents Incomplete", "Rejected by Shop", "Cancelled"],
  "Documents Under Review": ["Documents Incomplete", "Correction Requested", "Ready for Processing", "Rejected by Shop", "Cancelled"],
  "Documents Incomplete": ["Documents Under Review", "Correction Requested", "Rejected by Shop", "Cancelled"],
  "Correction Requested": ["Documents Under Review", "Documents Incomplete", "Rejected by Shop", "Cancelled"],
  "Ready for Processing": ["In Progress", "Rejected by Shop", "Cancelled"],
  "In Progress": ["Submitted to Government Authority", "Completed by Shop", "Rejected by Shop", "Cancelled"],
  "Submitted to Government Authority": ["Awaiting Government Decision", "Approved by Authority", "Rejected by Authority"],
  "Awaiting Government Decision": ["Approved by Authority", "Rejected by Authority"],
  "Approved by Authority": ["Completed by Shop"],
  "Rejected by Authority": ["Completed by Shop", "In Progress"],
};

export default function ApplicationDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const { t, loc } = useLang();
  const [app, setApp] = useState(null);
  const [history, setHistory] = useState([]);
  const [docs, setDocs] = useState([]);
  const [comments, setComments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [priority, setPriority] = useState("normal");
  const [dueDate, setDueDate] = useState("");
  const [ownerStatus, setOwnerStatus] = useState("");
  const canManage = user?.role === "owner" || user?.role === "admin";

  const loadApplication = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await getApplication(id);
      setApp(result.application);
      setPriority(result.application.priority || "normal");
      setDueDate(result.application.internal_due_date ? new Date(result.application.internal_due_date).toISOString().slice(0, 10) : "");
      setHistory(result.history);
      setDocs(result.documents);
      setComments(result.comments);
    } catch (e) {
      setError(e.message || "Unable to load this application");
      setApp(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { loadApplication(); }, [loadApplication]);

  const handleUpload = async (item, file, replaceDocumentId) => {
    if (!file) return;
    if (!["application/pdf", "image/jpeg", "image/png"].includes(file.type)) {
      setError("Choose a PDF, JPEG, or PNG file.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("The file exceeds the 10 MB limit.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await uploadApplicationDocument(id, item.id, file, replaceDocumentId);
      await loadApplication();
    } catch (e) {
      setError(e.message || "Unable to upload the document");
    } finally {
      setBusy(false);
    }
  };

  const handleSubmit = async () => {
    setBusy(true);
    setError("");
    try {
      await submitApplication(id);
      await loadApplication();
    } catch (e) {
      setError(e.message || "Unable to submit the application");
    } finally {
      setBusy(false);
    }
  };

  const handleDownload = async (document) => {
    setBusy(true);
    setError("");
    try {
      await downloadApplicationDocument(document.id, document.file_name);
    } catch (e) {
      setError(e.message || "Unable to download the document");
    } finally {
      setBusy(false);
    }
  };

  const handleCopy = async () => {
    const summary = [
      `Application: ${app.application_number || app.id}`,
      `Service: ${loc(app, "service_name") || app.service?.name?.mr || ""}`,
      `Status: ${app.status}`,
      `Priority: ${app.priority || "normal"}`,
      `Application details:\n${(app.form_requirements_snapshot || []).map((item) => `- ${loc(item, "label")}: ${app.application_data?.[item.id] || ""}`).join("\n")}`,
      `Checklist:\n${(app.checklist_snapshot || []).map((item) => `- ${loc(item, "label")}`).join("\n")}`,
    ].join("\n");
    try {
      await navigator.clipboard.writeText(summary);
    } catch {
      setError("Unable to copy application details. Check clipboard permissions and try again.");
    }
  };

  const handleOwnerStatusChange = async () => {
    if (!ownerStatus) return;
    const reason = ownerStatus === "Rejected by Shop" ? window.prompt("Enter the reason for rejecting this application:") : null;
    if (ownerStatus === "Rejected by Shop" && !reason?.trim()) return;
    setBusy(true);
    setError("");
    try {
      await updateApplicationStatus(id, ownerStatus, reason?.trim());
      setOwnerStatus("");
      await loadApplication();
    } catch (e) {
      setError(e.message || "Unable to update application status");
    } finally {
      setBusy(false);
    }
  };

  const handleOwnerFieldsSave = async () => {
    setBusy(true);
    setError("");
    try {
      await updateApplicationOwnerFields(id, {
        priority,
        internal_due_date: dueDate ? new Date(`${dueDate}T23:59:00`).toISOString() : null,
      });
      await loadApplication();
    } catch (e) {
      setError(e.message || "Unable to save application priority and due date");
    } finally {
      setBusy(false);
    }
  };

  const handleDocumentReview = async (document, verificationStatus) => {
    const reviewerComment = verificationStatus === "correction_requested"
      ? window.prompt("Tell the customer what needs to be corrected:")
      : null;
    if (verificationStatus === "correction_requested" && !reviewerComment?.trim()) return;
    setBusy(true);
    setError("");
    try {
      await reviewApplicationDocument(document.id, verificationStatus, reviewerComment?.trim());
      await loadApplication();
    } catch (e) {
      setError(e.message || "Unable to review document");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return <div className="max-w-3xl mx-auto px-4 py-20 text-center text-muted-foreground">{t("common.loading")}</div>;
  }
  if (!app) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-20 text-center">
        <p role={error ? "alert" : undefined} className={error ? "text-destructive" : "text-muted-foreground"}>{error || "404"}</p>
        <Button asChild variant="link"><Link to="/dashboard">{t("appDetail.backToDashboard")}</Link></Button>
      </div>
    );
  }

  const docsByItem = {};
  (docs || []).forEach((d) => {
    if (!docsByItem[d.checklist_item_id] || d.upload_date > (docsByItem[d.checklist_item_id].upload_date || "")) {
      docsByItem[d.checklist_item_id] = d;
    }
  });

  const reversedHistory = [...history].reverse();
  const canUpload = user?.role === "customer" && ["Draft", "Documents Incomplete", "Correction Requested"].includes(app.status);
  const uploadedItemIds = new Set(docs.map((document) => document.checklist_item_id));
  const missingRequiredDocuments = (app.checklist_snapshot || []).some(
    (item) => item.required !== false && !uploadedItemIds.has(item.id)
  );

  return (
    <div className="max-w-3xl mx-auto px-4 py-10">
      <Link to="/dashboard" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-6">
        <ArrowLeft className="w-4 h-4" />{t("appDetail.backToDashboard")}
      </Link>

      {error && <div role="alert" className="mb-4 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">{error}</div>}

      <div className="flex items-start justify-between gap-3 mb-6">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
            <FileText className="w-6 h-6" />
          </div>
          <div>
            <h1 className="font-heading font-bold text-xl text-foreground">{loc(app, "service_name")}</h1>
            <p className="text-xs text-muted-foreground">{app.application_id || app.id.slice(-8)}</p>
          </div>
        </div>
        <StatusBadge status={app.status} />
      </div>

      {user?.role === "staff" && (
        <div className="mb-6 flex justify-end">
          <Button type="button" variant="outline" onClick={handleCopy}>Copy application summary</Button>
        </div>
      )}

      {canManage && (
        <section className="mb-6 rounded-xl border border-border bg-card p-5">
          <h2 className="font-heading font-semibold text-foreground mb-4">Owner review and scheduling</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="text-sm">Priority
              <select className="mt-1 h-10 w-full rounded-md border border-input bg-background px-3" value={priority} onChange={(event) => setPriority(event.target.value)}>
                {["low", "normal", "high", "urgent"].map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <label className="text-sm">Internal due date
              <input type="date" className="mt-1 h-10 w-full rounded-md border border-input bg-background px-3" value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
            </label>
            <div className="flex items-end"><Button type="button" variant="outline" disabled={busy} onClick={handleOwnerFieldsSave}>Save priority and date</Button></div>
          </div>
          {(NEXT_STATUSES[app.status] || []).length > 0 && (
            <div className="mt-4 flex flex-wrap items-end gap-2">
              <label className="text-sm">Update customer-visible status
                <select className="mt-1 block h-10 rounded-md border border-input bg-background px-3" value={ownerStatus} onChange={(event) => setOwnerStatus(event.target.value)}>
                  <option value="">Select next status…</option>
                  {(NEXT_STATUSES[app.status] || []).map((status) => <option key={status} value={status}>{status}</option>)}
                </select>
              </label>
              <Button type="button" disabled={busy || !ownerStatus} onClick={handleOwnerStatusChange}>Update status</Button>
            </div>
          )}
        </section>
      )}

      {(app.form_requirements_snapshot || []).length > 0 && (
        <section className="rounded-xl border border-border bg-card p-5 mb-6">
          <h2 className="font-heading font-semibold text-foreground mb-3">Application details</h2>
          <dl className="grid gap-3 sm:grid-cols-2">
            {app.form_requirements_snapshot.map((item) => (
              <div key={item.id} className="rounded-lg bg-muted/30 p-3">
                <dt className="text-xs text-muted-foreground">{loc(item, "label")}</dt>
                <dd className="mt-1 break-words text-sm text-foreground">{app.application_data?.[item.id] || "—"}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {/* Checklist */}
      <div className="rounded-xl border border-border bg-card p-5 mb-6">
        <h2 className="font-heading font-semibold text-foreground mb-3">{t("appDetail.checklist")}</h2>
        <ul className="space-y-2">
          {(app.checklist_snapshot || []).map((item, i) => {
            const doc = docsByItem[item.id];
            const Icon = doc ? (REVIEW_ICON[doc.review_status] || Clock) : UploadCloud;
            return (
              <li key={item.id || i} className="flex items-start gap-3 p-3 rounded-lg bg-muted/30">
                <Icon className={`w-5 h-5 shrink-0 mt-0.5 ${doc ? (doc.review_status === "verified" ? "text-green-600" : doc.review_status === "rejected" ? "text-red-600" : doc.review_status === "replacement_requested" ? "text-orange-600" : "text-muted-foreground") : "text-muted-foreground/50"}`} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-foreground">{loc(item, "label")}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {item.required ? t("common.required") : t("common.optional")}
                    {doc ? ` · ${doc.submission_mode === "physical" ? "दुकानात प्राप्त" : "ऑनलाइन"} · ${t(`status.${doc.review_status}`) || doc.review_status}` : ""}
                  </p>
                  {doc?.reviewer_comments && (
                    <p className="text-xs text-orange-700 mt-1">{doc.reviewer_comments}</p>
                  )}
                  {doc?.file_name && (
                    <button
                      type="button"
                      className="mt-2 text-xs font-medium text-primary hover:underline disabled:opacity-50"
                      disabled={busy}
                      onClick={() => handleDownload(doc)}
                    >
                      {doc.file_name} · Download
                    </button>
                  )}
                  {canManage && doc && !["verified", "correction_requested"].includes(doc.review_status) && (
                    <div className="mt-2 flex gap-3">
                      <button type="button" disabled={busy} className="text-xs font-medium text-green-700 hover:underline disabled:opacity-50" onClick={() => handleDocumentReview(doc, "verified")}>Accept document</button>
                      <button type="button" disabled={busy} className="text-xs font-medium text-destructive hover:underline disabled:opacity-50" onClick={() => handleDocumentReview(doc, "correction_requested")}>Request correction</button>
                    </div>
                  )}
                  {canUpload && (!doc || ["rejected", "replacement_requested"].includes(doc.review_status)) && (
                    <label className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline cursor-pointer">
                      {doc ? "Upload replacement" : "Upload document"}
                      <input
                        type="file"
                        accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
                        className="sr-only"
                        disabled={busy}
                        onChange={(event) => {
                          handleUpload(item, event.target.files?.[0], doc?.id);
                          event.target.value = "";
                        }}
                      />
                    </label>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </div>

      {/* Comments */}
      {(app.customer_comments || comments.length > 0) && (
        <div className="rounded-xl border border-border bg-card p-5 mb-6">
          <h2 className="font-heading font-semibold text-foreground mb-3 flex items-center gap-2"><MessageSquare className="w-4 h-4" />{t("appDetail.comments")}</h2>
          {app.customer_comments && (
            <div className="mb-3">
              <p className="text-xs font-medium text-muted-foreground mb-1">{t("appDetail.customerComments")}</p>
              <p className="text-sm text-foreground">{app.customer_comments}</p>
            </div>
          )}
          {comments.map((comment) => (
            <div key={comment.id || comment._id} className="border-t border-border pt-3 mt-3">
              <p className="text-sm text-foreground">{comment.message}</p>
              <p className="text-xs text-muted-foreground mt-1">{new Date(comment.created_at).toLocaleString()}</p>
            </div>
          ))}
        </div>
      )}

      {user?.role === "customer" && app.status === "Draft" && (
        <div className="mb-6 flex flex-col gap-2">
          <Button onClick={handleSubmit} disabled={busy || missingRequiredDocuments}>
            {busy ? "Please wait..." : "Submit application"}
          </Button>
          {missingRequiredDocuments && <p className="text-xs text-muted-foreground text-center">Upload all required documents before submitting.</p>}
        </div>
      )}

      {/* Status history */}
      <div className="rounded-xl border border-border bg-card p-5">
        <h2 className="font-heading font-semibold text-foreground mb-4">{t("appDetail.history")}</h2>
        {reversedHistory.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("appDetail.noHistory")}</p>
        ) : (
          <ol className="relative border-l border-border ml-2 space-y-4">
            {reversedHistory.map((h, i) => (
              <li key={h.id || i} className="pl-4">
                <span className="absolute -left-[5px] mt-1.5 w-2.5 h-2.5 rounded-full bg-primary" />
                <p className="text-sm font-medium text-foreground">{t(`status.${getStatusTranslationKey(h.new_status)}`) || h.new_status}</p>
                {h.reason && <p className="text-xs text-muted-foreground mt-0.5">{h.reason}</p>}
                <p className="text-xs text-muted-foreground mt-0.5">
                  {new Date(h.timestamp).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                </p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}