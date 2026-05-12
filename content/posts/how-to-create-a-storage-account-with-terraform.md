---
title: "How to Create an Azure Storage Account with Terraform"
date: 2026-04-30
draft: true
description: "A practical Terraform configuration for deploying a production-ready Azure Storage account with security defaults baked in."

tags:
  - Storage Account
  - Terraform
  - IaC
series:
  - Storage Accounts

comments: true
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: true
ShowPostNavLinks: true
ShowWordCount: false

cover:
  image: /covers/iac.svg
  alt: Infrastructure as Code
  relative: false
weight: 3
---

If you haven't read [What Is an Azure Storage Account and When Should You Use One?](/posts/what-is-a-storage-account), start there. This post covers deploying one with Terraform using a production-ready security baseline.

---

## Prerequisites

- Terraform CLI installed
- Azure CLI authenticated (`az login`)

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
    storage {
      # Prevent accidental deletion of storage accounts
      prevent_accidental_purge = true  # Available in azurerm >= 3.x
    }
  }
}
```

## The Terraform

```hcl
variable "location" {
  type    = string
  default = "uksouth"
}

variable "resource_group_name" {
  type = string
}

variable "storage_account_name" {
  description = "3-24 lowercase alphanumeric characters."
  type        = string
}

variable "account_replication_type" {
  description = "LRS, ZRS, GRS, GZRS, RA-GRS, RA-GZRS"
  type        = string
  default     = "ZRS"
}

variable "enable_hierarchical_namespace" {
  description = "Enable Data Lake Gen2. Cannot be changed after creation."
  type        = bool
  default     = false
}

resource "azurerm_storage_account" "main" {
  name                     = var.storage_account_name
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = var.account_replication_type
  account_kind             = "StorageV2"

  # Security baseline
  https_traffic_only_enabled       = true
  min_tls_version                  = "TLS1_2"
  allow_nested_items_to_be_public  = false
  shared_access_key_enabled        = false   # Require Azure AD auth
  public_network_access_enabled    = false   # Use Private Endpoints

  # Data Lake Gen2 (cannot be changed after creation)
  is_hns_enabled = var.enable_hierarchical_namespace

  network_rules {
    default_action = "Deny"
    bypass         = ["AzureServices"]
    ip_rules       = []
  }

  blob_properties {
    delete_retention_policy {
      days = 7
    }
    container_delete_retention_policy {
      days = 7
    }
    versioning_enabled = true
  }

  tags = {
    environment = "prod"
    managed_by  = "terraform"
  }
}

# Optional: create a blob container
resource "azurerm_storage_container" "data" {
  name                  = "data"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "private"
}

output "storage_account_id"           { value = azurerm_storage_account.main.id }
output "storage_account_name"         { value = azurerm_storage_account.main.name }
output "primary_blob_endpoint"        { value = azurerm_storage_account.main.primary_blob_endpoint }
```

## Deploying

```bash
terraform init
terraform plan \
  -var="resource_group_name=rg-storage-prod" \
  -var="storage_account_name=stproduksouth001"
terraform apply \
  -var="resource_group_name=rg-storage-prod" \
  -var="storage_account_name=stproduksouth001"
```

## Adding a Private Endpoint

```hcl
resource "azurerm_private_endpoint" "blob" {
  name                = "pe-${var.storage_account_name}-blob"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.private_endpoint_subnet_id

  private_service_connection {
    name                           = "psc-${var.storage_account_name}-blob"
    private_connection_resource_id = azurerm_storage_account.main.id
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [var.blob_private_dns_zone_id]
  }
}
```

## Assigning RBAC

With shared key access disabled, managed identities need RBAC roles:

```hcl
data "azurerm_role_definition" "blob_contributor" {
  name = "Storage Blob Data Contributor"
}

resource "azurerm_role_assignment" "app_blob_access" {
  scope                = azurerm_storage_account.main.id
  role_definition_id   = data.azurerm_role_definition.blob_contributor.id
  principal_id         = var.app_managed_identity_principal_id
}
```

## Verifying

```bash
az storage account show \
  --resource-group rg-storage-prod \
  --name stproduksouth001 \
  --query '{publicNetworkAccess: publicNetworkAccess, httpsOnly: enableHttpsTrafficOnly, tls: minimumTlsVersion, sharedKey: allowSharedKeyAccess}' \
  --output table
```

## Common gotchas

**1. Attribute name changes between AzureRM provider versions**
The `enable_https_traffic_only` attribute was renamed to `https_traffic_only_enabled` in AzureRM provider v4.x. Similarly `enable_hns` became `is_hns_enabled`. If you're upgrading provider versions, check the changelog — several storage account attributes were renamed or removed. Pin your provider version and review release notes before upgrading.

**2. `shared_access_key_enabled = false` breaks `azurerm_storage_container` data sources**
Terraform's `azurerm_storage_container` data source and some storage-related data sources use shared key auth internally. With shared key disabled, these data sources may fail during plan or apply. Work around this by referencing container names as variables rather than looking them up via data sources.

**3. `public_network_access_enabled = false` causes immediate connectivity loss**
If you're retrofitting this to an existing storage account that clients are actively using, setting this to `false` will immediately block all public traffic. Ensure Private Endpoints are in place and verified before applying this change to existing accounts.

**4. Versioning + lifecycle policies**
If you enable `versioning_enabled = true`, add a lifecycle management policy or costs will grow. Terraform can manage lifecycle rules via `azurerm_storage_management_policy`:

```hcl
resource "azurerm_storage_management_policy" "main" {
  storage_account_id = azurerm_storage_account.main.id

  rule {
    name    = "delete-old-versions"
    enabled = true
    filters {
      blob_types = ["blockBlob"]
    }
    actions {
      version {
        delete_after_days_since_creation = 30
      }
    }
  }
}
```

---

## Summary

Deploying a storage account with Terraform is clean once you know which attributes map to which portal settings. The security baseline — no public access, shared key disabled, HTTPS enforced, soft delete and versioning on — should be your default for every storage account in production. Pin the AzureRM provider version and read the release notes when upgrading; storage account attributes have been renamed between major versions.
