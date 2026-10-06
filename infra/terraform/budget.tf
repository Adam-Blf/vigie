# The project must cost nothing. A budget of 1 with an alert at 1 % of actual spend means
# the very first cent billed anywhere in the compartment sends an e-mail.
resource "oci_budget_budget" "vigie" {
  # Budgets can only live in the root compartment, whatever they target.
  compartment_id = var.tenancy_ocid
  display_name   = "vigie-zero-cost"
  description    = "Garde-fou : toute dépense sur le compartiment Vigie déclenche une alerte."
  amount         = var.budget_amount
  reset_period   = "MONTHLY"
  target_type    = "COMPARTMENT"
  targets        = [var.compartment_ocid]
  freeform_tags  = local.tags
}

resource "oci_budget_alert_rule" "first_cent" {
  budget_id      = oci_budget_budget.vigie.id
  display_name   = "vigie-first-cent"
  type           = "ACTUAL"
  threshold      = var.budget_alert_percent
  threshold_type = "PERCENTAGE"
  recipients     = var.budget_email
  message        = "Vigie : une dépense réelle a été constatée sur Oracle Cloud. Vérifier immédiatement."
  freeform_tags  = local.tags
}
