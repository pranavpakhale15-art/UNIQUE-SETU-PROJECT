import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, FolderOpen, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import ServiceCard from "@/components/ServiceCard";
import { usePublishedServices, useServiceCategories } from "@/lib/serviceQueries";
import { useLang } from "@/lib/i18n/LanguageContext";

export default function ServicesPage() {
  const { loc } = useLang();
  const servicesQuery = usePublishedServices();
  const categoriesQuery = useServiceCategories();
  const services = servicesQuery.data?.items || [];
  const categories = categoriesQuery.data || [];
  const [query, setQuery] = useState("");
  const loading = servicesQuery.isLoading || categoriesQuery.isLoading;
  const error = servicesQuery.error?.message || categoriesQuery.error?.message || "";

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
    });
    const legacy = new Map();
    filtered.filter((service) => !service.section_id || !used.has(service.id)).forEach((service) => {
      const name = service.category || "Other services";
      if (!legacy.has(name)) legacy.set(name, []);
      legacy.get(name).push(service);
    });
    legacy.forEach((items, label) => result.push({ id: `legacy-${label}`, label, to: `/services/category/legacy-${encodeURIComponent(label)}`, items }));
    return result;
  }, [categories, filtered, loc]);

  const categoryCards = groups
    .filter((group) => group.items.length || !query.trim() || group.label.toLowerCase().includes(query.trim().toLowerCase()))
    .map((group) => (
    <Link
      key={group.id}
      to={group.to}
      className="group rounded-2xl border border-border bg-card p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-lg"
    >
      <div className="flex items-start justify-between gap-3">
        <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <FolderOpen className="h-5 w-5" aria-hidden="true" />
        </span>
        <span className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground">
          {group.items.length} {group.items.length === 1 ? "service" : "services"} <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
        </span>
      </div>
      <h2 className="mt-4 font-heading text-base font-semibold text-foreground">{group.label}</h2>
      <p className="mt-1 text-sm text-muted-foreground">Browse services in this category</p>
    </Link>
  ));

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
      {loading ? <p className="py-16 text-center text-muted-foreground">Loading services…</p> : error ? null : groups.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">No published services match your search.</p>
      ) : (
        <div className="space-y-10">
          {categoryCards.length > 0 && (
            <section aria-label="Service categories" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {categoryCards}
            </section>
          )}
          {groups.some((group) => group.items.length) ? groups.filter((group) => group.items.length).map((group) => (
            <section key={group.id} aria-labelledby={`category-${group.id}`}>
              <div className="mb-4 flex items-center justify-between gap-3">
                <h2 id={`category-${group.id}`} className="font-heading text-xl font-semibold">{group.label}</h2>
                <Link to={group.to} className="text-sm font-medium text-primary hover:underline">View category</Link>
              </div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{group.items.map((service) => <ServiceCard key={service.id} service={service} />)}</div>
            </section>
          )) : <p className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">No published services match your search.</p>}
        </div>
      )}
    </main>
  );
}
