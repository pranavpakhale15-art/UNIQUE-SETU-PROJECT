import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bell, CheckCheck } from "lucide-react";
import { listNotifications, markAllNotificationsRead, markNotificationRead } from "@/api/backendClient";
import { Button } from "@/components/ui/button";

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setError("");
    try {
      const page = await listNotifications();
      setNotifications(page.items || []);
    } catch (loadError) {
      setError(loadError.message || "Unable to load notifications.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const markRead = async (id) => {
    setBusy(true);
    try {
      await markNotificationRead(id);
      await load();
    } catch (actionError) {
      setError(actionError.message || "Unable to update notification.");
    } finally {
      setBusy(false);
    }
  };

  const markAllRead = async () => {
    setBusy(true);
    try {
      await markAllNotificationsRead();
      await load();
    } catch (actionError) {
      setError(actionError.message || "Unable to update notifications.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">Account</p>
          <h1 className="mt-1 flex items-center gap-2 font-heading text-2xl font-bold"><Bell className="h-6 w-6" />Notifications</h1>
          <p className="mt-1 text-sm text-muted-foreground">Application updates and document requests for your account.</p>
        </div>
        <Button type="button" variant="outline" disabled={busy || !notifications.some((item) => !item.is_read)} onClick={markAllRead}>
          <CheckCheck className="mr-2 h-4 w-4" />Mark all as read
        </Button>
      </div>
      {error && <p role="alert" className="mb-4 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
      {loading ? <p className="py-16 text-center text-muted-foreground">Loading notifications…</p> : notifications.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">You’re all caught up. New updates will appear here.</div>
      ) : (
        <ul className="space-y-3">
          {notifications.map((item) => {
            const id = item.id || item._id;
            return (
              <li key={id} className={`rounded-xl border bg-card p-4 ${item.is_read ? "border-border" : "border-primary/40 bg-primary/[0.03]"}`}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium text-foreground">{item.title || "Notification"}</p>
                    <p className="mt-1 text-sm text-muted-foreground">{item.message}</p>
                    <p className="mt-2 text-xs text-muted-foreground">{item.created_at ? new Date(item.created_at).toLocaleString() : ""}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {item.related_application_id && <Button asChild size="sm" variant="outline"><Link to={item.related_document_id
                      ? `/applications/${item.related_application_id}?notificationId=${encodeURIComponent(id)}&documentId=${encodeURIComponent(item.related_document_id)}`
                      : `/applications/${item.related_application_id}?notificationId=${encodeURIComponent(id)}`}>{item.related_document_id ? "View document" : "View application"}</Link></Button>}
                    {!item.is_read && <Button size="sm" variant="ghost" disabled={busy} onClick={() => markRead(id)}>Mark read</Button>}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
