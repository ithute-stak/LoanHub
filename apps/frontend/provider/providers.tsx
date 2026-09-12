"use client";

import { SystemAssistant } from "@/components/assistant/system-assistant";
import { MobileAppNavigation } from "@/components/navigation/mobile-app-navigation";

import type { ReactNode } from "react";
import { Provider } from "react-redux";

import { AppDataProvider } from "@/provider/appDataProvider";
import { AuthProvider } from "@/provider/AuthProvider";
import { TenantProvider } from "@/provider/tenantProvider";
import { NotificationProvider } from "@/provider/notificationProvider";
import { ChatProvider } from "@/provider/chatProvider";
import { RealtimeProvider } from "@/provider/realtimeProvider";
import { store } from "@/store";
import { api } from "@/lib/api";
import { installReduxHttpCache } from "@/lib/http-cache";
import { ImpersonationBanner } from "@/components/admin/impersonation-banner";
import {
    SandboxAccessCard,
    SandboxBanner,
} from "@/components/sandbox/sandbox-banner";

installReduxHttpCache(api, store);

export function Providers({ children }: { children: ReactNode }) {
    return (
        <Provider store={store}>
            <AuthProvider>
                <TenantProvider>
                    <RealtimeProvider>
                        <NotificationProvider>
                            <ChatProvider>
                                <AppDataProvider>
                                    {children}
                                    <MobileAppNavigation />
                                    <SystemAssistant />
                                </AppDataProvider>
                                <ImpersonationBanner />
                                <SandboxAccessCard />
                                <SandboxBanner />
                            </ChatProvider>
                        </NotificationProvider>
                    </RealtimeProvider>
                </TenantProvider>
            </AuthProvider>
        </Provider>
    );
}
