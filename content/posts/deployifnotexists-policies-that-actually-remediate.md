---
title: "DeployIfNotExists Policies That Actually Remediate"
date: 2026-05-12
draft: true
description: "DINE is Azure Policy's most powerful effect. It's also the most frequently misconfigured, and when it fails it often does so silently. Here's what has to be right."

tags:
  - Governance
  - Azure Policy
  - Security
  - Landing Zones

cover:
  image: /covers/governance.svg
  alt: Azure Governance
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

**Phase 1 - Condition check.** The policy engine evaluates the `if` block against the resource. If the resource matches, it moves to phase 2.

**Phase 2 - Existence check.** The engine evaluates the `existenceCondition` in the `then.details` block. It looks for a related resource (a child resource, a resource in a related scope) that represents the desired state. If that resource exists and matches the condition, the resource is **compliant**. If not, it's **non-compliant**.

**Phase 3 - Remediation.** For non-compliant resources, a remediation task can trigger the `deployment` block in the policy definition. That deployment is executed by the managed identity attached to the policy assignment.

The critical point: DINE does not retroactively fix existing resources on assignment. Resources created or updated after the assignment are evaluated on deployment. Resources that existed before the assignment sit non-compliant until you explicitly create a remediation task.

---

## The three things that must be right

### 1. Managed identity has the right permissions

The policy assignment's managed identity must have the RBAC permissions required to deploy what the `deployment` block specifies. The policy definition's `roleDefinitionIds` array declares which roles the identity should have - Azure assigns these at the scope of the policy assignment when you save it.

This is the most common failure point. If the managed identity can't write the resource type it's deploying, the remediation task fails with a 403, and the resource stays non-compliant. That failure appears in the remediation task's deployment details, not in the top-level Policy compliance view - so it's easy to miss.

For policies assigned at management group scope, the managed identity needs the relevant roles across every subscription in scope. Check this explicitly; Azure assigns the role at management group level but subscriptions created after the assignment may not inherit it cleanly if you've customised role inheritance.

### 2. A remediation task exists for pre-existing resources

Assigning a DINE policy fixes future resources, not existing ones. For anything that existed before the assignment, you need a remediation task. You can create one from the Azure portal (Policy > Remediation > New remediation task), via Azure CLI, or as a step in your assignment pipeline.

When building landing zone policies, the recommended pattern is to create the remediation task immediately after assignment as part of the same pipeline run. That way, the policy catches both existing non-compliant resources and future ones.

### 3. The existenceCondition accurately reflects compliance

The `existenceCondition` is how the policy decides whether to remediate or leave a resource alone. If it's too loose, the policy considers everything compliant and never remediates. If it's too strict, it remediates repeatedly and produces duplicates.

A common mistake with diagnostic settings policies: checking only that *a* diagnostic setting exists, rather than that one targeting the *correct* Log Analytics workspace exists. The result is a policy that reports compliance even when the diagnostics are pointing at the wrong destination.

---

## Common gotchas

**1. Policy evaluation lag**

After assigning a policy or triggering a remediation task, nothing happens immediately. Compliance evaluation runs on a schedule - up to 24 hours, though you can trigger an on-demand scan. Remediation tasks then queue and execute asynchronously. Wait at least 30 minutes before concluding something is broken, and trigger an on-demand scan before drawing conclusions.

**2. Remediation task scope doesn't match non-compliant resources**

The remediation task scope defaults to the assignment scope. If your non-compliant resources are in a specific subscription or resource group, scope the task accordingly. Scanning at management group scope for resources in a single subscription is slower and produces noisy results.

**3. Duplicate remediation from overlapping assignments**

If you assign the same DINE policy at both management group and subscription scope - a common accident during landing zone iteration - both assignments may attempt to remediate the same resource. The result depends on the policy; for diagnostic settings this typically creates duplicate settings targeting the same workspace. Neither assignment shows an error.

**4. DINE when Modify is the right effect**

DINE is designed for deploying child resources or complex configurations. If you need to set a property directly on the resource - a tag, a boolean setting like `publicNetworkAccess: Disabled` - the **Modify** effect is cleaner. Modify edits the resource in place without spinning up a deployment. Using DINE for simple property changes adds latency and complexity for no benefit.

| Use case | Correct effect |
|---|---|
| Enable diagnostic settings (child resource) | DeployIfNotExists |
| Attach Defender plan | DeployIfNotExists |
| Set a tag on a resource | Modify |
| Set `publicNetworkAccess: Disabled` | Modify |
| Deny resource creation entirely | Deny |

**5. roleDefinitionIds uses wrong format**

The `roleDefinitionIds` array requires the full resource ID of the role definition:

```
/providers/Microsoft.Authorization/roleDefinitions/b24988ac-6180-42a0-ab88-20f7382dd24c
```

Not the role display name. If the ID is wrong or refers to a non-existent role, the managed identity is never assigned the correct role and every remediation task silently fails at the 403 stage.

**6. Definition scope vs assignment scope mismatch**

Custom policy definitions scoped to a management group can only be assigned at that management group or below within the same hierarchy. Attempting to assign a management-group-scoped definition at a subscription outside that hierarchy will fail at assignment time, not at evaluation time.

---

## Debugging a failing remediation

When a remediation task runs but the resource stays non-compliant, follow this sequence:

**Step 1 - Check remediation task status.** Policy > Remediation > find the task. A `Failed` status exposes a link to the underlying ARM deployment with the specific error.

**Step 2 - Read the deployment error.** The error message is usually precise: a 403 indicates a permissions problem on the managed identity; a 400 or 409 typically indicates a template or conflict issue in the deployment block itself.

**Step 3 - Verify the managed identity role assignment.** Policy > Assignments > select the assignment > Managed Identity tab. Confirm the identity has the roles from `roleDefinitionIds` at the right scope. It's worth checking the role assignment directly in IAM on the subscription or management group, not just via the policy blade.

**Step 4 - Trigger an on-demand compliance scan.** Use `az policy state trigger-scan --resource-group <rg>` or the equivalent at subscription/management group scope. This forces a fresh evaluation rather than waiting for the scheduled cycle.

**Step 5 - Check Activity Log on the target resource.** Filter by the managed identity's principal ID. You can see the deployment attempts, their timestamps, and any error codes.

---

## Summary

DINE is a three-part contract: the right identity, with the right permissions, checking for the right existing state. The existence check and managed identity permissions account for the majority of silent failures. The remediation task creation step accounts for most cases where existing resources stay non-compliant after a new assignment.

When building governance at landing zone scale, treat each DINE assignment as code: version the definition, automate the role assignment, create the remediation task in the same pipeline run, and verify compliance state after the evaluation cycle completes. Policy compliance showing green is only meaningful if you've confirmed what the existence check actually validates.
