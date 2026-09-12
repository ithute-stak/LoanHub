import { redirect } from "next/navigation";

export default function CompanyPhonebookPage() {
  redirect("/company/calls?tab=phonebook");
}
