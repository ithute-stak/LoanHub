/** Pure replay-envelope validator for the opt-in Data Center browser bridge.
 * No financial record payloads, tenant fallback or client-side authority.
 * Throwing forces the bridge to revoke its projection and request a new snapshot.
 */
export type DataCenterReplayEvent = {
    cursor: number;
    resource: string;
    entity_id: string;
    branch_id: string | null;
    action: string;
};
export type DataCenterReplayEnvelope = {
    contract?: string;
    company_id?: string;
    payloads_included?: boolean;
    generation?: string;
    from_cursor?: number;
    next_cursor?: number;
    high_watermark?: number;
    has_more?: boolean;
    events?: DataCenterReplayEvent[];
};
const RESOURCES = new Set(["branches", "loanProducts", "staff", "clients", "loans", "payments"]);
const ACTIONS = new Set(["created", "updated", "deleted"]);

export function validateDataCenterReplay(
    reply: DataCenterReplayEnvelope,
    expected: {companyId: string; generation: string; afterCursor: number},
): {nextCursor: number; hasMore: boolean} {
    if (!reply || reply.contract !== "loanhub.data-center-replay.v1" ||
        reply.company_id !== expected.companyId ||
        reply.payloads_included !== false ||
        reply.generation !== expected.generation ||
        !Number.isSafeInteger(expected.afterCursor) || expected.afterCursor < 0 ||
        reply.from_cursor !== expected.afterCursor ||
        !Number.isSafeInteger(reply.next_cursor) ||
        !Number.isSafeInteger(reply.high_watermark) ||
        typeof reply.has_more !== "boolean" ||
        !Array.isArray(reply.events) || reply.events.length > 200 ||
        reply.high_watermark! < expected.afterCursor) {
        throw new Error("Invalid Data Center replay envelope");
    }
    let cursor = expected.afterCursor;
    for (const event of reply.events) {
        if (!event || !Number.isSafeInteger(event.cursor) ||
            event.cursor !== ++cursor ||
            !RESOURCES.has(event.resource) ||
            !ACTIONS.has(event.action) ||
            typeof event.entity_id !== "string" || !event.entity_id ||
            (event.branch_id !== null && typeof event.branch_id !== "string")) {
            throw new Error("Invalid Data Center replay event");
        }
    }
    if (reply.next_cursor !== cursor ||
        reply.next_cursor! > reply.high_watermark! ||
        reply.has_more !== (cursor < reply.high_watermark!)) {
        throw new Error("Inconsistent Data Center replay pagination");
    }
    return {nextCursor: cursor, hasMore: reply.has_more};
}
