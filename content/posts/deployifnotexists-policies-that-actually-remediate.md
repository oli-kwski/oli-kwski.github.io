---
title: "DeployIfNotExists Policies That Actually Remediate"
date: 2026-08-21
draft: false
description: "DINE is Azure Policy's most powerful effect. It's also the most frequently misconfigured, and when it fails it often does so silently. Here's what has to be right."

tags:
  - Governance
  - Azure Policy
  - Security
  - Landing Zones

cover:
  image: /covers/deployifnotexists-cover.svg
  alt: DeployIfNotExists Policies That Actually Remediate
  relative: false

comments: true
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: false
---

DeployIfNotExists (DINE) is the most powerful Azure Policy effect. Rather than flagging non-compliance, it automatically deploys the fix - enabling diagnostic settings, attaching Defender plans, adding resource locks. In practice it's also the effect most likely to silently fail. Policy compliance shows non-compliant, a remediation task runs, nothing changes, and the root cause isn't immediately obvious.

This post covers how DINE actually works, the three things that must be correct for it to remediate, and how to find out what went wrong when it doesn't.

---

## How DINE works

Policy evaluation for a DINE policy follows three phases:

**Phase 1 - Condition check:** The policy engine evaluates the `if` block against the resource. If the resource matches, it moves to phase 2.

**Phase 2 - Existence check:** The engine evaluates the `existenceCondition` in the `then.details` block. It looks for a related resource (a child resource, a resource in a related scope) that represents the desired state. If that resource exists and matches the condition, the resource is **compliant**. If not, it's **non-compliant**.

**Phase 3 - Remediation:** For non-compliant resources, a remediation task can trigger the `deployment` block in the policy definition. That deployment is executed by the managed identity attached to the policy assignment.

> **Important:** DINE does not retroactively fix existing resources on assignment. Resources created or updated after the assignment are evaluated on deployment. Resources that existed before the assignment sit non-compliant until you explicitly create a remediation task.

---

## The three things that must be right

### 1. Managed identity has the right permissions

The policy assignment's managed identity must have the RBAC permissions required to deploy what the `deployment` block specifies. The policy definition's `roleDefinitionIds` array declares which roles the identity should have - but whether that role actually gets granted automatically depends entirely on how you assign the policy. See [gotcha 6](#terraform-role-grant) below - it catches almost everyone at least once.

This is the most common failure point. If the managed identity can't write the resource type it's deploying, the remediation task fails with a 403, and the resource stays non-compliant. That failure appears in the remediation task's deployment details, not in the top-level Policy compliance view - so it's easy to miss.

For policies assigned at management group scope, grant the role at the management group itself, not at each subscription individually. RBAC inheritance from a management group down to its subscriptions is automatic, so a role granted at the right scope covers subscriptions added later without further work. The failure mode here is granting the role too narrowly in the first place: scoping the `azurerm_role_assignment` to today's subscriptions instead of the management group means tomorrow's subscription never had the grant at all. Check the scope the role was assigned at, not whether inheritance worked.

### 2. A remediation task exists for pre-existing resources

Assigning a DINE policy fixes future resources, not existing ones. For anything that existed before the assignment, you need a remediation task. You can create one from the Azure portal (Policy > Remediation > New remediation task), via the Azure CLI or PowerShell, or as a step in your assignment pipeline.

When building landing zone policies, the pattern to aim for is creating the remediation task immediately after assignment as part of the same pipeline run, so the policy catches both existing non-compliant resources and future ones.

There's a scope caveat worth knowing here. The portal's "create a remediation task" tick box on the assignment wizard is only supported for assignments at subscription scope. For management-group-scoped assignments - which is most landing zone policy - you have to create the remediation task separately, and only after an evaluation cycle has actually determined which resources are non-compliant. Build that ordering into your pipeline rather than assuming assignment and remediation can happen in one step.

### 3. The existenceCondition accurately reflects compliance

The `existenceCondition` is how the policy decides whether to remediate or leave a resource alone. If it's too loose, the policy considers everything compliant and never remediates. If it's too strict, it remediates repeatedly and produces duplicates.

A common mistake with diagnostic settings policies: checking only that *a* diagnostic setting exists, rather than that one targeting the *correct* Log Analytics workspace exists. The result is a policy that reports compliance even when the diagnostics are pointing at the wrong destination.

---

## Common gotchas

**1. Policy evaluation lag**

After assigning a policy or triggering a remediation task, nothing happens immediately. Assignments are automatically re-evaluated once every 24 hours, and remediation tasks then queue and execute asynchronously. Before concluding something is broken, trigger an on-demand scan and give it time to complete - large assignments across many resources can take a while.

**2. Remediation task scope doesn't match non-compliant resources**

The remediation task scope defaults to the assignment scope. If your non-compliant resources are in a specific subscription or resource group, scope the task accordingly. Scanning at management group scope for resources in a single subscription is slower and produces noisy results.

**3. Duplicate remediation from overlapping assignments**

If you assign the same DINE policy at both management group and subscription scope - a common accident during landing zone iteration - both assignments may attempt to remediate the same resource. The result depends on the policy; for diagnostic settings this typically creates duplicate settings targeting the same workspace. Neither assignment shows an error.

**4. DINE when Modify is the right effect**

DINE is designed for deploying child resources or complex configurations. If you need to set a property directly on the resource - a tag, or a modifiable property like `allowBlobPublicAccess` - the **Modify** effect is cleaner. Modify edits the resource in place without spinning up a deployment. Using DINE for simple property changes adds latency and complexity for no benefit.

One caveat with Modify: it only works on properties whose aliases are marked as modifiable in the request's API version. If the alias isn't modifiable, evaluation falls back to the definition's `conflictEffect`, so it's worth setting that to `audit` rather than letting requests fail outright.

| Use case | Correct effect |
|---|---|
| Enable diagnostic settings (child resource) | DeployIfNotExists |
| Attach Defender plan | DeployIfNotExists |
| Set a tag on a resource | Modify |
| Set a modifiable property such as `allowBlobPublicAccess` | Modify |
| Deny resource creation entirely | Deny |

**5. roleDefinitionIds uses wrong format**

The `roleDefinitionIds` array requires the full resource ID of the role definition:

```
/providers/Microsoft.Authorization/roleDefinitions/b24988ac-6180-42a0-ab88-20f7382dd24c
```

Not the role display name. If the ID is wrong or refers to a non-existent role, the managed identity is never assigned the correct role and every remediation task silently fails at the 403 stage.

<a id="terraform-role-grant"></a>**6. IaC deployments don't auto-grant the role**

In the Azure portal, creating a policy assignment auto-grants the managed identity the roles listed in `roleDefinitionIds`. Through any SDK-based deployment method - Terraform, Bicep, ARM templates, PowerShell, the CLI - it does not. You have to create the role assignment yourself as a separate resource; skip it and the identity exists but has no permissions, so every remediation silently fails at the 403 stage. In Terraform that means an explicit `azurerm_role_assignment` alongside the policy assignment itself - it's easy to assume the portal's auto-grant behaviour is universal until you deploy the same policy through code.

**7. Definition scope vs assignment scope mismatch**

A policy definition's location determines where it can be assigned - resources must sit within the resource hierarchy of that definition location. A definition saved at a management group can be assigned to that management group and any child management group or subscription beneath it, but not to a subscription outside that hierarchy. If you plan to apply a definition across several subscriptions, save it at a management group that contains all of them. Getting this wrong fails at assignment time rather than at evaluation time, so at least it surfaces early.

---

## Debugging a failing remediation

When a remediation task runs but the resource stays non-compliant, follow this sequence:

**Step 1 - Check remediation task status:** Policy > Remediation > find the task. A `Failed` status exposes a link to the underlying ARM deployment with the specific error.

**Step 2 - Read the deployment error:** The error message is usually precise: a 403 indicates a permissions problem on the managed identity; a 400 or 409 typically indicates a template or conflict issue in the deployment block itself.

**Step 3 - Verify the managed identity role assignment:** Policy > Assignments > select the assignment > Managed Identity tab. Confirm the identity has the roles from `roleDefinitionIds` at the right scope. It's worth checking the role assignment directly in IAM on the subscription or management group, not just via the policy blade.

**Step 4 - Trigger an on-demand compliance scan:** Use `az policy state trigger-scan --resource-group <rg>`, or omit the resource group to scan the whole subscription. This forces a fresh evaluation rather than waiting for the scheduled cycle. Note that on-demand scans only work at subscription or resource group scope - there's no management group equivalent, so for a management-group-scoped assignment you need to loop through the subscriptions underneath it.

**Step 5 - Check Activity Log on the target resource:** Filter by the managed identity's principal ID. You can see the deployment attempts, their timestamps, and any error codes.

---

## Summary

DINE is a three-part contract: the right identity, with the right permissions, checking for the right existing state. The existence check and managed identity permissions account for the majority of silent failures. The remediation task creation step accounts for most cases where existing resources stay non-compliant after a new assignment.

When building governance at landing zone scale, treat each DINE assignment as code: version the definition, automate the role assignment, create the remediation task in the same pipeline run, and verify compliance state after the evaluation cycle completes. Policy compliance showing green is only meaningful if you've confirmed what the existence check actually validates.