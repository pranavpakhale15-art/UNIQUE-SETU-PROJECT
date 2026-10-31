import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Download, Eye, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { listReleasedDocuments, markNotificationRead, viewApplicationDocument, downloadApplicationDocument } from "@/api/backendClient";

export default function CustomerDocumentsPage() {
  const [params] = useSearchParams();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyDocumentId, setBusyDocumentId] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const firstPage = await listReleasedDocuments(1, 100);
        const laterPages = await Promise.all(Array.from({ length: Math.max(0, (firstPage.pages || 1) - 1) }, (_, index) => listReleasedDocuments(index + 2, 100)));
        const records = [firstPage, ...laterPages].flatMap((page) => page.items || []);
        if (active) setDocuments(records);
        const notificationId = params.get("notificationId");
        const documentId = params.get("documentId");
        const releasedDocument = records.find((document) => document.id === documentId);
        if (notificationId && releasedDocument) {
          await markNotificationRead(notificationId, releasedDocument.application_id);
        }
      } catch (loadError) {
        if (active) setError(loadError.message || "Unable to load released documents.");
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    return () => { active = false; };
  }, [params]);

  const openDocument = async (document, action) => {
    setBusyDocumentId(document.id);
    setError("");
    try {
      if (action === "view") await viewApplicationDocument(document.id);
      else await downloadApplicationDocument(document.id, document.file_name);
    } catch (actionError) {
      setError(actionError.message || "Unable to open the released document.");
    } finally {
      setBusyDocumentId("");
    }
  };

  return (
    <main id="documents" className="mx-auto max-w-5xl px-4 py-10">
      <p className="text-xs font-semibold uppercase tracking-wide text-primary">Customer account</p>
      <h1 className="mt-1 flex items-center gap-2 font-heading text-2xl font-bold"><FileText className="h-6 w-6" />My Documents</h1>
      <p className="mb-6 mt-1 text-sm text-muted-foreground">Only final documents that the owner has officially released to your account appear here.</p>
      {error && <p role="alert" className="mb-4 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
      {loading ? <p className="py-16 text-center text-muted-foreground">Loading released documents…</p> : documents.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">No documents have been released to you yet. Files you upload for verification stay in their application and are not listed here.</div>
      ) : <div className="space-y-3">
        {documents.map((document) => (
          <article key={document.id} className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border bg-card p-4">
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{document.file_name || "Released document"}</p>
              <p className="mt-1 text-xs text-muted-foreground">Type: {document.document_type || "Document"} · Received: {document.date_received ? new Date(document.date_received).toLocaleDateString() : "—"}</p>
              <p className="mt-1 text-xs text-muted-foreground">Application ID: {document.application_number || document.application_id} · {document.service_name}</p>
            </div>
            <div className="flex shrink-0 gap-2">
              <Button size="sm" variant="outline" disabled={busyDocumentId === document.id} onClick={() => openDocument(document, "view")}><Eye className="mr-1 h-4 w-4" />View</Button>
              <Button size="sm" disabled={busyDocumentId === document.id} onClick={() => openDocument(document, "download")}><Download className="mr-1 h-4 w-4" />Download</Button>
              <Button asChild size="sm" variant="ghost"><Link to={`/applications/${document.application_id}`}>Application</Link></Button>
            </div>
          </article>
        ))}
      </div>}
    </main>
  );
}
