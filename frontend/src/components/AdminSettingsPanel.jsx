import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { getAdminSystemSettings, updateAdminSystemSettings } from "@/api/backendClient";

const initial = { business_name: "", business_address: "", support_phone: "", default_language: "mr", maintenance_mode: false };
const inputClass = "mt-1 h-10 w-full rounded-md border border-input bg-background px-3 text-sm";

export default function AdminSettingsPanel() {
  const [values, setValues] = useState(initial);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    getAdminSystemSettings().then((settings) => setValues({ ...initial, ...settings })).catch((loadError) => setError(loadError.message || "Unable to load settings.")).finally(() => setLoading(false));
  }, []);

  const save = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await updateAdminSystemSettings(values);
      setNotice("Settings saved.");
    } catch (saveError) {
      setError(saveError.message || "Unable to save settings.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section id="settings" className="mb-10 rounded-xl border border-border bg-card p-5">
      <h2 className="font-heading text-xl font-semibold">System settings</h2>
      <p className="mb-4 mt-1 text-sm text-muted-foreground">Business contact and default language settings served by the backend.</p>
      {loading ? <p className="text-sm text-muted-foreground">Loading settings…</p> : (
        <form onSubmit={save} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <label className="text-xs text-muted-foreground">Business name<input required minLength={2} maxLength={160} className={inputClass} value={values.business_name} onChange={(event) => setValues({ ...values, business_name: event.target.value })} /></label>
          <label className="text-xs text-muted-foreground">Support phone<input maxLength={24} className={inputClass} value={values.support_phone} onChange={(event) => setValues({ ...values, support_phone: event.target.value })} /></label>
          <label className="text-xs text-muted-foreground">Default language<select className={inputClass} value={values.default_language} onChange={(event) => setValues({ ...values, default_language: event.target.value })}><option value="mr">Marathi</option><option value="en">English</option><option value="hi">Hindi</option></select></label>
          <label className="text-xs text-muted-foreground sm:col-span-2">Business address<textarea maxLength={500} rows="2" className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" value={values.business_address} onChange={(event) => setValues({ ...values, business_address: event.target.value })} /></label>
          <label className="flex items-center gap-2 pt-5 text-sm"><input type="checkbox" checked={Boolean(values.maintenance_mode)} onChange={(event) => setValues({ ...values, maintenance_mode: event.target.checked })} />Maintenance mode flag</label>
          <div className="sm:col-span-2 lg:col-span-3"><Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save settings"}</Button></div>
        </form>
      )}
      {notice && <p role="status" className="mt-3 text-sm text-green-700">{notice}</p>}
      {error && <p role="alert" className="mt-3 text-sm text-destructive">{error}</p>}
    </section>
  );
}
