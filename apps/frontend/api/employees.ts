import { api } from "@/lib/api";
import type {
    Employee,
    EmployeeProfilePayload,
    PerformanceGoal,
    PerformanceGoalPayload,
    PerformanceReviewPayload,
} from "@/types/employee";

export async function listEmployees(params?: {
    search?: string;
    branch_id?: string;
    department?: string;
    active_only?: boolean;
}): Promise<Employee[]> {
    const response = await api.get<Employee[]>("/employees", {
        params,
    });
    return response.data;
}

export async function updateEmployeeProfile(
    staffId: string,
    payload: EmployeeProfilePayload,
): Promise<Employee> {
    const response = await api.put<Employee>(
        `/employees/${staffId}/profile`,
        payload,
    );
    return response.data;
}

export async function listEmployeeGoals(
    staffId: string,
): Promise<PerformanceGoal[]> {
    const response = await api.get<PerformanceGoal[]>(
        `/employees/${staffId}/goals`,
    );
    return response.data;
}

export async function createEmployeeGoal(
    staffId: string,
    payload: PerformanceGoalPayload,
): Promise<PerformanceGoal> {
    const response = await api.post<PerformanceGoal>(
        `/employees/${staffId}/goals`,
        payload,
    );
    return response.data;
}

export async function createEmployeeReview(
    staffId: string,
    payload: PerformanceReviewPayload,
): Promise<void> {
    await api.post(
        `/employees/${staffId}/reviews`,
        payload,
    );
}
