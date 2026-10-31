import React, { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  archiveService,
  createService,
  createServiceCategory,
  deleteService,
  deleteServiceCategory,
  listServiceCategories,
  publishService,
  updateService,
  updateServiceCategory,
  uploadServiceThumbnail,
} from "@/api/backendClient";
import { Eye, ImagePlus, Layers3, Pencil, Plus, Search, Trash2 } from "lucide-react";

const inputClass = "h-10 w-full rounded-md border border-input bg-background px-3 text-sm";
const textareaClass = "w-full rounded-md border border-input bg-background px-3 py-2 text-sm";
const blankForm = {
  service_code: "", name_mr: "", name_en: "", name_hi: "", description_mr: "", description_en: "", description_hi: "",
  category: "", section_id: "", customer_instructions: "", estimated_processing_time: "", pricing: "",
  display_order: 0, is_featured: false, thumbnail_alt_text: "", requirements: "", form_requirements: "",
};

function localized(value, language) {
  return typeof value === "string" ? value : value?.[language] || "";
}

function requirementsText(items = []) {
  return items.map((item) => {
    const label = localized(item.label || item.name, "en") || localized(item.label || item.name, "mr") || "";
    const description = localized(item.description, "en");
    const formats = Array.isArray(item.accepted_formats) ? item.accepted_formats.join(",") : "";
    return [label, item.required === false ? "optional" : "required", description, formats, item.max_size_mb || ""].join(" | ");
  }).join("\n");
}

function formRequirementsText(items = []) {
  return items.map((item) => `${localized(item.label || item.name, "en") || localized(item.label || item.name, "mr") || ""} | ${item.required === false ? "optional" : "required"}`).join("\n");
}

function parseRequirements(value, serviceCode) {
  return value.split(/\r?\n/).map((line, index) => line.trim()).filter(Boolean).map((line, index) => {
    const [label = "", required = "required", description = "", formats = "", maxSize = ""] = line.split("|").map((part) => part.trim());
    const slug = label.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || `document-${index + 1}`;
    return {
      id: `${serviceCode.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${slug}-${index + 1}`.slice(0, 120),
      label: { mr: label, en: label, hi: label },
      description: { en: description },
      required: required.toLowerCase() !== "optional",
      accepted_formats: formats ? formats.split(",").map((item) => item.trim()).filter(Boolean) : ["pdf", "jpg", "png"],
      ...(maxSize && Number.isFinite(Number(maxSize)) ? { max_size_mb: Number(maxSize) } : {}),
      order: index + 1,
    };
  });
}

function parseFormRequirements(value, serviceCode) {
  return value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map((line, index) => {
    const [label = "", required = "required"] = line.split("|").map((part) => part.trim());
    const slug = label.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || `field-${index + 1}`;
    return {
      id: `${serviceCode.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${slug}-${index + 1}`.slice(0, 120),
      label: { mr: label, en: label, hi: label },
      required: required.toLowerCase() !== "optional",
      order: index + 1,
    };
  });
}

function formFromService(service) {
  return {
    ...blankForm,
    service_code: service.service_code || "",
    name_mr: localized(service.name, "mr"), name_en: localized(service.name, "en"), name_hi: localized(service.name, "hi"),
    description_mr: localized(service.description, "mr"), description_en: localized(service.description, "en"), description_hi: localized(service.description, "hi"),
    category: service.category || "", section_id: service.section_id || "",
    customer_instructions: localized(service.customer_instructions, "en"),
    estimated_processing_time: localized(service.estimated_processing_time, "en") || service.estimated_processing_time || "",
    pricing: typeof service.pricing === "object" ? JSON.stringify(service.pricing) : service.pricing || "",
    display_order: service.display_order || 0, is_featured: Boolean(service.is_featured),
    requirements: requirementsText(service.document_requirements || service.checklist || []),
    form_requirements: formRequirementsText(service.form_requirements || []),
    thumbnail_alt_text: localized(service.thumbnail_alt_text, "en") || localized(service.thumbnail?.alt_text, "en"),
  };
}

export default function ServiceCatalogAdmin({ services, loc, runAction, busy }) {
  const [categories, setCategories] = useState([]);
  const [form, setForm] = useState(blankForm);
  const [editingId, setEditingId] = useState(null);
  const [thumbnail, setThumbnail] = useState(null);
  const [publishAfterSave, setPublishAfterSave] = useState(false);
  const [categoryForm, setCategoryForm] = useState({ slug: "", name_en: "", name_mr: "", name_hi: "", display_order: 0, is_visible: true });
  const [editingCategoryId, setEditingCategoryId] = useState(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");

  const loadCategories = async () => {
    try {
      setCategories(await listServiceCategories(true));
    } catch (loadError) {
      setError(loadError.message || "Unable to load service sections.");
    }
  };

  useEffect(() => { loadCategories(); }, []);

  const visibleServices = useMemo(() => services.filter((service) => {
    const text = `${service.service_code || ""} ${loc(service, "name")} ${service.category || ""}`.toLowerCase();
    const matchesText = !query.trim() || text.includes(query.trim().toLowerCase());
    const matchesStatus = statusFilter === "all" || (statusFilter === "published" ? service.is_published : statusFilter === "draft" ? !service.is_published && service.checklist_review_required : !service.is_published && !service.checklist_review_required);
    const matchesCategory = categoryFilter === "all" || (categoryFilter === "legacy" ? !service.section_id : service.section_id === categoryFilter);
    return matchesText && matchesStatus && matchesCategory;
  }), [services, loc, query, statusFilter, categoryFilter]);

  const resetForm = () => { setForm(blankForm); setEditingId(null); setThumbnail(null); setPublishAfterSave(false); };

  const submitService = async (event) => {
    event.preventDefault();
    setError("");
    const requirements = parseRequirements(form.requirements, form.service_code);
    if (!requirements.length) {
      setError("Add at least one document requirement before saving a service.");
      return;
    }
    let pricing = form.pricing.trim() || null;
    if (pricing?.startsWith("{")) {
      try { pricing = JSON.parse(pricing); } catch { setError("Pricing must be plain text or valid JSON."); return; }
    }
    const data = {
      service_code: form.service_code.trim().toUpperCase(),
      name: { mr: form.name_mr.trim(), en: form.name_en.trim(), hi: form.name_hi.trim() },
      description: { mr: form.description_mr.trim(), en: form.description_en.trim(), hi: form.description_hi.trim() },
      category: form.category.trim() || categories.find((item) => item.id === form.section_id)?.name?.en || "Services",
      section_id: form.section_id || null,
      customer_instructions: form.customer_instructions.trim(),
      estimated_processing_time: form.estimated_processing_time.trim() || null,
      pricing,
      display_order: Number(form.display_order) || 0,
      is_featured: form.is_featured,
      thumbnail_alt_text: { mr: form.thumbnail_alt_text, en: form.thumbnail_alt_text, hi: form.thumbnail_alt_text },
      document_requirements: requirements,
      form_requirements: parseFormRequirements(form.form_requirements, form.service_code),
    };
    const success = await runAction(async () => {
      let id = editingId;
      if (id) {
        await updateService(id, data);
        await updateService(id, { checklist_review_required: false });
      } else {
        const created = await createService(data);
        id = created.id;
        await updateService(id, { checklist_review_required: false });
      }
      if (thumbnail) await uploadServiceThumbnail(id, thumbnail);
      if (publishAfterSave) await publishService(id);
    }, editingId ? "Service changes saved." : "Service saved as a draft.");
    if (success) {
      resetForm();
      await loadCategories();
    }
  };

  const startEdit = (service) => {
    setEditingId(service.id);
    setForm(formFromService(service));
    setThumbnail(null);
    setPublishAfterSave(false);
    document.getElementById("service-form")?.scrollIntoView({ behavior: "smooth" });
  };

  const saveCategory = async (event) => {
    event.preventDefault();
    setError("");
    const payload = {
      slug: categoryForm.slug.trim().toLowerCase(),
      name: { mr: categoryForm.name_mr.trim(), en: categoryForm.name_en.trim(), hi: categoryForm.name_hi.trim() },
      display_order: Number(categoryForm.display_order) || 0,
      is_visible: categoryForm.is_visible,
    };
    const success = await runAction(async () => {
      if (editingCategoryId) await updateServiceCategory(editingCategoryId, payload);
      else await createServiceCategory(payload);
    }, editingCategoryId ? "Section updated." : "Section created.");
    if (success) {
      setCategoryForm({ slug: "", name_en: "", name_mr: "", name_hi: "", display_order: 0, is_visible: true });
      setEditingCategoryId(null);
      await loadCategories();
    }
  };

  const editCategory = (category) => {
    setEditingCategoryId(category.id);
    setCategoryForm({
      slug: category.slug || "", name_en: localized(category.name, "en"), name_mr: localized(category.name, "mr"),
      name_hi: localized(category.name, "hi"), display_order: category.display_order || 0, is_visible: category.is_visible,
    });
  };

  const toggleCategory = async (category) => {
    const success = await runAction(() => updateServiceCategory(category.id, { is_visible: !category.is_visible }), "Section visibility updated.");
    if (success) await loadCategories();
  };

  const metrics = {
    total: services.length,
    active: services.filter((service) => service.is_published).length,
    inactive: services.filter((service) => !service.is_published && !service.checklist_review_required).length,
    drafts: services.filter((service) => !service.is_published && service.checklist_review_required).length,
    featured: services.filter((service) => service.is_featured).length,
  };

  return (
    <div className="space-y-8">
      {error && <p role="alert" className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
        <section id="reports" aria-label="Service catalog statistics" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
          {[["Total services", metrics.total], ["Active", metrics.active], ["Inactive", metrics.inactive], ["Drafts", metrics.drafts], ["Total categories", categories.length], ["Featured / popular", metrics.featured]].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-border bg-card p-4"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 font-heading text-2xl font-bold">{value}</p></div>
        ))}
      </section>

      <section id="categories-admin" className="rounded-xl border border-border bg-card p-5">
        <h2 className="flex items-center gap-2 font-heading text-xl font-semibold"><Layers3 className="h-5 w-5" />Service sections and categories</h2>
        <p className="mb-4 mt-1 text-sm text-muted-foreground">Sections control customer-facing service grouping. Hide a section to remove it from browsing while preserving historical services.</p>
        <form onSubmit={saveCategory} className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <input required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" aria-label="Section slug" placeholder="section-slug" className={inputClass} value={categoryForm.slug} onChange={(event) => setCategoryForm({ ...categoryForm, slug: event.target.value })} />
          <input required aria-label="Section name in English" placeholder="Name (English)" className={inputClass} value={categoryForm.name_en} onChange={(event) => setCategoryForm({ ...categoryForm, name_en: event.target.value })} />
          <input aria-label="Section name in Marathi" placeholder="Name (Marathi)" className={inputClass} value={categoryForm.name_mr} onChange={(event) => setCategoryForm({ ...categoryForm, name_mr: event.target.value })} />
          <input aria-label="Section name in Hindi" placeholder="Name (Hindi)" className={inputClass} value={categoryForm.name_hi} onChange={(event) => setCategoryForm({ ...categoryForm, name_hi: event.target.value })} />
          <div className="flex gap-2"><input aria-label="Section display order" type="number" min="0" className={inputClass} value={categoryForm.display_order} onChange={(event) => setCategoryForm({ ...categoryForm, display_order: event.target.value })} /><Button type="submit" disabled={busy}><Plus className="mr-1 h-4 w-4" />{editingCategoryId ? "Save" : "Add"}</Button></div>
        </form>
        <div className="space-y-2">
          {categories.length === 0 && <p className="text-sm text-muted-foreground">No sections yet. Create one above.</p>}
          {categories.map((category) => (
            <div key={category.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border p-3">
              <div><p className="font-medium">{localized(category.name, "en") || category.slug}</p><p className="text-xs text-muted-foreground">{category.slug} · order {category.display_order} · {category.is_visible ? "Visible" : "Hidden"}</p></div>
              <div className="flex gap-2"><Button size="sm" variant="outline" disabled={busy} onClick={() => editCategory(category)}>Rename / reorder</Button><Button size="sm" variant="outline" disabled={busy} onClick={() => toggleCategory(category)}>{category.is_visible ? "Hide" : "Show"}</Button><Button size="sm" variant="destructive" disabled={busy} onClick={() => window.confirm("Delete this unused section? Existing service references are protected.") && runAction(() => deleteServiceCategory(category.id), "Section deleted.").then(loadCategories)}><Trash2 className="mr-1 h-4 w-4" />Delete</Button></div>
            </div>
          ))}
        </div>
      </section>

      <section id="service-form" className="rounded-xl border border-border bg-card p-5">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div><h2 className="font-heading text-xl font-semibold">{editingId ? "Edit service" : "Add a service"}</h2><p className="mt-1 text-sm text-muted-foreground">Create or update a database-backed service. Review the checklist, then publish when ready.</p></div>
          {editingId && <Button type="button" variant="outline" onClick={resetForm}>Cancel editing</Button>}
        </div>
        <form onSubmit={submitService} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <label className="text-xs text-muted-foreground">Service code<input required pattern="[A-Za-z0-9_-]+" className={`${inputClass} mt-1`} value={form.service_code} onChange={(event) => setForm({ ...form, service_code: event.target.value })} /></label>
            <label className="text-xs text-muted-foreground">Name (Marathi)<input required className={`${inputClass} mt-1`} value={form.name_mr} onChange={(event) => setForm({ ...form, name_mr: event.target.value })} /></label>
            <label className="text-xs text-muted-foreground">Name (English)<input required className={`${inputClass} mt-1`} value={form.name_en} onChange={(event) => setForm({ ...form, name_en: event.target.value })} /></label>
            <label className="text-xs text-muted-foreground">Name (Hindi)<input required className={`${inputClass} mt-1`} value={form.name_hi} onChange={(event) => setForm({ ...form, name_hi: event.target.value })} /></label>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="text-xs text-muted-foreground">Description (Marathi)<textarea required rows="3" className={`${textareaClass} mt-1`} value={form.description_mr} onChange={(event) => setForm({ ...form, description_mr: event.target.value })} /></label>
            <label className="text-xs text-muted-foreground">Description (English)<textarea required rows="3" className={`${textareaClass} mt-1`} value={form.description_en} onChange={(event) => setForm({ ...form, description_en: event.target.value })} /></label>
            <label className="text-xs text-muted-foreground">Description (Hindi)<textarea required rows="3" className={`${textareaClass} mt-1`} value={form.description_hi} onChange={(event) => setForm({ ...form, description_hi: event.target.value })} /></label>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <label className="text-xs text-muted-foreground">Customer section<select className={`${inputClass} mt-1`} value={form.section_id} onChange={(event) => setForm({ ...form, section_id: event.target.value })}><option value="">Legacy category</option>{categories.map((category) => <option key={category.id} value={category.id}>{localized(category.name, "en") || category.slug}{category.is_visible ? "" : " (hidden)"}</option>)}</select></label>
            <label className="text-xs text-muted-foreground">Legacy category<input className={`${inputClass} mt-1`} value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })} /></label>
            <label className="text-xs text-muted-foreground">Processing time<input className={`${inputClass} mt-1`} placeholder="e.g. 7–10 working days" value={form.estimated_processing_time} onChange={(event) => setForm({ ...form, estimated_processing_time: event.target.value })} /></label>
            <label className="text-xs text-muted-foreground">Fee / pricing<input className={`${inputClass} mt-1`} placeholder="Text or JSON" value={form.pricing} onChange={(event) => setForm({ ...form, pricing: event.target.value })} /></label>
          </div>
          <label className="block text-xs text-muted-foreground">Customer instructions<textarea rows="2" className={`${textareaClass} mt-1`} value={form.customer_instructions} onChange={(event) => setForm({ ...form, customer_instructions: event.target.value })} /></label>
          <div>
            <label className="block text-xs text-muted-foreground">Document requirements (one per line: Name | required/optional | instructions | accepted formats | max MB)</label>
            <textarea required rows="5" className={`${textareaClass} mt-1 font-mono`} placeholder={'Identity proof | required | Bring original and copy | pdf,jpg,png | 10\nAddress proof | optional | Recent copy | pdf,jpg | 5'} value={form.requirements} onChange={(event) => setForm({ ...form, requirements: event.target.value })} />
            <p className="mt-1 text-xs text-muted-foreground">Document IDs and order are generated from each line. Keep checklist requirements verified before publishing.</p>
          </div>
          <label className="block text-xs text-muted-foreground">Customer-entered form fields (one per line: Field name | required/optional)<textarea rows="3" className={`${textareaClass} mt-1`} placeholder={'Applicant name | required\nReference number | optional'} value={form.form_requirements} onChange={(event) => setForm({ ...form, form_requirements: event.target.value })} /></label>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <label className="text-xs text-muted-foreground">Display order<input type="number" min="0" className={`${inputClass} mt-1`} value={form.display_order} onChange={(event) => setForm({ ...form, display_order: event.target.value })} /></label>
            <label className="text-xs text-muted-foreground">Thumbnail (JPEG/PNG)<input type="file" accept="image/jpeg,image/png,.jpg,.jpeg,.png" className="mt-2 block w-full text-sm" onChange={(event) => setThumbnail(event.target.files?.[0] || null)} /></label>
            <label className="text-xs text-muted-foreground">Thumbnail alt text<input className={`${inputClass} mt-1`} value={form.thumbnail_alt_text} onChange={(event) => setForm({ ...form, thumbnail_alt_text: event.target.value })} /></label>
            <label className="flex items-center gap-2 pt-5 text-sm"><input type="checkbox" checked={form.is_featured} onChange={(event) => setForm({ ...form, is_featured: event.target.checked })} />Featured / popular</label>
            <label className="flex items-center gap-2 pt-5 text-sm"><input type="checkbox" checked={publishAfterSave} onChange={(event) => setPublishAfterSave(event.target.checked)} />Publish after save</label>
          </div>
          <div className="flex flex-wrap gap-2"><Button type="submit" disabled={busy}><ImagePlus className="mr-2 h-4 w-4" />{editingId ? "Save changes" : "Save service draft"}</Button><Button type="button" variant="outline" disabled={!form.name_en} onClick={() => setPreview({ ...form, document_requirements: parseRequirements(form.requirements, form.service_code) })}><Eye className="mr-2 h-4 w-4" />Preview</Button></div>
        </form>
      </section>

      <section id="services-admin" className="rounded-xl border border-border bg-card p-5">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3"><div><h2 className="font-heading text-xl font-semibold">Service catalog</h2><p className="text-sm text-muted-foreground">{services.length} service records · {categories.length} sections</p></div><div className="flex flex-wrap gap-2"><label className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><input aria-label="Search services" placeholder="Search services" className={`${inputClass} pl-9`} value={query} onChange={(event) => setQuery(event.target.value)} /></label><select aria-label="Filter by service status" className={inputClass} value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All statuses</option><option value="published">Published</option><option value="draft">Needs review</option><option value="inactive">Unpublished</option></select><select aria-label="Filter by service section" className={inputClass} value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}><option value="all">All sections</option><option value="legacy">Legacy category</option>{categories.map((category) => <option key={category.id} value={category.id}>{localized(category.name, "en") || category.slug}</option>)}</select></div></div>
        {visibleServices.length === 0 ? <p className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">No services match these filters.</p> : (
          <div className="space-y-3">
            {visibleServices.map((service) => (
              <article key={service.id} className="flex flex-wrap items-center gap-4 rounded-lg border border-border p-3">
                {service.thumbnail_url ? <img src={service.thumbnail_url} alt={loc(service, "name")} className="h-16 w-20 rounded-md object-cover" /> : <div className="flex h-16 w-20 items-center justify-center rounded-md bg-muted"><ImagePlus className="h-5 w-5 text-muted-foreground" /></div>}
                <div className="min-w-0 flex-1"><p className="font-medium">{loc(service, "name")}</p><p className="text-xs text-muted-foreground">{service.service_code} · {categories.find((category) => category.id === service.section_id)?.name?.en || service.category} · order {service.display_order || 0} · {service.document_requirements?.length || service.checklist?.length || 0} requirements</p><p className="text-xs text-muted-foreground">{service.is_published ? "Published" : service.checklist_review_required ? "Draft · checklist review needed" : "Unpublished"}{service.is_featured ? " · Featured" : ""}</p></div>
                <div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" disabled={busy} onClick={() => setPreview(service)}><Eye className="mr-1 h-4 w-4" />Preview</Button><Button size="sm" variant="outline" disabled={busy} onClick={() => startEdit(service)}><Pencil className="mr-1 h-4 w-4" />Edit</Button>{service.is_published ? <Button size="sm" variant="outline" disabled={busy} onClick={() => runAction(() => archiveService(service.id), "Service archived.")}>Unpublish</Button> : <Button size="sm" disabled={busy || service.checklist_review_required} onClick={() => runAction(() => publishService(service.id), "Service published.")}>Publish</Button>}<Button size="sm" variant="destructive" disabled={busy} onClick={() => window.confirm("Delete this service permanently? Existing application records are protected; if it is in use, archive it instead.") && runAction(() => deleteService(service.id), "Service deleted.")}><Trash2 className="h-4 w-4" /></Button></div>
              </article>
            ))}
          </div>
        )}
      </section>

      {preview && <div role="dialog" aria-modal="true" aria-labelledby="service-preview-title" className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={(event) => { if (event.target === event.currentTarget) setPreview(null); }}><div className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-xl bg-card p-6 shadow-xl"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-wide text-primary">Customer preview</p><h2 id="service-preview-title" className="mt-1 font-heading text-xl font-semibold">{preview.name_en || loc(preview, "name") || "New service"}</h2></div><Button variant="ghost" onClick={() => setPreview(null)}>Close</Button></div><p className="mt-3 text-sm text-muted-foreground">{preview.description_en || localized(preview.description, "en") || "Service description preview"}</p><p className="mt-3 text-sm">{preview.customer_instructions || ""}</p><h3 className="mt-5 font-medium">Document checklist</h3><ul className="mt-2 space-y-2">{(preview.document_requirements || preview.checklist || []).map((item, index) => <li key={item.id || index} className="rounded-lg bg-muted/40 p-3 text-sm">{localized(item.label || item.name, "en") || item.label_en || item.id || `Requirement ${index + 1}`} · {item.required === false ? "Optional" : "Required"}{item.description?.en ? ` — ${item.description.en}` : ""}</li>)}</ul></div></div>}
    </div>
  );
}
