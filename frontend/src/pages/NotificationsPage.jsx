import React, { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck, Circle, CircleCheck } from "lucide-react";
import { listNotifications, markAllNotificationsRead, markNotificationRead } from "@/api/backendClient";
import { Button } from "@/components/ui/button";

function notificationDate(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString();
}

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState("");
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const requestedNotificationId = searchParams.get("notificationId") || "";

  const load = useCallback(async () => {
    setError("");
    try {
      const page = await listNotifications();
      setNotifications(page.items || []);
    } catch (loadError) {
      setError(loadError.message || "Unable to load notifications.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const markRead = useCallback(async (id) => {
    setBusy(true);
    try {
      await markNotificationRead(id);
      setNotifications((current) => current.map((item) => (item.id || item._id) === id
        ? { ...item, is_read: true }
        : item));
      await queryClient.invalidateQueries({ queryKey: ["notification-unread-count"] });
    } catch (actionError) {
      setError(actionError.message || "Unable to update notification.");
    } finally {
      setBusy(false);
    }
  }, [queryClient]);

  const markAllRead = async () => {
    setBusy(true);
    try {
      await markAllNotificationsRead();
      setNotifications((current) => current.map((item) => ({ ...item, is_read: true })));
      await queryClient.invalidateQueries({ queryKey: ["notification-unread-count"] });
    } catch (actionError) {
      setError(actionError.message || "Unable to update notifications.");
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (loading || !requestedNotificationId) return;
    const notification = notifications.find((item) => (item.id || item._id) === requestedNotificationId);
    if (!notification) return;
    setExpandedId(requestedNotificationId);
    if (!notification.is_read) void markRead(requestedNotificationId);
  }, [loading, markRead, notifications, requestedNotificationId]);

  const openNotification = async (item) => {
    const id = item.id || item._id;
    const opening = expandedId !== id;
    setExpandedId(opening ? id : "");
    if (opening && !item.is_read) await markRead(id);
  };

  const unreadNotifications = notifications.filter((item) => !item.is_read);
  const readNotifications = notifications.filter((item) => item.is_read);
  const renderNotification = (item) => {
    const id = item.id || item._id;
    const expanded = expandedId === id;
    return (
      <li key={id} className={`rounded-xl border bg-card p-4 transition-colors ${item.is_read ? "border-border" : "border-primary/40 bg-primary/[0.03]"}`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <button type="button" className="min-w-0 flex-1 text-left" aria-expanded={expanded} onClick={() => void openNotification(item)}>
            <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${item.is_read ? "text-muted-foreground" : "text-primary"}`}>
              {item.is_read ? <CircleCheck className="h-3.5 w-3.5" /> : <Circle className="h-3.5 w-3.5 fill-current" />}
              {item.is_read ? "Read" : "Unread"}
            </span>
            <p className="mt-1 font-medium text-foreground">{item.title || "Notification"}</p>
            <p className={`mt-1 whitespace-pre-wrap text-sm text-muted-foreground ${expanded ? "" : "line-clamp-2"}`}>
              {item.message || item.title || "You have a new update."}
            </p>
            <p className="mt-2 text-xs text-muted-foreground">{notificationDate(item.created_at)}</p>
            <span className="sr-only">{expanded ? "Collapse message" : "Open full message"}</span>
          </button>
          {item.related_application_id && (
            <Button asChild size="sm" variant="outline" className="shrink-0">
              <Link to={item.related_document_id
                ? `/applications/${item.related_application_id}?notificationId=${encodeURIComponent(id)}&documentId=${encodeURIComponent(item.related_document_id)}`
                : `/applications/${item.related_application_id}?notificationId=${encodeURIComponent(id)}`}>
                {item.related_document_id ? "View document" : "View application"}
              </Link>
            </Button>
          )}
        </div>
      </li>
    );
  };

  return (
    <main className="mx-auto max-w-4xl px-4 py-10">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-primary">Account</p>
          <h1 className="mt-1 flex items-center gap-2 font-heading text-2xl font-bold"><Bell className="h-6 w-6" />Notifications</h1>
          <p className="mt-1 text-sm text-muted-foreground">Application updates and messages sent to your account stay here for your records.</p>
        </div>
        <Button type="button" variant="outline" disabled={busy || unreadNotifications.length === 0} onClick={markAllRead}>
          <CheckCheck className="mr-2 h-4 w-4" />Mark all as read
        </Button>
      </div>
      {error && <p role="alert" className="mb-4 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
      {loading ? <p className="py-16 text-center text-muted-foreground">Loading notifications…</p> : error && notifications.length === 0 ? null : notifications.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border p-12 text-center text-sm text-muted-foreground">You’re all caught up. New updates will appear here.</div>
      ) : (
        <div className="space-y-8">
          <section aria-labelledby="unread-notifications-heading">
            <h2 id="unread-notifications-heading" className="mb-3 font-heading text-lg font-semibold">Unread notifications <span className="text-sm font-normal text-muted-foreground">({unreadNotifications.length})</span></h2>
            {unreadNotifications.length ? (
              <ul className="space-y-3">{unreadNotifications.map(renderNotification)}</ul>
            ) : (
              <p className="rounded-xl border border-dashed border-border p-5 text-sm text-muted-foreground">No unread notifications.</p>
            )}
          </section>
          <section aria-labelledby="read-notifications-heading">
            <h2 id="read-notifications-heading" className="mb-3 font-heading text-lg font-semibold">Read notifications <span className="text-sm font-normal text-muted-foreground">({readNotifications.length})</span></h2>
            {readNotifications.length ? (
              <ul className="space-y-3">{readNotifications.map(renderNotification)}</ul>
            ) : (
              <p className="rounded-xl border border-dashed border-border p-5 text-sm text-muted-foreground">Read notifications will remain available here.</p>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
