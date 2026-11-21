/** Memory-only authorized directory projections for LoanHub.
 * This reducer is inert until a server-authorized snapshot/replay transport is
 * connected and release gates pass. Do not persist this reducer to storage.
 */
export type DirectoryKind = 'clients' | 'loans' | 'payments' | 'branches' | 'staff' | 'loanProducts';
export type DirectoryScope = Readonly<{
    userId: string;
    companyId: string;
    role: string;
    branchId: string | null;
}>;
export type SafeRow = Readonly<Record<string, string | null | undefined> & { id: string; company_id: string }>;
export type DirectoryBucket = Readonly<{ ids: readonly string[]; byId: Readonly<Record<string, SafeRow>> }>;
export type DirectoryProjection = Readonly<{
    scope: DirectoryScope;
    cursor: number;
    ready: boolean;
    buckets: Readonly<Record<DirectoryKind, DirectoryBucket>>;
}>;
export type DataCenterState = Readonly<{
    sessionId: string | null;
    scope: DirectoryScope | null;
    cursor: number | null;
    ready: boolean;
    buckets: Readonly<Partial<Record<DirectoryKind, DirectoryBucket>>>;
}>;

type ProjectionAction = {
    type: 'dataCenter/verifiedSnapshotInstalled' | 'dataCenter/verifiedProjectionCommitted';
    payload: { sessionId: string; projection: DirectoryProjection };
};
type ClearAction = { type: 'dataCenter/sessionRevoked'; payload: { sessionId: string } };
type ConnectionLost = { type: 'dataCenter/connectionLost'; payload: { sessionId: string } };
type Action = ProjectionAction | ClearAction | ConnectionLost | { type: string; payload?: unknown };
const KINDS: readonly DirectoryKind[] = ['clients', 'loans', 'payments', 'branches', 'staff', 'loanProducts'];
const SAFE_FIELDS: Readonly<Record<DirectoryKind, readonly string[]>> = {
    clients: ['id','company_id','branch_id','account_reference','full_name','status','updated_at'],
    loans: ['id','company_id','branch_id','loan_reference','status','updated_at'],
    payments: ['id','company_id','branch_id','loan_id','status','updated_at'],
    branches: ['id','company_id','branch_id','name','code','status','updated_at'],
    staff: ['id','company_id','branch_id','display_name','role','status','updated_at'],
    loanProducts: ['id','company_id','branch_id','name','status','updated_at'],
};
const blank = (): DataCenterState => ({sessionId:null,scope:null,cursor:null,ready:false,buckets:{}});
const own = (obj: object,key: string) => Object.prototype.hasOwnProperty.call(obj,key);
const validScope = (scope: DirectoryScope): boolean =>
    !!scope && typeof scope.userId === 'string' && !!scope.userId.trim() &&
    typeof scope.companyId === 'string' && !!scope.companyId.trim() &&
    typeof scope.role === 'string' && !!scope.role.trim() &&
    (scope.branchId === null || (typeof scope.branchId === 'string' && !!scope.branchId.trim()));
const scopeKey = (scope: DirectoryScope | null) => scope &&
    JSON.stringify([scope.userId,scope.companyId,scope.role,scope.branchId]);

/** No record is accepted merely because an action claims it is authorized.
 * Every resource and field is checked against the directory-only allowlist.
 * The FastAPI server must independently authorize projection construction.
 */
function validated(projection: DirectoryProjection): {scope:DirectoryScope;cursor:number;ready:boolean;buckets:DataCenterState['buckets']} | null {
    if (!projection || !validScope(projection.scope) ||
        !Number.isSafeInteger(projection.cursor) || projection.cursor < 0 ||
        typeof projection.ready !== 'boolean' || !projection.buckets ||
        typeof projection.buckets !== 'object' || Array.isArray(projection.buckets) ||
        Object.keys(projection.buckets).length !== KINDS.length ||
        Object.keys(projection.buckets).some(k => !KINDS.includes(k as DirectoryKind))) return null;
    const buckets: Partial<Record<DirectoryKind, DirectoryBucket>> = {};
    for (const kind of KINDS) {
        const bucket = projection.buckets[kind];
        if (!bucket || !Array.isArray(bucket.ids) || !bucket.byId ||
            typeof bucket.byId !== 'object' || Array.isArray(bucket.byId) ||
            bucket.ids.length > 200000 || Object.keys(bucket.byId).length !== bucket.ids.length ||
            new Set(bucket.ids).size !== bucket.ids.length) return null;
        const byId: Record<string, SafeRow> = Object.create(null);
        for (const id of bucket.ids) {
            if (typeof id !== 'string' || !id || !own(bucket.byId,id)) return null;
            const row = bucket.byId[id];
            if (!row || typeof row !== 'object' || Array.isArray(row) ||
                row.id !== id || row.company_id !== projection.scope.companyId ||
                (projection.scope.branchId !== null && row.branch_id !== projection.scope.branchId) ||
                Object.keys(row).some(k => !SAFE_FIELDS[kind].includes(k)) ||
                Object.values(row).some(v => v !== null && v !== undefined && typeof v !== 'string')) return null;
            byId[id] = {...row};
        }
        buckets[kind] = {ids:[...bucket.ids],byId};
    }
    return {scope:{...projection.scope},cursor:projection.cursor,ready:projection.ready,buckets};
}
export const dataCenterActions = {
    install: (sessionId:string,projection:DirectoryProjection):ProjectionAction => ({
        type:'dataCenter/verifiedSnapshotInstalled',payload:{sessionId,projection},
    }),
    commit: (sessionId:string,projection:DirectoryProjection):ProjectionAction => ({
        type:'dataCenter/verifiedProjectionCommitted',payload:{sessionId,projection},
    }),
    clear: (sessionId:string):ClearAction => ({type:'dataCenter/sessionRevoked',payload:{sessionId}}),
    disconnected: (sessionId:string):ConnectionLost => ({type:'dataCenter/connectionLost',payload:{sessionId}}),
};
export default function dataCenterReducer(state:DataCenterState=blank(),action:Action={type:''}):DataCenterState {
    if (action.type === 'dataCenter/sessionRevoked' &&
        (action as ClearAction).payload?.sessionId === state.sessionId && state.sessionId !== null) return blank();
    if (action.type === 'dataCenter/connectionLost' &&
        (action as ConnectionLost).payload?.sessionId === state.sessionId && state.sessionId !== null)
        return {...state,ready:false};
    if (action.type !== 'dataCenter/verifiedSnapshotInstalled' &&
        action.type !== 'dataCenter/verifiedProjectionCommitted') return state;
    const payload = (action as ProjectionAction).payload;
    if (!payload || typeof payload.sessionId !== 'string' || !payload.sessionId.trim()) return state;
    const next = validated(payload.projection);
    if (!next || !next.ready) return state;
    if (action.type === 'dataCenter/verifiedSnapshotInstalled') {
        // The old session must explicitly clear before another session can start.
        if (state.sessionId && state.sessionId !== payload.sessionId) return state;
        if (state.sessionId && (scopeKey(state.scope) !== scopeKey(next.scope) ||
            (state.cursor !== null && next.cursor < state.cursor))) return state;
        return {...next,sessionId:payload.sessionId};
    }
    if (state.sessionId !== payload.sessionId || scopeKey(state.scope) !== scopeKey(next.scope) ||
        state.cursor === null || next.cursor <= state.cursor) return state;
    return {...next,sessionId:payload.sessionId};
}
export function selectVerifiedDirectory(root:{dataCenter:DataCenterState},kind:DirectoryKind) {
    const state = root.dataCenter;
    if (!KINDS.includes(kind) || !state.ready || !state.sessionId) return {records:[] as SafeRow[],current:false};
    const bucket = state.buckets[kind];
    return {records:bucket?.ids.map(id => ({...bucket.byId[id]})) ?? [],current:true};
}