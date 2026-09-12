export const INTERFACE_SCALE_STORAGE_KEY = "loanhub.interface-scale";
export const LOW_RESOURCE_MODE_STORAGE_KEY = "loanhub.low-resource-mode";
export const WORKSPACE_FULLSCREEN_STORAGE_KEY = "loanhub.workspace-fullscreen";
export const INTERFACE_PREFERENCES_EVENT = "loanhub:interface-preferences";

export const DEFAULT_INTERFACE_SCALE = 100;
export const MIN_INTERFACE_SCALE = 80;
export const MAX_INTERFACE_SCALE = 125;
export const INTERFACE_SCALE_STEP = 5;
export const DEFAULT_WORKSPACE_FULLSCREEN = true;

function clampScale(value: number): number {
    if (!Number.isFinite(value)) return DEFAULT_INTERFACE_SCALE;
    const stepped = Math.round(value / INTERFACE_SCALE_STEP) * INTERFACE_SCALE_STEP;
    return Math.min(MAX_INTERFACE_SCALE, Math.max(MIN_INTERFACE_SCALE, stepped));
}

function browserAvailable(): boolean {
    return typeof window !== "undefined" && typeof document !== "undefined";
}

export function readInterfaceScale(): number {
    if (!browserAvailable()) return DEFAULT_INTERFACE_SCALE;
    try {
        const stored = window.localStorage.getItem(INTERFACE_SCALE_STORAGE_KEY);
        return stored === null ? DEFAULT_INTERFACE_SCALE : clampScale(Number(stored));
    } catch {
        return DEFAULT_INTERFACE_SCALE;
    }
}

export function readLowResourceMode(): boolean {
    if (!browserAvailable()) return false;
    try {
        return window.localStorage.getItem(LOW_RESOURCE_MODE_STORAGE_KEY) === "true";
    } catch {
        return false;
    }
}

export function readWorkspaceFullscreen(): boolean {
    if (!browserAvailable()) return DEFAULT_WORKSPACE_FULLSCREEN;
    try {
        const stored = window.localStorage.getItem(WORKSPACE_FULLSCREEN_STORAGE_KEY);
        return stored === null ? DEFAULT_WORKSPACE_FULLSCREEN : stored === "true";
    } catch {
        return DEFAULT_WORKSPACE_FULLSCREEN;
    }
}

function applyScaleToDocument(scale: number): void {
    if (!browserAvailable()) return;
    const safeScale = clampScale(scale);
    document.documentElement.style.setProperty("--loanhub-ui-scale", `${safeScale}%`);
    document.documentElement.dataset.loanhubUiScale = String(safeScale);
}

function applyLowResourceModeToDocument(enabled: boolean): void {
    if (!browserAvailable()) return;
    document.documentElement.dataset.loanhubLite = enabled ? "true" : "false";
}

function applyWorkspaceModeToDocument(fullscreen: boolean): void {
    if (!browserAvailable()) return;
    document.documentElement.dataset.loanhubWorkspace = fullscreen ? "fullscreen" : "normal";
}

function notifyPreferenceChange(): void {
    if (!browserAvailable()) return;
    window.dispatchEvent(new Event(INTERFACE_PREFERENCES_EVENT));
}

export function setInterfaceScale(value: number): number {
    const scale = clampScale(value);
    if (!browserAvailable()) return scale;

    try {
        window.localStorage.setItem(INTERFACE_SCALE_STORAGE_KEY, String(scale));
    } catch {
        // The setting still applies for the current page when storage is unavailable.
    }

    applyScaleToDocument(scale);
    notifyPreferenceChange();
    return scale;
}

export function setLowResourceMode(enabled: boolean): void {
    if (!browserAvailable()) return;

    try {
        window.localStorage.setItem(LOW_RESOURCE_MODE_STORAGE_KEY, String(enabled));
    } catch {
        // The setting still applies for the current page when storage is unavailable.
    }

    applyLowResourceModeToDocument(enabled);
    notifyPreferenceChange();
}

export function setWorkspaceFullscreen(enabled: boolean): void {
    if (!browserAvailable()) return;

    try {
        window.localStorage.setItem(WORKSPACE_FULLSCREEN_STORAGE_KEY, String(enabled));
    } catch {
        // The setting still applies for the current page when storage is unavailable.
    }

    applyWorkspaceModeToDocument(enabled);
    notifyPreferenceChange();
}

export function resetInterfacePreferences(): void {
    if (!browserAvailable()) return;

    try {
        window.localStorage.removeItem(INTERFACE_SCALE_STORAGE_KEY);
        window.localStorage.removeItem(LOW_RESOURCE_MODE_STORAGE_KEY);
        window.localStorage.removeItem(WORKSPACE_FULLSCREEN_STORAGE_KEY);
    } catch {
        // Reset the current page even when storage is unavailable.
    }

    applyScaleToDocument(DEFAULT_INTERFACE_SCALE);
    applyLowResourceModeToDocument(false);
    applyWorkspaceModeToDocument(DEFAULT_WORKSPACE_FULLSCREEN);
    notifyPreferenceChange();
}

export function subscribeInterfacePreferences(onStoreChange: () => void): () => void {
    if (!browserAvailable()) return () => undefined;

    function handleStorage(event: StorageEvent): void {
        if (
            event.key === INTERFACE_SCALE_STORAGE_KEY
            || event.key === LOW_RESOURCE_MODE_STORAGE_KEY
            || event.key === WORKSPACE_FULLSCREEN_STORAGE_KEY
            || event.key === null
        ) {
            applyScaleToDocument(readInterfaceScale());
            applyLowResourceModeToDocument(readLowResourceMode());
            applyWorkspaceModeToDocument(readWorkspaceFullscreen());
            onStoreChange();
        }
    }

    window.addEventListener(INTERFACE_PREFERENCES_EVENT, onStoreChange);
    window.addEventListener("storage", handleStorage);

    return () => {
        window.removeEventListener(INTERFACE_PREFERENCES_EVENT, onStoreChange);
        window.removeEventListener("storage", handleStorage);
    };
}

export function recommendedInterfaceScale(viewportWidth?: number): number {
    const width = viewportWidth ?? (typeof window !== "undefined" ? window.innerWidth : 1920);
    if (width <= 1024) return 80;
    if (width <= 1280) return 85;
    if (width <= 1440) return 90;
    if (width <= 1600) return 95;
    return 100;
}
