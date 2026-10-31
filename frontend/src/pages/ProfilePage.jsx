import React, { useState } from "react";
import { useAuth } from "@/lib/AuthContext";
import { Button } from "@/components/ui/button";
import { uploadProfilePhoto } from "@/api/backendClient";
import { UserRound } from "lucide-react";

export default function ProfilePage() {
  const { user, checkUserAuth } = useAuth();
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const savePhoto = async (event) => {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setNotice("");
    setError("");
    try {
      await uploadProfilePhoto(file);
      setFile(null);
      setNotice("Profile photo updated securely.");
      await checkUserAuth();
    } catch (uploadError) {
      setError(uploadError.message || "Unable to update your profile photo.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <p className="text-xs font-semibold uppercase tracking-wide text-primary">Account</p>
      <h1 className="mt-1 flex items-center gap-2 font-heading text-2xl font-bold"><UserRound className="h-6 w-6" />Profile</h1>
      <section className="mt-6 rounded-xl border border-border bg-card p-5">
        <dl className="grid gap-4 sm:grid-cols-2">
          <div><dt className="text-xs text-muted-foreground">Full name</dt><dd className="mt-1 font-medium">{user?.full_name || "—"}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Mobile number</dt><dd className="mt-1 font-medium">{user?.mobile_number || "—"}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Email</dt><dd className="mt-1 font-medium">{user?.email || "—"}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Account type</dt><dd className="mt-1 font-medium capitalize">{user?.role || "—"}</dd></div>
        </dl>
      </section>
      {user?.role === "customer" && (
        <section className="mt-5 rounded-xl border border-border bg-card p-5">
          <h2 className="font-heading font-semibold">Profile photo</h2>
          <p className="mt-1 text-sm text-muted-foreground">Upload a JPEG or PNG. Files are stored using the backend’s configured private storage.</p>
          <form onSubmit={savePhoto} className="mt-4 flex flex-wrap items-center gap-3">
            <input type="file" accept="image/jpeg,image/png,.jpg,.jpeg,.png" onChange={(event) => setFile(event.target.files?.[0] || null)} />
            <Button type="submit" disabled={!file || busy}>{busy ? "Saving…" : "Update photo"}</Button>
          </form>
        </section>
      )}
      {notice && <p role="status" className="mt-4 rounded-lg bg-green-50 p-3 text-sm text-green-800">{notice}</p>}
      {error && <p role="alert" className="mt-4 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
    </main>
  );
}
