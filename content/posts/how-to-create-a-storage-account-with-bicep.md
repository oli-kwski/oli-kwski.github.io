---
title: "How to Create an Azure Storage Account with Bicep"
date: 2026-04-30
draft: true
description: "A practical Bicep template for deploying a production-ready Azure Storage account with sensible security defaults."

tags:
  - Azure
  - Storage
  - Storage Account
  - Bicep
  - IaC
categories:
  - Azure
  - Storage
series:
  - Storage Accounts
  - Bicep

comments: true
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: true
ShowPostNavLinks: true
ShowWordCount: false
---

If you haven't read [What Is an Azure Storage Account and When Should You Use One?](/posts/what-is-a-storage-account), start there. This post is about deploying one with Bicep with a production-ready security baseline baked in.

---

## Prerequisites

- Azure CLI installed and authenticated
- A target resource group

## The Bicep

A StorageV2 account with ZRS redundancy, no public network access, and soft delete enabled:

```bicep
@description('Azure region.')
param location string = resourceGroup().location

@description('Storage account name. Must be 3-24 characters, lowercase alphanumeric only.')
@minLength(3)
@maxLength(24)
param storageAccountName string

@description('Storage account SKU.')
@allowed([
  'Standard_LRS'
  'Standard_ZRS'
  'Standard_GRS'
  'Standard_GZRS'
  'Premium_LRS'
  'Premium_ZRS'
])
param sku string = 'Standard_ZRS'

@description('Enable hierarchical namespace (Data Lake Gen2).')
param enableHierarchicalNamespace bool = false

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: {
    name: sku
  }
  properties: {
    // Security baseline
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false        // Require Azure AD auth; disable shared key
    publicNetworkAccess: 'Disabled'   // Use Private Endpoints for access

    // Data Lake Gen2 (cannot be changed after creation)
    isHnsEnabled: enableHierarchicalNamespace

    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'       // Allows trusted Microsoft services (e.g. Azure Backup)
      ipRules: []
      virtualNetworkRules: []
    }

    // Access tier for blob storage
    accessTier: 'Hot'
  }
}

// Blob service settings — soft delete and versioning
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 7
    }
    isVersioningEnabled: true
  }
}

// Optional: a container
resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'data'
  properties: {
    publicAccess: 'None'
  }
}

output storageAccountId string = storageAccount.id
output storageAccountName string = storageAccount.name
output primaryBlobEndpoint string = storageAccount.properties.primaryEndpoints.blob
```

## Deploying

```bash
az deployment group create \
  --resource-group rg-storage-prod \
  --template-file storage.bicep \
  --parameters storageAccountName='stproduksouth001' sku='Standard_ZRS'
```

## Adding a Private Endpoint

With `publicNetworkAccess: 'Disabled'`, the storage account is unreachable without a Private Endpoint. Deploy one using the Private Endpoint Bicep from the [Creating a Private Endpoint in Azure with Bicep](/posts/how-to-create-a-private-endpoint) post. Reference the storage account resource ID as the `privateLinkServiceId` and use `blob` as the `groupId`.

## Assigning RBAC

With shared key access disabled, you need to assign RBAC roles instead. Assign `Storage Blob Data Contributor` (or Contributor/Reader) to managed identities or users:

```bicep
resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccount.id, principalId, storageBlobDataContributorRole)
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'ba92f5b4-2d11-453d-a403-e96b0029c9fe'  // Storage Blob Data Contributor
    )
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}
```

## Verifying

```bash
# Check the storage account properties
az storage account show \
  --resource-group rg-storage-prod \
  --name stproduksouth001 \
  --query '{publicNetworkAccess: publicNetworkAccess, httpsOnly: enableHttpsTrafficOnly, tls: minimumTlsVersion, sharedKey: allowSharedKeyAccess}' \
  --output table
```

From inside the linked VNet, verify the blob endpoint resolves to a private IP:

```bash
nslookup stproduksouth001.blob.core.windows.net
```

## Common gotchas

**1. `allowSharedKeyAccess: false` breaks some Azure services**
Some Azure services — including certain Azure portal operations and Azure Storage Explorer when not using Azure AD — rely on shared key access. Disabling it can break diagnostics logging, Azure Backup for VMs, and some Functions bindings. Test thoroughly in a non-production environment first.

**2. `publicNetworkAccess: 'Disabled'` vs `defaultAction: 'Deny'`**
Setting `publicNetworkAccess: 'Disabled'` is a hard block — no firewall rules can override it. Setting `defaultAction: 'Deny'` with IP or VNet rules is softer — it allows exceptions. Use `'Disabled'` for fully private storage, `'Deny'` with exceptions if you need hybrid access (e.g. an on-premises IP allowlist).

**3. Blob versioning increases storage costs**
Versioning retains previous blob versions indefinitely until explicitly deleted or a lifecycle policy removes them. Enable a lifecycle policy alongside versioning or storage costs can grow unexpectedly.

**4. Storage account name is permanent**
You cannot rename a storage account. The name becomes part of the endpoint (`youraccount.blob.core.windows.net`) and cannot be changed. If you get the name wrong in production, you need a new storage account and a data migration.

---

## Summary

A production-ready storage account in Bicep is a few dozen lines of configuration, but the defaults Azure ships are not suitable for production. Disable public access, require HTTPS and TLS 1.2, disable shared key access, enable soft delete and versioning on the blob service, and deploy Private Endpoints for internal access. Sort the security baseline at deploy time — retrofitting it to a storage account with existing clients is painful.
