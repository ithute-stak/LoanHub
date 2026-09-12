import { WorkspaceItemEditor } from "@/components/documents/workspace-item-editor";
export default async function PlatformDocumentEditorPage({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <WorkspaceItemEditor documentId={id} basePath="/platform/documents" mode="platform" />; }
