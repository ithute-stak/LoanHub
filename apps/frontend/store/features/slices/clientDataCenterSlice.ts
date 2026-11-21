import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { CompanyClient } from "@/types/companyClient";

type ScopeClients = {
    byId: Record<string, CompanyClient>;
    ids: string[];
    directoryLoaded: boolean;
};
type ClientDataCenterState = { scopes: Record<string, ScopeClients> };
const initialState: ClientDataCenterState = { scopes: {} };

const clientDataCenterSlice = createSlice({
    name: "clientDataCenter",
    initialState,
    reducers: {
        clientsReceived(state, action: PayloadAction<{
            scope: string;
            clients: CompanyClient[];
            completeDirectory?: boolean;
        }>) {
            const { scope, clients, completeDirectory } = action.payload;
            const bucket = state.scopes[scope] ??= { byId: {}, ids: [], directoryLoaded: false };
            for (const client of clients) {
                if (!bucket.byId[client.id]) bucket.ids.push(client.id);
                bucket.byId[client.id] = client;
            }
            if (completeDirectory) {
                // Replacing a complete list removes records no longer visible.
                const nextIds = clients.map((client) => client.id);
                const nextById: Record<string, CompanyClient> = {};
                for (const client of clients) nextById[client.id] = client;
                bucket.ids = nextIds;
                bucket.byId = nextById;
                bucket.directoryLoaded = true;
            }
        },
        clientDataCenterCleared(state) {
            state.scopes = {};
        },
        clientScopeCleared(state, action: PayloadAction<string>) {
            delete state.scopes[action.payload];
        },
    },
});

export const { clientsReceived, clientDataCenterCleared, clientScopeCleared } = clientDataCenterSlice.actions;
export default clientDataCenterSlice.reducer;
