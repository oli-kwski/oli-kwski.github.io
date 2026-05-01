---
title: "How to Create an Azure Key Vault with Terraform"
date: 2026-04-30
draft: true
description: "Practical Terraform for deploying an Azure Key Vault with production-ready security defaults, RBAC, and Private Endpoint integration."

tags:
  - Azure
  - Security
  - Key Vault
  - Terraform
  - IaC
categories:
  - Azure
  - Security
series:
  - Key Vault
  - Terraform

comments: true
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: true
ShowPostNavLinks: true
ShowWordCount: false
---

If you haven't read [What Is Azure Key Vault and Why Should You Use It?](/posts/what-is-azure-key-vault), start there. This post covers deploying one with Terraform using a production-ready baseline.

---

## Prerequisites

- Terraform CLI installed
- Azure CLI authenticated

## Provider configuration

```hcl
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = false  # Don't purge on destroy in production
      recover_soft_deleted_key_vaults = true   # Recover if soft-deleted vault exists
    }
  }
}
```

## The Terraform

### Key Vault with security baseline

```hcl
data "azurerm_client_config" "current" {}

variable "resource_group_name" { type = string }
variable "location" { type = string; default = "uksouth" }
variable "key_vault_name" { type = string }

variable "soft_delete_retention_days" {
  description = "Soft delete retention period (7–90 days)."
  type        = number
  default     = 90
}

resource "azurerm_key_vault" "main" {
  name                = var.key_vault_name
  location            = var.location
  resource_group_name = var.resource_group_name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"  # "premium" for HSM-backed keys

  # Azure RBAC instead of vault access policies
  enable_rbac_authorization = true

  # Soft delete and purge protection
  soft_delete_retention_days = var.soft_delete_retention_days
  purge_protection_enabled   = true  # Irreversible

  # Network — disable public access
  public_network_access_enabled = false

  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"
    ip_rules       = []
  }

  tags = {
    environment = "prod"
    managed_by  = "terraform"
  }
}

# Grant the Terraform deploying principal Key Vault Administrator access
resource "azurerm_role_assignment" "deployer_admin" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Administrator"
  principal_id         = data.azurerm_client_config.current.object_id
}

output "key_vault_id"   { value = azurerm_key_vault.main.id }
output "key_vault_name" { value = azurerm_key_vault.main.name }
output "key_vault_uri"  { value = azurerm_key_vault.main.vault_uri }
```

### Adding secrets

```hcl
variable "db_connection_string" {
  description = "Database connection string to store as a secret."
  type        = string
  sensitive   = true  # Marks the value as sensitive in Terraform output
}

resource "azurerm_key_vault_secret" "db_connection" {
  name         = "db-connection-string"
  value        = var.db_connection_string
  key_vault_id = azurerm_key_vault.main.id
  content_type = "text/plain"

  depends_on = [azurerm_role_assignment.deployer_admin]
}
```

Mark variables holding secrets as `sensitive = true` — Terraform will redact them in plan and apply output.

### Granting a managed identity read access

```hcl
variable "app_managed_identity_object_id" {
  description = "Object ID of the managed identity needing secret read access."
  type        = string
}

resource "azurerm_role_assignment" "app_secrets_user" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = var.app_managed_identity_object_id
}
```

### Private Endpoint

```hcl
resource "azurerm_private_endpoint" "key_vault" {
  name                = "pe-${var.key_vault_name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.private_endpoint_subnet_id

  private_service_connection {
    name                           = "psc-${var.key_vault_name}"
    private_connection_resource_id = azurerm_key_vault.main.id
    subresource_names              = ["vault"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [var.key_vault_private_dns_zone_id]
  }
}
```

The Private DNS Zone for Key Vault is `privatelink.vaultcore.azure.net`.

## Deploying

```bash
terraform init

# Pass the connection string via environment variable to avoid it appearing in shell history
export TF_VAR_db_connection_string="Server=sql-prod.database.windows.net;..."

terraform plan \
  -var="resource_group_name=rg-security-prod" \
  -var="key_vault_name=kv-prod-uksouth-001"

terraform apply
```

## Verifying

```bash
az keyvault show \
  --resource-group rg-security-prod \
  --name kv-prod-uksouth-001 \
  --query '{publicNetworkAccess: properties.publicNetworkAccess, rbac: properties.enableRbacAuthorization, purgeProtection: properties.enablePurgeProtection}' \
  --output table
```

## Common gotchas

**1. `purge_soft_delete_on_destroy` in the provider features block**
By default in AzureRM provider, `purge_soft_delete_on_destroy = true`. This means running `terraform destroy` will permanently purge the vault immediately, bypassing soft delete. This is useful in dev but dangerous in production. Override it to `false` in production configurations.

**2. `recover_soft_deleted_key_vaults = true` can cause unexpected imports**
If a vault with the same name exists in soft-deleted state, Terraform will recover and import it rather than creating a new one. This is usually the right behaviour, but be aware that the recovered vault may have different properties than what your config specifies — the provider will then apply your config to update it.

**3. RBAC propagation delay affects `azurerm_key_vault_secret`**
When Terraform creates the vault and the admin role assignment in the same apply, there's a race condition: the secret resource may fail if role propagation hasn't completed before Terraform tries to write the secret. The `depends_on = [azurerm_role_assignment.deployer_admin]` in the secret resource helps, but Azure's IAM propagation is eventually consistent and may still occasionally fail on first apply. A retry usually succeeds.

**4. Sensitive variables and state file**
Even with `sensitive = true` on a variable, the value is stored in plain text in the Terraform state file. Use a remote backend with encryption (Azure Blob Storage with CMK, or Terraform Cloud) and restrict access to the state file as you would to the secret itself.

**5. Key Vault soft-deleted vaults hold the name for 90 days**
If you destroy a vault and try to create a new one with the same name in the same region, Terraform will fail unless it can recover the soft-deleted vault. Use `purge_soft_delete_on_destroy = true` in dev environments where vault churn is expected, and plan vault naming to avoid this in production.

---

## Summary

Key Vault with Terraform is a clean deployment once you understand the provider `features` block and the soft delete/purge protection lifecycle. Use `sensitive = true` on secret variables, `depends_on` on secret resources to handle RBAC propagation, and set `purge_soft_delete_on_destroy = false` in production. Assign `Key Vault Secrets User` (not Administrator) to managed identities, and deploy a Private Endpoint for fully private access.
