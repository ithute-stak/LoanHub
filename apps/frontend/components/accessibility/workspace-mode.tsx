"use client";

import { Maximize2, Minimize2 } from "lucide-react";
import { useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";
import {
    DEFAULT_WORKSPACE_FULLSCREEN,
    readWorkspaceFullscreen,
    setWorkspaceFullscreen,
    subscribeInterfacePreferences,
} from "@/lib/interface-preferences";

function serverSnapshot(): boolean {
    return DEFAULT_WORKSPACE_FULLSCREEN;
}

export function useWorkspaceFullscreen(): boolean {
    return useSyncExternalStore(
        subscribeInterfacePreferences,
        readWorkspaceFullscreen,
        serverSnapshot,
    );
}

export function WorkspaceModeToggle({
    showLabel = false,
}: {
    showLabel?: boolean;
}) {
    const fullscreenWorkspace = useWorkspaceFullscreen();
    const actionLabel = fullscreenWorkspace
        ? "Turn full-screen workspace off"
        : "Turn full-screen workspace on";
    const visibleLabel = fullscreenWorkspace ? "Normal view" : "Full screen";
    const Icon = fullscreenWorkspace ? Minimize2 : Maximize2;

    return (
        <Button
            type="button"
            variant="outline"
            size={showLabel ? "sm" : "icon-lg"}
            className={showLabel ? "rounded-xl" : "h-10 w-10 rounded-xl"}
            onClick={() => setWorkspaceFullscreen(!fullscreenWorkspace)}
            title={actionLabel}
            aria-label={actionLabel}
            aria-pressed={fullscreenWorkspace}
            data-workspace-mode={fullscreenWorkspace ? "fullscreen" : "normal"}
        >
            <Icon className="h-4 w-4" />
            {showLabel ? visibleLabel : null}
        </Button>
    );
}

export function NormalWorkspaceButton({
    showLabel = false,
}: {
    showLabel?: boolean;
}) {
    return (
        <Button
            type="button"
            variant="outline"
            size={showLabel ? "sm" : "icon-lg"}
            className={showLabel ? "rounded-xl" : "h-10 w-10 rounded-xl"}
            onClick={() => setWorkspaceFullscreen(false)}
            title="Return to normal LoanHub layout"
            aria-label="Return to normal LoanHub layout"
        >
            <Minimize2 className="h-4 w-4" />
            {showLabel ? "Normal view" : null}
        </Button>
    );
}
