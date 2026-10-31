import React, { useEffect, useMemo, useState } from "react";
import { Outlet, Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/lib/AuthContext";
import { useLang } from "@/lib/i18n/LanguageContext";
import Logo from "@/components/Logo";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import { Menu, X, Phone, MapPin, ChevronDown } from "lucide-react";
import { toast } from "@/components/ui/use-toast";
import { listServiceCategories, listServices } from "@/api/backendClient";

function Layout() {
  const { user, isAuthenticated, logout } = useAuth();
  const { t, loc, lang } = useLang();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [serviceCategories, setServiceCategories] = useState([]);

  useEffect(() => setOpen(false), [location.pathname]);

  useEffect(() => {
    let active = true;
    if (!isAuthenticated || user?.role !== "customer") {
      setServiceCategories([]);
      return () => { active = false; };
    }
    Promise.all([listServiceCategories(), listServices(lang)]).then(([categories, services]) => {
      if (!active) return;
      const managed = categories.map((category) => ({
        id: `section-${category.id}`,
        label: loc(category, "name") || category.slug,
        to: `/services/category/section-${category.id}`,
      }));
      const managedIds = new Set(categories.map((category) => category.id));
      const legacy = [...new Set((services.items || []).filter((service) => !service.section_id || !managedIds.has(service.section_id))
        .map((service) => service.category).filter(Boolean))].map((category) => ({
        id: `legacy-${category}`,
        label: category,
        to: `/services/category/legacy-${encodeURIComponent(category)}`,
      }));
      setServiceCategories([...managed, ...legacy]);
    }).catch((error) => {
      if (active) setServiceCategories([]);
      console.error("Unable to load service categories for navigation:", error);
    });
    return () => { active = false; };
  }, [isAuthenticated, user?.role, lang, loc]);

  const scrollToSection = (id) => {
    setOpen(false);
    const doScroll = () => {
      const el = document.getElementById(id);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    };
    if (location.pathname !== "/") {
      navigate("/");
      setTimeout(doScroll, 350);
    } else {
      doScroll();
    }
  };

  const handleLogout = async () => {
    setOpen(false);
    try {
      await logout(false);
      navigate("/");
    } catch (error) {
      toast({
        title: "Unable to log out",
        description: error.message || "Please try again.",
        variant: "destructive",
      });
    }
  };
  const dashboardPath = user?.role === "customer" ? "/dashboard" : "/workspace";
  const roleLinks = user?.role === "customer" ? [
    { label: "Dashboard", to: "/dashboard" },
    { label: "New Application", to: "/services" },
    { label: "My Applications / Application History", to: "/applications" },
    { label: "My Documents", to: "/documents" },
    { label: "Notifications", to: "/notifications" },
    { label: "Profile", to: "/profile" },
    { label: "Help & Support", to: "/help" },
  ] : user?.role === "owner" ? [
    { label: "Owner Dashboard", to: "/workspace" },
    { label: "All Applications", to: "/workspace#applications" },
    { label: "Applications by Document Category", to: "/workspace#categories" },
    { label: "Pending Verification", to: "/workspace#verification" },
    { label: "Completed Documents", to: "/workspace#completed-documents" },
    { label: "Customer Management", to: "/workspace#customers" },
    { label: "Notifications", to: "/notifications" },
    { label: "Profile", to: "/profile" },
  ] : user?.role === "admin" ? [
    { label: "Admin Dashboard", to: "/workspace" },
    { label: "Manage Services", to: "/workspace#services-admin" },
    { label: "Add New Service", to: "/workspace#service-form" },
    { label: "Manage Service Categories", to: "/workspace#categories-admin" },
    { label: "Manage Document Requirements", to: "/workspace#service-form" },
    { label: "Manage Thumbnails and Images", to: "/workspace#service-form" },
    { label: "Manage Customers", to: "/workspace#customers" },
    { label: "Manage Owners and Staff", to: "/workspace#customers" },
    { label: "Manage Applications", to: "/workspace#applications" },
    { label: "Reports and Analytics", to: "/workspace#reports" },
    { label: "Notifications", to: "/notifications" },
    { label: "Settings", to: "/workspace#settings" },
    { label: "Profile", to: "/profile" },
  ] : user?.role === "staff" ? [
    { label: "Assigned Applications", to: "/workspace#applications" },
    { label: "Notifications", to: "/notifications" },
    { label: "Profile", to: "/profile" },
  ] : [];

  const guestLinks = useMemo(() => ([
    { label: t("nav.home"), to: "/" },
    { label: t("nav.howItWorks"), action: () => scrollToSection("how") },
    { label: "Register Now", to: "/register" },
    { label: t("nav.login"), to: "/login" },
  ]), [t]);

  const renderRoleMenu = () => (
    <>
      {roleLinks.map((item) => <Link key={item.label} to={item.to} onClick={() => setOpen(false)} className="block rounded-md px-3 py-2.5 text-sm font-medium hover:bg-accent">{item.label}</Link>)}
      {user?.role === "customer" && (
        <details className="group rounded-md border-t border-border pt-1">
          <summary className="flex cursor-pointer list-none items-center justify-between rounded-md px-3 py-2.5 text-sm font-medium hover:bg-accent">Document Categories <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" /></summary>
          {serviceCategories.map((category) => <Link key={category.id} to={category.to} onClick={() => setOpen(false)} className="block rounded-md py-2 pl-6 pr-3 text-sm text-muted-foreground hover:bg-accent hover:text-foreground">{category.label}</Link>)}
          {serviceCategories.length === 0 && <p className="px-6 py-2 text-xs text-muted-foreground">No published service categories.</p>}
        </details>
      )}
    </>
  );

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <header className="sticky top-0 z-40 border-b border-border bg-card/85 backdrop-blur supports-[backdrop-filter]:bg-card/70">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-end gap-3 px-4">
          {!isAuthenticated && <nav className="hidden items-center gap-1 2xl:flex" aria-label="Guest navigation">
            {guestLinks.map((item) => item.to
              ? <Link key={item.label} to={item.to} className="rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground">{item.label}</Link>
              : <button key={item.label} type="button" onClick={item.action} className="rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground">{item.label}</button>)}
          </nav>}
          <div className="ml-auto flex min-w-0 items-center gap-2">
            <div className="hidden 2xl:block"><LanguageSwitcher /></div>
            <Logo to={isAuthenticated ? dashboardPath : "/"} />
            <button className="rounded-md p-2 hover:bg-accent" onClick={() => setOpen(!open)} aria-label={open ? "Close navigation menu" : "Open navigation menu"} aria-expanded={open} aria-controls="site-navigation-menu">
              {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>
        {open && (
          <div id="site-navigation-menu" className="absolute right-4 top-16 z-50 max-h-[calc(100vh-5rem)] w-[min(22rem,calc(100vw-2rem))] overflow-y-auto rounded-xl border border-border bg-card p-3 shadow-xl">
            <div className="mb-2 flex justify-end 2xl:hidden"><LanguageSwitcher /></div>
            {isAuthenticated ? (
              <>
                <p className="px-3 py-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{user?.role} navigation</p>
                {renderRoleMenu()}
                <button onClick={handleLogout} className="mt-2 block w-full rounded-md border-t border-border px-3 py-2.5 text-left text-sm font-medium text-destructive hover:bg-accent">{t("nav.logout")}</button>
              </>
            ) : guestLinks.map((item) => item.to
              ? <Link key={item.label} to={item.to} onClick={() => setOpen(false)} className="block rounded-md px-3 py-2.5 text-sm font-medium hover:bg-accent">{item.label}</Link>
              : <button key={item.label} type="button" onClick={item.action} className="block w-full rounded-md px-3 py-2.5 text-left text-sm font-medium hover:bg-accent">{item.label}</button>)}
          </div>
        )}
      </header>

      <main className="flex-1"><Outlet /></main>

      <footer className="border-t border-border bg-card">
        <div className="max-w-6xl mx-auto px-4 py-10 grid gap-8 md:grid-cols-3">
          <div className="space-y-2">
            <Logo size="sm" to={isAuthenticated ? dashboardPath : "/"} />
            <p className="text-sm text-muted-foreground max-w-xs">{t("home.disclaimer")}</p>
          </div>
          <div id="contact" className="space-y-2">
            <h3 className="font-heading font-semibold text-sm uppercase tracking-wide text-foreground">{t("home.contactTitle")}</h3>
            <p className="text-sm text-muted-foreground flex items-start gap-2"><MapPin className="w-4 h-4 mt-0.5 shrink-0" />{t("home.address")}</p>
            <a href="tel:+918149921445" className="text-sm text-muted-foreground flex items-center gap-2 hover:text-foreground"><Phone className="w-4 h-4 shrink-0" />{t("home.phone")}</a>
          </div>
          <div className="space-y-2">
            <h3 className="font-heading font-semibold text-sm uppercase tracking-wide text-foreground">{t("common.appName")}</h3>
            <p className="text-sm text-muted-foreground">{t("footer.builtWith")}</p>
            <div className="flex gap-4 text-sm">
              <span className="text-muted-foreground hover:text-foreground cursor-pointer">{t("home.privacy")}</span>
              <span className="text-muted-foreground hover:text-foreground cursor-pointer">{t("home.terms")}</span>
            </div>
          </div>
        </div>
        <div className="border-t border-border py-4 text-center text-xs text-muted-foreground">
          © {new Date().getFullYear()} {t("common.appName")}. {t("footer.rights")}
        </div>
      </footer>
    </div>
  );
}

export default Layout;