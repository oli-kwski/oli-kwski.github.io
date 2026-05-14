---
title: "Setting Up a Bicep Development Environment on Windows"
date: 2026-05-14
draft: false
description: "Everything you need to write and deploy Bicep templates on Windows - VS Code, the Bicep extension, and Azure CLI - installed and verified in one go."

tags:
  - Bicep

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
weight: 2
---

Before writing your first Bicep template you need three things on your machine: VS Code, the Bicep extension, and Azure CLI (which includes Bicep). This post walks through installing and verifying all of them on Windows.

---

## What you're installing and why

| Tool | Why you need it |
|---|---|
| **VS Code** | Editor with first-class Bicep support |
| **Bicep extension** | Syntax highlighting, IntelliSense, inline errors, and type-checking |
| **Azure CLI** | Deploys templates, manages subscriptions and resource groups |
| **Bicep** | Installed via Azure CLI - compiles `.bicep` files to ARM JSON |

You can write Bicep without VS Code, but you'd be giving up IntelliSense and real-time validation - the two things that make Bicep significantly easier to work with than raw ARM JSON. My advice - don't skip the extension.

---

## 1. Install VS Code

Download and install from [code.visualstudio.com](https://code.visualstudio.com/). Accept the defaults - tick "Add to PATH" during setup so you can open files from the terminal with `code`.

---

## 2. Install the Bicep extension

Open VS Code, go to the Extensions panel (`Ctrl+Shift+X`), and search for **Bicep**. The extension you want is published by Microsoft (`ms-azuretools.vscode-bicep`).

Install it. No configuration required - it activates automatically on `.bicep` files.

What you get:
- Real-time type checking and validation
- IntelliSense for resource types, properties, and API versions
- Inline error highlighting before you even try to deploy
- Go-to-definition for modules and parameters

---

## 3. Install Azure CLI

Azure CLI handles authentication, subscription management, resource group creation, and running deployments. Bicep compilation is handled through `az bicep` commands built into the CLI.

**Option 1 - winget (recommended):**

```powershell
winget install Microsoft.AzureCLI
```

**Option 2 - MSI installer:**

Download from [aka.ms/installazurecliwindows](https://aka.ms/installazurecliwindows) and run the installer.

After installing, close and reopen your terminal, then verify:

```powershell
az --version
```

You should see Azure CLI version plus a list of installed extensions.

---

## 4. Install Bicep via Azure CLI

The Bicep CLI is a self-contained binary managed by Azure CLI - it's installed separately from the CLI itself and doesn't get added to your PATH. Install it with:

```powershell
az bicep install
```

Verify:

```powershell
az bicep version
```

To upgrade Bicep later without touching Azure CLI itself:

```powershell
az bicep upgrade
```

---

## 6. Sign in to Azure

```powershell
az login
```

This opens a browser window for authentication. If you have access to multiple tenants, specify yours explicitly:

```powershell
az login --tenant <your-tenant-id>
```

Confirm your active subscription:

```powershell
az account show
```

If you need to switch subscriptions:

```powershell
az account set --subscription <subscription-id-or-name>
```

---

## 7. Verify everything works

Create a minimal Bicep file to confirm the toolchain is working end-to-end. In your terminal:

```powershell
New-Item -Name test.bicep -ItemType File
code test.bicep
```

Paste this into the file:

```bicep
param location string = 'uksouth'

output locationOut string = location
```

Save it, then compile it:

```powershell
az bicep build --file test.bicep
```

This produces `test.json` in the same directory. If it runs without errors, your toolchain is working. Delete both files when you're done.

---

## Common gotchas

**1. PowerShell execution policy blocks scripts.** If you see an error about running scripts being disabled, run this in an elevated PowerShell session:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**2. `az` not found after install.** The installer adds Azure CLI to your PATH, but your current terminal session won't pick it up. Close and reopen the terminal (or restart VS Code's integrated terminal) after installation.

**3. Multiple Azure CLI versions.** If you've previously installed Azure CLI via pip or another method, you may have conflicting versions. Use `where az` in PowerShell to see which binary is being resolved. Prefer the MSI or winget installation - they're easier to upgrade and uninstall.

**4. Bicep extension not activating.** The extension activates on `.bicep` files only. If it's not loading, check the language mode in VS Code's status bar (bottom right) - it should show `Bicep` when a `.bicep` file is open. If it shows something else, click it and select Bicep manually.

---

## Summary

With VS Code, the Bicep extension, Azure CLI, and Bicep installed, you have everything needed to write, validate, and deploy Bicep templates. The extension does a lot of heavy lifting - resource type IntelliSense and inline validation catch most mistakes before you get near a deployment.