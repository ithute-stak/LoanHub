"use client";

import * as React from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

type CustomDialogProps = {
  trigger?: React.ReactNode;
  title?: string;
  description?: React.ReactNode;
  /** @deprecated Modal branding is fixed to the official LoanHub image. */
  banner?: string;
  /** @deprecated The shared logo has a fixed accessible label. */
  bannerAlt?: string;
  solidHeader?: boolean;
  children: React.ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  contentClassName?: string;
  bodyClassName?: string;
};

export function CustomDialog({
  trigger,
  title,
  description,
  solidHeader = false,
  children,
  open,
  onOpenChange,
  contentClassName,
  bodyClassName,
}: CustomDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {trigger ? <DialogTrigger asChild>{trigger}</DialogTrigger> : null}

      <DialogContent
        className={cn(
          "flex max-h-[95vh] flex-col gap-0 overflow-hidden rounded-[1.75rem]",
          "border border-white/20 bg-card p-0 shadow-2xl sm:max-w-4xl",
          contentClassName,
        )}
      >
        <div className={cn("w-full shrink-0 border-b border-white/10 bg-gradient-to-r from-slate-950 to-slate-800", solidHeader && "from-slate-950 to-slate-950")}>
          <div className="px-4 py-4 text-left sm:px-6">
            <DialogHeader className="gap-1 pr-10">
              <DialogTitle className="text-2xl font-black tracking-tight text-white">
                {title ?? "LoanHub"}
              </DialogTitle>
              {description ? (
                <DialogDescription className="max-w-3xl text-sm text-white/80">
                  {description}
                </DialogDescription>
              ) : null}
            </DialogHeader>
          </div>
        </div>

        <div className={cn("min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto", bodyClassName)}>
          {children}
        </div>
      </DialogContent>
    </Dialog>
  );
}
