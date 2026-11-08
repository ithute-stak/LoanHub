"""Offline release provenance manifest: compares review artifacts, not live approval."""
from dataclasses import dataclass
import hashlib,hmac,re

class ManifestError(ValueError):pass

@dataclass(frozen=True,slots=True)
class ArtifactDigest:
    path:str
    sha256:str

@dataclass(frozen=True,slots=True)
class ReleaseManifest:
    git_commit:str
    artifacts:tuple[ArtifactDigest,...]
    security_review_ref:str
    provider_certification_refs:tuple[str,...]
    migration_approval_ref:str
    rollback_test_ref:str
    staging_test_ref:str
    deployment_authorized:bool=False

def verify_manifest(m:ReleaseManifest,actual_digests:dict[str,str])->None:
    if not isinstance(m,ReleaseManifest) or not re.fullmatch(r'[0-9a-f]{40}',m.git_commit):
        raise ManifestError('Pinned Git commit required')
    if m.deployment_authorized is not True:
        raise ManifestError('Release is not authorized')
    if not m.artifacts or len(m.artifacts)!=len(set(x.path for x in m.artifacts)):
        raise ManifestError('Missing or duplicate release files')
    if not all(isinstance(x,str) and len(x)>=8 for x in (
        m.security_review_ref,m.migration_approval_ref,m.rollback_test_ref,m.staging_test_ref)):
        raise ManifestError('Signed-off review evidence references required')
    if not m.provider_certification_refs or any(len(x)<8 for x in m.provider_certification_refs):
        raise ManifestError('Provider certification evidence required')
    for item in m.artifacts:
        if (not item.path or item.path.startswith('/') or '..' in item.path.split('/') or
            not re.fullmatch(r'[0-9a-f]{64}',item.sha256)):
            raise ManifestError('Unsafe artifact path or digest')
        actual=actual_digests.get(item.path)
        if not isinstance(actual,str) or not hmac.compare_digest(actual,item.sha256):
            raise ManifestError('Artifact changed since review')
