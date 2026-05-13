---
title: "How to Create a Storage Account with Bicep"
date: 2026-05-13
draft: false
description: "A straightforward Bicep template for deploying an Azure Storage account with a blob container."

tags:
  - Storage Account
  - Bicep
series:
  - Bicep

comments: true
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: true
ShowWordCount: false

cover:
  image: /covers/iac.svg
  alt: Infrastructure as Code
  relative: false
weight: 2
---

This post assumes you know what a storage account is and focuses on deploying one with Bicep. If you don't, first read [What Is an Azure Storage Account and When Should You Use One?](/posts/what-is-a-storage-account)

---

## Prerequisites

- Azure CLI installed and authenticated (`az login`)
- Bicep CLI (`az bicep install` if not present)
- VS Code installed
- Bicep VS Code extension installed

If you need to set any of these up, see [Setting Up a Bicep Development Environment on Windows](/posts/bicep-environment-setup-windows).

## The code

The below bicep code will deploy the following:

- A resource group
- A storage account with a blob container

The code is split into 2 files, `main.bicep` and a storage module named `storage.bicep`.

### main.bicep

```bicep
targetScope = 'subscription'

param location string = 'uksouth'
param rgName string = 'rg-demo-dev-uksouth-001'

// uniqueString() produces a deterministic 13-char hash from the resource group ID.
var storageName = 'st${uniqueString(newRG.id)}'

// 1. Create a resource group
resource newRG 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: rgName
  location: location
}

// 2. Deploy storage into it
module storageModule './storage.bicep' = {
  name: 'storageDeploy'
  scope: resourceGroup(newRG.name)
  params: {
    location: location
    storageAccountName: storageName
  }
}

// Output the generated name so you know what was created
output storageAccountName string = storageName
```

### storage.bicep

```bicep
param location string
param storageAccountName string

resource storageAccount 'Microsoft.Storage/storageAccounts@2025-08-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    accessTier: 'Hot'
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2025-08-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    deleteRetentionPolicy: { enabled: true, days: 7 }
  }
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-08-01' = {
  parent: blobService
  name: 'data'
}

output storageAccountId string = storageAccount.id
```

{{< important >}}
Microsoft's Cloud Adoption Framework recommends the pattern `st[workload][environment][region][instance]` - for example `stdemodevuksouth001`. The `st` prefix is correct, but storage accounts have stricter constraints than most Azure resources; 24 characters max, lowercase alphanumeric only, no hyphens. That makes it difficult to fit workload, environment, and region components in and still guarantee global uniqueness.

`uniqueString()` sidesteps this by generating a deterministic 13-character hash from the resource group ID - the same RG always produces the same name, so redeployments are idempotent. The tradeoff is a name that gives you no context at a glance. In production you'd typically combine both approaches: a short readable prefix plus a truncated hash, such as `st${workload}${environment}${take(uniqueString(newRG.id), 6)}`.
{{< /important >}}

**A few notes on the properties set:**

- `supportsHttpsTrafficOnly: true` and `minimumTlsVersion: 'TLS1_2'` enforce encrypted transport.
- `allowBlobPublicAccess: false` prevents containers from being made publicly readable, which is the right default. The storage account itself is publicly accessible over the internet - if you need private access only, see the [private endpoint post](/posts/how-to-create-a-private-endpoint).
- `Standard_LRS` keeps costs low for a demo. For production, use `Standard_ZRS` or higher.

## Deploying

As the resource group is deployed as part of the template, the deployment targets the subscription rather than an existing resource group.

```bash
az deployment sub create --location uksouth --template-file main.bicep
```

## Verifying

Since the name is generated, pull it from the deployment output first:

```bash
az deployment sub show `
  --name main `
  --query "properties.outputs.storageAccountName.value" `
  --output tsv
```

Then verify the account:

```bash
az storage account show `
  --resource-group rg-demo-dev-uksouth-001 `
  --name <name from above> `
  --query "{sku: sku.name, kind: kind, httpsOnly: enableHttpsTrafficOnly, tlsVersion: minimumTlsVersion, blobPublicAccess: allowBlobPublicAccess, accessTier: accessTier}" `
  --output yaml
```

## Common gotchas

**1. Storage account names are globally unique and permanent**
The name becomes the endpoint (`youraccount.blob.core.windows.net`) and cannot be changed after deployment. If you get it wrong you need a new account and a data migration. Plan a naming scheme that includes an org identifier and environment suffix.

**2. `allowBlobPublicAccess` is account-level, not container-level**
Setting it to `false` at the account level blocks all containers from being made public regardless of their individual access settings. Setting it to `true` only allows containers to be made public - it doesn't make them public on its own.

**3. `Standard_LRS` is not suitable for production**
LRS stores three copies within a single datacentre. A zone or regional outage can make data unavailable. Use `Standard_ZRS` as the baseline for production workloads.

---

## Summary

Two files, one module call, and you have a storage account with a blob container deployed into a fresh resource group. The template enforces HTTPS and TLS 1.2 and disables blob public access, but otherwise keeps things simple. From here you can layer on redundancy, network restrictions, and RBAC as needed.
