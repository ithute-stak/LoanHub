"use client";

import Link from "next/link";
import { MessageCircleMore } from "lucide-react";

import { useChat } from "@/provider/chatProvider";
import type { UserRole } from "@/types/auth";

function routeFor(role: UserRole | null | undefined): string {
    if (role === "superadmin") return "/superadmin/chat";
    if (role === "borrower") return "/borrower/chat";
    return "/company/chat";
}

export function ChatLauncher({ role }: { role: UserRole | null | undefined }) {
    const { unreadCount, connected } = useChat();

    return (
        <Link
            href={routeFor(role)}
            aria-label="Open LoanHub chat"
            className="relative inline-flex h-10 w-10 items-center justify-center rounded-xl border bg-background transition hover:border-primary hover:text-primary"
        >
            <MessageCircleMore className="h-5 w-5" />
            {unreadCount > 0 && (
                <span className="absolute -right-1 -top-1 flex min-h-5 min-w-5 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-black text-white ring-2 ring-background">
                    {unreadCount > 99 ? "99+" : unreadCount}
                </span>
            )}
            <span
                className={`absolute bottom-1 right-1 h-2 w-2 rounded-full ring-2 ring-background ${
                    connected ? "bg-emerald-500" : "bg-muted-foreground"
                }`}
            />
        </Link>
    );
}
