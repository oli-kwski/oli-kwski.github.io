---
title: "What Is an Azure Virtual Network (VNet)?"
date: 2026-04-30
draft: true
description: "Virtual Networks are the fundamental networking primitive in Azure. Here's how they work, why you need them, and what to watch out for when planning one."

tags:
  - Azure
  - Networking
  - VNet
categories:
  - Azure
  - Networking
series:
  - VNets

comments: true
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: true
ShowPostNavLinks: true
ShowWordCount: false
---

Every resource you deploy in Azure lives somewhere. A Virtual Network (VNet) is that somewhere. Before you can connect VMs, deploy private endpoints, or route traffic through a firewall, you need a VNet.

---

## The problem they solve

Without network isolation, Azure resources would sit in a flat, shared network. VNets give you logical isolation: your resources are segregated from other Azure customers and from your own other environments, with full control over IP addressing, routing, and access.

Think of a VNet as the Azure equivalent of a traditional on-premises LAN — except it's software-defined, spans availability zones automatically, and you never have to rack a switch.

## What is a Virtual Network?

A VNet is a logically isolated network in Azure, scoped to a single region and a single subscription. When you create one, you define:

- **Address space** — one or more CIDR ranges (e.g. `10.0.0.0/16`) that the VNet owns.
- **Subnets** — subdivisions of that address space where resources actually attach (e.g. `10.0.1.0/24`).
- **DNS settings** — Azure-provided DNS (default) or custom DNS servers (your own resolver or Azure Firewall with DNS proxy).
- **DDoS protection** — Basic is free; Standard is a paid per-plan charge and covers all resources in the VNet.

Resources don't attach to the VNet directly — they attach to a **subnet** within the VNet via a network interface card (NIC).

## Key concepts

| Concept | What it does |
|---|---|
| Address space | The overall CIDR block(s) owned by the VNet |
| Subnet | A segment of the address space; resources live here |
| NSG | Controls inbound/outbound traffic at subnet or NIC level |
| Route table | Controls where traffic is sent (e.g. force via firewall) |
| VNet peering | Connects two VNets for private traffic |
| Private DNS zone | Provides internal name resolution for resources in the VNet |
| Service endpoint | Extends the VNet identity to a PaaS service's public endpoint |
| Private endpoint | Brings a PaaS service into the VNet with a private IP |

## VNet scope

VNets are regional — a VNet in UK South cannot natively span to North Europe. To connect VNets across regions, you use **global VNet peering** or **Azure Virtual WAN**. VNets are also subscription-scoped, though cross-subscription peering is fully supported.

## Planning your address space

This is where most mistakes are made. Pick ranges from RFC 1918 private space:

- `10.0.0.0/8`
- `172.16.0.0/12`
- `192.168.0.0/16`

Avoid ranges that overlap with:
- On-premises networks (if connecting via VPN or ExpressRoute)
- Other VNets you intend to peer with
- Azure-reserved ranges (`169.254.0.0/16`, `168.63.129.16`)

Azure **reserves 5 IP addresses in every subnet** — the first four and the last one. A `/29` leaves you only 3 usable IPs. Size subnets with room to grow.

## Common gotchas

**1. You cannot resize a subnet that contains resources**
Once VMs, Private Endpoints, or other resources are deployed into a subnet, you cannot change the subnet CIDR without removing them first. Plan generously upfront.

**2. Adding address space is fine; removing it is not**
You can add a new, non-overlapping range to an existing VNet. Removing a range that subnets use requires deleting those subnets and everything in them first.

**3. Peered VNets cannot have overlapping address spaces**
If you're planning a hub-and-spoke topology, all VNets must have unique, non-overlapping address spaces. Discovering an overlap after peering is established is painful — you'll need to remove the peering, rework the address space (which requires clearing subnets), and re-peer.

**4. Custom DNS requires a forwarder to `168.63.129.16`**
If you're using custom DNS servers — Active Directory DNS, Unbound, or Azure Firewall DNS proxy — they must forward unresolved queries to `168.63.129.16` (Azure's internal resolver). Without this, Private DNS zones linked to the VNet won't resolve correctly from inside the VNet.

---

## Summary

VNets are the starting point for almost everything in Azure networking. Get the address space right at the outset — it's the one thing that's genuinely painful to change after resources are deployed. Size subnets generously, plan for peering from day one if you're building a landing zone, and understand that NSGs and route tables are your primary tools for controlling traffic within and between VNets.
