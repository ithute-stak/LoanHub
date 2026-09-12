"use client";

import {
    AtSign,
    Globe,
    Link2,
    Loader2,
    Mail,
    MessageCircle,
    Save,
    Send,
    Share2,
    ShieldCheck,
    Video,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
    getCompanySocialShareSettings,
    updateCompanySocialShareSettings,
    type CompanySocialShareSettingsPayload,
} from "@/api/social-sharing";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { CompanySocialShareSettings } from "@/types/files";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

const CHANNELS = [
    { value: "native", label: "Device share", description: "Use the phone or computer share sheet.", icon: Share2 },
    { value: "copy", label: "Copy link", description: "Copy the secure link to the clipboard.", icon: Link2 },
    { value: "whatsapp", label: "WhatsApp", description: "Open the WhatsApp share composer.", icon: MessageCircle },
    { value: "facebook", label: "Facebook", description: "Open the Facebook share dialog.", icon: Globe },
    { value: "linkedin", label: "LinkedIn", description: "Share through LinkedIn.", icon: Globe },
    { value: "x", label: "X", description: "Open an X post composer.", icon: AtSign },
    { value: "telegram", label: "Telegram", description: "Open the Telegram share composer.", icon: Send },
    { value: "email", label: "Email", description: "Create an email containing the secure link.", icon: Mail },
] as const;

const EMPTY: CompanySocialShareSettingsPayload = {
    external_sharing_enabled: false,
    default_expiry_hours: 24,
    default_message: "A secure LoanHub document has been shared with you.",
    enabled_channels: ["native", "copy", "whatsapp", "email"],
    whatsapp_number: null,
    facebook_url: null,
    instagram_url: null,
    linkedin_url: null,
    x_handle: null,
    telegram_username: null,
    youtube_url: null,
};

function toPayload(value: CompanySocialShareSettings): CompanySocialShareSettingsPayload {
    return {
        external_sharing_enabled: value.external_sharing_enabled,
        default_expiry_hours: value.default_expiry_hours,
        default_message: value.default_message,
        enabled_channels: value.enabled_channels,
        whatsapp_number: value.whatsapp_number,
        facebook_url: value.facebook_url,
        instagram_url: value.instagram_url,
        linkedin_url: value.linkedin_url,
        x_handle: value.x_handle,
        telegram_username: value.telegram_username,
        youtube_url: value.youtube_url,
    };
}

export function CompanySocialSharingSettings({
    companyId,
    canManage,
}: {
    companyId: string;
    canManage: boolean;
}) {
    const [form, setForm] = useState<CompanySocialShareSettingsPayload>(EMPTY);
    const [initial, setInitial] = useState<CompanySocialShareSettingsPayload>(EMPTY);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        setLoading(true);
        void getCompanySocialShareSettings(companyId)
            .then((value) => {
                const payload = toPayload(value);
                setForm(payload);
                setInitial(payload);
            })
            .catch((error: unknown) => {
                toast.error(getErrorMessage(error, "Social sharing settings could not be loaded."));
            })
            .finally(() => setLoading(false));
    }, [companyId]);

    const dirty = useMemo(
        () => JSON.stringify(form) !== JSON.stringify(initial),
        [form, initial],
    );

    function update<K extends keyof CompanySocialShareSettingsPayload>(
        field: K,
        value: CompanySocialShareSettingsPayload[K],
    ) {
        setForm((current) => ({ ...current, [field]: value }));
    }

    function toggleChannel(channel: string) {
        update(
            "enabled_channels",
            form.enabled_channels.includes(channel)
                ? form.enabled_channels.filter((item) => item !== channel)
                : [...form.enabled_channels, channel],
        );
    }

    async function save() {
        if (!canManage || saving) return;
        setSaving(true);
        try {
            const result = await updateCompanySocialShareSettings(companyId, form);
            const payload = toPayload(result);
            setForm(payload);
            setInitial(payload);
            toast.success("Social sharing settings updated.");
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Social sharing settings could not be saved."));
        } finally {
            setSaving(false);
        }
    }

    if (loading) {
        return (
            <section className="flex min-h-80 items-center justify-center rounded-3xl border bg-card">
                <Loader2 className="h-7 w-7 animate-spin text-primary" />
            </section>
        );
    }

    return (
        <section className="overflow-hidden rounded-3xl border bg-card shadow-sm">
            <div className="border-b bg-gradient-to-r from-primary/10 via-background to-violet-500/10 p-5 sm:p-7">
                <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                        <div className="flex items-center gap-2 text-primary">
                            <Share2 className="h-5 w-5" />
                            <span className="text-xs font-black uppercase tracking-[0.16em]">Controlled external sharing</span>
                        </div>
                        <h2 className="mt-2 text-2xl font-black">Social media and share-link settings</h2>
                        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                            Choose which social channels staff may use when sharing expiring public document links. LoanHub never stores social-media passwords in this form.
                        </p>
                    </div>
                    <div className="flex items-center gap-3 rounded-2xl border bg-background/80 p-4 shadow-sm">
                        <div>
                            <p className="text-sm font-black">External document sharing</p>
                            <p className="mt-1 text-xs text-muted-foreground">{form.external_sharing_enabled ? "Enabled for non-confidential files" : "Disabled for all company files"}</p>
                        </div>
                        <Switch
                            checked={form.external_sharing_enabled}
                            onCheckedChange={(checked) => update("external_sharing_enabled", checked)}
                            disabled={!canManage}
                        />
                    </div>
                </div>
            </div>

            <div className="space-y-8 p-5 sm:p-7">
                <section>
                    <div className="flex items-start gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary"><Share2 className="h-5 w-5" /></div>
                        <div>
                            <h3 className="text-lg font-black">Allowed share channels</h3>
                            <p className="mt-1 text-sm text-muted-foreground">These buttons appear after a staff member generates a secure external link.</p>
                        </div>
                    </div>
                    <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        {CHANNELS.map((channel) => {
                            const Icon = channel.icon;
                            const checked = form.enabled_channels.includes(channel.value);
                            return (
                                <label key={channel.value} className={`flex cursor-pointer items-start gap-3 rounded-2xl border p-4 transition ${checked ? "border-primary bg-primary/5" : "hover:border-primary/30"}`}>
                                    <Checkbox
                                        checked={checked}
                                        onCheckedChange={() => toggleChannel(channel.value)}
                                        disabled={!canManage}
                                        className="mt-1"
                                    />
                                    <div className="min-w-0">
                                        <div className="flex items-center gap-2"><Icon className="h-4 w-4 text-primary" /><p className="font-black">{channel.label}</p></div>
                                        <p className="mt-1 text-xs leading-5 text-muted-foreground">{channel.description}</p>
                                    </div>
                                </label>
                            );
                        })}
                    </div>
                </section>

                <section className="border-t pt-8">
                    <div className="grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
                        <div>
                            <h3 className="text-lg font-black">Default share policy</h3>
                            <p className="mt-2 text-sm leading-6 text-muted-foreground">Set a safe expiry and a standard message. Staff can shorten the expiry when generating a link.</p>
                        </div>
                        <div className="grid gap-4 sm:grid-cols-2">
                            <div>
                                <label className="text-xs font-black uppercase tracking-wide text-muted-foreground">Default link expiry</label>
                                <NativeSelect
                                    value={String(form.default_expiry_hours)}
                                    onChange={(event) => update("default_expiry_hours", Number(event.target.value))}
                                    disabled={!canManage}
                                    className="mt-2 h-11 w-full rounded-xl border bg-background px-3 text-sm font-bold"
                                >
                                    <option value="1">1 hour</option>
                                    <option value="6">6 hours</option>
                                    <option value="24">24 hours</option>
                                    <option value="72">3 days</option>
                                    <option value="168">7 days</option>
                                </NativeSelect>
                            </div>
                            <div className="sm:col-span-2">
                                <label className="text-xs font-black uppercase tracking-wide text-muted-foreground">Default message</label>
                                <Textarea
                                    value={form.default_message ?? ""}
                                    onChange={(event) => update("default_message", event.target.value || null)}
                                    rows={3}
                                    disabled={!canManage}
                                    className="mt-2"
                                    placeholder="A secure LoanHub document has been shared with you."
                                />
                            </div>
                        </div>
                    </div>
                </section>

                <section className="border-t pt-8">
                    <div>
                        <h3 className="text-lg font-black">Company social profiles</h3>
                        <p className="mt-1 text-sm text-muted-foreground">Store the official public profiles used by the business. These are not login credentials or API secrets.</p>
                    </div>
                    <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                        <SocialField icon={MessageCircle} label="WhatsApp business number" value={form.whatsapp_number ?? ""} onChange={(value) => update("whatsapp_number", value || null)} placeholder="+266 5800 0000" disabled={!canManage} />
                        <SocialField icon={Globe} label="Facebook page URL" value={form.facebook_url ?? ""} onChange={(value) => update("facebook_url", value || null)} placeholder="https://facebook.com/..." disabled={!canManage} />
                        <SocialField icon={Globe} label="Instagram page URL" value={form.instagram_url ?? ""} onChange={(value) => update("instagram_url", value || null)} placeholder="https://instagram.com/..." disabled={!canManage} />
                        <SocialField icon={Globe} label="LinkedIn page URL" value={form.linkedin_url ?? ""} onChange={(value) => update("linkedin_url", value || null)} placeholder="https://linkedin.com/company/..." disabled={!canManage} />
                        <SocialField icon={AtSign} label="X handle" value={form.x_handle ?? ""} onChange={(value) => update("x_handle", value || null)} placeholder="@company" disabled={!canManage} />
                        <SocialField icon={Send} label="Telegram username" value={form.telegram_username ?? ""} onChange={(value) => update("telegram_username", value || null)} placeholder="company_support" disabled={!canManage} />
                        <SocialField icon={Video} label="YouTube channel URL" value={form.youtube_url ?? ""} onChange={(value) => update("youtube_url", value || null)} placeholder="https://youtube.com/@..." disabled={!canManage} />
                    </div>
                </section>

                <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
                    <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
                    Confidential files are blocked from external sharing even when this setting is enabled. Public links expire automatically, can be revoked, and expose only the selected file.
                </div>
            </div>

            {canManage && (
                <div className="flex flex-col-reverse gap-3 border-t bg-muted/20 p-5 sm:flex-row sm:justify-end sm:p-6">
                    <Button type="button" variant="outline" disabled={!dirty || saving} onClick={() => setForm(initial)}>Discard changes</Button>
                    <Button type="button" disabled={!dirty || saving} onClick={() => void save()}>
                        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                        Save social sharing
                    </Button>
                </div>
            )}
        </section>
    );
}

function SocialField({
    icon: Icon,
    label,
    value,
    onChange,
    placeholder,
    disabled,
}: {
    icon: typeof Share2;
    label: string;
    value: string;
    onChange: (value: string) => void;
    placeholder: string;
    disabled: boolean;
}) {
    return (
        <label className="rounded-2xl border bg-muted/15 p-4">
            <span className="flex items-center gap-2 text-sm font-black"><Icon className="h-4 w-4 text-primary" />{label}</span>
            <Input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} disabled={disabled} className="mt-3 h-11 bg-background" />
        </label>
    );
}
