import { redirect } from "next/navigation";

/** Backward-compatible route retained for old bookmarks. */
export default function CompanyAdminAliasPage() {
    redirect("/company");
}
