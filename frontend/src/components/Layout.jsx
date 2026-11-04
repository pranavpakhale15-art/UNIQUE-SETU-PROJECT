import React, { useState } from "react";
import { Outlet, Link, useNavigate, useLocation } from "react-router-dom";
import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/AuthContext";
import { useLang } from "@/lib/i18n/LanguageContext";
import Logo from "@/components/Logo";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import { Button } from "@/components/ui/button";
import { LogIn, LogOut, LayoutDashboard, Menu, X, Phone, MapPin, ShieldCheck, Bell } from "lucide-react";
import { toast } from "@/components/ui/use-toast";
import { getUnreadNotificationCount } from "@/api/backendClient";

function Layout() {
  const { user, isAuthenticated, logout } = useAuth();
  const { t } = useLang();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const userId = user?.id || user?._id;
  const unreadCountQuery = useQuery({
    queryKey: ["notification-unread-count", userId],
    queryFn: getUnreadNotificationCount,
    select: (result) => result.unread_count,
    enabled: Boolean(isAuthenticated && userId),
    refetchInterval: 60_000,
  });

  useEffect(() => {
    const refreshCount = () => queryClient.invalidateQueries({ queryKey: ["notification-unread-count"] });
    window.addEventListener("setu:notification-read", refreshCount);
    window.addEventListener("setu:notifications-read-all", refreshCount);
    return () => {
      window.removeEventListener("setu:notification-read", refreshCount);
      window.removeEventListener("setu:notifications-read-all", refreshCount);
    };
  }, [queryClient]);

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
    { label: t("nav.services"), action: () => { setOpen(false); navigate("/services"); } },
    { label: t("nav.howItWorks"), action: () => scrollToSection("how") },
    { label: t("nav.contact"), action: () => scrollToSection("contact") },
  ];

  const accountLinks = user?.role === "customer"
    ? [
      { label: t("nav.dashboard"), to: "/dashboard" },
      { label: "My applications", to: "/applications" },
      { label: "My documents", to: "/documents" },
      { label: "Notifications", to: "/notifications" },
      { label: "Profile", to: "/profile" },
      { label: "Help & support", to: "/help" },
    ]
    : isAuthenticated
      ? [
        { label: t("nav.dashboard"), to: dashboardPath },
        { label: "Notifications", to: "/notifications" },
        { label: "Profile", to: "/profile" },
      ]
      : [];

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <div className="hidden sm:block border-b border-primary-foreground/10 bg-primary text-primary-foreground">
        <div className="max-w-7xl mx-auto px-6 h-8 flex items-center justify-between text-[11px] font-medium">
          <span className="inline-flex items-center gap-1.5 opacity-80"><ShieldCheck className="w-3.5 h-3.5" />{t("common.tagline")}</span>
          <div className="flex items-center gap-5">
            <span className="inline-flex items-center gap-1.5 opacity-80"><MapPin className="w-3 h-3" />{t("home.address")}</span>
            <a href="tel:+918149921445" className="inline-flex items-center gap-1.5 transition-opacity hover:opacity-75"><Phone className="w-3 h-3" />{t("home.phone")}</a>
          </div>
        </div>
      </div>
      <header className="sticky top-0 z-40 border-b border-border/70 bg-card/90 backdrop-blur-xl supports-[backdrop-filter]:bg-card/75">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-[4.5rem] flex items-center justify-between gap-2">
          <Logo />
          <nav className="hidden md:flex items-center gap-1">
            {navItems.map((n) => (
              <button
                key={n.label}
                onClick={n.action}
                className="px-3.5 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-secondary rounded-lg transition-colors"
              >
                {n.label}
              </button>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <div className="hidden sm:block"><LanguageSwitcher /></div>
            {isAuthenticated ? (
              <>
                <Button asChild variant="ghost" size="sm" className="relative" aria-label="Notifications">
                  <Link to="/notifications" aria-label={unreadCountQuery.isError
                    ? "Notifications; unread count unavailable"
                    : `Notifications${unreadCountQuery.data ? `, ${unreadCountQuery.data} unread` : ""}`}>
                    <Bell className="h-4 w-4" />
                    {unreadCountQuery.isError ? (
                      <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold text-destructive-foreground">!</span>
                    ) : unreadCountQuery.data > 0 ? (
                      <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold text-destructive-foreground">
                        {unreadCountQuery.data > 99 ? "99+" : unreadCountQuery.data}
                      </span>
                    ) : null}
                  </Link>
                </Button>
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
            <button className="p-2.5 -mr-2 rounded-xl border border-border bg-card" onClick={() => setOpen(!open)} aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open}>
              {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
        {open && (
          <div className="border-t border-border bg-card px-4 py-4 space-y-1 shadow-xl">
            <div className="pb-2"><LanguageSwitcher /></div>
            {navItems.map((n) => (
              <button key={n.label} onClick={n.action} className="block w-full text-left px-3 py-2 text-sm font-medium rounded-md hover:bg-accent">
                {n.label}
              </button>
            ))}
            <div className="pt-2 border-t border-border space-y-1">
              {isAuthenticated ? (
                <>
                  {accountLinks.map((item) => (
                    <Link key={item.to} to={item.to} onClick={() => setOpen(false)} className="block px-3 py-2 text-sm font-medium rounded-md hover:bg-accent">{item.label}</Link>
                  ))}
                  <button onClick={handleLogout} className="block w-full text-left px-3 py-2 text-sm font-medium rounded-md hover:bg-accent text-destructive">{t("nav.logout")}</button>
                </>
              ) : (
                <>
                  <Link to="/login" onClick={() => setOpen(false)} className="block px-3 py-2 text-sm font-medium rounded-md hover:bg-accent">{t("nav.login")}</Link>
                  <Link to="/register" onClick={() => setOpen(false)} className="block px-3 py-2 text-sm font-medium rounded-md hover:bg-accent">{t("nav.register")}</Link>
                </>
              )}
            </div>
          </div>
        )}
      </header>

      <main key={location.pathname} className="flex-1 page-enter"><Outlet /></main>

      <footer className="border-t border-border bg-card">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-14 grid gap-10 md:grid-cols-[1.25fr_1fr_1fr]">
          <div className="space-y-2">
            <Logo size="sm" to="/" />
            <p className="text-sm text-muted-foreground max-w-xs">{t("home.disclaimer")}</p>
          </div>
          <div id="contact" className="space-y-3">
            <h3 className="font-heading font-semibold text-xs uppercase tracking-[0.16em] text-foreground">{t("home.contactTitle")}</h3>
            <p className="text-sm text-muted-foreground flex items-start gap-2.5"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-secondary"><MapPin className="w-3.5 h-3.5" /></span><span className="pt-1">{t("home.address")}</span></p>
            <a href="tel:+918149921445" className="text-sm text-muted-foreground flex items-center gap-2.5 hover:text-foreground"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-secondary"><Phone className="w-3.5 h-3.5" /></span>{t("home.phone")}</a>
          </div>
          <div className="space-y-2">
            <h3 className="font-heading font-semibold text-xs uppercase tracking-[0.16em] text-foreground">{t("common.appName")}</h3>
            <p className="text-sm text-muted-foreground">{t("footer.builtWith")}</p>
            <div className="flex gap-4 text-sm">
              <span className="text-muted-foreground hover:text-foreground cursor-pointer">{t("home.privacy")}</span>
              <span className="text-muted-foreground hover:text-foreground cursor-pointer">{t("home.terms")}</span>
            </div>
          </div>
        </div>
        <div className="border-t border-border bg-secondary/40 py-4 text-center text-xs text-muted-foreground">
          © {new Date().getFullYear()} {t("common.appName")}. {t("footer.rights")}
        </div>
      </footer>
    </div>
  );
}

export default Layout;
