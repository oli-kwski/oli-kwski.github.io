---
title: "What Is a Private DNS Zone and Why Do You Need One?"
date: 2026-07-17
draft: false
description: "Private DNS Zones are the often-overlooked half of Private Endpoint deployments. Here's how they work, why they matter, and the mistakes that trip people up."

tags:
  - Networking
  - DNS
  - Private Endpoints
  - Azure Fundamentals

pinned: true

cover:
  image: /covers/what-is-a-private-dns-zone-cover.svg
  alt: What Is a Private DNS Zone and Why Do You Need One
  relative: false

comments: true
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: true
ShowWordCount: false
weight: 1
---

If you've deployed a Private Endpoint and wondered why your VM is still hitting the public IP of a storage account, the answer is almost always DNS. Private DNS Zones are the piece that ties Private Endpoints together. If you haven't deployed a Private Endpoint yet, check out [What Are Private Endpoints and Why You Should Use Them](/posts/azure-private-endpoints-explained) first.

---

## The problem they solve

When you resolve `yourstorageaccount.blob.core.windows.net` from inside a VNet, without a Private DNS Zone you get the public IP - even if a Private Endpoint exists and is connected. The Private Endpoint creates a network path, but name resolution is a separate concern.

Azure solves this with Private DNS Zones. A Private DNS Zone is a DNS zone hosted by Azure that is only visible to resources inside the VNets you link it to. It contains an A record mapping the storage account's privatelink hostname to the Private Endpoint's private IP.

## How the resolution chain works

Azure PaaS services are designed to work with a CNAME indirection:

1. You resolve `yourstorageaccount.blob.core.windows.net`
2. Public Azure DNS returns a CNAME: `yourstorageaccount.privatelink.blob.core.windows.net`
3. If a Private DNS Zone for `privatelink.blob.core.windows.net` is linked to the resolving VNet, Azure returns the Private Endpoint's private IP
4. Traffic flows to the private IP, staying on the Microsoft backbone

From outside the VNet, step 3 resolves via public DNS to the storage account's public IP instead. The same hostname works in both contexts - the resolution path changes based on where the query originates.

## Which zone do I need?

Each Azure service has its own privatelink DNS zone. The most common ones are:

| Service | Sub-resource | Private DNS Zone |
|---|---|---|
| Azure Blob Storage | `blob` | `privatelink.blob.core.windows.net` |
| Azure File Storage | `file` | `privatelink.file.core.windows.net` |
| Azure SQL Database | `sqlServer` | `privatelink.database.windows.net` |
| Azure Key Vault | `vault` | `privatelink.vaultcore.azure.net` |
| Azure Container Registry | `registry` | `privatelink.azurecr.io` |
| Azure Monitor (Log Analytics) | `azuremonitor` | `privatelink.monitor.azure.com` * |
| Azure Service Bus | `namespace` | `privatelink.servicebus.windows.net` |

\* Azure Monitor Private Link needs five zones, not one: `privatelink.monitor.azure.com`, `privatelink.oms.opinsights.azure.com`, `privatelink.ods.opinsights.azure.com`, `privatelink.agentsvc.azure-automation.net`, and `privatelink.blob.core.windows.net`. Miss one and you'll get partial functionality - queries work but ingestion or agent connectivity silently falls back to public endpoints.

The full list is in the [Microsoft documentation](https://learn.microsoft.com/en-us/azure/private-link/private-endpoint-dns). There are dozens of zones - one per sub-resource type in many cases.

## VNet links

Creating a Private DNS Zone isn't enough on its own. You must **link it to the VNet** for resources in that VNet to use it. A zone can be linked to multiple VNets, and a VNet can have multiple zones linked to it.

Links have an optional **auto-registration** feature. When enabled, Azure automatically creates DNS records for VMs in the linked VNet. For Private Endpoint scenarios, leave this disabled - Private Endpoint records are registered via a DNS zone group on the endpoint itself, not auto-registration.

## Hub-and-spoke DNS

This is where most enterprise deployments go wrong.

In a hub-and-spoke topology, spoke VMs typically use the hub's DNS server (Azure Firewall DNS proxy, a custom resolver, or Azure DNS Private Resolver). If your Private DNS Zones are only linked to the spoke VNet, queries that flow through the hub's DNS won't find the zone - they'll fall back to public resolution and return the public IP.

**The fix:** link Private DNS Zones to the hub VNet (or wherever your central DNS resolver lives), not just the spokes.

With Azure DNS Private Resolver (the preferred approach for enterprise scale), you don't need to link zones to every spoke - only to the resolver's inbound endpoint VNet.

## Common gotchas

**1. Forgetting the VNet link entirely**
The zone exists, the DNS zone group on the Private Endpoint registered the A record - but nobody linked the zone to the VNet. Queries return the public IP. Always verify with `nslookup` or `dig` from inside the VNet.

**2. One zone per service type, not per resource**
You don't create a new `privatelink.blob.core.windows.net` zone for each storage account. You create one zone, link it to the VNet(s), and each Private Endpoint's DNS zone group adds its A record to that shared zone.

**3. Zone name must match exactly**
The zone name must be the full privatelink FQDN as listed in the documentation. A typo or slight variation means the zone is never consulted for that hostname.

**4. Auto-registration and Private Endpoints don't mix**
Auto-registration is designed for VM DNS records, not Private Endpoint records. Enable it on a zone that also receives Private Endpoint A records and you risk a name collision. If a VM's auto-registered hostname matches the name a Private Endpoint's DNS zone group needs to write, the Private Endpoint's record overwrites the VM's. Recreate that VM, or let it renew its lease, and auto-registration writes straight back over the Private Endpoint's record - so resolution flips depending on which one wrote last. Keep auto-registration disabled on zones used for Private Endpoints.

---

## Summary

Private DNS Zones are not optional when using Private Endpoints in any serious environment. They intercept name resolution for linked VNets and return the private IP instead of the public one. Create one zone per service type, link it to the right VNets (hub in a hub-and-spoke topology, not just the spokes), and leave auto-registration switched off. Get this right once and every Private Endpoint you deploy afterwards just works. Get it wrong and you'll be back here running `nslookup` from inside a VNet, wondering why traffic still isn't taking the private path.