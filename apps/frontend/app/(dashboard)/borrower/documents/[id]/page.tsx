import { WorkspaceItemEditor } from "@/components/documents/workspace-item-editor";
export default async function BorrowerDocumentEditorPage({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <WorkspaceItemEditor documentId={id} basePath="/borrower/documents" mode="borrower" />; }
