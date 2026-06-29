---
title: "Deploying Entra-Only AVD from Scratch with Terraform"
date: 2026-05-31
draft: true
tags:
  - AVD
  - Azure Virtual Desktop
  - Entra ID
  - Terraform
  - IaC
description: "Full end-to-end Terraform deployment of an Entra-only Azure Virtual Desktop environment - host pool, session hosts, FSLogix on Azure Files, Conditional Access."

cover:
  image: /covers/iac.svg
  alt: Terraform IaC
  relative: false

comments: true
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: true
ShowWordCount: false
---

This is the Terraform equivalent of the [Bicep deployment post](../avd-entra-only-deploy-bicep). Same architecture, same gotchas - different toolchain. If you want the why behind the design decisions, read that post first.

## Project structure

```
avd/
├── main.tf
├── variables.tf
├── outputs.tf
├── providers.tf
├── modules/
│   ├── hostpool/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── storage/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── sessionhosts/
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
├── scripts/
│   └── configure-fslogix.ps1
└── terraform.tfvars
```

## providers.tf

```hcl
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
  }
  backend "azurerm" {
    resource_group_name  = "rg-tfstate"
    storage_account_name = "stterraformstate"
    container_name       = "tfstate"
    key                  = "avd-prod.tfstate"
  }
}

provider "azurerm" {
  features {}
}
```

## variables.tf

```hcl
variable "location" {
  type    = string
  default = "uksouth"
}

variable "resource_group_name" {
  type    = string
  default = "rg-avd-prod"
}

variable "host_pool_name" {
  type    = string
  default = "hp-avd-prod"
}

variable "workspace_name" {
  type    = string
  default = "ws-avd-prod"
}

variable "app_group_name" {
  type    = string
  default = "ag-avd-prod-desktop"
}

variable "storage_account_name" {
  type    = string
  default = "stavdprodprofiles"
}

variable "session_host_count" {
  type    = number
  default = 3
}

variable "session_host_size" {
  type    = string
  default = "Standard_D4s_v5"
}

variable "subnet_id" {
  type = string
}

variable "admin_username" {
  type    = string
  default = "avdadmin"
}

variable "admin_password" {
  type      = string
  sensitive = true
}
```

## main.tf

```hcl
resource "azurerm_resource_group" "avd" {
  name     = var.resource_group_name
  location = var.location
}

module "hostpool" {
  source              = "./modules/hostpool"
  name                = var.host_pool_name
  location            = var.location
  resource_group_name = azurerm_resource_group.avd.name
}

resource "azurerm_virtual_desktop_application_group" "desktop" {
  name                = var.app_group_name
  location            = var.location
  resource_group_name = azurerm_resource_group.avd.name
  type                = "Desktop"
  host_pool_id        = module.hostpool.id
}

resource "azurerm_virtual_desktop_workspace" "main" {
  name                = var.workspace_name
  location            = var.location
  resource_group_name = azurerm_resource_group.avd.name
}

resource "azurerm_virtual_desktop_workspace_application_group_association" "main" {
  workspace_id         = azurerm_virtual_desktop_workspace.main.id
  application_group_id = azurerm_virtual_desktop_application_group.desktop.id
}

module "storage" {
  source              = "./modules/storage"
  name                = var.storage_account_name
  location            = var.location
  resource_group_name = azurerm_resource_group.avd.name
}

module "sessionhosts" {
  source               = "./modules/sessionhosts"
  count_hosts          = var.session_host_count
  location             = var.location
  resource_group_name  = azurerm_resource_group.avd.name
  vm_size              = var.session_host_size
  subnet_id            = var.subnet_id
  host_pool_name       = var.host_pool_name
  host_pool_token      = module.hostpool.registration_token
  admin_username       = var.admin_username
  admin_password       = var.admin_password
  storage_account_name = module.storage.name
  storage_account_key  = module.storage.key

  depends_on = [module.hostpool, module.storage]
}
```

## modules/hostpool/main.tf

```hcl
variable "name" {}
variable "location" {}
variable "resource_group_name" {}

resource "azurerm_virtual_desktop_host_pool" "main" {
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name

  type                     = "Pooled"
  load_balancer_type       = "BreadthFirst"
  preferred_app_group_type = "Desktop"
  maximum_sessions_allowed = 10

  # targetisaadjoined:i:1 required for non-Entra-joined client devices
  custom_rdp_properties = "targetisaadjoined:i:1;"
}

resource "azurerm_virtual_desktop_host_pool_registration_info" "main" {
  hostpool_id     = azurerm_virtual_desktop_host_pool.main.id
  expiration_date = timeadd(timestamp(), "8h")
}

output "id" {
  value = azurerm_virtual_desktop_host_pool.main.id
}

output "registration_token" {
  value     = azurerm_virtual_desktop_host_pool_registration_info.main.token
  sensitive = true
}
```

> **Gotcha:** `timeadd(timestamp(), "8h")` means the registration token expires 8 hours from `terraform apply`. If your session host deployment takes longer than that (e.g. large scale-out, slow DSC), the VMs will register but the token will be invalid and they'll stay in an unavailable state. Extend this if you're deploying many hosts. You can re-run the registration info resource to get a fresh token without reprovisioning.

## modules/storage/main.tf

```hcl
variable "name" {}
variable "location" {}
variable "resource_group_name" {}

resource "azurerm_storage_account" "profiles" {
  name                     = var.name
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Premium"
  account_replication_type = "LRS"
  account_kind             = "FileStorage"
  min_tls_version          = "TLS1_2"
  https_traffic_only_enabled = true

  azure_files_authentication {
    directory_type = "AADKERB"  # Entra Kerberos - no AD DS
  }
}

resource "azurerm_storage_share" "profiles" {
  name               = "profiles"
  storage_account_id = azurerm_storage_account.profiles.id
  quota              = 1024
}

output "id" {
  value = azurerm_storage_account.profiles.id
}

output "name" {
  value = azurerm_storage_account.profiles.name
}

output "key" {
  value     = azurerm_storage_account.profiles.primary_access_key
  sensitive = true
}
```

> **Gotcha:** `account_kind = "FileStorage"` is required for Premium file shares. If you omit it and use the default (`StorageV2`), you'll get standard performance shares. The provider won't error - you just end up with a slower storage account. FSLogix profile load times will suffer noticeably under load.

## modules/sessionhosts/main.tf

```hcl
variable "count_hosts" {}
variable "location" {}
variable "resource_group_name" {}
variable "vm_size" {}
variable "subnet_id" {}
variable "host_pool_name" {}
variable "host_pool_token" { sensitive = true }
variable "admin_username" {}
variable "admin_password" { sensitive = true }
variable "storage_account_name" {}
variable "storage_account_key" { sensitive = true }

locals {
  name_prefix = "avd-sh"
  fslogix_script = templatefile("${path.module}/../../scripts/configure-fslogix.ps1", {
    storage_account_name = var.storage_account_name
    storage_account_key  = var.storage_account_key
  })
}

resource "azurerm_network_interface" "main" {
  count               = var.count_hosts
  name                = "${local.name_prefix}-${count.index}-nic"
  location            = var.location
  resource_group_name = var.resource_group_name

  ip_configuration {
    name                          = "ipconfig1"
    subnet_id                     = var.subnet_id
    private_ip_address_allocation = "Dynamic"
  }
}

resource "azurerm_windows_virtual_machine" "main" {
  count               = var.count_hosts
  name                = "${local.name_prefix}-${count.index}"
  location            = var.location
  resource_group_name = var.resource_group_name
  size                = var.vm_size
  admin_username      = var.admin_username
  admin_password      = var.admin_password

  identity {
    type = "SystemAssigned"  # required for Entra join
  }

  network_interface_ids = [azurerm_network_interface.main[count.index].id]

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
  }

  source_image_reference {
    publisher = "MicrosoftWindowsDesktop"
    offer     = "windows-11"
    sku       = "win11-24h2-avd"
    version   = "latest"
  }

  patch_mode = "AutomaticByPlatform"
}

# Entra join extension - no domain join
resource "azurerm_virtual_machine_extension" "entra_join" {
  count                      = var.count_hosts
  name                       = "AADLoginForWindows"
  virtual_machine_id         = azurerm_windows_virtual_machine.main[count.index].id
  publisher                  = "Microsoft.Azure.ActiveDirectory"
  type                       = "AADLoginForWindows"
  type_handler_version       = "2.0"
  auto_upgrade_minor_version = true

  settings = jsonencode({
    mdmId = ""  # empty = Intune enrolment
  })
}

# AVD agent + host pool registration
resource "azurerm_virtual_machine_extension" "avd_agent" {
  count                      = var.count_hosts
  name                       = "DSC"
  virtual_machine_id         = azurerm_windows_virtual_machine.main[count.index].id
  publisher                  = "Microsoft.Powershell"
  type                       = "DSC"
  type_handler_version       = "2.73"
  auto_upgrade_minor_version = true

  settings = jsonencode({
    modulesUrl            = "https://wvdportalstorageblob.blob.core.windows.net/galleryartifacts/Configuration_1.0.02799.442.zip"
    configurationFunction = "Configuration.ps1\\AddSessionHost"
    properties = {
      HostPoolName          = var.host_pool_name
      RegistrationInfoToken = var.host_pool_token
      AadJoin               = true  # critical for Entra-only
    }
  })

  depends_on = [azurerm_virtual_machine_extension.entra_join]
}

# FSLogix config
resource "azurerm_virtual_machine_extension" "fslogix" {
  count                      = var.count_hosts
  name                       = "FSLogixConfig"
  virtual_machine_id         = azurerm_windows_virtual_machine.main[count.index].id
  publisher                  = "Microsoft.Compute"
  type                       = "CustomScriptExtension"
  type_handler_version       = "1.10"
  auto_upgrade_minor_version = true

  settings = jsonencode({
    commandToExecute = "powershell -ExecutionPolicy Unrestricted -EncodedCommand ${base64encode(local.fslogix_script)}"
  })

  depends_on = [azurerm_virtual_machine_extension.avd_agent]
}
```

## scripts/configure-fslogix.ps1

```powershell
$profileShare = "\\${storage_account_name}.file.core.windows.net\profiles"

$fslogixPath = 'HKLM:\SOFTWARE\FSLogix\Profiles'
New-Item -Path $fslogixPath -Force | Out-Null

Set-ItemProperty -Path $fslogixPath -Name 'Enabled' -Value 1
Set-ItemProperty -Path $fslogixPath -Name 'VHDLocations' -Value $profileShare
Set-ItemProperty -Path $fslogixPath -Name 'DeleteLocalProfileWhenVHDShouldApply' -Value 1
Set-ItemProperty -Path $fslogixPath -Name 'FlipFlopProfileDirectoryName' -Value 1

net use $profileShare /user:"Azure\${storage_account_name}" "${storage_account_key}" /persistent:yes
```

The `${...}` placeholders are Terraform `templatefile` interpolations - the actual storage account name and key are injected at plan time, not at runtime.

## terraform.tfvars

```hcl
location             = "uksouth"
resource_group_name  = "rg-avd-prod"
host_pool_name       = "hp-avd-prod"
workspace_name       = "ws-avd-prod"
app_group_name       = "ag-avd-prod-desktop"
storage_account_name = "stavdprodprofiles"
session_host_count   = 3
session_host_size    = "Standard_D4s_v5"
subnet_id            = "/subscriptions/<sub-id>/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet-prod/subnets/snet-avd"
admin_username       = "avdadmin"
# admin_password passed via env var: TF_VAR_admin_password
```

## Deploying

```bash
# Set sensitive var via env
export TF_VAR_admin_password="$(az keyvault secret show \
  --vault-name kv-avd-prod \
  --name avd-admin-password \
  --query value -o tsv)"

terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

## Post-deployment: RBAC

Terraform doesn't assign RBAC unless you add it explicitly. After apply:

```bash
# Virtual Machine User Login - required for Entra-joined VM sign-in
az role assignment create \
  --role "Virtual Machine User Login" \
  --assignee-object-id <user-group-object-id> \
  --scope /subscriptions/<sub-id>/resourceGroups/rg-avd-prod

# App group assignment
az desktopvirtualization application-group user-list update \
  --application-group-name ag-avd-prod-desktop \
  --resource-group rg-avd-prod \
  --user-object-id <user-group-object-id>

# FSLogix profile share access
az role assignment create \
  --role "Storage File Data SMB Share Contributor" \
  --assignee-object-id <user-group-object-id> \
  --scope /subscriptions/<sub-id>/resourceGroups/rg-avd-prod/providers/Microsoft.Storage/storageAccounts/stavdprodprofiles
```

You can also add these as `azurerm_role_assignment` resources in Terraform - the tradeoff is that Terraform then owns the RBAC state, which can cause issues if you also manage it in PIM or via portal.

## State considerations

A few things worth flagging for ongoing operations:

The `azurerm_virtual_desktop_host_pool_registration_info` resource generates a new token on every `terraform apply` because `timestamp()` changes. This is fine for initial deployment but will trigger unnecessary updates on subsequent runs. Consider storing the token expiry as a variable you control, or use a `lifecycle { ignore_changes = [expiration_date] }` block after initial setup.

Session hosts are stateful. If Terraform decides to replace a VM (e.g. image update, size change), the existing user sessions and local profile data on that VM are lost. Use a separate process (image gallery + reimage) for rolling session host updates rather than letting Terraform destroy-and-recreate.

## What to verify

Same checks as the Bicep post:

- Session hosts show as **Available** in the host pool
- Devices visible in Entra ID and Intune
- Test user connects via Windows App or web client
- FSLogix profile VHD created in Azure Files on first login
- MFA triggered on connection

---

*Sources: [Microsoft Entra joined session hosts - Microsoft Learn](https://learn.microsoft.com/en-us/azure/virtual-desktop/azure-ad-joined-session-hosts) - [FSLogix on Entra Joined AVD - NielsKok.Tech](https://www.nielskok.tech/azure-virtual-desktop/fslogix-on-entra-joined-avd/)*
