"use client";

import {
    type FormEvent,
    useCallback,
    useEffect,
    useMemo,
    useState,
} from "react";
import { toast } from "@/utils/toast";
import { api } from "@/lib/api";

import { useAppData } from "@/provider/appDataProvider";
import { useTenant } from "@/provider/tenantProvider";
import { useAppDispatch } from "@/store/hooks";
import { updateCompany } from "@/store/slices/companiesSlice";
import {
    COMPANY_MANAGEMENT_ROLES,
    hasRole,
} from "@/types/auth";
import { getErrorMessage } from "@/utils/apiError";

import {
    calculateCompletion,
    EMPTY_COMPANY_FORM,
    normalizeCompanyForm,
    validateCompanyForm,
} from "../_lib/company-settings";
import type {
    CompanySettingsErrors,
    CompanySettingsField,
    CompanySettingsForm,
} from "../_types/company-settings";

type CompanyBranding = {
    company_id: string;
    left_logo_file?: { id: string; original_name: string } | null;
    right_logo_file?: { id: string; original_name: string } | null;
    left_logo_download_url?: string | null;
    right_logo_download_url?: string | null;
};

function toForm(company: {
    name?: string | null;
    registration_number?: string | null;
    license_number?: string | null;
    phone?: string | null;
    email?: string | null;
    website?: string | null;
    address?: string | null;
    district?: string | null;
    mpesa_shortcode?: string | null;
}): CompanySettingsForm {
    return {
        name: company.name ?? "",
        registration_number: company.registration_number ?? "",
        license_number: company.license_number ?? "",
        phone: company.phone ?? "",
        email: company.email ?? "",
        website: company.website ?? "",
        address: company.address ?? "",
        district: company.district ?? "",
        mpesa_shortcode: company.mpesa_shortcode ?? "",
    };
}

export function useCompanySettings() {
    const dispatch = useAppDispatch();

    const {
        currentCompany,
        refreshAllData,
        isCompaniesLoading,
        errors: appDataErrors,
    } = useAppData();

    const { activeRole } = useTenant();

    const [form, setForm] =
        useState<CompanySettingsForm>(EMPTY_COMPANY_FORM);

    const [initialForm, setInitialForm] =
        useState<CompanySettingsForm>(EMPTY_COMPANY_FORM);

    const [errors, setErrors] =
        useState<CompanySettingsErrors>({});

    const [submitting, setSubmitting] = useState(false);
    const [branding, setBranding] = useState<CompanyBranding | null>(null);
    const [uploadingLogo, setUploadingLogo] = useState<"left" | "right" | null>(null);

    const canManage = hasRole(
        activeRole,
        COMPANY_MANAGEMENT_ROLES,
    );

    useEffect(() => {
        if (!currentCompany) return;

        const timer = window.setTimeout(() => {
            const next = toForm(currentCompany);
            setForm(next);
            setInitialForm(next);
            setErrors({});
        }, 0);

        return () => window.clearTimeout(timer);
    }, [currentCompany]);

    const isDirty = useMemo(
        () =>
            JSON.stringify(normalizeCompanyForm(form)) !==
            JSON.stringify(normalizeCompanyForm(initialForm)),
        [form, initialForm],
    );

    const profileCompletion = useMemo(
        () => calculateCompletion(form),
        [form],
    );

    useEffect(() => {
        if (!isDirty) return;

        const handleBeforeUnload = (event: BeforeUnloadEvent) => {
            event.preventDefault();
            event.returnValue = "";
        };

        window.addEventListener("beforeunload", handleBeforeUnload);

        return () =>
            window.removeEventListener(
                "beforeunload",
                handleBeforeUnload,
            );
    }, [isDirty]);

    const updateField = useCallback(
        <K extends CompanySettingsField>(
            field: K,
            value: CompanySettingsForm[K],
        ) => {
            setForm((current) => ({
                ...current,
                [field]: value,
            }));

            setErrors((current) => {
                if (!current[field]) return current;

                const next = { ...current };
                delete next[field];

                return next;
            });
        },
        [],
    );

    const reset = useCallback(() => {
        setForm(initialForm);
        setErrors({});
        toast.success("Unsaved changes were discarded.");
    }, [initialForm]);

    const loadBranding = useCallback(async () => {
        if (!currentCompany) return;
        try {
            const response = await api.get<CompanyBranding>(`/companies/${currentCompany.id}/branding`);
            setBranding(response.data);
        } catch {
            setBranding(null);
        }
    }, [currentCompany]);

    useEffect(() => {
        void loadBranding();
    }, [loadBranding]);

    const uploadLogo = useCallback(
        async (position: "left" | "right", file: File | null) => {
            if (!currentCompany || !canManage || !file) return;
            const formData = new FormData();
            formData.append("file", file);
            setUploadingLogo(position);
            try {
                const response = position === "left"
                    ? await api.post<CompanyBranding>(`/companies/${currentCompany.id}/branding/logo-left`, formData)
                    : await api.post<CompanyBranding>(`/companies/${currentCompany.id}/branding/logo-right`, formData);
                setBranding(response.data);
                toast.success(position === "left" ? "Left document logo uploaded." : "Right document logo uploaded.");
            } catch (error: unknown) {
                toast.error(getErrorMessage(error, "Logo upload failed."));
            } finally {
                setUploadingLogo(null);
            }
        },
        [canManage, currentCompany],
    );

    const save = useCallback(
        async (event: FormEvent<HTMLFormElement>) => {
            event.preventDefault();

            if (!currentCompany || !canManage || submitting) {
                return;
            }

            const validationErrors = validateCompanyForm(form);
            setErrors(validationErrors);

            if (Object.keys(validationErrors).length > 0) {
                toast.error("Please correct the highlighted fields.");
                return;
            }

            const payload = normalizeCompanyForm(form);

            setSubmitting(true);

            try {
                await dispatch(
                    updateCompany({
                        id: currentCompany.id,
                        payload,
                    }),
                ).unwrap();

                setForm(payload);
                setInitialForm(payload);
                setErrors({});

                toast.success("Company profile updated successfully.");

                await refreshAllData();
                await loadBranding();
            } catch (error: unknown) {
                const message = getErrorMessage(
                    error,
                    "Could not update company profile.",
                );

                setErrors({ form: message });
                toast.error(message);
            } finally {
                setSubmitting(false);
            }
        },
        [
            canManage,
            currentCompany,
            dispatch,
            form,
            refreshAllData,
            submitting,
            loadBranding,
        ],
    );

    return {
        currentCompany,
        form,
        errors,

        canManage,
        submitting,
        isDirty,
        profileCompletion,

        isLoading: isCompaniesLoading && !currentCompany,

        pageError:
            errors.form ??
            appDataErrors?.companies ??
            null,

        updateField,
        reset,
        save,
        refreshAllData,
        branding,
        uploadingLogo,
        uploadLogo,
    };
}

export type CompanySettingsModel =
    ReturnType<typeof useCompanySettings>;
