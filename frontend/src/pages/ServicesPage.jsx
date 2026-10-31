import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import ServiceCard from "@/components/ServiceCard";
import { listServiceCategories, listServices } from "@/api/backendClient";
import { useLang } from "@/lib/i18n/LanguageContext";

export default function ServicesPage() {
  const { loc } = useLang();
  const [services, setServices] = useState([]);
  const [categories, setCategories] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([listServices(), listServiceCategories()]).then(([servicePage, categoryRecords]) => {
      if (!active) return;
      setServices(servicePage.items || []);
      setCategories(categoryRecords || []);
    }).catch((loadError) => {
      if (active) setError(loadError.message || "Unable to load services.");
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return services;
    return services.filter((service) => {
      const section = categories.find((category) => category.id === service.section_id);
      return [service.name_en, service.name_mr, service.name_hi, service.category, loc(section || {}, "name")]
        .some((value) => String(value || "").toLowerCase().includes(term));
    });
  }, [categories, loc, query, services]);

  const groups = useMemo(() => {
    const used = new Set();
    const result = categories.map((category) => {
      const items = filtered.filter((service) => service.section_id === category.id);
      items.forEach((service) => used.add(service.id));
      return { id: category.id, label: loc(category, "name") || category.slug, to: `/services/category/section-${category.id}`, items };
    }).filter((group) => group.items.length);
    const legacy = new Map();
    filtered.filter((service) => !service.section_id || !used.has(service.id)).forEach((service) => {
      const name = service.category || "Other services";
      if (!legacy.has(name)) legacy.set(name, []);
      legacy.get(name).push(service);
    });
    legacy.forEach((items, label) => result.push({ id: `legacy-${label}`, label, to: `/services/category/legacy-${encodeURIComponent(label)}`, items }));
    return result;
  }, [categories, filtered, loc]);

  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      <p className="text-xs font-semibold uppercase tracking-wide text-primary">Unique Setu</p>
      <h1 className="mt-1 font-heading text-2xl font-bold md:text-3xl">Browse services</h1>
      <p className="mt-2 text-sm text-muted-foreground">Choose a service category or search the published catalogue.</p>
      <label className="relative my-6 block max-w-lg">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input aria-label="Search services and categories" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search services and categories" className="h-11 pl-10" />
      </label>
      {error && <p role="alert" className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
      {loading ? <p className="py-16 text-center text-muted-foreground">Loading services…</p> : groups.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">No published services match your search.</p>
      ) : <div className="space-y-10">{groups.map((group) => (
        <section key={group.id} aria-labelledby={`category-${group.id}`}>
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 id={`category-${group.id}`} className="font-heading text-xl font-semibold">{group.label}</h2>
            <Link to={group.to} className="text-sm font-medium text-primary hover:underline">View category</Link>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{group.items.map((service) => <ServiceCard key={service.id} service={service} />)}</div>
        </section>
      ))}</div>}
    </main>
  );
}
