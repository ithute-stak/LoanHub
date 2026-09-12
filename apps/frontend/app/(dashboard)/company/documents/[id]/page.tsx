import { WorkspaceItemEditor } from "@/components/documents/workspace-item-editor";
export default async function CompanyDocumentEditorPage({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <WorkspaceItemEditor documentId={id} basePath="/company/documents" mode="company" />; }
