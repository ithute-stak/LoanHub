"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { Gavel, Handshake } from "lucide-react";

const COLLECTION_WORKSPACES = [
  {
    href: "/company/collections",
    label: "Recovery centre",
    description: "Arrears, promises, follow-ups and legal control",
    icon: Gavel,
    exact: true,
  },
  {
    href: "/company/collections/lelefa",
    label: "Lelefa managed collections",
    description: "Select difficult debts, request an offer and approve the mandate",
    icon: Handshake,
    exact: false,
  },
] as const;

export default function CollectionsLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="space-y-4">
      <section className="overflow-hidden rounded-2xl border bg-card shadow-sm">
        <div className="border-b bg-muted/30 px-4 py-3 sm:px-5">
          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-muted-foreground">Collections command navigation</p>
          <p className="mt-1 text-sm font-semibold text-foreground">Keep internal recovery and external Lelefa handover in one controlled workflow.</p>
        </div>
        <div className="grid gap-2 p-3 md:grid-cols-2">
          {COLLECTION_WORKSPACES.map((item) => {
            const active = item.exact ? pathname === item.href : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={[
                  "group flex items-start gap-3 rounded-xl border px-4 py-3 transition",
                  active
                    ? "border-primary/40 bg-primary/10 text-primary shadow-sm"
                    : "border-transparent bg-muted/20 text-foreground hover:border-primary/30 hover:bg-primary/5",
                ].join(" ")}
              >
                <span className={[
                  "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl",
                  active ? "bg-primary text-primary-foreground" : "bg-background text-primary ring-1 ring-border",
                ].join(" ")}>
                  <Icon className="h-4 w-4" />
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-black">{item.label}</span>
                  <span className={[
                    "mt-1 block text-xs leading-5",
                    active ? "text-primary/80" : "text-muted-foreground",
                  ].join(" ")}>
                    {item.description}
                  </span>
                </span>
              </Link>
            );
          })}
        </div>
      </section>
      {children}
    </div>
  );
}
