---
title: "Creating a Private Endpoint in Azure with Bicep"
date: 2026-04-15
draft: true
description: "A step-by-step guide to deploying an Azure Private Endpoint for a Storage account using Bicep, including Private DNS Zone integration."

tags:
  - Azure
  - Networking
  - Security
  - Private Endpoints
  - Bicep
  - IaC
categories:
  - Networking
series:
  - Private Endpoints

comments: true
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: false
ShowPostNavLinks: true
---

This post walks through creating a Private Endpoint for an Azure Storage account using Bicep. If you're not familiar with what Private Endpoints are and why you'd want one, start with [What Are Private Endpoints and Why You Should Use Them](/posts/azure-private-endpoints-explained).

---

## Prerequisites

Before deploying, you'll need:

- An existing virtual network and subnet to host the Private Endpoint
- An existing Private DNS Zone for `privatelink.blob.core.windows.net` linked to your vnet (or you can create one as part of this deployment)
- An existing Storage account

## The Bicep

Here's a minimal Bicep snippet that creates a Private Endpoint for a Storage account blob sub-resource and registers it in a Private DNS Zone:

```bicep
resource privateEndpoint 'Microsoft.Network/privateEndpoints@2023-09-01' = {
  name: 'pe-${storageAccount.name}'
  location: location
  properties: {
    subnet: {
      id: subnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'pe-${storageAccount.name}-connection'
        properties: {
          privateLinkServiceId: storageAccount.id
          groupIds: ['blob']  // 'blob' | 'file' | 'queue' | 'table'
        }
      }
    ]
  }
}

resource privateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-09-01' = {
  parent: privateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-blob'
        properties: {
          privateDnsZoneId: privateDnsZone.id  // privatelink.blob.core.windows.net
        }
      }
    ]
  }
}
```

### groupIds — picking the right sub-resource

The `groupIds` value tells Azure which sub-resource of the service you're connecting to. A single storage account exposes multiple sub-resources, each requiring its own Private Endpoint if you want full private coverage:

| groupId | Endpoint |
|---|---|
| `blob` | `youraccount.blob.core.windows.net` |
| `file` | `youraccount.file.core.windows.net` |
| `queue` | `youraccount.queue.core.windows.net` |
| `table` | `youraccount.table.core.windows.net` |
| `dfs` | `youraccount.dfs.core.windows.net` (Data Lake) |

In practice, deploy only the sub-resources you actually use.

## Disabling public access

Once you've verified traffic flows over the private endpoint, lock down the storage account's public endpoint:

```bicep
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  // ...
  properties: {
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
  }
}
```

Setting `publicNetworkAccess: 'Disabled'` takes precedence over all firewall rules — the public endpoint is completely closed regardless of what IP allowlists or vnet service endpoint rules exist.

## Verifying it works

From a VM or other resource inside the linked vnet, check that the storage hostname resolves to the private IP:

```bash
nslookup yourstorageaccount.blob.core.windows.net
```

You should see the response chain through `privatelink.blob.core.windows.net` and resolve to a private IP in your subnet — not the public IP. If you still see the public IP, the Private DNS Zone is either not linked to the vnet or the DNS zone group wasn't created correctly.

For hub-and-spoke topologies using a centralised DNS server or Azure Firewall DNS proxy, ensure the Private DNS Zone is linked to the **hub** vnet, not just the spoke.

## Common gotchas

**NSG support on the subnet**
NSGs apply to Private Endpoint NICs from API version `2021-02-01` onwards, but you must explicitly opt in at the subnet level:

```bicep
properties: {
  privateEndpointNetworkPolicies: 'Enabled'
}
```

Without this, NSG rules are silently ignored on the Private Endpoint subnet.

**Approval workflows**
If the target resource is in a different subscription or tenant, the Private Endpoint connection requires manual approval from the resource owner. Automate this with `autoApproval` policies in Azure Policy if your organisation controls both sides.

**Cost**
Private Endpoints cost around £5–6/month per endpoint plus a small per-GB data processing charge. Negligible for production, but worth tracking if you're deploying many.

---

## Summary

Deploying a Private Endpoint with Bicep is straightforward once the DNS wiring is understood. Create the `privateEndpoints` resource, attach a `privateDnsZoneGroups` child resource to register the A record automatically, then disable the public endpoint on the storage account. Verify with `nslookup` from inside the vnet before considering the job done.
