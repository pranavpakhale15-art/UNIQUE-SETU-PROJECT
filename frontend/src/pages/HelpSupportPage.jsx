import React from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { LifeBuoy, Phone, MapPin } from "lucide-react";

export default function HelpSupportPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-10">
      <p className="text-xs font-semibold uppercase tracking-wide text-primary">Support</p>
      <h1 className="mt-1 flex items-center gap-2 font-heading text-2xl font-bold"><LifeBuoy className="h-6 w-6" />Help &amp; Support</h1>
      <p className="mt-2 text-sm text-muted-foreground">For help with an application, sign in and open its details to review the status, document checklist, and centre messages.</p>
      <section className="mt-6 space-y-4 rounded-xl border border-border bg-card p-5">
        <a className="flex items-center gap-3 text-sm hover:text-primary" href="tel:+918149921445"><Phone className="h-4 w-4" />Call the centre: 8149921445</a>
        <p className="flex items-start gap-3 text-sm text-muted-foreground"><MapPin className="mt-0.5 h-4 w-4 shrink-0" />Mahalaxmi Nagar, Mothi Umri, Akola, Maharashtra 444003</p>
        <div className="flex flex-wrap gap-2 pt-2">
          <Button asChild variant="outline"><Link to="/dashboard">My applications</Link></Button>
          <Button asChild variant="outline"><Link to="/notifications">Notifications</Link></Button>
        </div>
      </section>
    </main>
  );
}
