---
title: "How to Create an Azure VNet with Bicep"
date: 2026-04-30
draft: true
description: "A practical guide to deploying an Azure Virtual Network and subnets using Bicep, including parameter patterns and common configuration options."

tags:
  - Azure
  - Networking
  - VNet
  - Bicep
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
weight: 2
---

If you haven't read [What Is an Azure Virtual Network?](/posts/what-is-a-vnet), start there. This post assumes you know what a VNet is and focuses on deploying one with Bicep.

---

## Prerequisites

- Azure CLI installed and authenticated (`az login`)
- A target resource group (or deploy one as part of this)
- Bicep CLI (`az bicep install` if not present)

## The Bicep

A VNet with two subnets — one for workloads, one for private endpoints:

```bicep
@description('Azure region for the VNet.')
param location string = resourceGroup().location

@description('Name of the VNet.')
param vnetName string = 'vnet-prod-uksouth-001'

@description('Address space for the VNet.')
param vnetAddressPrefix string = '10.0.0.0/16'

resource vnet 'Microsoft.Network/virtualNetworks@2023-09-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
    subnets: [
      {
        name: 'snet-workloads'
        properties: {
          addressPrefix: '10.0.1.0/24'
          // Uncomment to attach an NSG
          // networkSecurityGroup: {
          //   id: nsg.id
          // }
        }
      }
      {
        name: 'snet-private-endpoints'
        properties: {
          addressPrefix: '10.0.2.0/24'
          // Enable NSG support on the Private Endpoint subnet (off by default)
          privateEndpointNetworkPolicies: 'Enabled'
        }
      }
    ]
    // Use Azure-provided DNS (default). Override with custom DNS server IPs:
    // dhcpOptions: {
    //   dnsServers: ['10.0.0.4']
    // }
  }
}

output vnetId string = vnet.id
output vnetName string = vnet.name
output subnetIds object = {
  workloads: vnet.properties.subnets[0].id
  privateEndpoints: vnet.properties.subnets[1].id
}
```

## Deploying

Deploy to an existing resource group:

```bash
az deployment group create \
  --resource-group rg-networking-prod \
  --template-file vnet.bicep \
  --parameters vnetName='vnet-prod-uksouth-001' vnetAddressPrefix='10.0.0.0/16'
```

Or use a parameters file (`vnet.bicepparam`):

```bicep
using 'vnet.bicep'

param vnetName = 'vnet-prod-uksouth-001'
param vnetAddressPrefix = '10.0.0.0/16'
```

```bash
az deployment group create \
  --resource-group rg-networking-prod \
  --template-file vnet.bicep \
  --parameters vnet.bicepparam
```

## Verifying

Check the deployed VNet and its subnets:

```bash
az network vnet show \
  --resource-group rg-networking-prod \
  --name vnet-prod-uksouth-001 \
  --query '{addressSpace: addressSpace.addressPrefixes, subnets: subnets[].{name: name, prefix: addressPrefix}}' \
  --output table
```

## Adding a DNS zone link

Once you have a Private DNS Zone deployed, link it to the VNet as a separate resource — not inline in the VNet Bicep:

```bicep
resource dnsZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: privateDnsZone
  name: 'link-${vnet.name}'
  location: 'global'
  properties: {
    virtualNetwork: {
      id: vnet.id
    }
    registrationEnabled: false
  }
}
```

Keep DNS zone links in the same Bicep file as the DNS zones, referencing the VNet by ID — this avoids circular dependencies when the VNet and DNS zones are in separate modules.

## Common gotchas

**1. Subnets defined in the VNet resource vs. as child resources**
You can define subnets either inline (as shown above) or as separate `Microsoft.Network/virtualNetworks/subnets` child resources. Don't mix both approaches in the same template — doing so causes race conditions during deployment where one definition overwrites the other, stripping subnets that Bicep thought were authoritative.

**2. `privateEndpointNetworkPolicies` defaults to `Disabled`**
NSG rules are silently ignored on Private Endpoint subnets unless you set `privateEndpointNetworkPolicies: 'Enabled'`. If you're attaching an NSG to your private endpoint subnet and wondering why deny rules aren't being respected, this is why.

**3. Re-deploying doesn't remove subnets**
If you remove a subnet from the Bicep and redeploy, the subnet is deleted — including anything in it. Treat the VNet Bicep as the authoritative list of subnets and be deliberate about removals.

**4. Naming convention**
The [Azure naming convention](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/resource-naming) for VNets is `vnet-<workload>-<env>-<region>-<instance>` (e.g. `vnet-shared-prod-uksouth-001`) and subnets `snet-<purpose>`. Establish this from day one — renaming a VNet means recreating it.

---

## Summary

Deploying a VNet with Bicep is straightforward. Define the address space, list your subnets inline, and output the resource IDs for use in downstream modules. The main things to get right upfront: address space sizing, subnet sizing, and whether you need custom DNS. All of those become expensive to change after resources are deployed.
