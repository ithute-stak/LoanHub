import { redirect } from "next/navigation";

type DirectLendingRedirectPageProps = {
    searchParams: Promise<{
        application?: string | string[];
    }>;
};

export default async function DirectLendingRedirectPage({
    searchParams,
}: DirectLendingRedirectPageProps) {
    const params = await searchParams;
    const application = Array.isArray(params.application)
        ? params.application[0]
        : params.application;

    const destination = new URLSearchParams({ workspace: "applications" });
    if (application) destination.set("application", application);

    redirect(`/company/marketplace?${destination.toString()}`);
}
