"use client";

import {useState} from "react";
import {createRoot} from "react-dom/client";
import {Button} from "@/components/ui/button";
import {Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle} from "@/components/ui/dialog";
import {Textarea} from "@/components/ui/textarea";

type DialogKind = "message" | "confirm" | "prompt";
type DialogResult = string | boolean | null;
type Options = {title?: string; confirmLabel?: string; destructive?: boolean; minLength?: number};

function NativeDialogReplacement({
    kind, message, initialValue, options, resolve,
}: {
    kind: DialogKind;
    message: string;
    initialValue: string;
    options: Options;
    resolve: (value: DialogResult) => void;
}) {
    const [value, setValue] = useState(initialValue);
    const title = options.title ?? (kind === "message" ? "LoanHub notice" : kind === "confirm" ? "Confirm action" : "Provide information");
    const minLength = options.minLength ?? 0;
    const allowed = kind !== "prompt" || value.trim().length >= minLength;

    return <Dialog open onOpenChange={(open) => { if (!open) resolve(kind === "confirm" ? false : null); }}>
        <DialogContent className="sm:max-w-lg" onEscapeKeyDown={() => resolve(kind === "confirm" ? false : null)}>
            <DialogHeader>
                <DialogTitle>{title}</DialogTitle>
                <DialogDescription className="whitespace-pre-wrap break-words leading-relaxed">{message}</DialogDescription>
            </DialogHeader>
            {kind === "prompt" ? <Textarea
                autoFocus
                aria-label={title}
                value={value}
                onChange={(event) => setValue(event.target.value)}
                rows={3}
                className="min-h-24 resize-y"
            /> : null}
            <DialogFooter>
                {kind !== "message" ? <Button variant="outline" type="button" onClick={() => resolve(kind === "confirm" ? false : null)}>Cancel</Button> : null}
                <Button type="button" variant={options.destructive ? "destructive" : "default"} disabled={!allowed}
                    onClick={() => resolve(kind === "confirm" ? true : kind === "prompt" ? value : null)}>
                    {options.confirmLabel ?? (kind === "message" ? "Close" : kind === "confirm" ? "Confirm" : "Continue")}
                </Button>
            </DialogFooter>
        </DialogContent>
    </Dialog>;
}

function openLoanHubDialog(kind: DialogKind, message: string, initialValue = "", options: Options = {}): Promise<DialogResult> {
    if (typeof document === "undefined") return Promise.resolve(kind === "confirm" ? false : null);
    return new Promise((finish) => {
        const mount = document.createElement("div");
        mount.dataset.loanhubDialog = kind;
        document.body.appendChild(mount);
        const root = createRoot(mount);
        let settled = false;
        const resolve = (answer: DialogResult) => {
            if (settled) return;
            settled = true;
            finish(answer);
            // Unmount outside React's event dispatch to avoid nested render warnings.
            window.setTimeout(() => {
                root.unmount();
                mount.remove();
            }, 0);
        };
        root.render(<NativeDialogReplacement kind={kind} message={message} initialValue={initialValue} options={options} resolve={resolve}/>);
    });
}

/** LoanHub branded replacement for native browser alert. */
export async function showAppMessage(message: string, options?: Options): Promise<void> {
    await openLoanHubDialog("message", message, "", options);
}

/** LoanHub branded replacement for native browser confirm. */
export async function confirmAppDialog(message: string, options?: Options): Promise<boolean> {
    return (await openLoanHubDialog("confirm", message, "", options)) === true;
}

/** LoanHub branded replacement for native browser prompt; Cancel returns null. */
export async function promptAppDialog(message: string, initialValue = "", options?: Options): Promise<string | null> {
    const result = await openLoanHubDialog("prompt", message, initialValue, options);
    return typeof result === "string" ? result : null;
}
