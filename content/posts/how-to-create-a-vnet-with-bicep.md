---
title: "How to Create a VNet with Bicep"
date: 2026-05-14
draft: false
description: "A practical guide to deploying a Virtual Network and subnets using Bicep in Azure, including parameter patterns and common configuration options."

tags:
  - Networking
  - VNet
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

This post assumes you know what a VNet is and focuses on deploying a VNet with Bicep. If you don't know what a VNet is, read this post first [What Is an Azure Virtual Network?](/posts/what-is-a-vnet)

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
- A VNet with two subnets

The code is split into 2 files, `main.bicep` and a VNet module named `vnet.bicep`.

### main.bicep

```bicep
targetScope = 'subscription'

param location string = 'uksouth'
param rgName string = 'rg-demo-dev-uksouth-001'

resource newRG 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: rgName
  location: location
}

module vnetDeployment './vnet.bicep' = {
  scope: resourceGroup(newRG.name)
  name: 'vnetDeployment'
}
```

### vnet.bicep

```bicep
@description('Azure region for the VNet.')
param location string = resourceGroup().location

@description('Name of the VNet.')
param vnetName string = 'vnet-demo-dev-uksouth-001'

@description('Address space for the VNet.')
param vnetAddressPrefix string = '10.0.0.0/16'

resource vnet 'Microsoft.Network/virtualNetworks@2025-05-01' = {
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
        }
      }
      {
        name: 'snet-private-endpoints'
        properties: {
          addressPrefix: '10.0.2.0/24'
        }
      }
    ]
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

As we are deploying the resource group for the VNet as part of the deployment we need to deploy directly to a subscription, you will have picked which subsciption when logging in to AZ CLI.

```bash
az deployment sub create --location uksouth --template-file main.bicep
```

## Verifying

Check the deployed VNet and its subnets:

```bash
az network vnet show `
  --resource-group rg-demo-dev-uksouth-001 `
  --name vnet-demo-dev-uksouth-001 `
  --query "{addressSpace: addressSpace.addressPrefixes, subnets: subnets[].{name: name, prefix: addressPrefix}}" `
  --output yaml
```

## Common gotchas

**1. Subnets defined in the VNet resource vs. as child resources**
You can define subnets either inline (as shown above) or as separate `Microsoft.Network/virtualNetworks/subnets` child resources. Don't mix both approaches in the same template - doing so causes race conditions during deployment where one definition overwrites the other, stripping subnets that Bicep thought were authoritative.

**2. `privateEndpointNetworkPolicies` defaults to `Disabled`**
NSG rules are silently ignored on Private Endpoint subnets unless you set `privateEndpointNetworkPolicies: 'Enabled'`. If you're attaching an NSG to your private endpoint subnet and wondering why deny rules aren't being respected, this is why.

**3. Re-deploying doesn't remove subnets**
If you remove a subnet from the Bicep and redeploy, the subnet is deleted - including anything in it. Treat the VNet Bicep as the authoritative list of subnets and be deliberate about removals.

**4. Naming convention**
The [Azure naming convention](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/resource-naming) for VNets is `vnet-<workload>-<env>-<region>-<instance>` (e.g. `vnet-demo-dev-uksouth-001`) and subnets `snet-<purpose>`. Establish this from day one - renaming a VNet means recreating it.

---

## Summary

Deploying a VNet with Bicep is straightforward. Define the address space, list your subnets inline, and output the resource IDs for use in downstream modules. The main things to get right upfront are; address space sizing, subnet sizing, and whether you need custom DNS. All of those become difficult to change after resources are deployed.
