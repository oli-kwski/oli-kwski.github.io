---
title: "How to Create an Azure Network Security Group with Terraform"
date: 2026-04-30
draft: true
description: "Practical Terraform for deploying an NSG with security rules, attaching it to a subnet, and enabling flow logs."

tags:
  - Azure
  - Networking
  - NSG
  - Security
  - Terraform
  - IaC
categories:
  - Azure
  - Networking
series:
  - Network Security Groups

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

If you haven't read [What Is an Azure Network Security Group?](/posts/what-is-a-network-security-group), start there. This post covers deploying an NSG and attaching it to a subnet using Terraform.

---

## Prerequisites

- Terraform CLI installed
- Azure CLI authenticated
- An existing VNet and subnet

## The Terraform

### NSG with rules

```hcl
variable "location" {
  type    = string
  default = "uksouth"
}

variable "resource_group_name" {
  type = string
}

variable "nsg_name" {
  type    = string
  default = "nsg-workloads-prod-uksouth-001"
}

resource "azurerm_network_security_group" "main" {
  name                = var.nsg_name
  location            = var.location
  resource_group_name = var.resource_group_name

  security_rule {
    name                       = "Allow-HTTPS-Inbound"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_address_prefix      = "Internet"
    source_port_range          = "*"
    destination_address_prefix = "*"
    destination_port_range     = "443"
    description                = "Allow HTTPS inbound from internet."
  }

  security_rule {
    name                       = "Deny-HTTP-Inbound"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "Tcp"
    source_address_prefix      = "Internet"
    source_port_range          = "*"
    destination_address_prefix = "*"
    destination_port_range     = "80"
    description                = "Deny unencrypted HTTP from internet."
  }

  security_rule {
    name                       = "Allow-AzureMonitor-Outbound"
    priority                   = 100
    direction                  = "Outbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_address_prefix      = "*"
    source_port_range          = "*"
    destination_address_prefix = "AzureMonitor"
    destination_port_range     = "443"
    description                = "Allow outbound to Azure Monitor."
  }

  security_rule {
    name                       = "Deny-Internet-Outbound"
    priority                   = 1000
    direction                  = "Outbound"
    access                     = "Deny"
    protocol                   = "*"
    source_address_prefix      = "*"
    source_port_range          = "*"
    destination_address_prefix = "Internet"
    destination_port_range     = "*"
    description                = "Deny direct internet egress — route via firewall."
  }

  tags = {
    environment = "prod"
    managed_by  = "terraform"
  }
}

output "nsg_id" {
  value = azurerm_network_security_group.main.id
}
```

### Attaching to a subnet

```hcl
resource "azurerm_subnet_network_security_group_association" "workloads" {
  subnet_id                 = var.workloads_subnet_id
  network_security_group_id = azurerm_network_security_group.main.id
}
```

Use `azurerm_subnet_network_security_group_association` rather than setting the NSG inline in `azurerm_subnet`. Mixing both causes Terraform to detect spurious drift.

### Separate NSG rules (alternative approach)

For large rule sets, use `azurerm_network_security_rule` resources instead of inline blocks. This allows rules to be added/removed independently without modifying the NSG resource itself:

```hcl
resource "azurerm_network_security_rule" "allow_https" {
  name                        = "Allow-HTTPS-Inbound"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_address_prefix       = "Internet"
  source_port_range           = "*"
  destination_address_prefix  = "*"
  destination_port_range      = "443"
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.main.name
}
```

Don't mix inline `security_rule` blocks and separate `azurerm_network_security_rule` resources on the same NSG — Terraform will conflict with itself.

### Flow logs

```hcl
data "azurerm_network_watcher" "main" {
  name                = "NetworkWatcher_uksouth"
  resource_group_name = "NetworkWatcherRG"
}

resource "azurerm_network_watcher_flow_log" "main" {
  network_watcher_name      = data.azurerm_network_watcher.main.name
  resource_group_name       = "NetworkWatcherRG"
  name                      = "flowlog-${var.nsg_name}"
  network_security_group_id = azurerm_network_security_group.main.id
  storage_account_id        = var.diagnostics_storage_account_id
  enabled                   = true
  version                   = 2

  retention_policy {
    enabled = true
    days    = 30
  }

  # Optional: Traffic Analytics
  # traffic_analytics {
  #   enabled               = true
  #   workspace_id          = var.log_analytics_workspace_id
  #   workspace_region      = var.location
  #   workspace_resource_id = var.log_analytics_workspace_resource_id
  #   interval_in_minutes   = 10
  # }
}
```

## Deploying

```bash
terraform init
terraform plan \
  -var="resource_group_name=rg-networking-prod" \
  -var="nsg_name=nsg-workloads-prod-uksouth-001"
terraform apply
```

## Verifying

```bash
# Check effective NSG rules on a NIC
az network nic list-effective-nsg \
  --resource-group rg-workloads-prod \
  --name nic-vm-001 \
  --output table

# Test a specific flow
az network watcher test-ip-flow \
  --resource-group rg-networking-prod \
  --direction Inbound \
  --protocol TCP \
  --local 10.0.1.5:443 \
  --remote 1.2.3.4:12345 \
  --vm vm-prod-001
```

## Common gotchas

**1. Don't mix inline rules and separate rule resources**
Using both `security_rule` blocks inside `azurerm_network_security_group` and separate `azurerm_network_security_rule` resources on the same NSG causes permanent plan drift — Terraform will continually try to remove the rules it doesn't "own". Pick one approach and stick to it.

**2. Subnet association creates implicit dependency**
`azurerm_subnet_network_security_group_association` is a separate resource in state. If you destroy the NSG without first destroying the association, you'll get a dependency error. Terraform handles destruction order automatically, but be aware if you're doing manual state manipulation.

**3. Flow logs resource group is `NetworkWatcherRG` by default**
Network Watcher (and therefore flow logs) is deployed automatically by Azure into `NetworkWatcherRG`. The Terraform resource for flow logs must reference this — it's not created in your resource group. Check with `az network watcher list` if you're unsure what exists.

**4. Priority gaps for future rules**
Leave gaps between priorities (100, 200, 300) so rules can be inserted later without renumbering. Renaming or renumbering existing rules causes Terraform to delete and recreate them, which creates a brief window where the rule is absent.

---

## Summary

NSGs in Terraform are clean and predictable. Create the NSG, attach it to subnets with `azurerm_subnet_network_security_group_association`, and choose either inline rules or separate `azurerm_network_security_rule` resources — not both. Enable flow logs pointing at a diagnostics storage account from day one. Use `az network nic list-effective-nsg` when rules aren't behaving as expected.
