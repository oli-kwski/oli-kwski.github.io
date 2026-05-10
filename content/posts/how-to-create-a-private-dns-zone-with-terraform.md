---
title: "How to Create an Azure Private DNS Zone with Terraform"
date: 2026-04-30
draft: true
description: "Step-by-step Terraform for deploying an Azure Private DNS Zone, linking it to a VNet, and integrating it with Private Endpoints."

tags:
  - Networking
  - DNS
  - Private DNS
  - Terraform
  - IaC
series:
  - Private DNS

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

If you haven't read [What Is an Azure Private DNS Zone and Why Do You Need One?](/posts/what-is-a-private-dns-zone), start there. This post covers deploying a Private DNS Zone and VNet link with Terraform.

---

## Prerequisites

- Terraform CLI installed
- Azure CLI authenticated (`az login`)
- An existing VNet (or deploy one in the same config)

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
  features {}
}
```

## The Terraform

### 1. Create the Private DNS Zone

```hcl
variable "resource_group_name" {
  description = "Resource group to deploy the DNS zone into."
  type        = string
}

variable "dns_zone_name" {
  description = "Private DNS zone name, e.g. privatelink.blob.core.windows.net"
  type        = string
  default     = "privatelink.blob.core.windows.net"
}

resource "azurerm_private_dns_zone" "main" {
  name                = var.dns_zone_name
  resource_group_name = var.resource_group_name

  tags = {
    environment = "prod"
    managed_by  = "terraform"
  }
}
```

### 2. Link to a VNet

```hcl
variable "vnet_id" {
  description = "Resource ID of the VNet to link the zone to."
  type        = string
}

resource "azurerm_private_dns_zone_virtual_network_link" "main" {
  name                  = "link-${basename(var.vnet_id)}"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.main.name
  virtual_network_id    = var.vnet_id
  registration_enabled  = false  # Leave false for Private Endpoint zones

  tags = {
    environment = "prod"
    managed_by  = "terraform"
  }
}
```

### 3. As a reusable module

```hcl
# modules/private_dns_zone/main.tf

variable "resource_group_name" { type = string }
variable "dns_zone_name" { type = string }
variable "vnet_ids" {
  description = "Map of VNet names to resource IDs to link."
  type        = map(string)
  default     = {}
}
variable "tags" { type = map(string); default = {} }

resource "azurerm_private_dns_zone" "main" {
  name                = var.dns_zone_name
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "links" {
  for_each = var.vnet_ids

  name                  = "link-${each.key}"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.main.name
  virtual_network_id    = each.value
  registration_enabled  = false
  tags                  = var.tags
}

output "private_dns_zone_id"   { value = azurerm_private_dns_zone.main.id }
output "private_dns_zone_name" { value = azurerm_private_dns_zone.main.name }
```

Calling the module:

```hcl
module "blob_dns_zone" {
  source              = "./modules/private_dns_zone"
  resource_group_name = "rg-networking-prod"
  dns_zone_name       = "privatelink.blob.core.windows.net"
  vnet_ids = {
    hub = module.hub_vnet.vnet_id
  }
  tags = {
    environment = "prod"
    managed_by  = "terraform"
  }
}
```

### 4. Wiring to a Private Endpoint

The DNS zone group on the Private Endpoint registers the A record automatically:

```hcl
resource "azurerm_private_endpoint" "storage_blob" {
  name                = "pe-${var.storage_account_name}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.private_endpoint_subnet_id

  private_service_connection {
    name                           = "psc-${var.storage_account_name}"
    private_connection_resource_id = azurerm_storage_account.main.id
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [module.blob_dns_zone.private_dns_zone_id]
  }
}
```

## Deploying

```bash
terraform init
terraform plan \
  -var="resource_group_name=rg-networking-prod" \
  -var="vnet_id=/subscriptions/<sub>/resourceGroups/rg-networking-prod/providers/Microsoft.Network/virtualNetworks/vnet-prod-uksouth-001"
terraform apply
```

## Verifying

```bash
# List Private DNS Zones
az network private-dns zone list \
  --resource-group rg-networking-prod \
  --output table

# Check VNet links
az network private-dns link vnet list \
  --resource-group rg-networking-prod \
  --zone-name privatelink.blob.core.windows.net \
  --output table
```

Verify DNS resolution from inside the linked VNet:

```bash
nslookup yourstorageaccount.blob.core.windows.net
```

Expect the response to chain through `privatelink.blob.core.windows.net` and resolve to a private IP.

## Common gotchas

**1. `basename()` may not work as expected for VNet IDs**
The `basename(var.vnet_id)` trick extracts the VNet name from the resource ID for use in the link name. Test this locally — if the ID format changes or has a trailing slash, `basename` may return an empty string. A safer alternative: pass the VNet name as an explicit variable.

**2. `for_each` on VNet links allows multiple links in one module call**
Using `for_each` on the link resource means you can link one zone to multiple VNets in a single module call. This is useful in hub-and-spoke where you might link a zone to both the hub and a dedicated DNS resolver VNet.

**3. Destroying the DNS zone removes all A records**
If you `terraform destroy` a zone (or it's removed from state), all A records go with it. Private Endpoints that registered records in the zone will appear connected but won't resolve. Recreating the zone and zone groups on each endpoint restores the records — but that may mean redeploying endpoints.

**4. Zone name uniqueness per subscription**
Terraform will fail at `plan` time if you try to create a zone with the same name in the same subscription and resource group. If you're using modules that create zones, ensure zone creation is idempotent and centralised — use a data source to reference an existing zone rather than creating it in multiple places.

```hcl
data "azurerm_private_dns_zone" "blob" {
  name                = "privatelink.blob.core.windows.net"
  resource_group_name = "rg-networking-prod"
}
```

---

## Summary

Deploying a Private DNS Zone with Terraform is two resources: the zone and the VNet link. Wrap them in a module with a `for_each` on the link resource so you can attach to multiple VNets cleanly. Use `private_dns_zone_group` on Private Endpoint resources to handle A record registration automatically. Verify with `nslookup` from inside the VNet before signing off the deployment.
