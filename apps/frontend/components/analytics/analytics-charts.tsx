"use client";

import {
    Area,
    AreaChart,
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    Legend,
    Line,
    LineChart,
    Pie,
    PieChart,
    PolarAngleAxis,
    PolarGrid,
    Radar,
    RadarChart,
    RadialBar,
    RadialBarChart,
    Scatter,
    ScatterChart,
    XAxis,
    YAxis,
    ZAxis,
} from "recharts";

import {
    ChartContainer,
    ChartTooltip,
    ChartTooltipContent,
    type ChartConfig,
} from "@/components/ui/chart";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type {
    AnalyticsBreakdownPoint,
    AnalyticsHeatmapPoint,
    AnalyticsScatterPoint,
    AnalyticsTimePoint,
} from "@/types/analytics";

const CHART_COLORS = [
    "var(--chart-1)",
    "var(--chart-2)",
    "var(--chart-3)",
    "var(--chart-4)",
    "var(--chart-5)",
];

function compact(value: number): string {
    return new Intl.NumberFormat("en-LS", {
        notation: Math.abs(value) >= 10_000 ? "compact" : "standard",
        maximumFractionDigits: 1,
    }).format(value);
}

function money(value: number): string {
    return new Intl.NumberFormat("en-LS", {
        style: "currency",
        currency: "LSL",
        maximumFractionDigits: 0,
    }).format(value);
}

function percent(value: number): string {
    return `${value.toFixed(1)}%`;
}

function flattenSeries(points: AnalyticsTimePoint[]): Array<Record<string, string | number>> {
    return points.map((point) => ({ period: point.period, ...point.values }));
}

function chartConfig(series: Array<{ key: string; label: string }>): ChartConfig {
    return Object.fromEntries(
        series.map((item, index) => [
            item.key,
            {
                label: item.label,
                color: CHART_COLORS[index % CHART_COLORS.length],
            },
        ]),
    ) as ChartConfig;
}

function EmptyChart({ label = "No analytics are available for this period." }: { label?: string }) {
    return (
        <div className="flex h-64 items-center justify-center rounded-2xl border border-dashed bg-muted/20 px-6 text-center text-sm text-muted-foreground">
            {label}
        </div>
    );
}

export function ChartCard({
    title,
    description,
    children,
    className,
}: {
    title: string;
    description: string;
    children: React.ReactNode;
    className?: string;
}) {
    return (
        <Card className={cn("rounded-3xl shadow-sm", className)}>
            <CardHeader>
                <CardTitle className="text-base font-black">{title}</CardTitle>
                <CardDescription className="leading-5">{description}</CardDescription>
            </CardHeader>
            <CardContent>{children}</CardContent>
        </Card>
    );
}

export function TrendAreaChart({
    title,
    description,
    points,
    series,
    valueKind = "number",
}: {
    title: string;
    description: string;
    points: AnalyticsTimePoint[];
    series: Array<{ key: string; label: string }>;
    valueKind?: "money" | "number" | "percent";
}) {
    if (points.length === 0) return <ChartCard title={title} description={description}><EmptyChart /></ChartCard>;
    const config = chartConfig(series);
    const formatter = valueKind === "money" ? money : valueKind === "percent" ? percent : compact;
    return (
        <ChartCard title={title} description={description}>
            <ChartContainer config={config} className="h-[300px] w-full aspect-auto">
                <AreaChart data={flattenSeries(points)} margin={{ left: 6, right: 12, top: 8 }}>
                    <defs>
                        {series.map((item) => (
                            <linearGradient key={item.key} id={`fill-${item.key}`} x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor={`var(--color-${item.key})`} stopOpacity={0.35} />
                                <stop offset="95%" stopColor={`var(--color-${item.key})`} stopOpacity={0.02} />
                            </linearGradient>
                        ))}
                    </defs>
                    <CartesianGrid vertical={false} strokeDasharray="3 3" />
                    <XAxis dataKey="period" tickLine={false} axisLine={false} minTickGap={28} />
                    <YAxis tickLine={false} axisLine={false} tickFormatter={formatter} width={70} />
                    <ChartTooltip content={<ChartTooltipContent formatter={(value) => formatter(Number(value))} />} />
                    {series.map((item, index) => (
                        <Area
                            key={item.key}
                            dataKey={item.key}
                            type="monotone"
                            stroke={`var(--color-${item.key})`}
                            fill={`url(#fill-${item.key})`}
                            strokeWidth={2.3}
                            stackId={series.length > 2 ? undefined : undefined}
                            isAnimationActive
                            animationDuration={450 + index * 80}
                        />
                    ))}
                </AreaChart>
            </ChartContainer>
        </ChartCard>
    );
}

export function MultiLineChart({
    title,
    description,
    points,
    series,
    valueKind = "number",
}: {
    title: string;
    description: string;
    points: AnalyticsTimePoint[];
    series: Array<{ key: string; label: string }>;
    valueKind?: "money" | "number" | "percent";
}) {
    if (points.length === 0) return <ChartCard title={title} description={description}><EmptyChart /></ChartCard>;
    const config = chartConfig(series);
    const formatter = valueKind === "money" ? money : valueKind === "percent" ? percent : compact;
    return (
        <ChartCard title={title} description={description}>
            <ChartContainer config={config} className="h-[300px] w-full aspect-auto">
                <LineChart data={flattenSeries(points)} margin={{ left: 6, right: 12, top: 8 }}>
                    <CartesianGrid vertical={false} strokeDasharray="3 3" />
                    <XAxis dataKey="period" tickLine={false} axisLine={false} minTickGap={28} />
                    <YAxis tickLine={false} axisLine={false} tickFormatter={formatter} width={70} />
                    <ChartTooltip content={<ChartTooltipContent formatter={(value) => formatter(Number(value))} />} />
                    <Legend />
                    {series.map((item) => (
                        <Line
                            key={item.key}
                            dataKey={item.key}
                            name={item.label}
                            type="monotone"
                            stroke={`var(--color-${item.key})`}
                            strokeWidth={2.4}
                            dot={{ r: 2.8 }}
                            activeDot={{ r: 5 }}
                        />
                    ))}
                </LineChart>
            </ChartContainer>
        </ChartCard>
    );
}

export function StackedBarChart({
    title,
    description,
    points,
    series,
    valueKind = "money",
}: {
    title: string;
    description: string;
    points: AnalyticsTimePoint[];
    series: Array<{ key: string; label: string }>;
    valueKind?: "money" | "number";
}) {
    if (points.length === 0) return <ChartCard title={title} description={description}><EmptyChart /></ChartCard>;
    const config = chartConfig(series);
    const formatter = valueKind === "money" ? money : compact;
    return (
        <ChartCard title={title} description={description}>
            <ChartContainer config={config} className="h-[300px] w-full aspect-auto">
                <BarChart data={flattenSeries(points)} margin={{ left: 4, right: 8, top: 8 }}>
                    <CartesianGrid vertical={false} strokeDasharray="3 3" />
                    <XAxis dataKey="period" tickLine={false} axisLine={false} minTickGap={28} />
                    <YAxis tickLine={false} axisLine={false} tickFormatter={formatter} width={72} />
                    <ChartTooltip content={<ChartTooltipContent formatter={(value) => formatter(Number(value))} />} />
                    <Legend />
                    {series.map((item) => (
                        <Bar key={item.key} dataKey={item.key} name={item.label} stackId="stack" fill={`var(--color-${item.key})`} radius={[4, 4, 0, 0]} />
                    ))}
                </BarChart>
            </ChartContainer>
        </ChartCard>
    );
}

export function DonutChart({
    title,
    description,
    points,
    valueKind = "number",
    centreLabel,
}: {
    title: string;
    description: string;
    points: AnalyticsBreakdownPoint[];
    valueKind?: "money" | "number" | "percent";
    centreLabel?: string;
}) {
    if (points.length === 0) return <ChartCard title={title} description={description}><EmptyChart /></ChartCard>;
    const visible = points.slice(0, 7);
    const total = visible.reduce((sum, item) => sum + item.value, 0);
    const formatter = valueKind === "money" ? money : valueKind === "percent" ? percent : compact;
    const config = Object.fromEntries(visible.map((item, index) => [item.label, { label: item.label, color: CHART_COLORS[index % CHART_COLORS.length] }])) as ChartConfig;
    return (
        <ChartCard title={title} description={description}>
            <ChartContainer config={config} className="mx-auto h-[300px] w-full max-w-[420px] aspect-auto">
                <PieChart>
                    <ChartTooltip content={<ChartTooltipContent nameKey="label" formatter={(value) => formatter(Number(value))} />} />
                    <Pie data={visible} dataKey="value" nameKey="label" innerRadius={70} outerRadius={105} paddingAngle={2.5} strokeWidth={2}>
                        {visible.map((item, index) => <Cell key={item.label} fill={CHART_COLORS[index % CHART_COLORS.length]} />)}
                    </Pie>
                    <text x="50%" y="47%" textAnchor="middle" dominantBaseline="middle" className="fill-foreground text-lg font-black">
                        {formatter(total)}
                    </text>
                    <text x="50%" y="55%" textAnchor="middle" dominantBaseline="middle" className="fill-muted-foreground text-xs">
                        {centreLabel ?? "Total"}
                    </text>
                    <Legend />
                </PieChart>
            </ChartContainer>
        </ChartCard>
    );
}

export function HorizontalBarChart({
    title,
    description,
    points,
    valueKind = "number",
    limit = 10,
}: {
    title: string;
    description: string;
    points: AnalyticsBreakdownPoint[];
    valueKind?: "money" | "number" | "percent";
    limit?: number;
}) {
    if (points.length === 0) return <ChartCard title={title} description={description}><EmptyChart /></ChartCard>;
    const data = points.slice(0, limit).reverse();
    const config = { value: { label: "Value", color: "var(--chart-1)" } } satisfies ChartConfig;
    const formatter = valueKind === "money" ? money : valueKind === "percent" ? percent : compact;
    const height = Math.max(260, data.length * 42);
    return (
        <ChartCard title={title} description={description}>
            <ChartContainer config={config} className="w-full aspect-auto" style={{ height }}>
                <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
                    <CartesianGrid horizontal={false} strokeDasharray="3 3" />
                    <XAxis type="number" tickLine={false} axisLine={false} tickFormatter={formatter} />
                    <YAxis type="category" dataKey="label" tickLine={false} axisLine={false} width={126} tick={{ fontSize: 11 }} />
                    <ChartTooltip content={<ChartTooltipContent formatter={(value) => formatter(Number(value))} />} />
                    <Bar dataKey="value" fill="var(--color-value)" radius={[0, 8, 8, 0]} />
                </BarChart>
            </ChartContainer>
        </ChartCard>
    );
}

export function DualMetricBarChart({
    title,
    description,
    points,
    primaryLabel,
    secondaryLabel,
}: {
    title: string;
    description: string;
    points: AnalyticsBreakdownPoint[];
    primaryLabel: string;
    secondaryLabel: string;
}) {
    if (points.length === 0) return <ChartCard title={title} description={description}><EmptyChart /></ChartCard>;
    const data = points.slice(0, 10).map((item) => ({ label: item.label, primary: item.value, secondary: item.secondary_value ?? 0 }));
    const config = {
        primary: { label: primaryLabel, color: "var(--chart-1)" },
        secondary: { label: secondaryLabel, color: "var(--chart-2)" },
    } satisfies ChartConfig;
    return (
        <ChartCard title={title} description={description}>
            <ChartContainer config={config} className="h-[340px] w-full aspect-auto">
                <BarChart data={data} margin={{ left: 4, right: 8, top: 8 }}>
                    <CartesianGrid vertical={false} strokeDasharray="3 3" />
                    <XAxis dataKey="label" tickLine={false} axisLine={false} interval={0} angle={-18} textAnchor="end" height={72} tick={{ fontSize: 10 }} />
                    <YAxis tickLine={false} axisLine={false} tickFormatter={compact} width={66} />
                    <ChartTooltip content={<ChartTooltipContent formatter={(value) => money(Number(value))} />} />
                    <Legend />
                    <Bar dataKey="primary" fill="var(--color-primary)" radius={[8, 8, 0, 0]} />
                    <Bar dataKey="secondary" fill="var(--color-secondary)" radius={[8, 8, 0, 0]} />
                </BarChart>
            </ChartContainer>
        </ChartCard>
    );
}

export function BubbleScatterChart({
    title,
    description,
    points,
    xLabel,
    yLabel,
    xKind = "number",
    yKind = "number",
}: {
    title: string;
    description: string;
    points: AnalyticsScatterPoint[];
    xLabel: string;
    yLabel: string;
    xKind?: "money" | "number" | "percent";
    yKind?: "money" | "number" | "percent";
}) {
    if (points.length === 0) return <ChartCard title={title} description={description}><EmptyChart /></ChartCard>;
    const config = { portfolio: { label: "Portfolio", color: "var(--chart-4)" } } satisfies ChartConfig;
    const xFormatter = xKind === "money" ? money : xKind === "percent" ? percent : compact;
    const yFormatter = yKind === "money" ? money : yKind === "percent" ? percent : compact;
    return (
        <ChartCard title={title} description={description}>
            <ChartContainer config={config} className="h-[330px] w-full aspect-auto">
                <ScatterChart margin={{ left: 12, right: 18, top: 12, bottom: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" dataKey="x" name={xLabel} tickFormatter={xFormatter} tickLine={false} axisLine={false} />
                    <YAxis type="number" dataKey="y" name={yLabel} tickFormatter={yFormatter} tickLine={false} axisLine={false} width={72} />
                    <ZAxis type="number" dataKey="size" range={[55, 450]} />
                    <ChartTooltip cursor={{ strokeDasharray: "3 3" }} content={<ChartTooltipContent formatter={(value, name) => name === xLabel ? xFormatter(Number(value)) : yFormatter(Number(value))} />} />
                    <Scatter name="Portfolio" data={points} fill="var(--color-portfolio)" />
                </ScatterChart>
            </ChartContainer>
        </ChartCard>
    );
}

export function RadarScoreChart({
    title,
    description,
    points,
}: {
    title: string;
    description: string;
    points: AnalyticsBreakdownPoint[];
}) {
    if (points.length === 0) return <ChartCard title={title} description={description}><EmptyChart /></ChartCard>;
    const max = Math.max(...points.map((item) => item.value), 1);
    const data = points.slice(0, 8).map((item) => ({ label: item.label, score: Math.round((item.value / max) * 100) }));
    const config = { score: { label: "Relative score", color: "var(--chart-2)" } } satisfies ChartConfig;
    return (
        <ChartCard title={title} description={description}>
            <ChartContainer config={config} className="h-[320px] w-full aspect-auto">
                <RadarChart data={data} outerRadius="72%">
                    <PolarGrid />
                    <PolarAngleAxis dataKey="label" tick={{ fontSize: 10 }} />
                    <ChartTooltip content={<ChartTooltipContent formatter={(value) => `${Number(value).toFixed(0)} / 100`} />} />
                    <Radar dataKey="score" stroke="var(--color-score)" fill="var(--color-score)" fillOpacity={0.25} strokeWidth={2.2} />
                </RadarChart>
            </ChartContainer>
        </ChartCard>
    );
}

export function RadialGauge({
    title,
    description,
    value,
    label,
}: {
    title: string;
    description: string;
    value: number;
    label: string;
}) {
    const bounded = Math.max(0, Math.min(100, value));
    const data = [{ name: label, value: bounded, fill: "var(--chart-2)" }];
    const config = { value: { label, color: "var(--chart-2)" } } satisfies ChartConfig;
    return (
        <ChartCard title={title} description={description}>
            <ChartContainer config={config} className="mx-auto h-[280px] w-full max-w-[360px] aspect-auto">
                <RadialBarChart data={data} startAngle={210} endAngle={-30} innerRadius="68%" outerRadius="100%" barSize={24}>
                    <RadialBar dataKey="value" background cornerRadius={14} />
                    <text x="50%" y="48%" textAnchor="middle" dominantBaseline="middle" className="fill-foreground text-3xl font-black">
                        {percent(bounded)}
                    </text>
                    <text x="50%" y="60%" textAnchor="middle" dominantBaseline="middle" className="fill-muted-foreground text-xs">
                        {label}
                    </text>
                </RadialBarChart>
            </ChartContainer>
        </ChartCard>
    );
}

export function FunnelChart({
    title,
    description,
    points,
}: {
    title: string;
    description: string;
    points: AnalyticsBreakdownPoint[];
}) {
    if (points.length === 0) return <ChartCard title={title} description={description}><EmptyChart /></ChartCard>;
    const max = Math.max(...points.map((item) => item.value), 1);
    return (
        <ChartCard title={title} description={description}>
            <div className="space-y-3">
                {points.map((item, index) => {
                    const width = Math.max(18, (item.value / max) * 100);
                    const previous = index === 0 ? null : points[index - 1];
                    const conversion = previous?.value ? (item.value / previous.value) * 100 : null;
                    return (
                        <div key={item.label} className="space-y-1.5">
                            <div className="flex items-center justify-between gap-3 text-xs">
                                <span className="font-black">{item.label}</span>
                                <span className="text-muted-foreground">{compact(item.value)}{conversion !== null ? ` · ${conversion.toFixed(1)}% conversion` : ""}</span>
                            </div>
                            <div className="flex justify-center">
                                <div className="h-9 rounded-xl bg-primary/85 shadow-sm transition-all" style={{ width: `${width}%` }} />
                            </div>
                        </div>
                    );
                })}
            </div>
        </ChartCard>
    );
}

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function ActivityHeatmap({
    title,
    description,
    points,
}: {
    title: string;
    description: string;
    points: AnalyticsHeatmapPoint[];
}) {
    const map = new Map(points.map((point) => [`${point.day}-${point.hour}`, point.value]));
    const max = Math.max(...points.map((point) => point.value), 1);
    return (
        <ChartCard title={title} description={description}>
            {points.length === 0 ? <EmptyChart /> : (
                <div className="overflow-x-auto pb-2">
                    <div className="min-w-[760px] space-y-2">
                        <div className="grid grid-cols-[42px_repeat(24,minmax(20px,1fr))] gap-1 text-[9px] text-muted-foreground">
                            <span />
                            {Array.from({ length: 24 }, (_, hour) => <span key={hour} className="text-center">{hour % 3 === 0 ? hour : ""}</span>)}
                        </div>
                        {WEEKDAYS.map((day) => (
                            <div key={day} className="grid grid-cols-[42px_repeat(24,minmax(20px,1fr))] gap-1">
                                <span className="flex items-center text-[10px] font-bold text-muted-foreground">{day}</span>
                                {Array.from({ length: 24 }, (_, hour) => {
                                    const value = map.get(`${day}-${hour}`) ?? 0;
                                    const opacity = value === 0 ? 0.05 : 0.18 + (value / max) * 0.82;
                                    return <div key={hour} title={`${day} ${hour}:00 · ${value} events`} className="h-6 rounded-md border border-primary/10" style={{ backgroundColor: `color-mix(in srgb, var(--chart-1) ${opacity * 100}%, transparent)` }} />;
                                })}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </ChartCard>
    );
}
