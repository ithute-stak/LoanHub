"use client";

import {
    Gauge,
    Maximize2,
    MonitorDown,
    RotateCcw,
    Type,
    ZoomIn,
    ZoomOut,
} from "lucide-react";
import { useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";
import {
    Popover,
    PopoverContent,
    PopoverDescription,
    PopoverHeader,
    PopoverTitle,
    PopoverTrigger,
} from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import {
    DEFAULT_INTERFACE_SCALE,
    INTERFACE_SCALE_STEP,
    MAX_INTERFACE_SCALE,
    MIN_INTERFACE_SCALE,
    readInterfaceScale,
    readLowResourceMode,
    readWorkspaceFullscreen,
    recommendedInterfaceScale,
    resetInterfacePreferences,
    setInterfaceScale,
    setLowResourceMode,
    setWorkspaceFullscreen,
    subscribeInterfacePreferences,
} from "@/lib/interface-preferences";

const SCALE_PRESETS = [
    { value: 80, label: "Compact", note: "Small / older screens" },
    { value: 90, label: "Dense", note: "More workspace" },
    { value: 100, label: "Default", note: "Standard LoanHub" },
    { value: 110, label: "Comfort", note: "Easier reading" },
    { value: 120, label: "Large", note: "Large text" },
] as const;

function serverScaleSnapshot(): number {
    return DEFAULT_INTERFACE_SCALE;
}

function serverLowResourceSnapshot(): boolean {
    return false;
}

function serverWorkspaceSnapshot(): boolean {
    return true;
}

export function InterfaceScaleController() {
    const scale = useSyncExternalStore(
        subscribeInterfacePreferences,
        readInterfaceScale,
        serverScaleSnapshot,
    );
    const lowResourceMode = useSyncExternalStore(
        subscribeInterfacePreferences,
        readLowResourceMode,
        serverLowResourceSnapshot,
    );
    const workspaceFullscreen = useSyncExternalStore(
        subscribeInterfacePreferences,
        readWorkspaceFullscreen,
        serverWorkspaceSnapshot,
    );

    const decreaseDisabled = scale <= MIN_INTERFACE_SCALE;
    const increaseDisabled = scale >= MAX_INTERFACE_SCALE;

    function fitCurrentScreen(): void {
        setInterfaceScale(recommendedInterfaceScale(window.innerWidth));
    }

    return (
        <Popover>
            <PopoverTrigger asChild>
                <Button
                    type="button"
                    variant="outline"
                    size="icon-lg"
                    className="relative h-10 w-10 rounded-xl"
                    title={`Display size: ${scale}%`}
                    aria-label={`Open display size controls. Current size ${scale}%`}
                >
                    <Type className="h-5 w-5" />
                    {scale !== DEFAULT_INTERFACE_SCALE ? (
                        <span className="absolute -bottom-1 -right-1 min-w-5 rounded-full bg-primary px-1 text-center text-[8px] font-black leading-5 text-primary-foreground ring-2 ring-background">
                            {scale}
                        </span>
                    ) : null}
                </Button>
            </PopoverTrigger>

            <PopoverContent align="end" className="w-[min(22rem,calc(100vw-2rem))] gap-4 p-4">
                <PopoverHeader>
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <PopoverTitle className="flex items-center gap-2 font-black">
                                <MonitorDown className="h-4 w-4 text-primary" />
                                Display & font size
                            </PopoverTitle>
                            <PopoverDescription className="mt-1 text-xs leading-5">
                                Scale LoanHub globally so tables, forms, sidebars and text fit the screen better.
                            </PopoverDescription>
                        </div>
                        <div className="rounded-xl bg-primary/10 px-2.5 py-1.5 text-sm font-black text-primary">
                            {scale}%
                        </div>
                    </div>
                </PopoverHeader>

                <div className="space-y-3 rounded-2xl border bg-muted/20 p-3">
                    <div className="flex items-center justify-between gap-3">
                        <div>
                            <p className="text-xs font-black">System interface scale</p>
                            <p className="mt-0.5 text-[10px] text-muted-foreground">
                                Changes the root CSS size across LoanHub.
                            </p>
                        </div>
                        <div className="flex items-center gap-1">
                            <Button
                                type="button"
                                size="icon"
                                variant="outline"
                                className="h-8 w-8 rounded-lg"
                                disabled={decreaseDisabled}
                                onClick={() => setInterfaceScale(scale - INTERFACE_SCALE_STEP)}
                                aria-label="Make LoanHub smaller"
                                title="Make interface smaller"
                            >
                                <ZoomOut className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                                type="button"
                                size="icon"
                                variant="outline"
                                className="h-8 w-8 rounded-lg"
                                disabled={increaseDisabled}
                                onClick={() => setInterfaceScale(scale + INTERFACE_SCALE_STEP)}
                                aria-label="Make LoanHub larger"
                                title="Make interface larger"
                            >
                                <ZoomIn className="h-3.5 w-3.5" />
                            </Button>
                        </div>
                    </div>

                    <input
                        type="range"
                        min={MIN_INTERFACE_SCALE}
                        max={MAX_INTERFACE_SCALE}
                        step={INTERFACE_SCALE_STEP}
                        value={scale}
                        onChange={(event) => setInterfaceScale(Number(event.target.value))}
                        aria-label="LoanHub interface scale"
                        className="h-2 w-full cursor-pointer accent-primary"
                    />

                    <div className="flex justify-between text-[9px] font-bold text-muted-foreground">
                        <span>{MIN_INTERFACE_SCALE}%</span>
                        <span>100%</span>
                        <span>{MAX_INTERFACE_SCALE}%</span>
                    </div>
                </div>

                <div className="grid grid-cols-5 gap-1.5">
                    {SCALE_PRESETS.map((preset) => (
                        <button
                            key={preset.value}
                            type="button"
                            onClick={() => setInterfaceScale(preset.value)}
                            title={`${preset.label}: ${preset.note}`}
                            className={`rounded-xl border px-1.5 py-2 text-center transition hover:border-primary/50 hover:bg-primary/5 ${scale === preset.value ? "border-primary bg-primary/10 text-primary" : "bg-background"}`}
                        >
                            <span className="block text-xs font-black">{preset.value}%</span>
                            <span className="mt-0.5 block truncate text-[8px] font-bold text-muted-foreground">
                                {preset.label}
                            </span>
                        </button>
                    ))}
                </div>

                <Button
                    type="button"
                    variant="outline"
                    className="w-full rounded-xl"
                    onClick={fitCurrentScreen}
                >
                    <MonitorDown className="h-4 w-4" />
                    Fit this screen automatically
                </Button>

                <div className="flex items-center justify-between gap-4 rounded-2xl border bg-muted/20 p-3">
                    <div className="min-w-0">
                        <label
                            htmlFor="loanhub-fullscreen-workspace"
                            className="flex cursor-pointer items-center gap-2 text-xs font-black"
                        >
                            <Maximize2 className="h-4 w-4 text-primary" />
                            Full-screen workspace
                            <span
                                className={`rounded-full px-2 py-0.5 text-[9px] font-black ${workspaceFullscreen ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" : "bg-muted text-muted-foreground"}`}
                            >
                                {workspaceFullscreen ? "On" : "Off"}
                            </span>
                        </label>
                        <p
                            id="loanhub-fullscreen-workspace-description"
                            className="mt-1 text-[10px] leading-4 text-muted-foreground"
                        >
                            Hides the permanent LoanHub sidebar and header. Use the visible expand or restore button at any time.
                        </p>
                    </div>
                    <Switch
                        id="loanhub-fullscreen-workspace"
                        checked={workspaceFullscreen}
                        onCheckedChange={setWorkspaceFullscreen}
                        aria-label="Full-screen workspace"
                        aria-describedby="loanhub-fullscreen-workspace-description"
                    />
                </div>

                <div className="flex items-center justify-between gap-4 rounded-2xl border bg-muted/20 p-3">
                    <div className="min-w-0">
                        <p className="flex items-center gap-2 text-xs font-black">
                            <Gauge className="h-4 w-4 text-primary" />
                            Low-resource mode
                        </p>
                        <p className="mt-1 text-[10px] leading-4 text-muted-foreground">
                            Reduces motion, blur and decorative effects for older or slower computers.
                        </p>
                    </div>
                    <Switch
                        checked={lowResourceMode}
                        onCheckedChange={setLowResourceMode}
                        aria-label="Low-resource mode"
                    />
                </div>

                <div className="flex items-center justify-between gap-3 border-t pt-3">
                    <p className="text-[10px] leading-4 text-muted-foreground">
                        Saved on this computer and reused after sign-in.
                    </p>
                    <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="shrink-0 rounded-xl"
                        onClick={resetInterfacePreferences}
                    >
                        <RotateCcw className="h-3.5 w-3.5" />
                        Reset
                    </Button>
                </div>
            </PopoverContent>
        </Popover>
    );
}
