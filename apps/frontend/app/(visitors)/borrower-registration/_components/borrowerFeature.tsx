"use client";

export function BorrowerFeature({
                                    icon: Icon,
                                    text,
                                }: {
    icon: React.ElementType;
    text: string;
}) {
    return (
        <div className="flex items-center gap-4">

            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/10">
                <Icon className="h-6 w-6"/>
            </div>

            <p className="font-semibold">
                {text}
            </p>

        </div>
    );
}