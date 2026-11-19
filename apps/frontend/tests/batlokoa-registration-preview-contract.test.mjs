/* Run: node --test tests/batlokoa-registration-preview-contract.test.mjs
 * Tests the actual TypeScript guard using TypeScript's transpiler. No network.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

const path = new URL("../lib/batlokoa-registration-preview-contract.ts", import.meta.url);
const source = readFileSync(path, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
const exports = {};
runInNewContext(compiled, { exports, Set, Error, Object, Array });
const validate = exports.validateBatlokoaPreviewContract;
assert.equal(typeof validate, "function");

const sections = [
  ["identity", ["branch_id","first_name","middle_name","last_name","gender","date_of_birth","national_id","passport_number","nationality","marital_status","phone","email","temporary_password"]],
  ["residence", ["district","town_or_village","physical_address"]],
  ["employment", ["employment_status","employment_type","employer_name","employer_group_id","new_employer_group","cdas_employee_number","income_day","job_title","monthly_income","salary_date"]],
  ["obligations", ["has_existing_loans","existing_loan_total","external_debts","bank_account"]],
  ["consent", ["consent_to_share_profile","consent_to_credit_checks"]],
];
const deferred = new Set(["email","temporary_password","employer_group_id","new_employer_group","cdas_employee_number"]);
const required = new Set(["branch_id","first_name","last_name","phone","gender","date_of_birth","district","employment_status","consent_to_share_profile","consent_to_credit_checks"]);
const sensitive = new Set(["national_id","passport_number","date_of_birth","phone","email","temporary_password","physical_address","monthly_income","existing_loan_total","external_debts","bank_account","cdas_employee_number"]);
const kindMap = {
  gender:"select",marital_status:"select",employment_status:"select",
  date_of_birth:"date",has_existing_loans:"boolean",
  consent_to_share_profile:"boolean",consent_to_credit_checks:"boolean",
  monthly_income:"currency",existing_loan_total:"currency",
  income_day:"integer",email:"email",temporary_password:"password",
  branch_id:"uuid",employer_group_id:"uuid",
  external_debts:"debt_list",bank_account:"bank_account",
  new_employer_group:"employer_group",
};
function specimen() {
  const availability = {
    new_only_registration_available: false,
    can_submit_new_only_registration: false,
    requires_identity_migration_approval: true,
    requires_independent_release_approval: true,
    reason_code: "NEW_ONLY_REGISTRATION_NOT_RELEASED",
  };
  const form = {
    schema_version: 2,
    identity_alternatives: ["national_id", "passport_number"],
    field_details: sections.flatMap(([, fields]) =>
      fields.map((key) => ({
        key, kind: kindMap[key] ?? "text",
        required: required.has(key), deferred: deferred.has(key),
        sensitive: sensitive.has(key),
      }))),
    registration_available: false, submit_allowed: false,
    client_data_requested: false,
    sections: sections.map(([id, fields]) => ({
      id, title: id, fields: [...fields],
      deferred_fields: fields.filter((key) => deferred.has(key)),
    })),
  };
  return {availability, form};
}
function passes(pair) {
  validate(pair.availability, pair.form);
}
function rejects(edit) {
  const pair = specimen();
  edit(pair);
  assert.throws(() => passes(pair), /review|contract|incomplete|changed|approved/);
}

test("complete reviewed read-only contract succeeds", () => passes(specimen()));
test("future availability or submit flag cannot activate the preview", () => {
  rejects((p) => {p.availability.can_submit_new_only_registration = true;});
  rejects((p) => {p.form.submit_allowed = true;});
  rejects((p) => {p.form.registration_available = true;});
  rejects((p) => {p.form.client_data_requested = true;});
});
test("unreviewed field, type, or section changes fail closed", () => {
  rejects((p) => {p.form.schema_version = 3;});
  rejects((p) => {p.form.sections[0].fields.pop();});
  rejects((p) => {p.form.sections[1].fields.push("new_unreviewed_field");});
  rejects((p) => {p.form.field_details[0].kind = "password";});
  rejects((p) => {p.form.field_details.pop();});
});
test("privacy, deferred fields, required consent and identity rules are enforced", () => {
  rejects((p) => {p.form.identity_alternatives.pop();});
  rejects((p) => {p.form.sections[0].deferred_fields.pop();});
  rejects((p) => {p.form.field_details.find((f)=>f.key==="national_id").sensitive = false;});
  rejects((p) => {p.form.field_details.find((f)=>f.key==="consent_to_credit_checks").required = false;});
});
