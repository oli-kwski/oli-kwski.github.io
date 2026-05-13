---
title: "What is Azure Bicep and Why Should You Use It?"
date: 2026-05-13
draft: false
description: "Bicep is Microsoft's domain-specific language for deploying Azure resources. Here's what it is, how it relates to ARM templates, and when to reach for it over Terraform."

tags:
  - Bicep
  - IaC

series:
  - Bicep

pinned: true

cover:
  image: /covers/iac.svg
  alt: Infrastructure as Code
  relative: false

comments: true
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: true
ShowWordCount: false
weight: 1
---

If you've ever opened an ARM template, you'll understand immediately why Bicep exists. ARM JSON is valid, powerful, and deeply unpleasant to write by hand - thousands of lines of nested braces, repeated API versions, and zero readability. Bicep solves that without introducing a third-party dependency.

---

## What Bicep is?

Bicep is a domain-specific language (DSL) developed by Microsoft for declaring Azure infrastructure. It compiles directly to ARM JSON, which means it uses the same underlying deployment engine as ARM templates - you're not adding an abstraction layer, you're just changing the authoring experience.

It ships as part of the Azure CLI and is maintained by the Azure team, so it tracks new Azure resource types quickly and gets first-class support in VS Code.

## How it relates to ARM templates

Every Bicep file compiles to an ARM template before deployment. When you run a deployment, the Azure CLI or Azure DevOps pipeline compiles your `.bicep` file to ARM JSON and sends that to Azure Resource Manager. The ARM engine never sees Bicep directly.

This has a practical implication: Bicep and ARM templates are interchangeable at the deployment layer. You can decompile existing ARM templates to Bicep, and you can compile Bicep to ARM JSON for teams or tools that only accept ARM. There's no lock-in to Bicep specifically - if you decide to move away from it, you compile once and you're out.

## What Bicep gives you over raw ARM JSON

The syntax differences are significant:

**Cleaner resource declarations.** ARM JSON requires you to specify `apiVersion`, `type`, `name`, `location`, and properties in a verbose nested structure. Bicep reduces this to a readable block with symbolic names that other resources can reference directly.

**No `dependsOn` noise.** In ARM JSON you manually declare dependencies between resources. Bicep infers dependencies automatically when one resource references another by its symbolic name.

**Parameters and variables with types.** Bicep parameters are typed (`string`, `int`, `bool`, `object`, `array`) and support decorators for validation (`@minLength`, `@maxValue`, `@allowed`). This catches errors at compile time rather than at deployment time.

**Modules.** Bicep files can call other Bicep files as modules, letting you build reusable components (a storage module, a network module, etc) that take parameters and output values back to the parent template. This is the primary mechanism for avoiding copy-paste across environments.

**String interpolation and functions.** Bicep supports string interpolation directly (`'${resourceGroup().name}-storage'`) rather than ARM's `concat()` function, which is a small but meaningful readability improvement across hundreds of resource names.

## Bicep vs Terraform

Both tools deploy infrastructure-as-code, but they sit in different positions:

| | Bicep | Terraform |
|---|---|---|
| **Scope** | Azure only | Multi-cloud |
| **State management** | None (uses ARM deployment history) | State file required |
| **Provider** | Microsoft-maintained | Community + HashiCorp |
| **New Azure resource support** | Same-day (compiles to ARM) | Depends on provider release |
| **Learning curve** | Lower if you're Azure-only | Higher, but transferable |
| **Ecosystem** | Azure-native (Bicep Registry, Azure Verified Modules) | Large community module registry |

The honest answer: if you're Azure-only, Bicep is the path of least resistance. It requires no state management, deploys through the same ARM engine you're already using, and Microsoft maintains it. If you need multi-cloud or your team is already invested in Terraform, stick with Terraform - there's no compelling reason to run both in the same environment.

## Common gotchas

**1. Decompiled ARM templates are a starting point, not a finished product.** The `az bicep decompile` command converts ARM JSON to Bicep, but the output is rarely clean. Variable names are generated, conditional logic often needs rewriting, and modules won't be extracted for you. Treat decompiled output as a draft.

**2. Bicep doesn't manage state.** Unlike Terraform, Bicep has no state file. Deleting a resource from your `.bicep` file and redeploying in Complete mode will delete that resource from Azure. In Incremental mode (the default), it won't - which can leave orphaned resources behind. Understanding deployment modes matters before you deploy to production.

**3. API versions are still your problem.** Bicep removes `apiVersion` from the syntax but you still control it - it's set per resource type and defaults to the latest at the time the Bicep tooling was installed. You'll want to pin API versions explicitly in production deployments to avoid surprises after tooling upgrades.

**4. Modules use their own scope.** A Bicep module deploys at its own target scope, which can differ from the parent template. If you're mixing resource group and subscription-scoped deployments in a module hierarchy, be deliberate about `targetScope` declarations.

---

## Summary

Bicep removes the worst of ARM JSON while staying on the ARM deployment engine, supports modules and typed parameters, and is maintained by Microsoft with same-day support for new resource types. If you're starting fresh on Azure, start with Bicep.