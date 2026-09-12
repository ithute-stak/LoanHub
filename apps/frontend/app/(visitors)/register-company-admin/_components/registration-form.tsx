"use client";

import {
    AlertCircle,
    Trash2,
} from "lucide-react";

import type {
    CompanyRegistrationModel,
} from "../_hooks/use-company-registration";
import {
    CompanyIdentityStep,
} from "./company-identity-step";
import {
    CompanyOperationsStep,
} from "./company-operations-step";
import {
    CompanyOwnerStep,
} from "./company-owner-step";
import {
    RegistrationActions,
} from "./registration-actions";
import {
    RegistrationReviewStep,
} from "./registration-review-step";
import {
    StepProgress,
} from "./step-progress";

type Props = CompanyRegistrationModel;

export function RegistrationForm({
    form,
    errors,

    currentStep,
    currentStepIndex,
    progress,

    isFirstStep,
    isLastStep,

    submitting,
    draftRestored,

    ownerFullName,

    updateField,
    goBack,
    goToStep,
    clearDraft,
    submit,
}: Props) {
    return (
        <section className="bg-card">
            <StepProgress
                currentStepIndex={
                    currentStepIndex
                }
                progress={progress}
                onStepClick={goToStep}
            />

            <form
                onSubmit={submit}
                noValidate
                className="p-5 sm:p-8 lg:p-10"
            >
                {draftRestored && (
                    <div className="mb-6 flex flex-col gap-3 rounded-2xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800 dark:border-blue-900 dark:bg-blue-950/30 dark:text-blue-300 sm:flex-row sm:items-center sm:justify-between">
                        <p>
                            A saved registration draft
                            was restored on this device.
                            Passwords are never saved.
                        </p>

                        <button
                            type="button"
                            onClick={clearDraft}
                            className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-lg border border-blue-300 bg-background px-3 text-xs font-black"
                        >
                            <Trash2 className="h-3.5 w-3.5" />
                            Clear draft
                        </button>
                    </div>
                )}

                {errors.form && (
                    <div className="mb-6 flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
                        <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />

                        <div>
                            <p className="font-black">
                                Application could not be
                                submitted
                            </p>

                            <p className="mt-1">
                                {errors.form}
                            </p>
                        </div>
                    </div>
                )}

                {currentStep.id ===
                    "company" && (
                    <CompanyIdentityStep
                        form={form}
                        errors={errors}
                        updateField={
                            updateField
                        }
                    />
                )}

                {currentStep.id ===
                    "operations" && (
                    <CompanyOperationsStep
                        form={form}
                        errors={errors}
                        updateField={
                            updateField
                        }
                    />
                )}

                {currentStep.id ===
                    "owner" && (
                    <CompanyOwnerStep
                        form={form}
                        errors={errors}
                        updateField={
                            updateField
                        }
                    />
                )}

                {currentStep.id ===
                    "review" && (
                    <RegistrationReviewStep
                        form={form}
                        errors={errors}
                        ownerFullName={
                            ownerFullName
                        }
                        updateField={
                            updateField
                        }
                    />
                )}

                <RegistrationActions
                    isFirstStep={
                        isFirstStep
                    }
                    isLastStep={isLastStep}
                    submitting={submitting}
                    onBack={goBack}
                />
            </form>
        </section>
    );
}
