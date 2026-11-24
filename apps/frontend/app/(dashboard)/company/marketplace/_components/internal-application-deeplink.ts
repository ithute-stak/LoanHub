/** Pure deep-link guards for the internal applications dialog. */
export function applicationToAutoOpen(
    requestedApplicationId: string | null,
    lastAutoOpenedApplicationId: string | null,
    selectedApplicationId: string | null,
    availableApplicationIds: readonly string[],
): string | null {
    if (!requestedApplicationId || selectedApplicationId || requestedApplicationId === lastAutoOpenedApplicationId) {
        return null;
    }
    return availableApplicationIds.includes(requestedApplicationId) ? requestedApplicationId : null;
}

/** Preserve unrelated filters and the URL hash when dismissing a deep-linked dialog. */
export function urlAfterClosingApplication(href: string): string | null {
    const url = new URL(href);
    if (!url.searchParams.has("application")) return null;
    url.searchParams.delete("application");
    return url.pathname + url.search + url.hash;
}
