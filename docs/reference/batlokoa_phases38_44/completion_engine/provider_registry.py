"""Fail-closed provider configuration; no live credentials/SDKs included."""
from dataclasses import dataclass
from typing import Mapping
from remaining_engine.contracts import ContractError

@dataclass(frozen=True, slots=True)
class ProviderConfiguration:
    provider_id: str
    adapter_id: str
    collections_enabled: bool
    payouts_enabled: bool
    sandbox_only: bool
    callback_verifier_certified: bool
    endpoint_tls_pinned_or_verified: bool
    merchant_owned_by_company: bool
    master_merchant_authorized: bool = False

def select_collection_provider(config: ProviderConfiguration, *, live: bool=False):
    if not isinstance(config, ProviderConfiguration) or not config.provider_id or not config.adapter_id:
        raise ContractError('Provider identity required')
    if not config.collections_enabled or not config.callback_verifier_certified:
        raise ContractError('Provider unavailable or unverified')
    if not config.endpoint_tls_pinned_or_verified:
        raise ContractError('TLS verification required')
    if not (config.merchant_owned_by_company or config.master_merchant_authorized):
        raise ContractError('Merchant custody authorization missing')
    if live and config.sandbox_only:
        raise ContractError('Sandbox provider cannot be used live')
    if live:
        # This offline package cannot certify real providers by itself.
        raise ContractError('Live providers require deployment-specific certification')
    return config.adapter_id

def assert_preserves_direct_mpesa(configs: Mapping[str, ProviderConfiguration]):
    # Config registry must not drop existing direct M-PESA in favor of Golink.
    if 'direct_mpesa' not in configs:
        raise ContractError('Existing direct M-PESA integration must remain registered')
    if configs['direct_mpesa'].provider_id != 'direct_mpesa':
        raise ContractError('Direct M-PESA provider binding changed')
