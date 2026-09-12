import {
    ArrowLeft,
    ArrowRight,
    Loader2,
    Send,
} from "lucide-react";

type Props = {
    isFirstStep: boolean;
    isLastStep: boolean;
    submitting: boolean;
    onBack: () => void;
};

export function RegistrationActions({
    isFirstStep,
    isLastStep,
    submitting,
    onBack,
}: Props) {
    return (
        <div className="mt-8 flex flex-col-reverse gap-3 border-t pt-6 sm:flex-row sm:items-center sm:justify-between">
            <button
                type="button"
                onClick={onBack}
                disabled={
                    isFirstStep ||
                    submitting
                }
                className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border bg-background px-5 text-sm font-black transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"
            >
                <ArrowLeft className="h-4 w-4" />
                Previous
            </button>

            <button
                type="submit"
                disabled={submitting}
                className="inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-primary px-6 text-sm font-black text-primary-foreground shadow-sm transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
                {submitting ? (
                    <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Submitting application...
                    </>
                ) : isLastStep ? (
                    <>
                        <Send className="h-4 w-4" />
                        Submit application
                    </>
                ) : (
                    <>
                        Continue
                        <ArrowRight className="h-4 w-4" />
                    </>
                )}
            </button>
        </div>
    );
}
