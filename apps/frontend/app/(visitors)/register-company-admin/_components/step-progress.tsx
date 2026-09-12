import {
    Check,
} from "lucide-react";

import {
    REGISTRATION_STEPS,
} from "../_lib/registration-constants";

type Props = {
    currentStepIndex: number;
    progress: number;
    onStepClick: (index: number) => void;
};

export function StepProgress({
    currentStepIndex,
    progress,
    onStepClick,
}: Props) {
    return (
        <div className="border-b bg-muted/20 px-5 py-5 sm:px-8">
            <div className="mb-4 flex items-center justify-between">
                <div>
                    <p className="text-xs font-black uppercase tracking-[0.18em] text-primary">
                        Company registration
                    </p>

                    <p className="mt-1 text-sm text-muted-foreground">
                        Step {currentStepIndex + 1} of{" "}
                        {REGISTRATION_STEPS.length}
                    </p>
                </div>

                <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-black text-primary">
                    {Math.round(progress)}%
                </span>
            </div>

            <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div
                    className="h-full rounded-full bg-primary transition-all duration-300"
                    style={{
                        width: `${progress}%`,
                    }}
                />
            </div>

            <div className="mt-5 grid grid-cols-4 gap-2">
                {REGISTRATION_STEPS.map(
                    (step, index) => {
                        const completed =
                            index <
                            currentStepIndex;

                        const active =
                            index ===
                            currentStepIndex;

                        return (
                            <button
                                key={step.id}
                                type="button"
                                onClick={() =>
                                    onStepClick(index)
                                }
                                disabled={
                                    index >
                                    currentStepIndex
                                }
                                className="group text-left disabled:cursor-default"
                            >
                                <div className="flex items-center gap-2">
                                    <span
                                        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-xs font-black transition ${
                                            completed
                                                ? "border-primary bg-primary text-primary-foreground"
                                                : active
                                                  ? "border-primary bg-primary/10 text-primary"
                                                  : "border-border bg-background text-muted-foreground"
                                        }`}
                                    >
                                        {completed ? (
                                            <Check className="h-4 w-4" />
                                        ) : (
                                            index + 1
                                        )}
                                    </span>

                                    <span
                                        className={`hidden text-xs font-bold md:block ${
                                            active ||
                                            completed
                                                ? "text-foreground"
                                                : "text-muted-foreground"
                                        }`}
                                    >
                                        {
                                            step.shortTitle
                                        }
                                    </span>
                                </div>
                            </button>
                        );
                    },
                )}
            </div>
        </div>
    );
}
