---
title: "AVD: Hybrid Join vs Entra-Only - What Actually Changes"
date: 2026-05-31
draft: true
tags:
  - AVD
  - Azure Virtual Desktop
  - Entra ID
  - Identity
description: "A straight comparison of hybrid-joined and Entra-only AVD deployments - architecture, requirements, gotchas, and when to pick each."

cover:
  image: /covers/general.svg
  alt: AVD Hybrid vs Entra-only
  relative: false

comments: true
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: true
ShowWordCount: false
---

Azure Virtual Desktop has supported Entra-only (cloud-native) session hosts for a while now, but a lot of deployments are still hybrid-joined out of habit or because the FSLogix story wasn't there yet. It is now. Here's what actually changes between the two models.

## The core difference

With **hybrid join**, your session hosts are domain-joined to on-premises AD and also registered in Entra ID via Entra Connect. The VMs need line-of-sight to a domain controller - either on-prem or something like Active Directory Domain Services running in Azure.

With **Entra-only join**, there's no AD domain involved at all. The VMs register directly in Entra ID. No DC, no Entra Connect, no line-of-sight requirement.

```
Hybrid join
──────────────────────────────────────────────────
User ──► Entra ID (auth) ──► AVD gateway
                               │
                         Session host (VM)
                               │
                         AD Domain Controller
                         (Kerberos, GPO, etc.)

Entra-only join
──────────────────────────────────────────────────
User ──► Entra ID (auth) ──► AVD gateway
                               │
                         Session host (VM)
                         (Entra-joined, Intune-managed)
```

## Side-by-side comparison

| | Hybrid join | Entra-only join |
|---|---|---|
| Domain controller required | Yes | No |
| Entra Connect required | Yes | No |
| On-prem resource access (Kerberos) | Yes | No (see below) |
| Intune management | Via hybrid join | Native, automatic enrolment |
| Group Policy | Full GPO support | Intune/Settings Catalogue only |
| FSLogix on Azure Files | AD auth to storage | Entra Kerberos (fully supported) |
| Supported OS | Win 10/11, Server 2019/2022 | Win 10/11 (2004+), Server 2019/2022/2025 |
| Client device requirement | Any | Entra-joined/registered to same tenant, or `targetisaadjoined:i:1` RDP property |
| SSO | Supported | Supported (recommended) |
| MFA via Conditional Access | Supported | Supported - requires excluding Azure Windows VM Sign-In app from CA policy |

## What changes with FSLogix

This was the main blocker for going Entra-only. FSLogix profile containers on Azure Files previously needed the storage account joined to AD DS or AADDS so it could hand out Kerberos tickets.

Microsoft Entra Kerberos for Azure Files is now fully supported for Entra-only deployments. The session host gets a Kerberos ticket from Entra ID rather than AD DS, and Azure Files accepts it. You configure it on the storage account, set the FSLogix registry keys as normal, and it just works.

One constraint: the storage account can only use one authentication method. If you enable Entra Kerberos, you can't also use AD DS auth on the same account.

> **Gotcha:** An April 2026 Windows update changed the default Kerberos encryption type from RC4 to AES-SHA1. If your FSLogix file shares aren't upgraded to AES-SHA1 before that update lands on your session hosts, users will get profile load failures. Check your storage account's Kerberos ticket encryption setting before patching.

## On-premises resource access

This is where Entra-only has a genuine gap. If users need to hit on-prem file shares, printers, or internal apps that rely on Kerberos against AD - that won't work from an Entra-only session host without additional infrastructure (e.g. VPN + AADDS, or a reverse proxy for the app).

If your users are cloud-native (M365, SaaS, Azure-hosted apps) this isn't an issue. If you're lifting-and-shifting a traditional desktop estate, it may be a blocker.

## Conditional Access

Both models support Conditional Access and MFA. The difference with Entra-only is that you need to exclude the **Azure Windows VM Sign-In** cloud app from any CA policy that enforces strong authentication methods (like Windows Hello), otherwise the VM sign-in flow breaks.

Also: if your client devices aren't Entra-joined or registered to the same tenant as the session hosts, you need to add `targetisaadjoined:i:1` as a custom RDP property on the host pool. Without it, web, Android, macOS, and iOS clients won't connect.

## Client device requirements

Hybrid join has no special requirements on the connecting device.

Entra-only is more specific. The Windows Desktop client works without extra config if the local PC is:
- Entra-joined to the same tenant as the session host, or
- Entra hybrid-joined to the same tenant, or
- Entra-registered (Windows 10/11 2004+) to the same tenant

For everything else - web client, mobile, macOS, unmanaged Windows - add `targetisaadjoined:i:1` to the host pool's custom RDP properties. Users will authenticate with username and password rather than SSO.

## Management

Hybrid-joined session hosts can be managed via GPO (traditional AD tooling) or Intune (requires hybrid join configured in Entra Connect).

Entra-only session hosts enrol in Intune automatically at provisioning time. You manage them entirely through Intune / Settings Catalogue. No GPO. If you have existing GPO-based configurations you rely on, you'll need to migrate those to Intune before cutting over.

## When to pick each

**Pick Entra-only if:**
- You're starting a net-new AVD deployment
- Users are cloud-native (no on-prem Kerberos dependencies)
- You want to avoid running/paying for domain controllers
- You want native Intune management without the Entra Connect overhead

**Pick hybrid join if:**
- You have on-premises resources that require Kerberos auth
- You have existing GPO configurations you can't migrate yet
- You're extending an existing AD-based AVD deployment

For anything net-new, Entra-only is the right default. You're not carrying AD dependency into a cloud estate, and the FSLogix story is solid. Hybrid join is increasingly the legacy path.

---

*Next up: deploying an Entra-only AVD environment from scratch with Bicep and Terraform.*
