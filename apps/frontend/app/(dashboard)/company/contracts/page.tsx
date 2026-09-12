import { redirect } from "next/navigation";

export default function ContractsPage() {
  redirect("/company/loans?tab=contracts");
}
