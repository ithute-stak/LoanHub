import type {Metadata, Viewport} from "next";
import "./globals.css";
import "./mobile-app.css";
import "./office-workspace.css";
import "./visitor-responsive.css";
import "./responsive-hardening.css";
import "./mobile-scroll-hardening.css";
import "./form-polish.css";
import {TooltipProvider} from "@/components/ui/tooltip";
import {Toaster} from "@/components/ui/sonner";
import React from "react";
import {ThemeProvider} from "@/components/theme-provider";
import MobilePullToRefresh from "@/components/system/mobile-pull-to-refresh";
import {Providers} from "@/provider/providers";


const interfacePreferencesBootScript = `
(() => {
    try {
        const root = document.documentElement;
        const rawScale = Number(localStorage.getItem("loanhub.interface-scale"));
        const safeScale = Number.isFinite(rawScale) && rawScale >= 80 && rawScale <= 125
            ? Math.round(rawScale / 5) * 5
            : 100;
        const lite = localStorage.getItem("loanhub.low-resource-mode") === "true";
        const storedWorkspaceMode = localStorage.getItem("loanhub.workspace-fullscreen");
        const workspaceFullscreen = storedWorkspaceMode === null ? true : storedWorkspaceMode === "true";
        root.style.setProperty("--loanhub-ui-scale", safeScale + "%");
        root.dataset.loanhubUiScale = String(safeScale);
        root.dataset.loanhubLite = lite ? "true" : "false";
        root.dataset.loanhubWorkspace = workspaceFullscreen ? "fullscreen" : "normal";
    } catch {
        // Use CSS defaults when browser storage is unavailable.
    }
})();
`;

export const metadata: Metadata = {
    title: "LoanHub — Lesotho Loan Marketplace",
    description: "Secure multi-tenant loan marketplace, lending, accounting, reporting and communication platform for Lesotho.",
    applicationName: "LoanHub",
    appleWebApp: {
        capable: true,
        title: "LoanHub",
        statusBarStyle: "default",
    },
    formatDetection: {
        telephone: false,
    },
};

export const viewport: Viewport = {
    width: "device-width",
    initialScale: 1,
    viewportFit: "cover",
    themeColor: [
        {media: "(prefers-color-scheme: light)", color: "#ffffff"},
        {media: "(prefers-color-scheme: dark)", color: "#020617"},
    ],
};

export default function RootLayout({children}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html suppressHydrationWarning
              lang="en"
              className="h-full antialiased"
        >
        <head>
            <script dangerouslySetInnerHTML={{__html: interfacePreferencesBootScript}} />
        </head>
        <body className="min-h-full flex flex-col">
        <ThemeProvider
            attribute="class"
            defaultTheme="system"
            enableSystem
            disableTransitionOnChange
        >
            <TooltipProvider>
                <MobilePullToRefresh />
                <Providers>{children}</Providers>
                <Toaster richColors position="top-right" />
            </TooltipProvider>
        </ThemeProvider>
        </body>
        </html>
    );
}