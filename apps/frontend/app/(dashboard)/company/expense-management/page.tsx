import { redirect } from "next/navigation";

export default function LegacyExpenseManagementRedirect() {
  redirect("/company/accounting");
}
