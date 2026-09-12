"use client";

import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { CustomDialog } from "@/components/ui/custom-dialog";
import { DialogFooter } from "@/components/ui/dialog";
import { LoadingButton } from "@/components/ui/loading-button";

type ConfirmDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;
  destructive?: boolean;
  loading?: boolean;
  onConfirm: () => void | Promise<void>;
};

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirm",
  destructive = false,
  loading = false,
  onConfirm,
}: ConfirmDialogProps) {
  return (
    <CustomDialog
      open={open}
      onOpenChange={(next) => !loading && onOpenChange(next)}
      title={title}
      description={description}
      contentClassName="sm:max-w-md"
    >
      <div className="space-y-5 p-6 sm:p-8">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-500/15 text-amber-700 dark:text-amber-300">
          <AlertTriangle className="h-6 w-6" />
        </div>
        <p className="text-sm leading-6 text-muted-foreground">Review the details before continuing. This action will be written to the system activity history.</p>
        <DialogFooter className="mx-0 mb-0">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>Cancel</Button>
          <LoadingButton
            type="button"
            variant={destructive ? "destructive" : "default"}
            loading={loading}
            loadingText="Working…"
            onClick={() => void onConfirm()}
          >
            {confirmLabel}
          </LoadingButton>
        </DialogFooter>
      </div>
    </CustomDialog>
  );
}
