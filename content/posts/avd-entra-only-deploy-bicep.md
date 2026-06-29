---
title: "Deploying Entra-Only AVD from Scratch with Bicep"
date: 2026-05-31
draft: true
tags:
  - AVD
  - Azure Virtual Desktop
  - Entra ID
  - Bicep
  - IaC
description: "Full end-to-end Bicep deployment of an Entra-only Azure Virtual Desktop environment - host pool, session hosts, FSLogix on Azure Files, Conditional Access."

cover:
  image: /covers/iac.svg
  alt: Bicep IaC
  relative: false

comments: true
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: true
ShowWordCount: false
---

This post covers deploying a net-new Entra-only AVD environment using Bicep. No domain controllers, no Entra Connect, no AD DS. Just Entra ID, Intune, and Azure Files.

If you want context on why Entra-only vs hybrid, [see the comparison post first](../avd-hybrid-vs-entra-only).

## What we're building

```
┌─────────────────────────────────────────────────┐
│  Resource Group: rg-avd-prod                    │
│                                                 │
│  ┌──────────────┐    ┌──────────────────────┐   │
│  │  Host Pool   │    │  Storage Account     │   │
│  │  (pooled)    │    │  (Azure Files/       │   │
│  └──────┬───────┘    │   FSLogix profiles)  │   │
│         │            └──────────────────────┘   │
│  ┌──────▼───────┐                               │
│  │ App Group    │    ┌──────────────────────┐   │
│  │ (Desktop)    │    │  Session Hosts       │   │
│  └──────┬───────┘    │  (Entra-joined,      │   │
│         │            │   Intune-enrolled)   │   │
│  ┌──────▼───────┐    └──────────────────────┘   │
│  │  Workspace   │                               │
│  └──────────────┘                               │
└─────────────────────────────────────────────────┘
```

## Prerequisites

Before running any Bicep:

- Azure subscription with Contributor + User Access Administrator (or Owner)
- Entra ID with the users you'll assign to AVD
- An existing VNet/subnet for the session hosts
- Intune licence for the users (for session host management)
- `Microsoft.DesktopVirtualization` resource provider registered

```bash
az provider register --namespace Microsoft.DesktopVirtualization
```

## Project structure

```
avd/
├── main.bicep
├── modules/
│   ├── hostpool.bicep
│   ├── appgroup.bicep
│   ├── workspace.bicep
│   ├── storage.bicep
│   └── sessionhosts.bicep
└── parameters/
    └── prod.bicepparam
```

## Parameters file

```bicep
// parameters/prod.bicepparam
using '../main.bicep'

param location = 'uksouth'
param environmentName = 'prod'
param hostPoolName = 'hp-avd-prod'
param workspaceName = 'ws-avd-prod'
param appGroupName = 'ag-avd-prod-desktop'
param storageAccountName = 'stavdprodprofiles'
param sessionHostCount = 3
param sessionHostSize = 'Standard_D4s_v5'
param sessionHostImageReference = {
  publisher: 'MicrosoftWindowsDesktop'
  offer: 'windows-11'
  sku: 'win11-24h2-avd'
  version: 'latest'
}
param subnetId = '/subscriptions/<sub-id>/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet-prod/subnets/snet-avd'
param adminUsername = 'avdadmin'
@secure()
param adminPassword = ''
```

## main.bicep

```bicep
targetScope = 'resourceGroup'

param location string
param environmentName string
param hostPoolName string
param workspaceName string
param appGroupName string
param storageAccountName string
param sessionHostCount int
param sessionHostSize string
param sessionHostImageReference object
param subnetId string
param adminUsername string
@secure()
param adminPassword string

module hostPool 'modules/hostpool.bicep' = {
  name: 'hostpool'
  params: {
    name: hostPoolName
    location: location
  }
}

module appGroup 'modules/appgroup.bicep' = {
  name: 'appgroup'
  params: {
    name: appGroupName
    location: location
    hostPoolId: hostPool.outputs.id
  }
}

module workspace 'modules/workspace.bicep' = {
  name: 'workspace'
  params: {
    name: workspaceName
    location: location
    appGroupId: appGroup.outputs.id
  }
}

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    name: storageAccountName
    location: location
  }
}

module sessionHosts 'modules/sessionhosts.bicep' = {
  name: 'sessionhosts'
  params: {
    count: sessionHostCount
    location: location
    vmSize: sessionHostSize
    imageReference: sessionHostImageReference
    subnetId: subnetId
    hostPoolName: hostPoolName
    hostPoolToken: hostPool.outputs.registrationToken
    adminUsername: adminUsername
    adminPassword: adminPassword
    storageAccountName: storageAccountName
    storageAccountKey: storage.outputs.key
  }
  dependsOn: [hostPool, storage]
}
```

## modules/hostpool.bicep

```bicep
param name string
param location string

var tokenExpirationTime = dateTimeAdd(utcNow(), 'PT8H')

resource hostPool 'Microsoft.DesktopVirtualization/hostPools@2024-04-03' = {
  name: name
  location: location
  properties: {
    hostPoolType: 'Pooled'
    loadBalancerType: 'BreadthFirst'
    preferredAppGroupType: 'Desktop'
    maxSessionLimit: 10
    // Entra-only: no domain join
    registrationInfo: {
      expirationTime: tokenExpirationTime
      registrationTokenOperation: 'Update'
    }
    customRdpProperty: 'targetisaadjoined:i:1;'
    // SSO via Entra authentication
    ssoClientId: ''
    ssoSecretType: 'SharedKey'
  }
}

output id string = hostPool.id
output registrationToken string = hostPool.properties.registrationInfo.token
```

> **Note on `targetisaadjoined:i:1`:** This custom RDP property is required for non-Windows or unmanaged client devices to connect. Without it, web, macOS, iOS, and Android clients fail to connect. Add it even if your users are on managed Windows devices - it doesn't hurt, and it saves a support call.

## modules/appgroup.bicep

```bicep
param name string
param location string
param hostPoolId string

resource appGroup 'Microsoft.DesktopVirtualization/applicationGroups@2024-04-03' = {
  name: name
  location: location
  properties: {
    applicationGroupType: 'Desktop'
    hostPoolArmPath: hostPoolId
  }
}

output id string = appGroup.id
```

## modules/workspace.bicep

```bicep
param name string
param location string
param appGroupId string

resource workspace 'Microsoft.DesktopVirtualization/workspaces@2024-04-03' = {
  name: name
  location: location
  properties: {
    applicationGroupReferences: [appGroupId]
  }
}
```

## modules/storage.bicep

This is where FSLogix profiles live. The key config here is enabling **Entra Kerberos** authentication so Entra-joined session hosts can authenticate to Azure Files without AD DS.

```bicep
param name string
param location string

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: name
  location: location
  sku: {
    name: 'Premium_LRS'
  }
  kind: 'FileStorage'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    azureFilesIdentityBasedAuthentication: {
      directoryServiceOptions: 'AADKERB'  // Entra Kerberos - no AD DS needed
    }
  }
}

resource fileShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  name: '${name}/default/profiles'
  properties: {
    shareQuota: 1024
    enabledProtocols: 'SMB'
  }
  dependsOn: [storageAccount]
}

output id string = storageAccount.id
output name string = storageAccount.name
// key output for FSLogix - use Key Vault in production
output key string = storageAccount.listKeys().keys[0].value
```

> **Gotcha:** `directoryServiceOptions: 'AADKERB'` is mutually exclusive with `AD` and `AADDS`. You can't mix auth methods on a single storage account. If you later need to add hybrid users to the same storage, you'll need a separate storage account.

> **Gotcha:** Premium FileStorage (`Premium_LRS`) is required for FSLogix profile containers. General Purpose v2 accounts with Azure Files support only standard performance, which will cause noticeable latency on profile load/save operations. Don't cheap out here.

## modules/sessionhosts.bicep

```bicep
param count int
param location string
param vmSize string
param imageReference object
param subnetId string
param hostPoolName string
param hostPoolToken string
param adminUsername string
@secure()
param adminPassword string
param storageAccountName string
@secure()
param storageAccountKey string

var namePrefix = 'avd-sh'

resource nics 'Microsoft.Network/networkInterfaces@2024-01-01' = [for i in range(0, count): {
  name: '${namePrefix}-${i}-nic'
  location: location
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          subnet: {
            id: subnetId
          }
          privateIPAllocationMethod: 'Dynamic'
        }
      }
    ]
  }
}]

resource vms 'Microsoft.Compute/virtualMachines@2024-03-01' = [for i in range(0, count): {
  name: '${namePrefix}-${i}'
  location: location
  identity: {
    type: 'SystemAssigned'  // required for Entra join
  }
  properties: {
    hardwareProfile: {
      vmSize: vmSize
    }
    storageProfile: {
      imageReference: imageReference
      osDisk: {
        createOption: 'FromImage'
        managedDisk: {
          storageAccountType: 'Premium_LRS'
        }
      }
    }
    osProfile: {
      computerName: '${namePrefix}-${i}'
      adminUsername: adminUsername
      adminPassword: adminPassword
      windowsConfiguration: {
        enableAutomaticUpdates: true
        patchSettings: {
          patchMode: 'AutomaticByPlatform'
        }
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: nics[i].id
        }
      ]
    }
  }
  dependsOn: [nics]
}]

// Entra join extension - replaces domain join extension for hybrid
resource entraJoinExtensions 'Microsoft.Compute/virtualMachines/extensions@2024-03-01' = [for i in range(0, count): {
  name: '${namePrefix}-${i}/AADLoginForWindows'
  location: location
  properties: {
    publisher: 'Microsoft.Azure.ActiveDirectory'
    type: 'AADLoginForWindows'
    typeHandlerVersion: '2.0'
    autoUpgradeMinorVersion: true
    settings: {
      mdmId: ''  // empty string = Intune enrolment if Intune licence assigned
    }
  }
  dependsOn: [vms]
}]

// AVD agent registration extension
resource avdExtensions 'Microsoft.Compute/virtualMachines/extensions@2024-03-01' = [for i in range(0, count): {
  name: '${namePrefix}-${i}/DSC'
  location: location
  properties: {
    publisher: 'Microsoft.Powershell'
    type: 'DSC'
    typeHandlerVersion: '2.73'
    autoUpgradeMinorVersion: true
    settings: {
      modulesUrl: 'https://wvdportalstorageblob.blob.core.windows.net/galleryartifacts/Configuration_1.0.02799.442.zip'
      configurationFunction: 'Configuration.ps1\\AddSessionHost'
      properties: {
        HostPoolName: hostPoolName
        RegistrationInfoToken: hostPoolToken
        AadJoin: true  // critical: tells the DSC script this is an Entra-only join
      }
    }
  }
  dependsOn: [entraJoinExtensions]
}]

// FSLogix configuration via Custom Script Extension
resource fslogixExtensions 'Microsoft.Compute/virtualMachines/extensions@2024-03-01' = [for i in range(0, count): {
  name: '${namePrefix}-${i}/FSLogixConfig'
  location: location
  properties: {
    publisher: 'Microsoft.Compute'
    type: 'CustomScriptExtension'
    typeHandlerVersion: '1.10'
    autoUpgradeMinorVersion: true
    settings: {
      commandToExecute: 'powershell -ExecutionPolicy Unrestricted -Command "& { ${loadTextContent('../scripts/configure-fslogix.ps1')} }" -StorageAccountName ${storageAccountName} -StorageAccountKey ${storageAccountKey}'
    }
  }
  dependsOn: [avdExtensions]
}]
```

> **Gotcha:** The `AadJoin: true` flag in the DSC extension is non-obvious and easy to miss. Without it, the AVD agent registration will still succeed but the session host shows up as needing a domain join that never comes. It will sit in an unavailable state.

> **Gotcha:** Extension ordering matters. Entra join must complete before the AVD DSC extension runs, and FSLogix config should come last. Bicep `dependsOn` handles this, but if you're deploying extensions via ARM or portal, get the sequence wrong and you'll be reprovisioning VMs.

## scripts/configure-fslogix.ps1

```powershell
param(
    [string]$StorageAccountName,
    [string]$StorageAccountKey
)

$profileShare = "\\$StorageAccountName.file.core.windows.net\profiles"

# FSLogix registry settings
$fslogixPath = 'HKLM:\SOFTWARE\FSLogix\Profiles'
New-Item -Path $fslogixPath -Force | Out-Null

Set-ItemProperty -Path $fslogixPath -Name 'Enabled' -Value 1
Set-ItemProperty -Path $fslogixPath -Name 'VHDLocations' -Value $profileShare
Set-ItemProperty -Path $fslogixPath -Name 'DeleteLocalProfileWhenVHDShouldApply' -Value 1
Set-ItemProperty -Path $fslogixPath -Name 'FlipFlopProfileDirectoryName' -Value 1

# Map the share so the storage key caches (Entra Kerberos handles ongoing auth)
net use $profileShare /user:"Azure\$StorageAccountName" $StorageAccountKey /persistent:yes
```

## Deploying

```bash
# Create resource group
az group create \
  --name rg-avd-prod \
  --location uksouth

# Deploy - pass admin password securely
az deployment group create \
  --resource-group rg-avd-prod \
  --template-file main.bicep \
  --parameters @parameters/prod.bicepparam \
  --parameters adminPassword="$(az keyvault secret show \
      --vault-name kv-avd-prod \
      --name avd-admin-password \
      --query value -o tsv)"
```

## Post-deployment: RBAC

Bicep doesn't assign RBAC by default. After deployment, assign these roles:

```bash
# Users need Virtual Machine User Login to sign in to Entra-joined VMs
az role assignment create \
  --role "Virtual Machine User Login" \
  --assignee-object-id <user-group-object-id> \
  --scope /subscriptions/<sub-id>/resourceGroups/rg-avd-prod

# Assign users to the application group
az desktopvirtualization application-group user-list update \
  --application-group-name ag-avd-prod-desktop \
  --resource-group rg-avd-prod \
  --user-object-id <user-group-object-id>

# Storage File Data SMB Share Contributor - for FSLogix profile access
az role assignment create \
  --role "Storage File Data SMB Share Contributor" \
  --assignee-object-id <user-group-object-id> \
  --scope /subscriptions/<sub-id>/resourceGroups/rg-avd-prod/providers/Microsoft.Storage/storageAccounts/stavdprodprofiles
```

> **Gotcha:** The `Virtual Machine User Login` role is easy to forget because AVD portal deployment handles it for you. With Bicep you own it. Without it, users authenticate fine but can't actually log in to the session host - they get a generic access denied at the VM level.

## Conditional Access

Wire up MFA before going to production. One gotcha specific to Entra-only:

If your CA policy targets the **Azure Virtual Desktop** app and enforces strong auth (e.g. MFA + compliant device), you also need to **exclude the Azure Windows VM Sign-In** app from any policy that requires Windows Hello or FIDO2. Otherwise the VM sign-in step breaks even if the AVD auth step succeeds.

Recommended CA setup:
1. Policy targeting **Azure Virtual Desktop** - require MFA + compliant device (session hosts enrolled in Intune will satisfy this)
2. Policy targeting **Azure Windows VM Sign-In** - require MFA only (no device compliance filter, exclude strong auth methods)

## What to verify

After deployment, check:

- Session hosts appear as **Available** in the host pool (not Unavailable or Needs Attention)
- Entra join visible in Entra ID under Devices
- Intune enrolment visible in Intune under Devices
- Test user can connect via [Windows App](https://apps.microsoft.com/detail/9n1f85v9t8bn) or web client at remote.cloud.microsoft
- FSLogix profile VHD created in the Azure Files share on first login
- MFA prompt triggered on connection

---

*The Terraform equivalent of this deployment is covered in the next post.*
