import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import ServiceCard from "@/components/ServiceCard";
import { listServiceCategories, listServices } from "@/api/backendClient";
import { useLang } from "@/lib/i18n/LanguageContext";

export default function ServiceCategoryPage() {
  const { categoryKey = "" } = useParams();
  const { loc } = useLang();
  const [services, setServices] = useState([]);
  const [title, setTitle] = useState("Services");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        let page;
        let categoryLabel = "Services";
        if (categoryKey.startsWith("section-")) {
          const sectionId = categoryKey.slice("section-".length);
          const [categories, servicesPage] = await Promise.all([
            listServiceCategories(),
            listServices("mr", false, { sectionId }),
          ]);
          const category = categories.find((record) => record.id === sectionId);
          if (!category) throw Object.assign(new Error("This service category is unavailable."), { status: 404 });
          categoryLabel = loc(category, "name") || category.slug;
          page = servicesPage;
        } else if (categoryKey.startsWith("legacy-")) {
          let legacyCategory = categoryKey.slice("legacy-".length);
          try { legacyCategory = decodeURIComponent(legacyCategory); } catch { /* React Router may already have decoded the parameter. */ }
          page = await listServices("mr", false, { category: legacyCategory });
          categoryLabel = legacyCategory;
        } else {
          throw Object.assign(new Error("This service category is unavailable."), { status: 404 });
        }
        if (active) {
          setTitle(categoryLabel);
          setServices(page.items || []);
        }
      } catch (loadError) {
        if (active) setError(loadError.message || "Unable to load this service category.");
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    return () => { active = false; };
  }, [categoryKey, loc]);

  return (
    <main className="mx-auto max-w-6xl px-4 py-10">
      <Link to="/services" className="mb-6 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />All services</Link>
      <p className="mt-5 text-xs font-semibold uppercase tracking-wide text-primary">Service category</p>
      <h1 className="mt-1 font-heading text-2xl font-bold md:text-3xl">{title}</h1>
      {error && <p role="alert" className="mt-5 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
      {loading ? <p className="py-16 text-center text-muted-foreground">Loading services…</p> : error ? null : services.length === 0 ? (
        <p className="mt-6 rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">There are no published services in this category yet.</p>
      ) : <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{services.map((service) => <ServiceCard key={service.id} service={service} />)}</div>}
    </main>
  );
}
