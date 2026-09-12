import { api } from "@/lib/api";
import type {
    PerformanceOverview,
} from "@/types/performance";

export type SystemPerformanceComponent = {
    key: string;
    label: string;
    score: number;
    weight: number;
    evidence: string;
};

export type SystemEmployeeRating = {
    staff_id: string;
    employee_id: string | null;
    employee_name: string;
    role: string;
    job_title: string | null;
    department: string | null;
    score: number;
    rating: string;
    confidence_percent: number;
    evidence_level: "high" | "moderate" | "limited" | "insufficient" | string;
    components: SystemPerformanceComponent[];
};

export type SystemEmployeeRatings = {
    methodology: string;
    employees: SystemEmployeeRating[];
};

export async function getPerformanceOverview(): Promise<PerformanceOverview> {
    const response = await api.get<PerformanceOverview>(
        "/performance/overview",
    );
    return response.data;
}

export async function getSystemEmployeeRatings(): Promise<SystemEmployeeRatings> {
    const response = await api.get<SystemEmployeeRatings>("/performance/system-ratings");
    return response.data;
}