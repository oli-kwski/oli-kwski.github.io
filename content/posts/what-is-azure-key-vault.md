---
title: "What Is Azure Key Vault and Why Should You Use It?"
date: 2026-07-02
draft: false
description: "Azure Key Vault centralises secrets, keys, and certificate management in Azure. Here's how it works, what to store in it, and the access patterns to get right."

tags:
  - Security
  - Key Vault
  - Azure Fundamentals

pinned: true

cover:
  image: /covers/what-is-azure-key-vault-cover.svg
  alt: What Is Azure Key Vault and Why Should You Use It
  relative: false

comments: true
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: true
ShowWordCount: false
weight: 1
---

At some point, every application needs to store a secret, whether that be a database connection string, an API key or a certificate. Storing these in code, environment variables, or config files is insecure. Azure Key Vault is where secrets belong.

---

## The problem they solve

Secrets in application code or config files:
- Get committed to version control accidentally
- Are visible to anyone with access to the deployment artefact
- Can't be rotated without a redeployment
- Have no audit trail

Key Vault addresses all of these. Secrets are stored encrypted, accessed via RBAC-controlled API calls, audited in the activity log, and can be rotated without changing application code.

## What does Key Vault store?

Key Vault manages three types of objects:

| Type | What it is | Example use case |
|---|---|---|
| **Secrets** | Key-value pairs of sensitive strings | Database passwords, API keys, connection strings |
| **Keys** | Cryptographic keys (RSA, EC) | Encrypting data at rest, signing tokens |
| **Certificates** | X.509 TLS/SSL certificates | HTTPS certificates for App Services, API Management |

Keys can optionally be backed by **Hardware Security Modules (HSMs)**, and which tier you pick decides the protection level:

- **Standard tier** - keys are software-protected, validated to FIPS 140 Level 1
- **Premium tier** - offers HSM-protection using FIPS 140-3 Level 3 validated Marvell LiquidSecurity HSMs, the highest level of cryptographic protection Key Vault offers

## Access models

Key Vault supports two access permission models:

**Vault access policies (legacy):**
A flat permission model that grants permissions at the vault level - all or nothing per object type. Still widely used but being superseded by RBAC.

> **Important:** Under the access policy model, anyone holding `Contributor`, `Key Vault Contributor`, or any role with `Microsoft.KeyVault/vaults/write` can grant themselves data plane access by editing the vault's access policy. That's a privilege escalation path - control plane access effectively becomes data plane access. Restrict who gets `Contributor` on your key vaults if you're still using access policies.

**Azure RBAC (recommended):**
Fine-grained access via built-in roles.

> **Note:** As of API version 2026-02-01, Azure RBAC is the default access control model for newly created key vaults - access policies now require explicitly setting `enableRbacAuthorization` to `false`.

Key roles:

| Role | What it can do |
|---|---|
| Key Vault Administrator | Full access to all object types |
| Key Vault Secrets Officer | Create, update, delete secrets |
| Key Vault Secrets User | Read secret values |
| Key Vault Reader | Read metadata; cannot read values |
| Key Vault Crypto Officer | Create and manage keys |
| Key Vault Crypto User | Encrypt/decrypt/sign with keys |

## Accessing secrets from applications

The right pattern is a **managed identity** - no credentials stored in code:

```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

credential = DefaultAzureCredential()
client = SecretClient(vault_url="https://kv-prod-demo.vault.azure.net/", credential=credential)

# "db-admin-password" is the secret's name in Key Vault, not the value
secret = client.get_secret("db-admin-password")
connection_string = f"Server=sql-prod-demo;Database=app;Password={secret.value}"
```

`DefaultAzureCredential` uses the managed identity assigned to the compute resource (VM, App Service, Function) automatically. No credentials in code, no secrets in config files.

## Soft delete and purge protection

Both should be enabled on every production vault:

- **Soft delete** - deleted secrets/keys/certs/vaults are retained for a configurable period (7–90 days) before permanent deletion.
- **Purge protection** - prevents permanent deletion of a soft-deleted vault or object during the retention period, even by an administrator.

> **Important:** Purge protection is irreversible once enabled. I'd recommend enabling it from day one on production vaults.

## Key Vault and Private Endpoints

By default, Key Vault is reachable over the public internet. For production, deploy a Private Endpoint and disable public access. The Private DNS Zone is `privatelink.vaultcore.azure.net`.

## Common gotchas

**1. Secret versioning**
Every update to a secret creates a new version. Applications referencing a secret by name (without a version) get the latest version automatically. Applications that hardcode a specific version ID won't receive rotated secrets. Reference secrets by name only, not by version.

**2. Soft delete cannot be disabled once the vault exists**
Azure has enforced soft delete by default on all new vaults since September 2019. You can't opt out. Plan your lifecycle management accordingly - deleted secrets count against your storage quota during the retention period.

**3. Key Vault throttling limits**
Key Vault has service limits: 4,000 transactions per 10 seconds for secrets, shared across every caller on that vault. A single noisy, buggy, or compromised consumer can throttle out every other app relying on the same vault - split high-traffic or unrelated workloads into their own vaults rather than sharing one. Cache the secret value in memory with a short TTL (e.g. 5 minutes) rather than calling Key Vault on every request, but know this trades availability for a slower kill switch: if you rotate a secret because it's leaked, instances holding a cached copy keep trusting the old value until the TTL expires.

**4. Vault access policies and RBAC don't mix well**
If you enable Azure RBAC on a vault that previously used access policies, the access policies are ignored. Don't run both models simultaneously on the same vault - it causes confusion about why access is or isn't working.

**5. Cross-tenant access requires federation**
If a workload in one tenant needs to access a Key Vault in another tenant (common in multi-tenant ISV scenarios), managed identity won't work directly - you need federated credentials or service principals with explicit cross-tenant permissions.

---

## Summary

Key Vault centralises secret, key, and certificate management with audit logging, soft delete, and RBAC. Use managed identities to access it - no credentials in code. Enable soft delete and purge protection on every production vault. Deploy a Private Endpoint and disable public access. Cache secret values in your application rather than calling Key Vault on every operation. And use Azure RBAC over vault access policies - it's more granular and it's where Microsoft's investment is going.
