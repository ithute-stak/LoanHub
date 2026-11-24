/**
 * A defensive contract gate for the *read-only* Batlokoa preview.
 *
 * This intentionally duplicates the reviewed field inventory. A backend
 * change MUST require a frontend review; otherwise the preview fails closed
 * instead of silently hiding a sensitive or mandatory field.
 */
import type {
  RegistrationAvailability,
  RegistrationFormRequirements,
} from "@/api/batlokoaRegistration";

const FIELDS_BY_SECTION: Readonly<Record<string, readonly string[]>> = {
  identity: [
    "branch_id", "first_name", "middle_name", "last_name", "gender",
    "date_of_birth", "national_id", "passport_number", "nationality",
    "marital_status", "phone", "email", "temporary_password",
  ],
  residence: ["district", "town_or_village", "physical_address"],
  employment: [
    "employment_status", "employment_type", "employer_name",
    "employer_group_id", "new_employer_group", "cdas_employee_number",
    "income_day", "job_title", "monthly_income", "salary_date",
  ],
  obligations: [
    "has_existing_loans", "existing_loan_total", "external_debts", "bank_account",
  ],
  consent: ["consent_to_share_profile", "consent_to_credit_checks"],
};

const DEFERRED = new Set([
  "email", "temporary_password", "employer_group_id",
  "new_employer_group", "cdas_employee_number",
]);
const REQUIRED = new Set([
  "branch_id", "first_name", "last_name", "phone", "gender",
  "date_of_birth", "district", "employment_status",
  "consent_to_share_profile", "consent_to_credit_checks",
]);
const SENSITIVE = new Set([
  "national_id", "passport_number", "date_of_birth", "phone", "email",
  "temporary_password", "physical_address", "monthly_income",
  "existing_loan_total", "external_debts", "bank_account",
  "cdas_employee_number",
]);
const KINDS: Readonly<Record<string, string>> = {
  gender: "select", marital_status: "select", employment_status: "select",
  date_of_birth: "date",
  has_existing_loans: "boolean", consent_to_share_profile: "boolean",
  consent_to_credit_checks: "boolean", monthly_income: "currency",
  existing_loan_total: "currency", income_day: "integer", email: "email",
  temporary_password: "password", branch_id: "uuid",
  employer_group_id: "uuid", external_debts: "debt_list",
  bank_account: "bank_account", new_employer_group: "employer_group",
};

const EXPECTED_IDS = Object.keys(FIELDS_BY_SECTION);
const EXPECTED_KEYS = EXPECTED_IDS.flatMap((id) => FIELDS_BY_SECTION[id]);
const EXPECTED_KEY_SET = new Set(EXPECTED_KEYS);

function exactSequence(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length &&
    left.every((value, index) => value === right[index]);
}

export function validateBatlokoaPreviewContract(
  availability: RegistrationAvailability,
  form: RegistrationFormRequirements,
): void {
  if (
    !availability ||
    !form ||
    availability.new_only_registration_available !== false ||
    availability.can_submit_new_only_registration !== false ||
    availability.requires_identity_migration_approval !== true ||
    availability.requires_independent_release_approval !== true ||
    availability.reason_code !== "NEW_ONLY_REGISTRATION_NOT_RELEASED" ||
    form.registration_available !== false ||
    form.submit_allowed !== false ||
    form.client_data_requested !== false ||
    form.schema_version !== 2 ||
    !Array.isArray(form.sections) ||
    !Array.isArray(form.field_details) ||
    !Array.isArray(form.identity_alternatives)
  ) {
    throw new Error("Batlokoa registration preview contract is not approved.");
  }
  if (!exactSequence(form.identity_alternatives, ["national_id", "passport_number"])) {
    throw new Error("Batlokoa identity requirements need independent review.");
  }
  if (
    form.sections.length !== EXPECTED_IDS.length ||
    form.field_details.length !== EXPECTED_KEYS.length ||
    !exactSequence(form.sections.map((s) => s.id), EXPECTED_IDS)
  ) {
    throw new Error("Batlokoa registration sections changed; review required.");
  }
  for (const section of form.sections) {
    if (
      typeof section.title !== "string" ||
      section.title.length === 0 ||
      !Array.isArray(section.fields) ||
      !Array.isArray(section.deferred_fields) ||
      !exactSequence(section.fields, FIELDS_BY_SECTION[section.id])
    ) {
      throw new Error("Batlokoa registration fields changed; review required.");
    }
    if (
      !exactSequence(
        section.deferred_fields,
        section.fields.filter((key) => DEFERRED.has(key)),
      )
    ) {
      throw new Error("Batlokoa deferred fields changed; review required.");
    }
  }
  const seen = new Set<string>();
  for (const item of form.field_details) {
    if (
      !item ||
      typeof item.key !== "string" ||
      !EXPECTED_KEY_SET.has(item.key) ||
      seen.has(item.key) ||
      item.kind !== (KINDS[item.key] ?? "text") ||
      item.deferred !== DEFERRED.has(item.key) ||
      item.required !== REQUIRED.has(item.key) ||
      item.sensitive !== SENSITIVE.has(item.key)
    ) {
      throw new Error("Batlokoa field validation metadata changed; review required.");
    }
    seen.add(item.key);
  }
  if (seen.size !== EXPECTED_KEY_SET.size) {
    throw new Error("Batlokoa registration metadata is incomplete.");
  }
}
