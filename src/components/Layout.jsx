import React, { useState } from "react";
import { Outlet, Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/lib/AuthContext";
import { useLang } from "@/lib/i18n/LanguageContext";
import Logo from "@/components/Logo";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import { Button } from "@/components/ui/button";
import { LogIn, LogOut, LayoutDashboard, Menu, X, Phone, MapPin } from "lucide-react";
import { toast } from "@/components/ui/use-toast";

function Layout() {
  const { user, isAuthenticated, logout } = useAuth();
  const { t } = useLang();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);

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

  const navItems = [
    { label: t("nav.home"), action: () => { setOpen(false); navigate("/"); } },
    { label: t("nav.services"), action: () => scrollToSection("services") },
    { label: t("nav.howItWorks"), action: () => scrollToSection("how") },
    { label: t("nav.contact"), action: () => scrollToSection("contact") },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <header className="sticky top-0 z-40 border-b border-border bg-card/85 backdrop-blur supports-[backdrop-filter]:bg-card/70">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between gap-2">
          <Logo />
          <nav className="hidden md:flex items-center gap-1">
            {navItems.map((n) => (
              <button
                key={n.label}
                onClick={n.action}
                className="px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground rounded-md transition-colors"
              >
                {n.label}
              </button>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <div className="hidden sm:block"><LanguageSwitcher /></div>
            {isAuthenticated ? (
              <>
                <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
                  <Link to={dashboardPath}><LayoutDashboard className="w-4 h-4 mr-1.5" />{t("nav.dashboard")}</Link>
                </Button>
                <Button variant="ghost" size="sm" onClick={handleLogout} className="hidden sm:inline-flex">
                  <LogOut className="w-4 h-4 mr-1.5" />{t("nav.logout")}
                </Button>
              </>
            ) : (
              <Button asChild size="sm" className="hidden sm:inline-flex">
                <Link to="/login"><LogIn className="w-4 h-4 mr-1.5" />{t("nav.login")}</Link>
              </Button>
            )}
            <button className="md:hidden p-2 -mr-2" onClick={() => setOpen(!open)} aria-label="Menu">
              {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
        {open && (
          <div className="md:hidden border-t border-border bg-card px-4 py-3 space-y-1">
            <div className="pb-2"><LanguageSwitcher /></div>
            {navItems.map((n) => (
              <button key={n.label} onClick={n.action} className="block w-full text-left px-3 py-2 text-sm font-medium rounded-md hover:bg-accent">
                {n.label}
              </button>
            ))}
            <div className="pt-2 border-t border-border space-y-1">
              {isAuthenticated ? (
                <>
                  <Link to={dashboardPath} onClick={() => setOpen(false)} className="block px-3 py-2 text-sm font-medium rounded-md hover:bg-accent">{t("nav.dashboard")}</Link>
                  <button onClick={handleLogout} className="block w-full text-left px-3 py-2 text-sm font-medium rounded-md hover:bg-accent text-destructive">{t("nav.logout")}</button>
                </>
              ) : (
                <Link to="/login" onClick={() => setOpen(false)} className="block px-3 py-2 text-sm font-medium rounded-md hover:bg-accent">{t("nav.login")}</Link>
              )}
            </div>
          </div>
        )}
      </header>

      <main className="flex-1"><Outlet /></main>

      <footer className="border-t border-border bg-card">
        <div className="max-w-6xl mx-auto px-4 py-10 grid gap-8 md:grid-cols-3">
          <div className="space-y-2">
            <Logo size="sm" to="/" />
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