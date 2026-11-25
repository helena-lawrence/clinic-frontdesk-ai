#!/usr/bin/env bash
set -euo pipefail
umask 077

destroy_plan="$RUNNER_TEMP/destroy.plan"
prepare_plan="$RUNNER_TEMP/prepare.plan"

# Select only existing protected resources, including on retries after a partial teardown.
terraform show -json "$destroy_plan" | jq -r '
  .resource_changes[]? | select(.change.actions == ["delete"]) | .address |
  select(. == "aws_db_instance.clinic" or . == "aws_ecr_repository.api" or
         . == "aws_ecr_repository.ui" or . == "aws_ecr_repository.predictor")
' > "$RUNNER_TEMP/prepare-targets"
targets=()
while IFS= read -r address; do
  targets+=("-target=$address")
done < "$RUNNER_TEMP/prepare-targets"

if (( ${#targets[@]} )); then
  terraform plan -lock-timeout=5m "${targets[@]}" -out="$prepare_plan"
  # Targeted plans can include dependencies. Reject creations, replacements and
  # unrelated updates before applying changes that disable deletion protection.
  terraform show -json "$prepare_plan" | jq -e '
    def changed_keys: . as $c | (($c.before + $c.after) | keys) |
      map(select($c.after_unknown[.] != true and $c.before[.] != $c.after[.]));
    all(.resource_changes[]? | select(.mode == "managed" and .change.actions != ["no-op"]);
      .change.actions == ["update"] and
      (if .address == "aws_db_instance.clinic" then
         (.change | changed_keys - ["deletion_protection", "skip_final_snapshot", "apply_immediately"]) == []
       elif (.address | test("^aws_ecr_repository\\.(api|ui|predictor)$")) then
         (.change | changed_keys - ["force_delete"]) == []
       else false end))
  ' >/dev/null || { echo "::error::Unexpected preparation changes. Review the Terraform plan."; exit 1; }
  terraform apply -lock-timeout=5m "$prepare_plan"
  terraform plan -destroy -lock-timeout=5m -out="$destroy_plan"
fi

terraform apply -lock-timeout=5m "$destroy_plan"
remaining=$(terraform state list)
if [[ -n "$remaining" ]]; then
  printf 'Terraform still tracks these addresses:\n%s\n' "$remaining" >&2
  exit 1
fi
echo "Teardown complete. The production Terraform state is empty." >> "$GITHUB_STEP_SUMMARY"
