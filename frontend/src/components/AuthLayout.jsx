import React from "react";
import Logo from "@/components/Logo";

export default function AuthLayout({ icon: Icon, title, subtitle, footer, children }) {
  return (
    <div className="relative min-h-screen flex items-center justify-center overflow-hidden bg-secondary/45 px-4 py-12">
      <div className="hero-grid absolute inset-0 opacity-40" />
      <div className="absolute -left-24 top-24 h-72 w-72 rounded-full bg-accent/10 blur-3xl" />
      <div className="absolute -right-20 bottom-10 h-80 w-80 rounded-full bg-primary/10 blur-3xl" />
      <div className="relative w-full max-w-md">
        <div className="mb-8 flex justify-center"><Logo /></div>
        <div className="rounded-[1.75rem] border border-white/80 bg-card/90 p-2 shadow-2xl shadow-primary/10 backdrop-blur-xl">
          <div className="rounded-[1.35rem] border border-border/70 bg-card p-6 sm:p-8">
            <div className="text-center mb-7">
              <div className="inline-flex items-center justify-center w-[3.25rem] h-[3.25rem] rounded-2xl bg-primary mb-4 shadow-lg shadow-primary/20">
                <Icon className="w-7 h-7 text-primary-foreground" aria-hidden="true" />
              </div>
              <h1 className="text-3xl font-bold tracking-[-0.03em] text-foreground">{title}</h1>
              {subtitle && <p className="text-muted-foreground mt-2">{subtitle}</p>}
            </div>
            {children}
          </div>
        </div>
        {footer && (
          <p className="text-center text-sm text-muted-foreground mt-6">{footer}</p>
        )}
      </div>
    </div>
  );
}
