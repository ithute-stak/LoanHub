export type HRDashboardSummary = {
    total_employees: number;
    active_employees: number;
    employees_present_today: number;
    employees_absent_today: number;
    employees_on_leave_today: number;
    pending_leave_requests: number;
    open_vacancies: number;
    active_training_programs: number;
    assigned_assets: number;
    payroll_status: string | null;
    payroll_net_total: number | string;
    departments: number;
    branches: number;
};

export type HRDepartment = {
    id: string;
    company_id: string;
    branch_id: string | null;
    parent_id: string | null;
    manager_employee_id: string | null;
    name: string;
    code: string;
    cost_centre: string | null;
    description: string | null;
    is_active: boolean;
    created_at: string;
    updated_at: string;
};

export type HRPosition = {
    id: string;
    company_id: string;
    department_id: string | null;
    reports_to_position_id: string | null;
    title: string;
    code: string;
    grade: string | null;
    description: string | null;
    minimum_salary: number | string | null;
    maximum_salary: number | string | null;
    currency: string;
    is_active: boolean;
    created_at: string;
    updated_at: string;
};

export type HRShift = {
    id: string;
    company_id: string;
    branch_id: string | null;
    name: string;
    code: string;
    start_time: string;
    end_time: string;
    break_minutes: number | string;
    late_grace_minutes: number | string;
    work_days: number[];
    is_active: boolean;
};

export type HRAttendanceEvent = {
    id: string;
    employee_id: string;
    event_type: string;
    occurred_at: string;
    source: string;
    status: string;
    notes: string | null;
};

export type HRLeaveType = {
    id: string;
    name: string;
    code: string;
    paid: boolean;
    annual_days: number | string;
    requires_attachment: boolean;
    approval_levels: number | string;
    is_active: boolean;
};

export type HRLeaveRequest = {
    id: string;
    employee_id: string;
    leave_type_id: string;
    start_date: string;
    end_date: string;
    days_requested: number | string;
    reason: string | null;
    status: string;
    manager_comment: string | null;
    created_at: string;
};

export type HRPayrollRun = {
    id: string;
    period_key: string;
    period_start: string;
    period_end: string;
    pay_date: string;
    status: string;
    currency: string;
    gross_total: number | string;
    deduction_total: number | string;
    net_total: number | string;
};

export type HRVacancy = {
    id: string;
    title: string;
    reference: string;
    openings: number | string;
    status: string;
    closing_date: string | null;
    created_at: string;
};

export type HRCandidate = {
    id: string;
    vacancy_id: string | null;
    full_name: string;
    email: string | null;
    phone: string | null;
    national_id: string | null;
    stage: string;
    score: number | string | null;
};

export type HRTrainingProgram = {
    id: string;
    title: string;
    provider: string | null;
    start_date: string | null;
    end_date: string | null;
    capacity: number | string | null;
    status: string;
    skills: string[];
    cost: number | string | null;
    currency: string;
};

export type HRAsset = {
    id: string;
    asset_tag: string;
    name: string;
    category: string;
    serial_number: string | null;
    status: string;
    condition: string;
    purchase_date: string | null;
    purchase_cost: number | string | null;
    currency: string;
};

export type HRDepartmentPayload = {
    name: string;
    code: string;
    branch_id?: string | null;
    parent_id?: string | null;
    manager_employee_id?: string | null;
    cost_centre?: string | null;
    description?: string | null;
    is_active?: boolean;
};

export type HRPositionPayload = {
    title: string;
    code: string;
    department_id?: string | null;
    grade?: string | null;
    minimum_salary?: number | null;
    maximum_salary?: number | null;
    currency?: string;
};

export type HRLeaveTypePayload = {
    name: string;
    code: string;
    paid: boolean;
    annual_days: number;
    requires_attachment: boolean;
    approval_levels: number;
    is_active?: boolean;
};

export type HRPayrollRunPayload = {
    period_key: string;
    period_start: string;
    period_end: string;
    pay_date: string;
    branch_id?: string | null;
    currency?: string;
};

export type HRVacancyPayload = {
    title: string;
    reference: string;
    description?: string | null;
    openings: number;
    status: "draft" | "published" | "closed" | "cancelled";
    closing_date?: string | null;
};

export type HRTrainingProgramPayload = {
    title: string;
    provider?: string | null;
    start_date?: string | null;
    end_date?: string | null;
    capacity?: number | null;
    status?: string;
    skills?: string[];
    cost?: number | null;
    currency?: string;
};

export type HRAssetPayload = {
    asset_tag: string;
    name: string;
    category: string;
    serial_number?: string | null;
    status?: string;
    condition?: string;
    purchase_date?: string | null;
    purchase_cost?: number | null;
    currency?: string;
    notes?: string | null;
};
