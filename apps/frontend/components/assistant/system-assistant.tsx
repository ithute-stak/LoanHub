"use client";


import { Input } from "@/components/ui/input";
import {
    Bot,
    LayoutGrid,
    Loader2,
    MessageCircleMore,
    MessageSquarePlus,
    Send,
    X,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { professionalApi } from "@/api/professional";
import { useChat } from "@/provider/chatProvider";
import { useAppSelector } from "@/store/hooks";
import { isCompanyRole, type UserRole } from "@/types/auth";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type AssistantMessage = {
    who: "bot" | "user";
    text: string;
    path?: string;
    label?: string;
};

function chatRoute(role: UserRole): string {
    if (role === "superadmin") return "/superadmin/chat";
    if (role === "borrower") return "/borrower/chat";
    return "/company/chat";
}

function queryRoute(role: UserRole): string {
    if (role === "superadmin") return "/superadmin/queries";
    if (role === "borrower") return "/borrower/queries";
    return "/company/queries";
}

export function SystemAssistant() {
    const pathname = usePathname();
    const router = useRouter();
    const user = useAppSelector((state) => state.auth.user);
    const authenticated = useAppSelector(
        (state) => state.auth.isAuthenticated,
    );
    const { unreadCount, connected } = useChat();

    const [open, setOpen] = useState(false);
    const [menuOpen, setMenuOpen] = useState(false);
    const toolsRef = useRef<HTMLElement | null>(null);
    const [question, setQuestion] = useState("");
    const [asking, setAsking] = useState(false);
    const [messages, setMessages] = useState<AssistantMessage[]>([
        {
            who: "bot",
            text: "Welcome to LoanHub. I can explain each module and take you to the correct page.",
        },
    ]);

    const allowed = useMemo(
        () =>
            Boolean(
                authenticated &&
                    user &&
                    (user.role === "superadmin" ||
                        user.role === "borrower" ||
                        isCompanyRole(user.role)),
            ),
        [authenticated, user],
    );

    useEffect(() => {
        setMenuOpen(false);
    }, [pathname]);

    useEffect(() => {
        if (!menuOpen) return;

        function handlePointerDown(event: PointerEvent): void {
            if (
                toolsRef.current &&
                !toolsRef.current.contains(event.target as Node)
            ) {
                setMenuOpen(false);
            }
        }

        function handleKeyDown(event: KeyboardEvent): void {
            if (event.key === "Escape") {
                setMenuOpen(false);
            }
        }

        document.addEventListener("pointerdown", handlePointerDown);
        document.addEventListener("keydown", handleKeyDown);

        return () => {
            document.removeEventListener("pointerdown", handlePointerDown);
            document.removeEventListener("keydown", handleKeyDown);
        };
    }, [menuOpen]);

    if (!allowed || !user || pathname === "/login") {
        return null;
    }

    // Keep a non-null role value for callbacks that may finish after a later
    // authentication state update. TypeScript deliberately does not retain the
    // `user` narrowing inside an async closure.
    const userRole = user.role;

    async function ask(): Promise<void> {
        const text = question.trim();
        if (!text || asking) return;

        setQuestion("");
        setMessages((current) => [
            ...current,
            { who: "user", text },
        ]);
        setAsking(true);

        try {
            const response = await professionalApi.ask(
                text,
                pathname,
            );

            setMessages((current) => [
                ...current,
                {
                    who: "bot",
                    text: response.answer,
                    path: response.action_path ?? undefined,
                    label: response.action_label ?? undefined,
                },
            ]);
        } catch (error) {
            toast.error(
                getErrorMessage(
                    error,
                    "The LoanHub assistant could not answer right now.",
                ),
            );
            setMessages((current) => [
                ...current,
                {
                    who: "bot",
                    text: "I could not complete that request. You can submit it to the platform owner using the support-query button below.",
                    path: queryRoute(userRole),
                    label: "Open support queries",
                },
            ]);
        } finally {
            setAsking(false);
        }
    }

    return (
        <>
            {open && (
                <section className="fixed bottom-24 right-4 z-[80] flex h-[min(30rem,calc(100vh-7rem))] w-[calc(100%-2rem)] max-w-sm flex-col overflow-hidden rounded-3xl border bg-card shadow-2xl sm:bottom-5 sm:right-24 sm:h-[min(34rem,calc(100vh-3rem))]">
                    <header className="flex items-center justify-between border-b bg-primary px-4 py-3 text-primary-foreground">
                        <div className="flex items-center gap-3">
                            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white/15">
                                <Bot className="h-5 w-5" />
                            </span>
                            <div>
                                <p className="font-black">
                                    LoanHub Assistant
                                </p>
                                <p className="text-xs text-primary-foreground/75">
                                    System guidance and navigation
                                </p>
                            </div>
                        </div>
                        <button
                            type="button"
                            onClick={() => setOpen(false)}
                            className="rounded-xl p-2 transition hover:bg-white/15"
                            aria-label="Close LoanHub assistant"
                        >
                            <X className="h-5 w-5" />
                        </button>
                    </header>

                    <div className="flex-1 space-y-3 overflow-y-auto p-4">
                        {messages.map((message, index) => (
                            <div
                                key={`${message.who}-${index}`}
                                className={
                                    message.who === "bot"
                                        ? "mr-8 rounded-2xl rounded-tl-md bg-muted p-3 text-sm leading-6"
                                        : "ml-8 rounded-2xl rounded-tr-md bg-primary p-3 text-sm leading-6 text-primary-foreground"
                                }
                            >
                                <p>{message.text}</p>
                                {message.path && (
                                    <button
                                        type="button"
                                        onClick={() => {
                                            router.push(
                                                message.path!,
                                            );
                                            setOpen(false);
                                        }}
                                        className="mt-2 font-black underline underline-offset-4"
                                    >
                                        {message.label ??
                                            "Open page"}
                                    </button>
                                )}
                            </div>
                        ))}
                        {asking && (
                            <div className="mr-8 flex items-center gap-2 rounded-2xl rounded-tl-md bg-muted p-3 text-sm text-muted-foreground">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                Finding the best answer...
                            </div>
                        )}
                    </div>

                    <div className="border-t p-3">
                        <div className="flex gap-2">
                            <Input
                                value={question}
                                onChange={(event) =>
                                    setQuestion(event.target.value)
                                }
                                onKeyDown={(event) => {
                                    if (
                                        event.key === "Enter" &&
                                        !event.shiftKey
                                    ) {
                                        event.preventDefault();
                                        void ask();
                                    }
                                }}
                                disabled={asking}
                                className="h-11 min-w-0 flex-1 rounded-xl border bg-background px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                                placeholder="Ask how to use LoanHub"
                            />
                            <button
                                type="button"
                                onClick={() => void ask()}
                                disabled={
                                    asking || !question.trim()
                                }
                                className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-primary-foreground disabled:opacity-50"
                                aria-label="Send question"
                            >
                                {asking ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <Send className="h-4 w-4" />
                                )}
                            </button>
                        </div>
                    </div>
                </section>
            )}

            <nav
                ref={toolsRef}
                className="fixed bottom-5 right-4 z-[75] flex flex-col items-end gap-3 sm:right-5"
                aria-label="LoanHub floating tools"
            >
                <AnimatePresence>
                    {menuOpen && !open && (
                        <motion.div
                            initial="closed"
                            animate="open"
                            exit="closed"
                            variants={{
                                open: {
                                    opacity: 1,
                                    transition: {
                                        delayChildren: 0.03,
                                        staggerChildren: 0.055,
                                    },
                                },
                                closed: {
                                    opacity: 0,
                                    transition: {
                                        staggerChildren: 0.035,
                                        staggerDirection: -1,
                                    },
                                },
                            }}
                            role="menu"
                            aria-label="LoanHub quick actions"
                            className="flex flex-col items-end gap-3"
                        >
                            <motion.div
                                variants={{
                                    open: { opacity: 1, y: 0, scale: 1 },
                                    closed: { opacity: 0, y: 12, scale: 0.92 },
                                }}
                                transition={{ duration: 0.18, ease: "easeOut" }}
                            >
                                <Link
                                    href={queryRoute(userRole)}
                                    onClick={() => setMenuOpen(false)}
                                    role="menuitem"
                                    className="group flex items-center gap-3"
                                    aria-label="Open support queries"
                                >
                                    <span className="rounded-xl border bg-card/95 px-3 py-2 text-xs font-black text-foreground shadow-lg backdrop-blur transition group-hover:border-primary/40 group-hover:text-primary">
                                        Support query
                                    </span>
                                    <span className="flex h-12 w-12 items-center justify-center rounded-full border bg-card text-foreground shadow-xl ring-4 ring-background transition group-hover:scale-105 group-hover:text-primary">
                                        <MessageSquarePlus className="h-5 w-5" />
                                    </span>
                                </Link>
                            </motion.div>

                            <motion.div
                                variants={{
                                    open: { opacity: 1, y: 0, scale: 1 },
                                    closed: { opacity: 0, y: 12, scale: 0.92 },
                                }}
                                transition={{ duration: 0.18, ease: "easeOut" }}
                            >
                                <Link
                                    href={chatRoute(userRole)}
                                    onClick={() => setMenuOpen(false)}
                                    role="menuitem"
                                    className="group flex items-center gap-3"
                                    aria-label="Open LoanHub chat"
                                >
                                    <span className="rounded-xl border bg-card/95 px-3 py-2 text-xs font-black text-foreground shadow-lg backdrop-blur transition group-hover:border-primary/40 group-hover:text-primary">
                                        Chat
                                        {unreadCount > 0 && (
                                            <span className="ml-2 rounded-full bg-red-600 px-1.5 py-0.5 text-[9px] text-white">
                                                {unreadCount > 99 ? "99+" : unreadCount}
                                            </span>
                                        )}
                                    </span>
                                    <span className="relative flex h-12 w-12 items-center justify-center rounded-full border bg-card text-foreground shadow-xl ring-4 ring-background transition group-hover:scale-105 group-hover:text-primary">
                                        <MessageCircleMore className="h-5 w-5" />
                                        {unreadCount > 0 && (
                                            <span className="absolute -right-1 -top-1 flex min-h-5 min-w-5 items-center justify-center rounded-full bg-red-600 px-1 text-[9px] font-black text-white">
                                                {unreadCount > 99 ? "99+" : unreadCount}
                                            </span>
                                        )}
                                        <span
                                            className={`absolute bottom-0.5 right-0.5 h-2.5 w-2.5 rounded-full ring-2 ring-card ${
                                                connected
                                                    ? "bg-emerald-500"
                                                    : "bg-slate-400"
                                            }`}
                                        />
                                    </span>
                                </Link>
                            </motion.div>

                            <motion.div
                                variants={{
                                    open: { opacity: 1, y: 0, scale: 1 },
                                    closed: { opacity: 0, y: 12, scale: 0.92 },
                                }}
                                transition={{ duration: 0.18, ease: "easeOut" }}
                            >
                                <button
                                    type="button"
                                    role="menuitem"
                                    onClick={() => {
                                        setOpen(true);
                                        setMenuOpen(false);
                                    }}
                                    className="group flex items-center gap-3"
                                    aria-label="Open LoanHub assistant"
                                >
                                    <span className="rounded-xl border bg-card/95 px-3 py-2 text-xs font-black text-foreground shadow-lg backdrop-blur transition group-hover:border-primary/40 group-hover:text-primary">
                                        LoanHub Assistant
                                    </span>
                                    <span className="flex h-12 w-12 items-center justify-center rounded-full border bg-card text-foreground shadow-xl ring-4 ring-background transition group-hover:scale-105 group-hover:text-primary">
                                        <Bot className="h-5 w-5" />
                                    </span>
                                </button>
                            </motion.div>
                        </motion.div>
                    )}
                </AnimatePresence>

                <motion.button
                    type="button"
                    onClick={() => {
                        if (open) {
                            setOpen(false);
                            setMenuOpen(false);
                            return;
                        }
                        setMenuOpen((current) => !current);
                    }}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.94 }}
                    title={
                        open || menuOpen
                            ? "Close LoanHub tools"
                            : "Open LoanHub tools"
                    }
                    aria-label={
                        open || menuOpen
                            ? "Close LoanHub tools"
                            : "Open LoanHub tools"
                    }
                    aria-haspopup="menu"
                    aria-expanded={menuOpen}
                    className="relative flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-2xl ring-4 ring-background transition focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary/30"
                >
                    <AnimatePresence mode="wait" initial={false}>
                        {open || menuOpen ? (
                            <motion.span
                                key="close"
                                initial={{ opacity: 0, rotate: -90, scale: 0.7 }}
                                animate={{ opacity: 1, rotate: 0, scale: 1 }}
                                exit={{ opacity: 0, rotate: 90, scale: 0.7 }}
                                transition={{ duration: 0.16 }}
                            >
                                <X className="h-6 w-6" />
                            </motion.span>
                        ) : (
                            <motion.span
                                key="tools"
                                initial={{ opacity: 0, rotate: 90, scale: 0.7 }}
                                animate={{ opacity: 1, rotate: 0, scale: 1 }}
                                exit={{ opacity: 0, rotate: -90, scale: 0.7 }}
                                transition={{ duration: 0.16 }}
                            >
                                <LayoutGrid className="h-6 w-6" />
                            </motion.span>
                        )}
                    </AnimatePresence>
                    {!menuOpen && !open && unreadCount > 0 && (
                        <span className="absolute -right-1 -top-1 flex min-h-5 min-w-5 items-center justify-center rounded-full bg-red-600 px-1 text-[9px] font-black text-white ring-2 ring-background">
                            {unreadCount > 99 ? "99+" : unreadCount}
                        </span>
                    )}
                </motion.button>
            </nav>
        </>
    );
}
