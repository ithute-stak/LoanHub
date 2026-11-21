"use client";

/** Staged Data Center entrypoint. Intentionally disabled.
 * Existing DB_EVENT invalidation and financial APIs remain authoritative.
 * Do not enable until authenticated snapshot/replay and CI gates pass.
 */
export const LOANHUB_DATA_CENTER_ENABLED = false;

export function LoanHubDataCenterBridge() {
    return null;
}
