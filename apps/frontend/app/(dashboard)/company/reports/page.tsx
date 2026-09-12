import { redirect } from "next/navigation";

export default function ReportsRedirectPage() {
    redirect("/company/documents?tab=reports");
}
