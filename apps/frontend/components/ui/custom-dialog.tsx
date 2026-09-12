"use client";

import * as React from "react";
import Image from "next/image";

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
  banner?: string;
  bannerAlt?: string;
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
  banner = "/loanhub-horizontal-logo.png",
  bannerAlt = "LoanHub dialog banner",
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
        <div className="relative h-32 w-full shrink-0 overflow-hidden">
          <Image
            src={banner}
            alt={bannerAlt}
            fill
            sizes="(max-width: 768px) 100vw, 896px"
            className="object-cover"
            preload
          />
          <div className="absolute inset-0 bg-gradient-to-r from-slate-950/90 via-slate-950/60 to-primary/25" />
          <div className="absolute inset-x-0 bottom-0 z-10 px-6 pb-5 text-left sm:px-8">
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

        <div className={cn("min-h-0 flex-1 overflow-y-auto", bodyClassName)}>
          {children}
        </div>
      </DialogContent>
    </Dialog>
  );
}
