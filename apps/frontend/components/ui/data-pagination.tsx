"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export function DataPagination({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(Math.max(page, 1), totalPages);
  const first = total === 0 ? 0 : (safePage - 1) * pageSize + 1;
  const last = Math.min(safePage * pageSize, total);
  return (
    <div className="flex flex-col gap-3 border-t px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between">
      <p className="text-muted-foreground">Showing {first}–{last} of {total}</p>
      <div className="flex items-center gap-2">
        <Button type="button" size="sm" variant="outline" disabled={safePage <= 1} onClick={() => onPageChange(safePage - 1)}>
          <ChevronLeft className="h-4 w-4" />Previous
        </Button>
        <span className="min-w-24 text-center font-bold">Page {safePage} of {totalPages}</span>
        <Button type="button" size="sm" variant="outline" disabled={safePage >= totalPages} onClick={() => onPageChange(safePage + 1)}>
          Next<ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
