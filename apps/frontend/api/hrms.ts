import { api } from "@/lib/api";
import type {
    HRAsset,
    HRAssetPayload,
    HRAttendanceEvent,
    HRCandidate,
    HRDashboardSummary,
    HRDepartment,
    HRDepartmentPayload,
    HRLeaveRequest,
    HRLeaveType,
    HRLeaveTypePayload,
    HRPayrollRun,
    HRPayrollRunPayload,
    HRPosition,
    HRPositionPayload,
    HRShift,
    HRTrainingProgram,
    HRTrainingProgramPayload,
    HRVacancy,
    HRVacancyPayload,
} from "@/types/hrms";

export async function getHRDashboard(): Promise<HRDashboardSummary> {
    const response = await api.get<HRDashboardSummary>("/hr/dashboard");
    return response.data;
}

export async function listHRDepartments(): Promise<HRDepartment[]> {
    const response = await api.get<HRDepartment[]>("/hr/departments");
    return response.data;
}

export async function createHRDepartment(payload: HRDepartmentPayload): Promise<HRDepartment> {
    const response = await api.post<HRDepartment>("/hr/departments", payload);
    return response.data;
}

export async function listHRPositions(): Promise<HRPosition[]> {
    const response = await api.get<HRPosition[]>("/hr/positions");
    return response.data;
}

export async function createHRPosition(payload: HRPositionPayload): Promise<HRPosition> {
    const response = await api.post<HRPosition>("/hr/positions", payload);
    return response.data;
}

export async function listHRShifts(): Promise<HRShift[]> {
    const response = await api.get<HRShift[]>("/hr/shifts");
    return response.data;
}

export async function listHRAttendanceEvents(params?: { attendance_date?: string }): Promise<HRAttendanceEvent[]> {
    const response = await api.get<HRAttendanceEvent[]>("/hr/attendance/events", { params });
    return response.data;
}

export async function listHRLeaveTypes(): Promise<HRLeaveType[]> {
    const response = await api.get<HRLeaveType[]>("/hr/leave/types");
    return response.data;
}

export async function createHRLeaveType(payload: HRLeaveTypePayload): Promise<HRLeaveType> {
    const response = await api.post<HRLeaveType>("/hr/leave/types", payload);
    return response.data;
}

export async function listHRLeaveRequests(): Promise<HRLeaveRequest[]> {
    const response = await api.get<HRLeaveRequest[]>("/hr/leave/requests");
    return response.data;
}

export async function decideHRLeaveRequest(
    requestId: string,
    decision: "approved" | "declined" | "cancelled",
    comment?: string,
): Promise<HRLeaveRequest> {
    const response = await api.patch<HRLeaveRequest>(`/hr/leave/requests/${requestId}/decision`, {
        decision,
        comment: comment || null,
    });
    return response.data;
}

export async function listHRPayrollRuns(): Promise<HRPayrollRun[]> {
    const response = await api.get<HRPayrollRun[]>("/hr/payroll/runs");
    return response.data;
}

export async function createHRPayrollRun(payload: HRPayrollRunPayload): Promise<HRPayrollRun> {
    const response = await api.post<HRPayrollRun>("/hr/payroll/runs", payload);
    return response.data;
}

export async function calculateHRPayrollRun(runId: string): Promise<HRPayrollRun> {
    const response = await api.post<HRPayrollRun>(`/hr/payroll/runs/${runId}/calculate`);
    return response.data;
}

export async function listHRVacancies(): Promise<HRVacancy[]> {
    const response = await api.get<HRVacancy[]>("/hr/recruitment/vacancies");
    return response.data;
}

export async function createHRVacancy(payload: HRVacancyPayload): Promise<HRVacancy> {
    const response = await api.post<HRVacancy>("/hr/recruitment/vacancies", payload);
    return response.data;
}

export async function listHRCandidates(): Promise<HRCandidate[]> {
    const response = await api.get<HRCandidate[]>("/hr/recruitment/candidates");
    return response.data;
}

export async function listHRTrainingPrograms(): Promise<HRTrainingProgram[]> {
    const response = await api.get<HRTrainingProgram[]>("/hr/training/programs");
    return response.data;
}

export async function createHRTrainingProgram(payload: HRTrainingProgramPayload): Promise<HRTrainingProgram> {
    const response = await api.post<HRTrainingProgram>("/hr/training/programs", payload);
    return response.data;
}

export async function listHRAssets(): Promise<HRAsset[]> {
    const response = await api.get<HRAsset[]>("/hr/assets");
    return response.data;
}

export async function createHRAsset(payload: HRAssetPayload): Promise<HRAsset> {
    const response = await api.post<HRAsset>("/hr/assets", payload);
    return response.data;
}
