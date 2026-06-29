---
title: "What is a Virtual Network (VNet)?"
date: 2026-05-08
draft: false
description: "Virtual Networks are fundamental to networking in Azure. Here's how they work, why you need them, and what to watch out for when planning one."

tags:
  - Networking
  - VNet
  - Azure Fundamentals

pinned: true

cover:
  image: /covers/networking.svg
  alt: Azure Networking
  relative: false

comments: true
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: true
ShowWordCount: false
weight: 1
---

Every resource you deploy in Azure needs to communicate with other resources. VNets make this possible. Before you can connect VMs, deploy private endpoints, or route traffic through a firewall, you need a VNet.

---

## The problem they solve

Think of a VNet as the Azure equivalent of a traditional on-premises LAN, except it's software-defined - and best of all, you never have to rack a switch.

Within Azure there is a need for network isolation; without it, Azure resources would sit in a flat, shared network. VNets give you that logical isolation. Your resources are segregated from other Azure customers and from other VNets (unless peered), with full control over IP addressing, routing, and access.


## What is a VNet?

A VNet is a logically isolated network in Azure, scoped to a single region and a single subscription. 

When you create a VNet, you define:

- **Address space** - one or more CIDR ranges (e.g. `10.0.0.0/16`) that the VNet owns.
- **Subnets** - subdivisions of that address space where resources are attached (e.g. `10.0.1.0/24`).
- **DNS settings** - Azure-provided DNS (default) or custom DNS servers (your own resolver, Azure Firewall with DNS proxy, or DNS servers if AD is still present in your environment).
- **DDoS protection** - Infrastructure protection (formerly basic) is free. Standard (DDoS Network Protection) is a paid per-plan charge, one plan covers multiple VNets.

{{< important >}}
Resources don't attach to the VNet directly - they attach to a subnet within the VNet via a network interface card (NIC).
{{< /important >}}

## Key concepts

| Concept | What it does |
|---|---|
| Address space | The overall CIDR block(s) owned by the VNet |
| Subnet | A segment of the address space. This is where a resource gets its IP from |
| NSG | Controls inbound/outbound traffic at subnet or NIC level |
| Route table | Controls where traffic is sent (e.g. force via firewall) |
| VNet peering | Connects two VNets for private traffic |
| Private DNS zone | Provides internal name resolution for resources in the VNet |
| Service endpoint | Extends the VNet identity to a PaaS service's public endpoint |
| Private endpoint | Brings a PaaS service into the VNet with a private IP |

## VNet scope

VNets are regional - a VNet in UK South cannot natively span to North Europe. To connect VNets across regions, you use **global VNet peering** or **Azure Virtual WAN**. VNets are also subscription-scoped, though cross-subscription peering is fully supported. All VNet peerings by default are non-transitive.

## Planning your address space

This is where most mistakes are made. You should pick ranges from RFC 1918 private space:

- `10.0.0.0/8`
- `172.16.0.0/12`
- `192.168.0.0/16`

Avoid ranges that overlap with:
- On-premises networks (if connecting via VPN or ExpressRoute)
- Other VNets you intend to peer with
- Azure-reserved ranges (`169.254.0.0/16` - used for link-local services including the Instance Metadata Service at `169.254.169.254`, and `168.63.129.16/32` - Azure's internal DNS resolver)

Azure reserves 5 IP addresses in every subnet - the first four and the last one. So a `/29` leaves you only 3 usable IPs. Make sure you size subnets with room to grow.

## Common gotchas

**1. You cannot resize a subnet that contains resources** - Once VMs, private endpoints, or other resources are deployed into a subnet, you cannot change the subnet CIDR without removing them first. Be generous when planning.

**2. Adding address space is fine. Removing it is not** - You can add a new, non-overlapping range to an existing VNet. Removing a range in use by subnets requires deleting those subnets and everything in them first.

**3. Peered VNets cannot have overlapping address spaces** - If you're planning a hub-and-spoke topology, all VNets must have unique, non-overlapping address spaces. Discovering an overlap after peering is established is painful - you'll need to remove the peering, rework the address space (which requires clearing subnets), and re-peer.

**4. Custom DNS requires a forwarder to `168.63.129.16`** - If you're using custom DNS servers, e.g. Active Directory DNS or Azure Firewall DNS proxy, they must forward unresolved queries to `168.63.129.16` (Azure's internal resolver). Without this, Private DNS zones linked to the VNet won't resolve correctly from inside the VNet.

**5. Reserved subnet names have exact sizing requirements** - Several subnet names are reserved by Azure and must be named exactly (case-sensitive). Each has a minimum size - deploying undersized will cause deployment to fail.

| Subnet name | Minimum size |
|---|---|
| `AzureBastionSubnet` | `/26` |
| `AzureFirewallManagementSubnet` | `/26` (Basic SKU and forced tunnel deployments only) |
| `AzureFirewallSubnet` | `/26` |
| `GatewaySubnet` | `/27` |
| `RouteServerSubnet` | `/27` |

---

## Summary

VNets are the starting point for almost everything in Azure networking. Get the address space right in the first instance, it's the one thing that's genuinely painful to change after resources are deployed.