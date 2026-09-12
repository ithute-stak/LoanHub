import {
    createSlice,
    PayloadAction
} from "@reduxjs/toolkit";

import {
    Borrower,
    BorrowerCreateResponse
} from "@/types/borrower";

import {
    fetchBorrowers,
    fetchBorrowerById,
    createBorrower,
    updateBorrower,
    deleteBorrower
} from "@/store/features/thunks/borrowerThunks";


interface BorrowerState {

    borrowers: Borrower[];

    selectedBorrower:
        Borrower | null;

    createdBorrower:
        BorrowerCreateResponse | null;

    loading:boolean;

    actionLoadingId:
        string | null;

    error:string | null;
}


const initialState:BorrowerState={
    borrowers:[],
    selectedBorrower:null,
    createdBorrower:null,
    loading:false,
    actionLoadingId:null,
    error:null
};


const borrowerSlice=createSlice({

    name:"borrowers",

    initialState,

    reducers:{

        clearBorrowerError(
            state
        ){
            state.error=null;
        },

        setSelectedBorrower(
            state,
            action:PayloadAction<
                Borrower|null
            >
        ){

            state.selectedBorrower=
                action.payload;
        }

    },

    extraReducers:(builder)=>{

        builder

            .addCase(
                fetchBorrowerById.fulfilled,
                (state,action)=>{
                    state.selectedBorrower=
                        action.payload;
                }
            )

            .addCase(
                createBorrower.pending,
                (state)=>{
                    state.loading=true;
                    state.error=null;
                    state.createdBorrower=null;
                }
            )

            .addCase(
                createBorrower.fulfilled,
                (state,action)=>{
                    state.loading=false;
                    state.error=null;
                    state.createdBorrower=
                        action.payload;
                }
            )

            .addCase(
                createBorrower.rejected,
                (state,action)=>{
                    state.loading=false;
                    state.error=
                        action.payload ??
                        "Failed to create borrower";
                }
            )

            .addCase(
                updateBorrower.fulfilled,
                (state,action)=>{

                    const index=
                        state.borrowers.findIndex(
                            b=>b.id===
                                action.payload.id
                        );

                    if(index!==-1){

                        state.borrowers[index]=
                            action.payload;
                    }
                }
            )

            .addCase(
                fetchBorrowers.pending,
                (state) => {
                    state.loading = true;
                    state.error = null;
                },
            )

            .addCase(
                fetchBorrowers.rejected,
                (state, action) => {
                    state.loading = false;
                    state.error =
                        action.payload ??
                        "Failed to fetch borrowers";
                },
            )

            .addCase(
                deleteBorrower.fulfilled,
                (state,action)=>{

                    state.borrowers=
                        state.borrowers.filter(
                            b=>b.id!==action.payload
                        );
                }
            )

    }

});

export const {
    clearBorrowerError,
    setSelectedBorrower
}=borrowerSlice.actions;

export default borrowerSlice.reducer;
