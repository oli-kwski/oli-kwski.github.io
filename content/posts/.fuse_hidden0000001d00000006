---
title: "What Is an Azure Network Security Group (NSG)?"
date: 2026-04-30
draft: true
description: "Network Security Groups are the primary access control mechanism for Azure VNets. Here's how they work, where to attach them, and the rules that catch people out."

tags:
  - Azure
  - Networking
  - NSG
  - Security
categories:
  - Azure
  - Networking
series:
  - Network Security Groups

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
ShowPostNavLinks: true
ShowWordCount: false
weight: 1
---

Once you have a VNet and subnets, the next question is how to control what traffic can flow between them. Network Security Groups (NSGs) are the answer for most scenarios — the lightweight, stateful firewall you attach to subnets or individual NICs to allow or deny traffic.

---

## The problem they solve

Without NSGs, all traffic within a VNet flows freely between subnets. Any VM in one subnet can reach any VM in another subnet on any port. NSGs let you define exactly which traffic is permitted, enforced at the subnet level, the NIC level, or both.

They're not a replacement for Azure Firewall in complex routing scenarios, but for east-west traffic control within a VNet — and for inbound internet access to specific ports — NSGs are the right tool.

## What is an NSG?

An NSG is a set of security rules evaluated in priority order (100–4096, lower number = higher priority). Each rule specifies:

- **Priority** — determines evaluation order; first matching rule wins
- **Source / Destination** — IP, CIDR, service tag, or application security group
- **Port** — single port, range, or `*` for all
- **Protocol** — TCP, UDP, ICMP, or Any
- **Action** — Allow or Deny

NSGs are **stateful** — if an outbound connection is permitted, the return traffic is automatically allowed without a separate inbound rule (and vice versa).

## Default rules

Every NSG ships with three inbound and three outbound default rules that cannot be deleted (priority 65000–65500):

**Inbound defaults:**
| Priority | Name | Allows |
|---|---|---|
| 65000 | AllowVnetInbound | All traffic from within the VNet |
| 65001 | AllowAzureLoadBalancerInbound | Health probe traffic from Azure Load Balancer |
| 65500 | DenyAllInbound | Everything else |

**Outbound defaults:**
| Priority | Name | Allows |
|---|---|---|
| 65000 | AllowVnetOutbound | All traffic to within the VNet |
| 65001 | AllowInternetOutbound | All outbound traffic to the internet |
| 65500 | DenyAllOutbound | Everything else |

The `AllowInternetOutbound` default is notable — VMs in a VNet can reach the internet by default unless you override it. If you're using Azure Firewall or an NVA for egress control, you need to override this with a route table (UDR) that sends internet-bound traffic to the firewall, not just an NSG deny rule.

## Where to attach an NSG

NSGs can be attached to **subnets** or **individual NICs**:

| Attachment point | Traffic controlled |
|---|---|
| Subnet | All traffic in/out of every resource in the subnet |
| NIC | Traffic to/from that specific resource only |

**Best practice: attach to subnets, not NICs.** NIC-level NSGs are harder to manage at scale and create operational complexity when rules need to be consistent across resources. Use subnet-level NSGs as your primary control, and NIC-level NSGs only when you need resource-specific exceptions.

When both a subnet NSG and a NIC NSG exist, **both** are evaluated. For inbound traffic: subnet NSG first, then NIC NSG. For outbound: NIC NSG first, then subnet NSG.

## Service tags

Instead of hardcoding IP ranges, NSGs support **service tags** — named groups of IP ranges that Microsoft maintains. Common ones:

| Tag | What it covers |
|---|---|
| `Internet` | All public internet IPs |
| `VirtualNetwork` | All IPs in the VNet and peered VNets |
| `AzureLoadBalancer` | Azure Load Balancer health probe IPs |
| `Storage` | Azure Storage service IPs (for the current region with `.UKSouth`) |
| `AzureMonitor` | Azure Monitor endpoints |
| `GatewayManager` | Azure VPN/Application Gateway management IPs |

Use service tags rather than IP ranges wherever possible — Microsoft updates the IP ranges behind service tags automatically.

## Application Security Groups

Application Security Groups (ASGs) let you group VMs logically and use those groups in NSG rules, rather than individual IPs or subnets. A rule referencing an ASG automatically applies to all NICs in that group:

```
Allow: ASG-WebTier → ASG-AppTier : TCP 8080
```

ASGs reduce the need for subnet-per-tier architectures and make NSG rules more readable and maintainable. The downside: ASGs are scoped to a VNet and a region, so they don't span across VNets.

## Common gotchas

**1. NSGs on Private Endpoint subnets are ignored by default**
Until you explicitly enable `privateEndpointNetworkPolicies` on the subnet, NSG rules are silently bypassed for Private Endpoint traffic. This is a common security misconfiguration. Enable the setting at the subnet level and verify NSG rules are being applied.

**2. DenyAllInbound doesn't block traffic within the subnet**
The `AllowVnetInbound` default rule covers all traffic from within the VNet, including other subnets. If you want to block traffic between subnets, add an explicit Deny rule with a lower priority number than 65000, specifying the source subnet CIDR.

**3. Effective security rules differ from configured rules**
When troubleshooting, use **Effective security rules** in the Azure portal (Network Watcher → Effective security rules) or `az network nic list-effective-nsg`. This shows the merged result of subnet + NIC NSGs, which is what's actually enforced — not just what you've configured on each NSG individually.

**4. NSG flow logs are not enabled by default**
NSG flow logs (for Network Watcher) capture allowed and denied flows — essential for security investigations. They're not enabled by default and have a small cost (storage + optional Traffic Analytics). Enable them from day one in production.

---

## Summary

NSGs are stateful, rule-based access control at the subnet or NIC level. Attach them to subnets, use service tags and ASGs instead of raw IP ranges where possible, and explicitly enable NSG policies on Private Endpoint subnets. Enable 