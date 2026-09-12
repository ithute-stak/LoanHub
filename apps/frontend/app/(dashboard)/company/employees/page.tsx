import { redirect } from "next/navigation";

export default function EmployeesRedirectPage() {
    redirect("/company/people?tab=employees");
}
