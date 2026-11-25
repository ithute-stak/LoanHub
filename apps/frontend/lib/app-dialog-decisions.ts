/** Safety-critical, DOM-independent rules shared by LoanHub confirmation dialogs. */
export type AppDialogKind = "message" | "confirm" | "prompt";
export type AppDialogResult = string | boolean | null;
export type AppDialogOptions = {
    title?: string;
    confirmLabel?: string;
    destructive?: boolean;
    minLength?: number;
};

/** Dismissal never means approval, including Escape and outside clicks. */
export function cancelledDialogResult(kind: AppDialogKind): AppDialogResult {
    return kind === "confirm" ? false : null;
}

/** The submit button must not be enabled while required evidence is too short. */
export function canSubmitDialog(kind: AppDialogKind, input: string, options: AppDialogOptions): boolean {
    return kind !== "prompt" || input.trim().length >= (options.minLength ?? 0);
}

/** Return an affirmative result only after an explicit, valid submit action. */
export function submittedDialogResult(kind: AppDialogKind, input: string, options: AppDialogOptions): AppDialogResult {
    if (!canSubmitDialog(kind, input, options)) return cancelledDialogResult(kind);
    if (kind === "confirm") return true;
    if (kind === "prompt") return input;
    return null;
}
