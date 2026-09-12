"use client";

import {
    type FormEvent,
    useCallback,
    useEffect,
    useMemo,
    useState,
} from "react";
import { toast } from "@/utils/toast";

import {
    registerCompanyOwner,
} from "@/api/companyRegistration";
import {
    getErrorMessage,
} from "@/utils/apiError";

import {
    COMPANY_REGISTRATION_DRAFT_KEY,
    INITIAL_COMPANY_REGISTRATION_FORM,
    REGISTRATION_STEPS,
} from "../_lib/registration-constants";
import {
    hasValidationErrors,
    validateRegistrationStep,
} from "../_lib/registration-validation";
import type {
    CompanyRegistrationErrors,
    CompanyRegistrationField,
    CompanyRegistrationForm,
    CompanyRegistrationPayload,
} from "../_types/company-registration";

function buildPayload(
    form: CompanyRegistrationForm,
): CompanyRegistrationPayload {
    return {
        company_name:
            form.company_name.trim(),

        registration_number:
            form.registration_number.trim() ||
            null,

        license_number:
            form.license_number.trim() ||
            null,

        company_phone:
            form.company_phone.trim(),

        company_email:
            form.company_email.trim() ||
            null,

        website:
            form.website.trim() ||
            null,

        address:
            form.address.trim(),

        district:
            form.district.trim(),

        owner_email:
            form.owner_email.trim() ||
            null,

        owner_phone:
            form.owner_phone.trim(),

        password:
            form.password,

        first_name:
            form.first_name.trim(),

        middle_name:
            form.middle_name.trim() ||
            null,

        last_name:
            form.last_name.trim(),

        national_id:
            form.national_id.trim() ||
            null,

        nationality:
            "Mosotho",

        town_or_village:
            form.town_or_village.trim(),

        physical_address:
            form.physical_address.trim(),
    };
}

export function useCompanyRegistration() {
    const [form, setForm] =
        useState<CompanyRegistrationForm>(
            INITIAL_COMPANY_REGISTRATION_FORM,
        );

    const [currentStepIndex, setCurrentStepIndex] =
        useState(0);

    const [errors, setErrors] =
        useState<CompanyRegistrationErrors>({});

    const [submitting, setSubmitting] =
        useState(false);

    const [complete, setComplete] =
        useState(false);

    const [draftRestored, setDraftRestored] =
        useState(false);

    const currentStep =
        REGISTRATION_STEPS[currentStepIndex] ??
        REGISTRATION_STEPS[0]!;

    const isFirstStep =
        currentStepIndex === 0;

    const isLastStep =
        currentStepIndex ===
        REGISTRATION_STEPS.length - 1;

    const progress =
        ((currentStepIndex + 1) /
            REGISTRATION_STEPS.length) *
        100;

    useEffect(() => {
        const timer = window.setTimeout(() => {
            try {
                const saved =
                    window.localStorage.getItem(
                        COMPANY_REGISTRATION_DRAFT_KEY,
                    );

                if (saved) {
                    const parsed =
                        JSON.parse(saved) as Partial<CompanyRegistrationForm>;

                    setForm((current) => ({
                        ...current,
                        ...parsed,

                        // Never restore credentials or legal confirmation.
                        password: "",
                        confirm_password: "",
                        accept_terms: false,
                    }));

                    setDraftRestored(true);
                }
            } catch {
                window.localStorage.removeItem(
                    COMPANY_REGISTRATION_DRAFT_KEY,
                );
            }
        }, 0);

        return () => window.clearTimeout(timer);
    }, []);

    useEffect(() => {
        const timeout = window.setTimeout(() => {
            const {
                password: _password,
                confirm_password:
                    _confirmPassword,
                accept_terms:
                    _acceptTerms,
                ...safeDraft
            } = form;

            window.localStorage.setItem(
                COMPANY_REGISTRATION_DRAFT_KEY,
                JSON.stringify(safeDraft),
            );
        }, 400);

        return () =>
            window.clearTimeout(timeout);
    }, [form]);

    const updateField = useCallback(
        <K extends CompanyRegistrationField>(
            field: K,
            value: CompanyRegistrationForm[K],
        ) => {
            setForm((current) => ({
                ...current,
                [field]: value,
            }));

            setErrors((current) => {
                if (!current[field]) {
                    return current;
                }

                const next = {
                    ...current,
                };

                delete next[field];

                return next;
            });
        },
        [],
    );

    const validateCurrentStep =
        useCallback(() => {
            const nextErrors =
                validateRegistrationStep(
                    currentStep.id,
                    form,
                );

            setErrors(nextErrors);

            return !hasValidationErrors(
                nextErrors,
            );
        }, [
            currentStep.id,
            form,
        ]);

    const goNext = useCallback(() => {
        if (!validateCurrentStep()) {
            toast.error(
                "Please correct the highlighted fields.",
            );

            return;
        }

        setCurrentStepIndex((current) =>
            Math.min(
                current + 1,
                REGISTRATION_STEPS.length - 1,
            ),
        );

        window.scrollTo({
            top: 0,
            behavior: "smooth",
        });
    }, [validateCurrentStep]);

    const goBack = useCallback(() => {
        setErrors({});

        setCurrentStepIndex((current) =>
            Math.max(0, current - 1),
        );

        window.scrollTo({
            top: 0,
            behavior: "smooth",
        });
    }, []);

    const goToStep = useCallback(
        (index: number) => {
            if (index >= currentStepIndex) {
                return;
            }

            setErrors({});
            setCurrentStepIndex(index);
        },
        [currentStepIndex],
    );

    const clearDraft = useCallback(() => {
        window.localStorage.removeItem(
            COMPANY_REGISTRATION_DRAFT_KEY,
        );

        setForm(
            INITIAL_COMPANY_REGISTRATION_FORM,
        );

        setCurrentStepIndex(0);
        setErrors({});
        setDraftRestored(false);

        toast.success(
            "Saved registration draft cleared.",
        );
    }, []);

    const submit = useCallback(
        async (
            event: FormEvent<HTMLFormElement>,
        ) => {
            event.preventDefault();

            if (!isLastStep) {
                goNext();
                return;
            }

            if (!validateCurrentStep()) {
                toast.error(
                    "Please accept the declaration before submitting.",
                );

                return;
            }

            setSubmitting(true);

            try {
                await registerCompanyOwner(
                    buildPayload(form),
                );

                window.localStorage.removeItem(
                    COMPANY_REGISTRATION_DRAFT_KEY,
                );

                setComplete(true);

                toast.success(
                    "Company application submitted.",
                );
            } catch (error: unknown) {
                const message =
                    getErrorMessage(
                        error,
                        "Could not register the company.",
                    );

                setErrors({
                    form: message,
                });

                toast.error(message);
            } finally {
                setSubmitting(false);
            }
        },
        [
            form,
            goNext,
            isLastStep,
            validateCurrentStep,
        ],
    );

    const ownerFullName = useMemo(() => {
        return [
            form.first_name,
            form.middle_name,
            form.last_name,
        ]
            .filter(Boolean)
            .join(" ")
            .trim();
    }, [
        form.first_name,
        form.middle_name,
        form.last_name,
    ]);

    return {
        form,
        errors,

        currentStep,
        currentStepIndex,
        progress,

        isFirstStep,
        isLastStep,

        submitting,
        complete,
        draftRestored,

        ownerFullName,

        updateField,
        goBack,
        goNext,
        goToStep,
        clearDraft,
        submit,
    };
}

export type CompanyRegistrationModel =
    ReturnType<
        typeof useCompanyRegistration
    >;
