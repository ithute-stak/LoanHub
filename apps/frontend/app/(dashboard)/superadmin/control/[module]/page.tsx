"use client";

import { useParams } from "next/navigation";

import { SuperAdminOwnerControl } from "@/components/dashboard/superadmin-owner-control";

export default function SuperAdminControlModulePage() {
    const params = useParams<{ module: string }>();
    return <SuperAdminOwnerControl selectedModule={params.module} />;
}
