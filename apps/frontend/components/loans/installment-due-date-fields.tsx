"use client";

import { CalendarDays, Sparkles } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function resizeInstallmentDueDates(values: string[], count: number): string[] {
  const safeCount = Math.max(0, Math.trunc(Number.isFinite(count) ? count : 0));
  return Array.from({ length: safeCount }, (_, index) => values[index] ?? "");
}


export function generateMonthlyInstallmentDueDates(startDate: string, count: number): string[] {
  const safeCount = Math.max(0, Math.trunc(Number.isFinite(count) ? count : 0));
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(startDate.trim());

  if (!match) return resizeInstallmentDueDates([], safeCount);

  const startYear = Number(match[1]);
  const startMonthIndex = Number(match[2]) - 1;
  const startDay = Number(match[3]);

  if (
    !Number.isInteger(startYear)
    || startMonthIndex < 0
    || startMonthIndex > 11
    || startDay < 1
    || startDay > 31
  ) {
    return resizeInstallmentDueDates([], safeCount);
  }

  return Array.from({ length: safeCount }, (_, index) => {
    // The first installment is one calendar month after the payout/interest
    // start. Every later installment keeps the original day-of-month anchor.
    // This avoids Jan 31 -> Feb 28 -> Mar 28 drift; March returns to the 31st.
    const absoluteMonth = startMonthIndex + index + 1;
    const year = startYear + Math.floor(absoluteMonth / 12);
    const monthIndex = absoluteMonth % 12;
    const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();
    const day = Math.min(startDay, daysInMonth);

    return `${year}-${String(monthIndex + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  });
}

/** First installment falls on the next future salary pay date, then monthly.
 * Uses UTC calendar arithmetic so 31st paydays clip in February and return
 * to the 31st in March. Does not assume pay dates when they are unknown.
 */
export function generatePaydayInstallmentDueDates(
  nextPayDate: string | null | undefined,
  incomeDay: number | null | undefined,
  count: number,
  today = new Date().toISOString().slice(0, 10),
): string[] {
  const size = Math.max(0, Math.trunc(Number.isFinite(count) ? count : 0));
  const datePattern = /^(\d{4})-(\d{2})-(\d{2})$/;
  const todayMatch = datePattern.exec(today);
  if (!todayMatch) return resizeInstallmentDueDates([], size);
  const todayYear = Number(todayMatch[1]);
  const todayMonth = Number(todayMatch[2]);
  const todayDay = Number(todayMatch[3]);
  let payday = Number(incomeDay);
  const suppliedPayday = nextPayDate ? datePattern.exec(nextPayDate) : null;
  const realNextPayDate = suppliedPayday && !Number.isNaN(Date.parse(nextPayDate!))
    && new Date(nextPayDate!).toISOString().slice(0, 10) === nextPayDate
    && nextPayDate > today;
  if (realNextPayDate && suppliedPayday) payday = Number(suppliedPayday[3]);
  if (!Number.isInteger(payday) || payday < 1 || payday > 31) return resizeInstallmentDueDates([], size);

  let firstYear = todayYear;
  let firstMonth = todayMonth;
  if (realNextPayDate && suppliedPayday) {
    firstYear = Number(suppliedPayday[1]);
    firstMonth = Number(suppliedPayday[2]);
  } else {
    const last = new Date(Date.UTC(firstYear, firstMonth, 0)).getUTCDate();
    if (Math.min(payday, last) <= todayDay) {
      firstMonth += 1;
      if (firstMonth > 12) { firstMonth = 1; firstYear += 1; }
    }
  }
  return Array.from({ length: size }, (_, index) => {
    const date = new Date(Date.UTC(firstYear, firstMonth - 1 + index, 1));
    const year = date.getUTCFullYear();
    const monthIndex = date.getUTCMonth();
    const last = new Date(Date.UTC(year, monthIndex + 1, 0)).getUTCDate();
    return `${year}-${String(monthIndex + 1).padStart(2, "0")}-${String(Math.min(payday, last)).padStart(2, "0")}`;
  });
}

export function installmentDueDatesComplete(values: string[], count: number): boolean {
  return values.length === count && values.every((value) => Boolean(value));
}

export function InstallmentDueDateFields({
  count,
  value,
  onChange,
  disabled = false,
  readOnly = false,
  description,
  statusLabel,
}: {
  count: number;
  value: string[];
  onChange?: (value: string[]) => void;
  disabled?: boolean;
  readOnly?: boolean;
  description?: string;
  statusLabel?: string;
}) {
  const dates = resizeInstallmentDueDates(value, count);
  const completed = dates.filter(Boolean).length;

  return (
    <div className="space-y-3 rounded-2xl border bg-muted/20 p-4 sm:col-span-2">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Label className="flex items-center gap-2 text-sm font-black">
            <CalendarDays className="h-4 w-4 text-primary" />
            Installment due dates
          </Label>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            {description ?? "Review the installment dates and adjust them where this workflow allows changes. LoanHub validates the final date order."}
          </p>
        </div>
        <p className="flex items-center gap-1.5 rounded-full border bg-background px-3 py-1 text-xs font-bold text-muted-foreground">
          {readOnly ? <Sparkles className="h-3.5 w-3.5 text-primary" /> : null}
          {statusLabel ?? `${completed}/${count} entered`}
        </p>
      </div>

      <div className="grid max-h-80 gap-3 overflow-y-auto pr-1 sm:grid-cols-2 lg:grid-cols-3">
        {dates.map((date, index) => (
          <div key={index} className="space-y-1.5 rounded-xl border bg-background p-3">
            <Label htmlFor={`installment-due-date-${index}`} className="text-xs font-black uppercase tracking-wide text-muted-foreground">
              Installment {index + 1}
            </Label>
            <Input
              id={`installment-due-date-${index}`}
              type="date"
              required
              disabled={disabled}
              readOnly={readOnly}
              value={date}
              className={readOnly ? "cursor-default bg-muted/30 font-semibold" : undefined}
              onChange={(event) => {
                if (readOnly || !onChange) return;
                const next = [...dates];
                next[index] = event.target.value;
                onChange(next);
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
