"use client";

import { Download, Loader2, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ManagedFile } from "@/types/files";
import { downloadManagedFile } from "@/api/files";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

export function SecureAudioPlayer({ file, mine }: { file: ManagedFile; mine: boolean }) {
    const [url, setUrl] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);
    async function load() {
        if (url || loading) return;
        setLoading(true);
        try {
            const response = await api.get<Blob>(`/files/${file.id}/download`, { responseType: "blob" });
            setUrl(URL.createObjectURL(response.data));
        } catch (error) { toast.error(getErrorMessage(error, "Voice note could not be loaded")); }
        finally { setLoading(false); }
    }
    if (!url) return <div className={`mt-2 flex items-center gap-2 rounded-xl border p-2 ${mine ? "border-white/25 bg-white/10" : "bg-muted/40"}`}><button type="button" onClick={() => void load()} className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-primary-foreground">{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4 fill-current" />}</button><div className="min-w-0 flex-1"><p className="text-xs font-black">Voice note</p><p className="text-[10px] opacity-70">{(file.size_bytes / 1024).toFixed(1)} KB · encrypted storage</p></div><button type="button" onClick={() => void downloadManagedFile(file)} className="p-2"><Download className="h-4 w-4" /></button></div>;
    return <div className={`mt-2 rounded-xl border p-2 ${mine ? "border-white/25 bg-white/10" : "bg-muted/40"}`}><audio controls preload="metadata" src={url} className="h-10 w-full" /><button type="button" onClick={() => void downloadManagedFile(file)} className="mt-1 inline-flex items-center gap-1 text-[10px] font-black"><Download className="h-3 w-3" />Download</button></div>;
}
