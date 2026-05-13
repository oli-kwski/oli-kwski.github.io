---
title: "What are Azure Storage Accounts and When Should You Use One?"
date: 2026-05-01
draft: false
description: "Azure Storage accounts are one of the most versatile services in Azure. Here's what's inside them, when to use each service, and the gotchas that bite people in production."

tags:
  - Storage Account
series:
  - Azure Fundamentals

pinned: true

cover:
  image: /covers/storage.svg
  alt: Azure Storage
  relative: false

comments: true
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: true
ShowWordCount: false
weight: 1
---

Almost every Azure workload interacts with a storage account at some point. Whether you're storing VM disks, application logs, static websites, or file shares, storage accounts are likely involved. Understanding what a storage account is and which service to pick saves you a lot of rework later.

---

## The problem they solve

Azure needs a place to store unstructured data (files, blobs, queues, tables) at scale. Storage accounts fulfil this need, providing multiple storage services under one endpoint.

Storage accounts are also used behind the scenes for several other Azure services. Azure Functions use Blob and Queue storage under the hood, Azure Diagnostics writes to storage accounts, VM boot diagnostics are sent to a storage account, and Azure Data Lake Storage Gen2 is built on top of Blob storage.

## What's inside a storage account?

A storage account is a namespace that provides access to four storage services:

| Service | What it stores | Typical use case |
|---|---|---|
| **Blob** | Unstructured objects (files, images, backups, logs) | Application file storage, backups, VM disks |
| **File** | Managed SMB/NFS file shares | Lift-and-shift of on-premises file servers |
| **Queue** | Messages up to 64 KB | Decoupling application components, work queues |
| **Table** | NoSQL key-value pairs | Structured non-relational data, audit logs |

Each service gets its own endpoint (e.g. `youraccount.blob.core.windows.net`, `youraccount.file.core.windows.net`).

## Account types and performance tiers

When creating a storage account, you choose the account type:

| Type | Supports | Notes |
|---|---|---|
| **General-purpose V2** | Blob, File, Queue, Table | Default choice for most workloads |
| **BlockBlobStorage** | Blob only | Premium performance, lower latency for blob operations |
| **FileStorage** | File only | Premium performance, required for NFS shares |

Performance tiers:

- **Standard** - backed by HDD. Suitable for most workloads.
- **Premium** - backed by SSD. Lower latency, higher throughput, higher cost. Required for NFS file shares and high-transaction blob workloads.

If you're not sure what to pick, the safe option is: **General-purpose V2, Standard**.

## Redundancy options

| Redundancy | Description | Good for |
|---|---|---|
| LRS | 3 copies in one datacentre | Dev/test, lowest cost |
| ZRS | 3 copies across availability zones | Production in single region |
| GRS | LRS + async copy to paired region | Disaster recovery (DR) |
| GZRS | ZRS + async copy to paired region | Production with geo-DR |
| RA-GRS / RA-GZRS | GRS/GZRS + read access to secondary | Read-heavy DR scenarios |

For production workloads: Use **ZRS** as the baseline. Add geo-replication (GRS/GZRS) if your RPO requires it.

## Access tiers (Blob only)

Blob storage supports tiering individual blobs or setting a default access tier on the account:

| Tier | Storage cost | Access cost | Minimum storage duration |
|---|---|---|---|
| Hot | Highest | Lowest | None |
| Cool | Lower | Higher | 30 days |
| Cold | Lower | Higher | 90 days |
| Archive | Lowest | High + rehydration delay | 180 days |

There is also **smart tier** - Smart tier automatically moves data between hot, cool and cold access tiers based on usage patterns, optimising your costs for these tiers automatically, you can read more into smart tiering [here.](https://learn.microsoft.com/en-us/azure/storage/blobs/access-tiers-smart?tabs=azure-portal)

**Lifecycle management policies** can also be used to automatically transition blobs between tiers based on age.

## Common use cases

**Application file storage:** VMs and App Services read/write files to Blob storage. Use a container per logical dataset, private access only, and a Private Endpoint for internal workloads.

<!-- **Azure Function triggers and bindings:** Functions use Blob, Queue, and Table storage for triggers and output bindings. The Functions runtime also requires a storage account for internal coordination. -->

**Diagnostic logs and metrics:** Azure Diagnostics, NSG flow logs, and Activity Logs can be sent to a storage account for long-term retention. A dedicated diagnostics storage account per environment keeps billing and access control clean.

**Static website hosting:** General-purpose V2 accounts support static website hosting - HTML, CSS, and JS served directly from Blob storage with a `$web` container. Pair this with Azure CDN or Front Door for custom domains and HTTPS.

**Data lake:** Enable the **Hierarchical Namespace** option on a General-purpose V2 account and you have Azure Data Lake Storage Gen2, which brings ACLs and real directory operations unlike the simulated directories in blob storage.

## Security baseline

For any storage account holding non-public data:

- Disable public network access
- Use Private Endpoints for internal access
- Require secure transfer
- Disable shared key access and use Entra ID / managed identities where possible
- Enable soft delete on blobs and containers
- Enable versioning for critical data

## Common gotchas

**Shared key access is enabled by default:** Storage accounts ship with shared key access enabled, meaning anyone with the account key has full access. If you're using managed identities or Entra ID auth, explicitly disable shared key access.

**Soft delete doesn't protect against container deletion by default:** Blob soft delete protects individual blobs. Container soft delete is separate and must be explicitly enabled, without it, a deleted container and all its contents are gone immediately.

**Hierarchical Namespace cannot be enabled after creation:** Once you create a storage account without Hierarchical Namespace, you cannot enable it later. If after creation you want Data Lake Gen2 features, you'll need a new storage account and to migrate all the data across.

**Storage account names must be globally unique** Storage account names must be globally unique across all Azure customers. Plan a naming scheme that incorporates your org identifier and randomised suffix if needed.

**Each service (blob, file, queue, table) needs its own private endpoint:** A single private endpoint only covers one sub-resource (e.g. `blob`). If you need private access to blob and file on the same account, you need two Private Endpoints and potentially two Private DNS Zones.

---

## Summary

Storage accounts are deceptively simple on the surface but have a lot of configuration options that matter for production workloads. If in doubt, pick General-purpose V2, ZRS for production redundancy, and establish a security baseline (no public access, private endpoints, Entra ID / managed identity auth) from the start. The options that can't be changed after creation - account type, performance tier, and hierarchical namespace - deserve particular attention before you deploy.