---
title: "What Are Private Endpoints and Why You Should Use Them"
date: 2026-04-08
draft: true
description: "Private Endpoints bring Azure PaaS services onto your virtual network with a private IP address, eliminating exposure to the public internet. Here's how they work and why they matter."

tags:
  - Azure
  - Networking
  - Security
  - Private Endpoints
categories:
  - Networking

comments: true
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: false
ShowPostNavLinks: true
---

When you spin up an Azure Storage account, an Azure SQL database, or a Key Vault, those services are — by default — reachable over the public internet. They're protected by authentication and firewall rules, but the traffic still traverses Microsoft's public endpoints. For many organisations, especially those with compliance requirements or a zero-trust security posture, that's not good enough.

**Private Endpoints** solve this. They're one of the most impactful networking features in Azure, and once you understand how they work you'll wonder how you ever lived without them.

---

## The problem they solve

Consider a virtual machine in a VNet that needs to read blobs from an Azure Storage account. Without a Private Endpoint, the VM's traffic leaves the VNet, hits the public IP of `mystorageaccount.blob.core.windows.net`, and comes back in. Even with a service firewall rule restricting access to your subnet, the traffic is still using the public endpoint — it's just filtered.

This creates a few issues:

- **Attack surface** — the service is reachable from anywhere on the internet, relying on auth and firewall rules as the only protection
- **Data exfiltration risk** — outbound traffic to storage goes to a public endpoint, making it harder to lock down with egress controls
- **Compliance** — frameworks like PCI-DSS, ISO 27001, and NHS DSPT often require that sensitive data never traverse public networks

## What a Private Endpoint actually is

A Private Endpoint is a **network interface with a private IP address** inside your VNet, mapped to a specific Azure PaaS resource. That's it — it's just a NIC.

When you create a Private Endpoint for your Storage account, Azure allocates a private IP (say `10.0.1.5`) in your chosen subnet and associates it with your storage account. Traffic from within your VNet to that IP goes directly to the storage account over the Microsoft backbone — never touching the public internet.

```
VNet (10.0.0.0/16)
  └── subnet-app (10.0.1.0/24)
        ├── vm-app  10.0.1.4
        └── pe-storage  10.0.1.5  ──► mystorageaccount (blob)
```

You can then **disable the public endpoint entirely** on the storage account, making it completely unreachable from the internet regardless of auth credentials.

## Private DNS — the piece everyone forgets

Here's the part that trips people up. After creating a Private Endpoint, if you resolve `mystorageaccount.blob.core.windows.net` from inside the VNet you'll still get the public IP — nothing has changed in DNS yet.

Azure handles this with **Private DNS Zones**. When you create a Private Endpoint, Azure can automatically create a DNS record in a Private DNS Zone linked to your VNet:

| Service | Private DNS Zone |
|---|---|
| Azure Blob Storage | `privatelink.blob.core.windows.net` |
| Azure SQL Database | `privatelink.database.windows.net` |
| Azure Key Vault | `privatelink.vaultcore.azure.net` |
| Azure Container Registry | `privatelink.azurecr.io` |

The DNS zone contains an A record mapping your storage account's hostname to the private IP (`10.0.1.5`). When a VM in the linked VNet resolves `mystorageaccount.blob.core.windows.net`, it gets the CNAME `mystorageaccount.privatelink.blob.core.windows.net`, which the Private DNS Zone resolves to `10.0.1.5`.

From outside the VNet (including your laptop), the same hostname resolves to the public IP as normal. The magic is that VNet-linked DNS zones take precedence for resources inside the VNet.

> **Important:** If you're using a hub-and-spoke topology with centralised DNS (e.g. Azure Firewall DNS proxy or custom DNS servers on the hub), you need to link the Private DNS Zones to the hub VNet — not just the spoke. Otherwise your spoke VMs, routing through the hub's DNS, won't get the private IP responses.

## Setting one up

Here's a minimal Bicep snippet that creates a Private Endpoint for a Storage account and hooks it into a Private DNS Zone:

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

The `groupIds` value tells Azure which sub-resource of the service you're connecting to. For storage accounts you might create separate Private Endpoints for `blob`, `file`, `queue`, and `table` depending on what you need.

## When to use them

Private Endpoints make sense whenever:

- **You have PaaS services that should only be reachable from within your network** — databases, Key Vaults, storage, ACR
- **You're operating in a regulated environment** — financial services, healthcare, government
- **You use a hub-and-spoke or Azure Virtual WAN topology** — Private Endpoints integrate neatly with centralised egress and DNS
- **You want to disable public access entirely** — pairing a Private Endpoint with `publicNetworkAccess: Disabled` on the resource gives you the strongest posture

They're less necessary for public-facing services (App Services, API Management front-ends) or dev/test environments where the overhead isn't justified.

## Common gotchas

**1. NSGs on the Private Endpoint subnet**
Network Security Groups apply to Private Endpoint NICs from API version `2021-02-01` onwards, but you need to explicitly enable it on the subnet:

```bicep
properties: {
  privateEndpointNetworkPolicies: 'Enabled'
}
```

Prior to this, NSG rules were silently ignored on Private Endpoint subnets, which confused a lot of people.

**2. Cross-region Private Endpoints**
You can create a Private Endpoint in a different region from the target resource. Traffic still stays on the Microsoft backbone, but latency will be higher than a same-region deployment.

**3. Approval workflows**
If the target resource is in a different subscription or tenant, the Private Endpoint connection needs to be manually approved by the resource owner. You can automate this with `autoApproval` policies in Azure Policy if your organisation controls both sides.

**4. Cost**
Private Endpoints aren't free — at time of writing they're around £5–6/month per endpoint plus a small per-GB data processing charge. For production workloads this is negligible, but worth bearing in mind if you're creating many of them.

---

## Summary

Private Endpoints are the right way to connect to Azure PaaS services from within a VNet. They replace a public internet hop with a private NIC, allow you to disable public access entirely, and integrate cleanly with Private DNS Zones for seamless name resolution. The DNS configuration is the fiddly bit — get that right and the rest is straightforward.

If you're building anything resembling a production landing zone, Private Endpoints should be part of your standard pattern from day one.
