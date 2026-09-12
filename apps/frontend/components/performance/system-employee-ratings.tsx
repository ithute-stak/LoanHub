"use client";

import { useCallback, useEffect, useState } from "react";
import { Activity, AlertTriangle, Gauge, Loader2, RefreshCw, ShieldCheck } from "lucide-react";

import { getSystemEmployeeRatings, type SystemEmployeeRatings } from "@/api/performance";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";


function confidenceClass(level: string) {
    if (level === "high") return "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
    if (level === "moderate") return "bg-blue-500/10 text-blue-700 dark:text-blue-300";
    if (level === "limited") return "bg-amber-500/10 text-amber-700 dark:text-amber-300";
    return "bg-muted text-muted-foreground";
}

export function SystemEmployeeRatingsPanel() {
    const [data, setData] = useState<SystemEmployeeRatings | null>(null);
    const [loading, setLoading] = useState(true);
    const [expanded, setExpanded] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            setData(await getSystemEmployeeRatings());
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Could not calculate system employee ratings."));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { void load(); }, [load]);

    if (loading) {
        return <section className="flex min-h-32 items-center justify-center rounded-3xl border bg-card"><Loader2 className="h-5 w-5 animate-spin text-primary" /></section>;
    }
    if (!data) return null;

    return (
        <section className="rounded-3xl border bg-card p-5 shadow-sm">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="flex items-start gap-3">
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary"><Gauge className="h-5 w-5" /></span>
                    <div>
                        <h2 className="font-black">System employee performance ratings</h2>
                        <p className="mt-1 max-w-4xl text-xs leading-5 text-muted-foreground">{data.methodology}</p>
                    </div>
                </div>
                <button type="button" onClick={() => void load()} className="inline-flex h-9 items-center justify-center gap-2 rounded-xl border px-3 text-xs font-black hover:bg-muted"><RefreshCw className="h-3.5 w-3.5" /> Recalculate</button>
            </div>

            {data.employees.length === 0 ? (
                <div className="mt-4 rounded-2xl border border-dashed p-7 text-center text-sm text-muted-foreground">No employee activity is available for automated rating yet.</div>
            ) : (
                <div className="mt-4 overflow-x-auto">
                    <table className="w-full min-w-[760px] text-left text-sm">
                        <thead className="text-xs uppercase tracking-wide text-muted-foreground">
                            <tr className="border-b">
                                <th className="px-3 py-2">Employee</th>
                                <th className="px-3 py-2">System score</th>
                                <th className="px-3 py-2">Rating</th>
                                <th className="px-3 py-2">Confidence</th>
                                <th className="px-3 py-2">Evidence</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.employees.map((employee) => (
                                <tr key={employee.staff_id} className="border-b last:border-0 align-top">
                                    <td className="px-3 py-3">
                                        <p className="font-black">{employee.employee_name}</p>
                                        <p className="mt-0.5 text-xs text-muted-foreground">{employee.job_title || employee.role}{employee.department ? ` · ${employee.department}` : ""}</p>
                                    </td>
                                    <td className="px-3 py-3"><span className="text-lg font-black">{employee.score.toFixed(1)}</span><span className="text-xs text-muted-foreground"> / 100</span></td>
                                    <td className="px-3 py-3 font-bold">{employee.rating}</td>
                                    <td className="px-3 py-3">
                                        <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-black ${confidenceClass(employee.evidence_level)}`}>
                                            {employee.evidence_level === "high" ? <ShieldCheck className="h-3.5 w-3.5" /> : employee.evidence_level === "insufficient" ? <AlertTriangle className="h-3.5 w-3.5" /> : <Activity className="h-3.5 w-3.5" />}
                                            {employee.confidence_percent.toFixed(0)}% {employee.evidence_level}
                                        </span>
                                    </td>
                                    <td className="px-3 py-3">
                                        <button type="button" onClick={() => setExpanded((current) => current === employee.staff_id ? null : employee.staff_id)} className="text-xs font-black text-primary hover:underline">{expanded === employee.staff_id ? "Hide evidence" : `View ${employee.components.length} metric${employee.components.length === 1 ? "" : "s"}`}</button>
                                        {expanded === employee.staff_id && (
                                            <div className="mt-2 max-w-md space-y-2">
                                                {employee.components.length === 0 ? <p className="text-xs text-muted-foreground">Not enough system evidence to rate this employee.</p> : employee.components.map((component) => (
                                                    <div key={component.key} className="rounded-xl bg-muted/40 p-2.5 text-xs">
                                                        <div className="flex justify-between gap-3"><strong>{component.label}</strong><span>{component.score.toFixed(1)} · {(component.weight * 100).toFixed(0)}% model weight</span></div>
                                                        <p className="mt-1 text-muted-foreground">{component.evidence}</p>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </section>
    );
}
