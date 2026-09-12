import {
    PerformanceDashboard,
} from "@/components/performance/performance-dashboard";
import { SystemEmployeeRatingsPanel } from "@/components/performance/system-employee-ratings";

export default function CompanyPerformancePage() {
    return (
        <div className="space-y-5">
            <SystemEmployeeRatingsPanel />
            <PerformanceDashboard mode="company" />
        </div>
    );
}