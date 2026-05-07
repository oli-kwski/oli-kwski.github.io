---
title: "How to Create an Azure Private DNS Zone with Bicep"
date: 2026-04-30
draft: true
description: "Step-by-step Bicep for deploying a Private DNS Zone, linking it to a VNet, and wiring it up to a Private Endpoint."

tags:
  - Azure
  - Networking
  - DNS
  - Private DNS
  - Bicep
  - IaC
categories:
  - Azure
  - Networking
series:
  - Private DNS Zones

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
weight: 2
---

If you haven't read [What Is an Azure Private DNS Zone and Why Do You Need One?](/posts/what-is-a-private-dns-zone), start there. This post focuses on the Bicep to deploy one and wire it to a VNet.

---

## Prerequisites

- An existing VNet (or deploy one as part of the same template)
- Azure CLI authenticated (`az login`)

## The Bicep

### 1. Create the Private DNS Zone

Private DNS Zones are always deployed to `global` — they're not region-specific resources:

```bicep
@description('The private DNS zone name, e.g. privatelink.blob.core.windows.net')
param dnsZoneName string = 'privatelink.blob.core.windows.net'

resource privateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: dnsZoneName
  location: 'global'
}
```

### 2. Link it to a VNet

```bicep
@description('Resource ID of the VNet to link the zone to.')
param vnetId string

resource vnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: privateDnsZone
  name: 'link-${last(split(vnetId, '/'))}'
  location: 'global'
  properties: {
    virtualNetwork: {
      id: vnetId
    }
    registrationEnabled: false  // Leave false for Private Endpoint zones
  }
}
```

### 3. Full module

Combining both into a reusable module (`modules/privateDnsZone.bicep`):

```bicep
@description('The private DNS zone name.')
param dnsZoneName string

@description('Resource ID of the VNet to link to.')
param vnetId string

@description('Tags to apply to resources.')
param tags object = {}

resource privateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: dnsZoneName
  location: 'global'
  tags: tags
}

resource vnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: privateDnsZone
  name: 'link-${last(split(vnetId, '/'))}'
  location: 'global'
  properties: {
    virtualNetwork: {
      id: vnetId
    }
    registrationEnabled: false
  }
}

output privateDnsZoneId string = privateDnsZone.id
output privateDnsZoneName string = privateDnsZone.name
```

Calling the module from a parent template:

```bicep
module blobDnsZone './modules/privateDnsZone.bicep' = {
  name: 'blobDnsZoneDeploy'
  params: {
    dnsZoneName: 'privatelink.blob.core.windows.net'
    vnetId: vnet.id
    tags: {
      environment: 'prod'
      managedBy: 'bicep'
    }
  }
}
```

### 4. Wiring to a Private Endpoint

The DNS Zone Group on a Private Endpoint is what registers the A record in the zone automatically. Add this child resource to your Private Endpoint:

```bicep
resource privateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-09-01' = {
  parent: privateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-blob'
        properties: {
          privateDnsZoneId: blobDnsZone.outputs.privateDnsZoneId
        }
      }
    ]
  }
}
```

Azure creates and maintains the A record in the zone automatically — you don't manage it manually.

## Deploying

```bash
az deployment group create \
  --resource-group rg-networking-prod \
  --template-file main.bicep \
  --parameters vnetId='/subscriptions/<sub-id>/resourceGroups/rg-networking-prod/providers/Microsoft.Network/virtualNetworks/vnet-prod-uksouth-001'
```

## Verifying

Check the zone exists and the VNet link is active:

```bash
# List DNS zones
az network private-dns zone list \
  --resource-group rg-networking-prod \
  --output table

# List VNet links on a zone
az network private-dns link vnet list \
  --resource-group rg-networking-prod \
  --zone-name privatelink.blob.core.windows.net \
  --output table
```

Verify DNS resolution from inside the VNet (via a VM or Azure Bastion):

```bash
nslookup yourstorageaccount.blob.core.windows.net
```

You should see the CNAME chain resolve to a private IP (`10.x.x.x`), not the public Azure IP.

## Common gotchas

**1. Zone must be deployed to `location: 'global'`**
Private DNS Zones aren't regional. Using a region string causes a deployment error. Always use `'global'`.

**2. DNS zone group deletes and recreates the A record on redeploy**
The `privateDnsZoneGroups` resource is idempotent — redeploying it simply updates the record. But if you delete the DNS zone group resource, the A record in the zone is removed. Don't manage the A record manually if you're using a zone group; they'll conflict.

**3. Multiple VNet links for hub-and-spoke**
If you have a hub VNet and spoke VNets, link the zone to the hub (where DNS resolution happens). Spokes that route DNS queries through the hub don't need their own link — unless they have their own DNS server or use Azure DNS Private Resolver inbound endpoints in the spoke.

**4. One zone per service type across all environments in the same subscription**
You can only have one Private DNS Zone with a given name per subscription. If you're deploying dev and prod in the same subscription, they share the zone — meaning a dev storage account Private Endpoint registers an A record in the same zone as prod. Consider whether that's acceptable, or whether separate subscriptions (as recommended by the CAF landing zone model) are warranted.

---

## Summary

Creating a Private DNS Zone with Bicep is a two-resource job: the zone itself (always `global`) and the VNet link. Make it a module — you'll deploy the same pattern for every service type you expose via Private Endpoints. Wire the zone to each Private Endpoint via a `privateDnsZoneGroups` child resource rather than managing A records manually.
