type Props = {
    eyebrow: string;
    title: string;
    description: string;
};

export function StepHeading({
    eyebrow,
    title,
    description,
}: Props) {
    return (
        <header className="mb-7">
            <p className="text-xs font-black uppercase tracking-[0.16em] text-primary">
                {eyebrow}
            </p>

            <h2 className="mt-2 text-2xl font-black tracking-tight sm:text-3xl">
                {title}
            </h2>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                {description}
            </p>
        </header>
    );
}
