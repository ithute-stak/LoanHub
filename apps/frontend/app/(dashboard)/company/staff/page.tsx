import { redirect } from "next/navigation";

export default function StaffRedirectPage() {
    redirect("/company/people?tab=access");
}
