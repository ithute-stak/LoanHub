"use client";

import { useEffect, useRef, type ReactNode } from "react";

import { useAppDispatch } from "@/store/hooks";
import { bootstrapAuth } from "@/store/slices/authSlice";

export function AuthProvider({ children }: { children: ReactNode }) {
    const dispatch = useAppDispatch();
    const started = useRef(false);

    useEffect(() => {
        if (started.current) {
            return;
        }
        started.current = true;
        const timer = window.setTimeout(() => void dispatch(bootstrapAuth()), 0);
        return () => window.clearTimeout(timer);
    }, [dispatch]);

    return children;
}
