import { api } from "@/lib/api";

export type MFAStatus = {enabled:boolean;enrollment_pending:boolean;recovery_codes_remaining:number;confirmed_at:string|null};
export type MFAEnrollment = {otpauth_uri:string;recovery_codes:string[];message:string};

export const mfaApi = {
  status: () => api.get<MFAStatus>("/auth/mfa/status").then(r=>r.data),
  enroll: () => api.post<MFAEnrollment>("/auth/mfa/enroll").then(r=>r.data),
  confirm: (otp:string) => api.post<{message:string}>("/auth/mfa/confirm",{otp}).then(r=>r.data),
  disable: (password:string, secondFactor:string) => api.post<{message:string}>("/auth/mfa/disable",{password,otp:/^\d{6}$/.test(secondFactor)?secondFactor:null,recovery_code:/^\d{6}$/.test(secondFactor)?null:secondFactor}).then(r=>r.data),
};
