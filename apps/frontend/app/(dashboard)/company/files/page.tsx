import { redirect } from "next/navigation";

export default function FilesRedirectPage() {
    redirect("/company/documents?tab=library");
}
