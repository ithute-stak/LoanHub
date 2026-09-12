import {CompanyStaff} from "@/types/companyStuff";

type Props = {
    admins: CompanyStaff[];
};

export function CompanyAdminStats({ admins }: Props) {
    const total: number = admins.length;
    const active: number = admins.filter(a => a.is_active).length;
    const inactive: number = total - active;

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

            <div className="rounded-2xl border bg-card p-4">
                <p className="text-sm text-muted-foreground">Total Admins</p>
                <h2 className="text-2xl font-black">{total}</h2>
            </div>

            <div className="rounded-2xl border bg-card p-4">
                <p className="text-sm text-muted-foreground">Active</p>
                <h2 className="text-2xl font-black text-green-600">
                    {active}
                </h2>
            </div>

            <div className="rounded-2xl border bg-card p-4">
                <p className="text-sm text-muted-foreground">Inactive</p>
                <h2 className="text-2xl font-black text-red-600">
                    {inactive}
                </h2>
            </div>

        </div>
    );
}