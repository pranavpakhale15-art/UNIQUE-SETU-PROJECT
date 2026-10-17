import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { useLang } from "@/lib/i18n/LanguageContext";
import { createApplication, listServices, submitApplication, updateApplicationDraft, uploadApplicationDocument } from "@/api/backendClient";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Loader2, CheckCircle2, Circle, UploadCloud, FileCheck2, X, AlertCircle } from "lucide-react";

const MAX_SIZE = 10 * 1024 * 1024;
const VALID_TYPES = ["application/pdf", "image/jpeg", "image/png"];

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function NewApplication() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { t, loc, lang } = useLang();
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedSlug, setSelectedSlug] = useState(params.get("service") || "");
  const [comments, setComments] = useState("");
  const [applicationData, setApplicationData] = useState({});
  const [uploads, setUploads] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [activeDraftId, setActiveDraftId] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const page = await listServices(lang);
        setServices(page.items || []);
      } catch (e) {
        setError(e.message || "Unable to load services");
      } finally {
        setLoading(false);
      }
    })();
  }, [lang]);

  const selected = services.find((s) => s.service_slug === selectedSlug);
  const checklist = selected?.checklist || [];
  const formRequirements = selected?.form_requirements || [];
  const requiredItems = checklist.filter((i) => i.required);
  const uploadedRequired = requiredItems.filter((i) => uploads[i.id]?.file);
  const remaining = requiredItems.length - uploadedRequired.length;
  const missingFormValues = formRequirements.filter(
    (item) => item.required && !applicationData[item.id]?.trim()
  ).length;
  const anyUploading = Object.values(uploads).some((u) => u.uploading);
  const canSubmit = selectedSlug && remaining === 0 && missingFormValues === 0 && !anyUploading && !submitting;

  const handleFile = async (item, file) => {
    if (!file) return;
    setError("");
    if (!VALID_TYPES.includes(file.type)) {
      setUploads((prev) => ({ ...prev, [item.id]: { error: t("newApp.invalidType") } }));
      return;
    }
    if (file.size > MAX_SIZE) {
      setUploads((prev) => ({ ...prev, [item.id]: { error: t("newApp.fileTooLarge") } }));
      return;
    }
    setUploads((prev) => ({ ...prev, [item.id]: { ...prev[item.id], uploading: true, error: undefined } }));
    try {
      setUploads((prev) => ({
        ...prev,
        [item.id]: {
          file,
          file_name: file.name,
          file_size: file.size,
          replace_document_id: prev[item.id]?.document_id || prev[item.id]?.replace_document_id,
        },
      }));
    } catch (e) {
      setUploads((prev) => ({ ...prev, [item.id]: { error: e.message || "Upload failed" } }));
    }
  };

  const removeFile = (itemId) => {
    setUploads((prev) => {
      const next = { ...prev };
      delete next[itemId];
      return next;
    });
  };

  const createApp = async (asDraft) => {
    setError("");
    if (!selected) {
      setError(t("newApp.selectService"));
      return;
    }
    if (!asDraft && (remaining > 0 || missingFormValues > 0)) {
      setError(t("newApp.requiredToSubmit"));
      return;
    }
    setSubmitting(true);
    try {
      const application = activeDraftId
        ? { id: activeDraftId }
        : await createApplication(selected.id, comments);
      setActiveDraftId(application.id);
      await updateApplicationDraft(application.id, comments, applicationData);

      for (const item of checklist) {
        const upload = uploads[item.id];
        if (!upload?.file || upload.document_id) continue;
        const document = await uploadApplicationDocument(application.id, item.id, upload.file, upload.replace_document_id);
        setUploads((previous) => ({
          ...previous,
          [item.id]: { ...previous[item.id], document_id: document.id, replace_document_id: null },
        }));
      }

      if (!asDraft) await submitApplication(application.id);
      navigate(`/applications/${application.id}`);
    } catch (e) {
      setError(e.message || "Error");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div className="max-w-2xl mx-auto px-4 py-20 text-center text-muted-foreground">{t("common.loading")}</div>;
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <Link to="/dashboard" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-6">
        <ArrowLeft className="w-4 h-4" />{t("appDetail.backToDashboard")}
      </Link>
      <h1 className="font-heading font-bold text-2xl text-foreground mb-6">{t("newApp.title")}</h1>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-destructive/10 text-destructive text-sm flex items-start gap-2">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />{error}
        </div>
      )}

      <div className="space-y-5 rounded-xl border border-border bg-card p-6">
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">{t("newApp.selectService")}</label>
          <select
            value={selectedSlug}
            onChange={(e) => { setSelectedSlug(e.target.value); setUploads({}); setApplicationData({}); setActiveDraftId(null); }}
            disabled={services.length === 0}
            className="w-full h-11 rounded-lg border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">—</option>
            {services.map((s) => (
              <option key={s.id} value={s.service_slug}>{loc(s, "name")}</option>
            ))}
          </select>
          {services.length === 0 && !error && (
            <p className="mt-3 text-sm text-muted-foreground">{t("newApp.noServicesAvailable")}</p>
          )}
        </div>

        {selected && (
          <>
            {formRequirements.length > 0 && (
              <section>
                <h2 className="block text-sm font-medium text-foreground mb-3">{t("newApp.detailsToProvide")}</h2>
                <div className="space-y-3">
                  {formRequirements.map((item) => (
                    <label key={item.id} className="block text-sm text-foreground">
                      {loc(item, "label")} {item.required && <span className="text-destructive">*</span>}
                      <input
                        type="text"
                        maxLength={2000}
                        required={item.required}
                        value={applicationData[item.id] || ""}
                        onChange={(event) => setApplicationData((current) => ({ ...current, [item.id]: event.target.value }))}
                        className="mt-1 h-11 w-full rounded-lg border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                    </label>
                  ))}
                </div>
              </section>
            )}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-foreground">{t("newApp.uploadDocs")}</label>
                {remaining > 0 && (
                  <span className="text-xs font-medium text-orange-600">{remaining} {t("newApp.remaining")}</span>
                )}
              </div>
              <ul className="space-y-2.5">
                {checklist.map((item, i) => {
                  const u = uploads[item.id];
                  const done = !!u?.file;
                  return (
                    <li key={item.id || i} className="rounded-lg border border-border p-3 bg-muted/20">
                      <div className="flex items-start gap-2.5">
                        {done ? (
                          <FileCheck2 className="w-5 h-5 text-green-600 shrink-0 mt-0.5" />
                        ) : item.required ? (
                          <CheckCircle2 className="w-5 h-5 text-orange-500 shrink-0 mt-0.5" />
                        ) : (
                          <Circle className="w-5 h-5 text-muted-foreground shrink-0 mt-0.5" />
                        )}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-foreground">{loc(item, "label")}</p>
                          <p className="text-xs text-muted-foreground">
                            {item.required ? t("common.required") : t("common.optional")} · {t("newApp.maxFileSize")}
                          </p>

                          {u?.error && (
                            <p className="text-xs text-destructive mt-1">{u.error}</p>
                          )}

                          {done ? (
                            <div className="mt-2 flex items-center justify-between gap-2">
                              <span className="text-xs text-foreground truncate flex items-center gap-1.5">
                                <FileCheck2 className="w-3.5 h-3.5 text-green-600 shrink-0" />
                                {u.file_name} <span className="text-muted-foreground">({formatSize(u.file_size)})</span>
                              </span>
                              <div className="flex items-center gap-2 shrink-0">
                                <label className="text-xs font-medium text-primary hover:underline cursor-pointer">
                                  {t("newApp.replace")}
                                  <input
                                    type="file"
                                    accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
                                    className="hidden"
                                    onChange={(e) => handleFile(item, e.target.files?.[0])}
                                  />
                                </label>
                                <button onClick={() => removeFile(item.id)} className="text-xs font-medium text-destructive hover:underline flex items-center gap-1">
                                  <X className="w-3 h-3" />{t("newApp.remove")}
                                </button>
                              </div>
                            </div>
                          ) : u?.uploading ? (
                            <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />{t("newApp.uploading")}
                            </div>
                          ) : (
                            <label className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-dashed border-border bg-background hover:border-primary/50 hover:bg-primary/5 cursor-pointer text-xs font-medium text-foreground transition-colors">
                              <UploadCloud className="w-3.5 h-3.5" />{t("newApp.chooseFile")}
                              <input
                                type="file"
                                accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
                                className="hidden"
                                onChange={(e) => handleFile(item, e.target.files?.[0])}
                              />
                            </label>
                          )}
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground mb-2">{t("newApp.commentsLabel")}</label>
              <textarea
                value={comments}
                onChange={(e) => setComments(e.target.value)}
                placeholder={t("newApp.commentsPlaceholder")}
                rows={3}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none"
              />
            </div>

            <div className="flex flex-col sm:flex-row gap-3 pt-2">
              <Button onClick={() => createApp(false)} disabled={!canSubmit} className="flex-1">
                {submitting ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />{t("common.loading")}</> : t("newApp.submit")}
              </Button>
              <Button onClick={() => createApp(true)} disabled={submitting || !selectedSlug} variant="outline" className="flex-1">
                {t("newApp.saveDraft")}
              </Button>
            </div>
            {(remaining > 0 || missingFormValues > 0) && (
              <p className="text-xs text-muted-foreground text-center">{t("newApp.requiredToSubmit")}</p>
            )}
          </>
        )}
      </div>
    </div>
  );
}