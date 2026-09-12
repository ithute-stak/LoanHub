export type EmployeePerformance = {
    staff_id: string;
    employee_id: string | null;
    user_id: string;
    branch_id: string | null;
    employee_name: string;
    role: string;
    job_title: string | null;
    department: string | null;
    offers_created: number;
    offers_accepted: number;
    loans_approved: number;
    loans_disbursed: number;
    payment_transactions: number;
    successful_payment_amount: string | number;
    active_goals: number;
    completed_goals: number;
    goal_completion_percent: number;
    average_review_score: number;
    performance_score: number;
};

export type BranchPerformance = {
    branch_id: string | null;
    branch_name: string;
    employee_count: number;
    active_loans: number;
    overdue_loans: number;
    loan_principal: string | number;
    payments_received: string | number;
    average_employee_score: number;
};

export type CompanyPerformance = {
    company_id: string;
    company_name: string;
    employee_count: number;
    branch_count: number;
    active_loans: number;
    overdue_loans: number;
    outstanding_balance: string | number;
    successful_payments: string | number;
    employee_average_score: number;
    operational_score: number;
};

export type PerformanceOverview = {
    scope: "company" | "platform" | string;
    employee_count: number;
    branch_count: number;
    company_count: number;
    active_loans: number;
    overdue_loans: number;
    total_outstanding: string | number;
    successful_payments: string | number;
    average_employee_score: number;
    employees: EmployeePerformance[];
    branches: BranchPerformance[];
    companies: CompanyPerformance[];
};
