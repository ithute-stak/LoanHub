import { api } from "@/lib/api";

/**
 * Batlokoa's protected *new-only* registration pathway is not released.
 * These are read-only endpoints. NEVER fall back to POST /company-clients,
 * which uses a separate legacy assisted registration pathway.
 */
export type RegistrationAvailability = {
  new_only_registration_available: false;
  can_submit_new_only_registration: false;
  requires_identity_migration_approval: boolean;
  requires_independent_release_approval: boolean;
  reason_code: string;
};

export type RegistrationFormSection = {
  id: string;
  title: string;
  fields: string[];
  deferred_fields: string[];
};

export type RegistrationFormRequirements = {
  schema_version: number;
  registration_available: false;
  submit_allowed: false;
  client_data_requested: false;
  sections: RegistrationFormSection[];
};

export async function getBatlokoaRegistrationAvailability(): Promise<RegistrationAvailability> {
  const result = await api.get<RegistrationAvailability>(
    "/batlokoa/registration/availability",
  );
  return result.data;
}

export async function getBatlokoaRegistrationFormRequirements(): Promise<RegistrationFormRequirements> {
  const result = await api.get<RegistrationFormRequirements>(
    "/batlokoa/registration/form-requirements",
  );
  return result.data;
}

export function isBatlokoaRegistrationPreviewOnly(
  availability: RegistrationAvailability,
  requirements: RegistrationFormRequirements,
): boolean {
  // The client NEVER implements or attempts a new-only registration write.
  // Never use this flag to choose a legacy assisted-registration endpoint.
  return (
    availability.can_submit_new_only_registration === false &&
    availability.new_only_registration_available === false &&
    requirements.submit_allowed === false &&
    requirements.registration_available === false &&
    requirements.client_data_requested === false
  );
}
