import { WorkspaceItemEditor } from "@/components/documents/workspace-item-editor";
export default async function SuperAdminDocumentEditorPage({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <WorkspaceItemEditor documentId={id} basePath="/superadmin/documents" mode="superadmin" />; }
