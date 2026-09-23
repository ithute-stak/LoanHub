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
        const storedScale = localStorage.getItem("loanhub.interface-scale");
        const rawScale = Number(storedScale);
        const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 1920;
        const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 1080;
        const automaticScale = viewportWidth <= 1024 || viewportHeight <= 640
            ? 85
            : viewportWidth <= 1280 || viewportHeight <= 720
                ? 90
                : viewportWidth <= 1440 || viewportHeight <= 800
                    ? 95
                    : 100;
        const safeScale = storedScale !== null && Number.isFinite(rawScale) && rawScale >= 80 && rawScale <= 125
            ? Math.round(rawScale / 5) * 5
            : automaticScale;

        const storedDensity = localStorage.getItem("loanhub.ui-density");
        const densityIsExplicit = storedDensity === "compact" || storedDensity === "comfortable";
        const automaticDensity = viewportWidth <= 1280 || viewportHeight <= 720 ? "compact" : "comfortable";
        const density = densityIsExplicit ? storedDensity : automaticDensity;

        const cores = Number(navigator.hardwareConcurrency || 0);
        const memory = Number(navigator.deviceMemory || 0);
        const constrainedHardware = (cores > 0 && cores <= 2) || (memory > 0 && memory <= 2);
        const storedLite = localStorage.getItem("loanhub.low-resource-mode");
        const lite = storedLite === "true" || (storedLite === null && constrainedHardware);

        const storedWorkspaceMode = localStorage.getItem("loanhub.workspace-fullscreen");
        const workspaceFullscreen = storedWorkspaceMode === null ? true : storedWorkspaceMode === "true";
        root.style.setProperty("--loanhub-ui-scale", safeScale + "%");
        root.dataset.loanhubUiScale = String(safeScale);
        root.dataset.loanhubAutoCompact = storedScale === null && automaticScale < 100 ? "true" : "false";
        root.dataset.loanhubDensity = density;
        root.dataset.loanhubDensityAuto = densityIsExplicit ? "false" : "true";
        root.dataset.loanhubLite = lite ? "true" : "false";
        root.dataset.loanhubWorkspace = workspaceFullscreen ? "fullscreen" : "normal";
    } catch {
        // Use CSS defaults when browser storage or hardware hints are unavailable.
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