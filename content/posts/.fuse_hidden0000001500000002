---
title: "How to Create an Azure VNet with Terraform"
date: 2026-04-30
draft: true
description: "A practical guide to deploying an Azure Virtual Network and subnets using Terraform, with the AzureRM provider."

tags:
  - Azure
  - Networking
  - VNet
  - Terraform
  - IaC
categories:
  - Azure
  - Networking
series:
  - Virtual Networks

comments: true
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: true
ShowPostNavLinks: true
ShowWordCount: false

cover:
  image: /covers/networking.svg
  alt: Azure Networking
  relative: false
weight: 3
---

If you haven't read [What Is an Azure Virtual Network?](/posts/what-is-a-vnet), start there. This post covers deploying a VNet with Terraform using the AzureRM provider.

---

## Prerequisites

- Terraform CLI installed (`terraform -v`)
- Azure CLI installed and authenticated (`az login`)
- AzureRM provider configured

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

A VNet with two subnets — workloads and private endpoints:

```hcl
variable "location" {
  description = "Azure region."
  type        = string
  default     = "uksouth"
}

variable "resource_group_name" {
  description = "Name of the resource group."
  type        = string
}

variable "vnet_name" {
  description = "Name of the VNet."
  type        = string
  default     = "vnet-prod-uksouth-001"
}

variable "vnet_address_space" {
  description = "Address space for the VNet."
  type        = list(string)
  default     = ["10.0.0.0/16"]
}

resource "azurerm_resource_group" "networking" {
  name     = var.resource_group_name
  location = var.location
}

resource "azurerm_virtual_network" "main" {
  name                = var.vnet_name
  location            = azurerm_resource_group.networking.location
  resource_group_name = azurerm_resource_group.networking.name
  address_space       = var.vnet_address_space

  # Optional: override DNS servers
  # dns_servers = ["10.0.0.4"]

  tags = {
    environment = "prod"
    managed_by  = "terraform"
  }
}

resource "azurerm_subnet" "workloads" {
  name                 = "snet-workloads"
  resource_group_name  = azurerm_resource_group.networking.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.1.0/24"]
}

resource "azurerm_subnet" "private_endpoints" {
  name                 = "snet-private-endpoints"
  resource_group_name  = azurerm_resource_group.networking.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.2.0/24"]

  # Enable NSG support on the Private Endpoint subnet
  private_endpoint_network_policies = "Enabled"
}

output "vnet_id" {
  value = azurerm_virtual_network.main.id
}

output "subnet_ids" {
  value = {
    workloads        = azurerm_subnet.workloads.id
    private_endpoints = azurerm_subnet.private_endpoints.id
  }
}
```

## Deploying

```bash
terraform init
terraform plan -var="resource_group_name=rg-networking-prod"
terraform apply -var="resource_group_name=rg-networking-prod"
```

Or use a `terraform.tfvars` file:

```hcl
resource_group_name = "rg-networking-prod"
vnet_name           = "vnet-prod-uksouth-001"
vnet_address_space  = ["10.0.0.0/16"]
```

```bash
terraform apply
```

## Verifying

```bash
az network vnet show \
  --resource-group rg-networking-prod \
  --name vnet-prod-uksouth-001 \
  --query '{addressSpace: addressSpace.addressPrefixes, subnets: subnets[].{name: name, prefix: addressPrefix}}' \
  --output table
```

## Linking a Private DNS Zone

Once a Private DNS Zone exists, link it to the VNet using a separate resource:

```hcl
resource "azurerm_private_dns_zone_virtual_network_link" "blob" {
  name                  = "link-${azurerm_virtual_network.main.name}"
  resource_group_name   = azurerm_resource_group.networking.name
  private_dns_zone_name = azurerm_private_dns_zone.blob.name
  virtual_network_id    = azurerm_virtual_network.main.id
  registration_enabled  = false
}
```

## Common gotchas

**1. Subnets as separate resources vs. inline blocks**
The AzureRM provider supports defining subnets either as `azurerm_subnet` resources (recommended) or as inline `subnet` blocks inside `azurerm_virtual_network`. Don't mix both — the provider will conflict with itself and you'll get intermittent plan drift. Use separate `azurerm_subnet` resources for everything.

**2. `private_endpoint_network_policies` attribute name changed in provider v3.x**
In older AzureRM provider versions this was `enforce_private_link_endpoint_network_policies`. It was deprecated and replaced with `private_endpoint_network_policies`. Check your provider version if you're seeing unknown attribute errors.

**3. Terraform doesn't protect you from destroying subnets with resources**
If you remove a subnet resource from your config and apply, Terraform will delete it — even if a VM or Private Endpoint is still in it. The deletion will fail, but the intent is there. Use `prevent_destroy` lifecycle rules on subnets that contain critical resources in production.

```hcl
lifecycle {
  prevent_destroy = true
}
```

**4. State file and multiple workspaces**
If you're managing multiple environments with Terraform workspaces, ensure your VNet address spaces are different per workspace. A common mistake is sharing a `tfvars` file across workspaces without overriding the CIDR — which leads to overlapping address spaces that break peering later.

---

## Summary

Deploying a VNet with Terraform is clean and predictable. Use separate `azurerm_subnet` resources rather than inline blocks, pin your provider version, and add `prevent_destroy` to subnets in production. Outputs for the VNet ID and subnet IDs are essential — downstream resources (Private Endpoints, NSGs) will reference them.
