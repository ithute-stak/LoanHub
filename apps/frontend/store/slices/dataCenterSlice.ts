/** Prepared Data Center boundary; feature remains disabled until server-side
 * authorized projection endpoints, replay, and full integration tests pass.
 * State is intentionally memory-only and never persisted to browser storage.
 */
export type DataCenterScope = {
    userId: string;
    companyId: string;
    role: string;
    branchId: string | null;
};
export type DataCenterState = {
    sessionId: string | null;
    scope: DataCenterScope | null;
    cursor: number | null;
    ready: boolean;
};
export const initialDataCenterState: DataCenterState = {
    sessionId: null,
    scope: null,
    cursor: null,
    ready: false,
};
export type DataCenterAction =
    | { type: "dataCenter/sessionCleared"; payload: { sessionId: string } }
    | { type: "dataCenter/connectionLost"; payload: { sessionId: string } };

export const dataCenterActions = {
    clear: (sessionId: string): DataCenterAction => ({
        type: "dataCenter/sessionCleared",
        payload: { sessionId },
    }),
    disconnected: (sessionId: string): DataCenterAction => ({
        type: "dataCenter/connectionLost",
        payload: { sessionId },
    }),
};

/** No record-bearing install action is exposed until the production
 * authorization and sanitization contract has passed its release gate.
 * Unrecognized actions are deliberately ignored.
 */
export default function dataCenterReducer(
    state: DataCenterState = initialDataCenterState,
    action: DataCenterAction | { type: string; payload?: unknown },
): DataCenterState {
    if (
        action.type === "dataCenter/sessionCleared" &&
        state.sessionId !== null &&
        (action as DataCenterAction).payload.sessionId === state.sessionId
    ) {
        return initialDataCenterState;
    }
    if (
        action.type === "dataCenter/connectionLost" &&
        state.sessionId !== null &&
        (action as DataCenterAction).payload.sessionId === state.sessionId
    ) {
        return { ...state, ready: false };
    }
    return state;
}
