---
title: "Private Endpoint DNS in Hub-and-Spoke: What Goes Wrong"
date: 2026-08-07
draft: false
description: "In a single VNet, private endpoint DNS just works. In hub-and-spoke it quietly breaks. Here's why, and how each resolution pattern holds up under real conditions."

tags:
  - Networking
  - DNS
  - Private Endpoints
  - Hub-and-Spoke

cover:
  image: /covers/private-endpoint-dns-hub-spoke-cover.svg
  alt: Private Endpoint DNS in Hub-and-Spoke - What Goes Wrong
  relative: false

comments: true
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: false
weight: 2
---

In a single VNet, private endpoint DNS is straightforward: create the private DNS zone, link it to the VNet, and name resolution works. In a hub-and-spoke topology it's a different story - not because of the topology itself, but because most hub-and-spoke designs deliberately override the spokes' default DNS setting to point at something centralised in the hub, whether that be a custom DNS server or an Azure DNS Private Resolver inbound endpoint. Once that's configured, every query from the spoke goes there first, and if your private DNS zones aren't visible from that resolver, the query resolves to the public IP instead of the private one.

This post covers the three most common resolution patterns and where each one breaks.

---

## Why the single-VNet approach breaks in hub-and-spoke

Usually in hub-and-spoke, spoke VNets don't use Azure's default DNS (`168.63.129.16`) directly. Each spoke's DNS server settings point at a forwarder in the hub - a custom DNS VM or a DNS Private Resolver inbound endpoint.

Azure resolves private DNS zones only for VNets linked to the private zone. If you link `privatelink.blob.core.windows.net` to only the spoke VNet but DNS queries are actually resolved by something in the hub, the zone link on the spoke does nothing, as the hub resolver has no knowledge of the zone.

<figure class="diagram wide">
  <img src="/private-endpoint-dns-hub-spoke/broken-dns.svg" alt="Diagram showing a VM in a spoke VNet querying a custom DNS server in the hub VNet. The private DNS zone is only linked to the spoke. The hub resolver forwards to Azure DNS and returns the public IP." style="display: block; width: 100%; height: auto;" />
  <figcaption style="margin-top: 0.75rem; font-size: 0.875rem;">Zone linked to spoke, resolution happens in hub - returns public IP</figcaption>
</figure>

The fix is to link private DNS zones to the **hub VNet** - whichever VNet contains the resolver - not the spokes.

> **Important:** A note on terminology: "hub" here means wherever DNS resolution actually happens, not necessarily the network hub in your topology. If you've got domain controllers doing double duty as DNS servers in an identity spoke, and that spoke is zone-linked, it's the hub for DNS purposes even though it's a spoke for routing. What matters is which VNet the resolver sits in and which VNet has the zone links - not what you've labelled it in your Hub-Spoke diagram.

---

## Resolution patterns

### Azure DNS Private Resolver (recommended)

DNS Private Resolver is Microsoft's managed forwarding solution. It deploys two endpoint types into your hub VNet:

- **Inbound endpoint** - a private IP in your hub VNet that accepts DNS queries from spokes or on-premises.
- **Outbound endpoint** - used for forwarding queries out to on-premises or external resolvers.

For private endpoint resolution within Azure, you only need the inbound endpoint. Set all spoke VNet DNS settings to the inbound endpoint IP. Queries hit the inbound endpoint, which resolves via `168.63.129.16`, and because the private DNS zones are linked to the hub VNet, the correct private IP is returned.

<figure class="diagram wide">
  <img src="/private-endpoint-dns-hub-spoke/dns-private-resolver.svg" alt="Diagram showing a spoke VM querying the DNS Private Resolver inbound endpoint in the hub VNet. The private DNS zones are linked to the hub VNet. The resolver returns the private IP of the private endpoint." style="display: block; width: 100%; height: auto;" />
  <figcaption style="margin-top: 0.75rem; font-size: 0.875rem;">DNS Private Resolver with zones linked to hub VNet - correct pattern</figcaption>
</figure>

### Custom DNS forwarder

If you're using a DNS server VM (Windows Server DNS, BIND, or an NVA) in the hub, it must forward unknown queries to `168.63.129.16`, not a public resolver. The DNS server's VNet must be linked to all relevant private DNS zones.

The key requirement: the DNS server's own VNet must have the zones linked - peering doesn't help here. VNet peering provides network connectivity, not DNS zone visibility, so a custom DNS VM whose VNet isn't linked to the `privatelink.*` zones will still return public IPs, regardless of how well the forwarder is configured or how well-peered its VNet is.

### Zones linked directly to every spoke

You'll see guides suggesting this approach. It works for a single spoke in isolation, but breaks down at scale:

- Each private DNS zone supports up to 1,000 VNet links.
- With tens of spokes and tens of `privatelink.*` zones, you're creating thousands of zone links.
- It bypasses centralised DNS entirely, which makes on-premises integration much harder.

**Avoid this pattern in anything resembling a production landing zone.**

---

## Pattern comparison

| Scenario | DNS Private Resolver | Custom DNS forwarder |
|---|---|---|
| Greenfield, Azure-only | Preferred | Unnecessary complexity |
| Hybrid (on-prem forwarding) | Handles both directions cleanly | Works, higher ops overhead |
| Existing DNS server investment | Plan a migration path | Acceptable with correct forwarder config |
| Conditional per-domain forwarding | Forwarding rulesets | Full flexibility |

---

## Common gotchas

**1. Zone linked to spoke, not hub**

The most common mistake. If spoke VMs point DNS at a forwarder in the hub, zone links on spoke VNets are ignored at resolution time. Link all `privatelink.*` zones to the hub VNet - the one the resolver lives in.

**2. Custom forwarder pointing at a public DNS server**

If your DNS server forwards unknown queries to `8.8.8.8` or `1.1.1.1` instead of `168.63.129.16`, private DNS zones are never consulted. Azure's private DNS is only resolvable through the Azure-provided DNS address.

**3. On-premises DNS missing conditional forwarders**

Machines on-premises query your on-prem DNS server first. Conditional forwarders work on exact domain suffixes, not wildcards, so you need one per zone - `privatelink.blob.core.windows.net`, `privatelink.vaultcore.azure.net`, and so on for every `privatelink.*` zone in use. Miss one and on-prem clients resolve that service to its public IP even when Azure VMs resolve correctly.

**4. Multiple regional hubs**

If you have separate hub VNets per region (`hub-uksouth`, `hub-ukwest`), each hub needs its own DNS configuration and its own set of zone links. A private DNS zone linked to `hub-uksouth` is not visible to a resolver running in `hub-ukwest`.

**5. Inbound vs outbound endpoints confused**

The inbound endpoint receives DNS queries. The outbound endpoint (paired with forwarding rulesets) sends queries out of Azure to on-premises. A common mistake is creating only an outbound endpoint and then pointing spoke DNS at it, which does nothing for internal resolution.

**6. Auto-registration enabled on a privatelink zone**

When creating a VNet link, there's an auto-registration toggle. For `privatelink.*` zones this must be **off**. Auto-registration is for VM hostname records. Enabling it on a privatelink zone adds noise and can cause confusion when troubleshooting - the A records for your private endpoints are created by the private endpoint itself, not by zone registration.

**7. NSG rules applied to the DNS Private Resolver subnet**

DNS Private Resolver inbound endpoints require an empty, dedicated subnet. Applying NSGs with restrictive inbound rules to this subnet - particularly blocking UDP/TCP 53 from spoke address spaces - will silently drop DNS queries. DNS normally runs over UDP, but falls back to TCP for larger responses, so both need to be permitted. Use a dedicated subnet with an NSG that explicitly allows UDP and TCP 53 from your spoke ranges.

---

## Summary

DNS is what makes private endpoints actually private in practice. In hub-and-spoke, the zone links need to follow the DNS traffic, not the VNet topology. Link `privatelink.*` zones to the hub, point spokes at a resolver that lives there, and test name resolution explicitly from a spoke VM before declaring an endpoint working. DNS Private Resolver is the cleanest solution for new deployments - it removes the DNS VM as a single point of failure and handles the on-premises forwarding path with forwarding rulesets rather than manual forwarder configuration.
