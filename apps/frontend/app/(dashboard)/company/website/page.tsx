import { CompanyWebsiteBuilder } from "@/components/company/company-website-builder";
import { CompanyWebsiteReadinessPanel } from "@/components/company/company-website-readiness";

export default function CompanyWebsitePage() {
    return (
        <div className="space-y-5">
            <CompanyWebsiteReadinessPanel />
            <CompanyWebsiteBuilder />
        </div>
    );
}