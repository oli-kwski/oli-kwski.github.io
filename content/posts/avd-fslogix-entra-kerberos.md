---
title: "Deploying AVD with FSLogix and Entra-Only Identities - No Domain Controllers Required"
date: 2026-06-29
draft: false
description: "End-to-end portal guide for deploying AVD with FSLogix profile containers on Azure Files using Entra-only identities - no domain controllers, no AADDS. Covers storage, Entra Kerberos, host pool, session hosts, and the gotchas that catch people out."

tags:
  - AVD
  - FSLogix
  - Entra ID
  - Azure Files

cover:
  image: /covers/avd-fslogix-entra-kerberos-cover.png
  alt: FSLogix Entra-only identities
  relative: false

comments: true
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: true
ShowWordCount: false
---

Using FSLogix with AVD has always required identities to be hybrid, cloud-only Entra identities weren't supported for Azure Files Kerberos authentication. That is now a thing of the past! Azure Files Entra Kerberos for cloud-only identities reached general availability on 19 May 2026, and here's how to set up AVD without AD via the portal.

> **Note:** Cloud-only identity support in Entra Kerberos is still marked preview in the core Entra docs - the GA milestone applies specifically to the Azure Files + FSLogix scenario.

## 1. Create Entra groups

In the portal, go to **Microsoft Entra ID -> Groups -> New group** and create 2 groups. 

- An assigned security group for your AVD users (e.g. `AVD Users`) - used for share permissions, RBAC, and app group assignment throughout this guide.
- A dynamic device security group for your session hosts (e.g. `AVD Session Hosts`) - used for Remote Connection Configuration in step 19. Set the dynamic membership rule to match your session host naming prefix (this guide uses `avd-sh`):

```
(device.displayName -startsWith "avd-sh")
```

> **Important:** Dynamic group membership can take several minutes to populate after session hosts are deployed. Don't rely on it being immediate when testing.

## 2. Create a resource group

In the portal, go to **Resource groups -> Create**. Give it a name (e.g. `rg-avd-demo`) then select your subscription and region. 

All AVD and storage resources in this guide we'll add into this resource group.

![Creating resource group](/avd-fslogix-entra-kerberos/create-rg.png)

## 3. Create the VNet, Subnets, NSG and Nat Gateway

In the portal, go to **Virtual networks -> Create**. Select your resource group and region, and give it a name (e.g. `vnet-avd-demo`).

![Creating VNet](/avd-fslogix-entra-kerberos/create-vnet.png)

On the **Address space** tab, set your address space as `/24`, which gives room to expand later.

Add the following private subnets:

| Name | Starting address | Size | NSG | NAT gateway |
|------|-----------------|------|-----|-------------|
| `snet-avd-demo-sessionhosts` | `10.0.0.0` | `/27` | `nsg-avd-demo-sessionhosts` | `ngw-avd-demo` |
| `snet-avd-demo-privateendpoints` | `10.0.0.128` | `/28` | - | - |

![Creating subnet](/avd-fslogix-entra-kerberos/create-subnet.png)
![Creating subnet](/avd-fslogix-entra-kerberos/create-subnet-2.png)

Microsoft retired default outbound internet access for new Azure VMs in September 2025, so session hosts need explicit outbound connectivity. Without it, registration and Intune enrolment fail silently - storage traffic is fine via the private endpoint, but the AVD control plane and Entra ID both require outbound 443.

Create the NSG and NAT gateway inline during subnet creation. For the NAT gateway you will need to create a public IP as part of the inline deployment - name it accordingly e.g. `pip-ngw-avd-demo`. We will add rules to the NSG in the next step.

> **Important:** The "private subnet" setting and the default outbound retirement are separate things - not enabling private subnet does not restore default outbound on new VMs. You need the NAT gateway regardless.

Once the VNet has deployed, find your NSG within your resource group and add the following outbound rules by going to **Settings -> Outbound security rules -> Add**:

![Configure NSG](/avd-fslogix-entra-kerberos/configure-nsg.png)

> **Important:** AVD uses reverse connect - session hosts initiate outbound connections to the AVD gateway over port 443. You do not need inbound RDP rules. Adding an inbound RDP allow rule is a common mistake that unnecessarily exposes session hosts.

> **Important:** This is for demo purposes only - in your prod environment set more secure NSG rules.

## 4. Create the storage account

In the portal, go to **Storage Accounts -> Create**.

On the **Basics** tab, the key settings are:

| Setting | Value |
|---------|-------|
| Primary service | Azure Files |
| Media tier | SSD (premium) - Standard is not supported for Entra Kerberos in all regions |
| File share billing | Provisioned v2 gives you independent control over capacity, throughput, and IOPS |
| Redundancy | LRS gives you three synchronous copies within a single datacentre; ZRS spreads those copies across three availability zones in the same region. For AVD profile storage, ZRS is the safer default if your region supports it - a single zone failure won't take down profile access. |

> **Note:** For this demo I'll pick LRS with no zone options and keep the rest of the settings default.

![Storage account instance details](/avd-fslogix-entra-kerberos/create-sa.png)

On the **Networking** tab create a private endpoint and add it to the session hosts subnet, create a private DNS zone inline with the creation of the private endpoint to ensure the session hosts can resolve the private endpoint.

> **Important:** You can disable public networking for the storage account as all traffic will go via the private endpoint, however this will prevent you adding the NTFS permissions via the portal unless access the Azure portal via a device that can resolve the storage account via its private endpoint, so make disabling public networking one of the last things you do.

![Create Private Endpoint](/avd-fslogix-entra-kerberos/create-sa1.png)

## 5. Configure the storage account

Create a file share: **Data storage -> Classic file shares -> Classic file share**. Give it a name (e.g. `fslogixprofiles`) and set the provisioned capacity. Microsoft's starting point is 30 GB per user - size up from there based on your profile data. Leave provisioned IOPS and throughput on 'Recommended provisioning' and set the protocol to 'SMB'.

![Classic fileshare settings](/avd-fslogix-entra-kerberos/new-fileshare.png)

Configure backups to your requirements.

## 6. Enable Entra Kerberos

On the file share, click **Not configured** next to **Identity-based access**.

![Setup entra kerberos](/avd-fslogix-entra-kerberos/configure-entra-kerberos.png)

This opens a screen with 3 identity source options. Click **Set up** under **Microsoft Entra Kerberos** - this opens a side panel.

![Setup entra kerberos](/avd-fslogix-entra-kerberos/configure-entra-kerberos-2.png)

Tick the **Microsoft Entra Kerberos** checkbox, leave the AD fields blank.

![Enable entra kerberos](/avd-fslogix-entra-kerberos/configure-entra-kerberos-3.png)

After saving, the Identity-based access section will show Entra Kerberos as enabled.

![Entra Kerberos configured](/avd-fslogix-entra-kerberos/entra-kerberos-configured.png)

This creates an Entra app registration for the storage account, it follows the format `[Storage Account] <storageaccountname>.file.core.windows.net` - you'll need it in steps 7 and 8.

## 7. Grant admin consent to the app registration

Enabling Entra Kerberos creates an app registration in your tenant. You need to grant admin consent to it before users can authenticate.

In the portal, go to **Microsoft Entra ID -> Manage -> App registrations -> All applications**, find the app named after your storage account. Select it, then go to **Manage -> API permissions** and click **Grant admin consent for [your directory]**.

![Enable entra kerberos](/avd-fslogix-entra-kerberos/grant-admin-consent.png)

You'll know this has been successful when the status for each API permission is "Granted [your directory]".

![Enable entra kerberos](/avd-fslogix-entra-kerberos/grant-admin-consent-2.png)

> **Important:** Without this step, Kerberos ticket requests will fail for all users.

## 8. Enable cloud-only groups support

This step is mandatory for cloud-only identity scenarios. Kerberos tickets can carry a maximum of 1,010 group SIDs. With Entra Kerberos supporting cloud-only identities, tickets must include both on-premises and cloud group SIDs. If the combined count exceeds 1,010, ticket issuance fails entirely.

To avoid this, you need to update the `Tags` field in the app registration's manifest. In the portal, find the app registration from step 6, under **Manage -> Manifest** search for "tags" and add in `"kdc_enable_cloud_group_sids"` 

![Update manifest](/avd-fslogix-entra-kerberos/update-manifest.png)

> **Note:** If for any reason you're unable to do this via the portal, you can follow [Microsoft's instructions](https://learn.microsoft.com/en-us/entra/identity/authentication/kerberos#how-to-update-tags-attribute-in-application-manifest-file) as there are multiple ways to acheive this.

> **Important:** Skipping this step means authentication will fail for any user who is a member of a large number of groups.

## 9. Exclude the storage account app from MFA Conditional Access

Entra Kerberos uses a non-interactive Kerberos exchange - it cannot complete a MFA challenge. If any Conditional Access policy enforcing MFA applies to the storage account app, profile mounts will fail silently.

In the portal, go to **Microsoft Entra Conditional Access -> Policies** and find any policies that enforce MFA. Add an exclusion for the storage account app: `[Storage Account] <storageaccountname>.file.core.windows.net`.

> **Important:** Do this before testing any profile mounts. The failure mode is a temporary profile - there's nothing in the FSLogix event log to indicate MFA is the cause.

## 10. Assign share-level permissions

For this step, whether you use specific RBAC role assignments or a default share-level permission depends on your region. Specific RBAC assignments for cloud-only identities are only supported in a [subset of Azure public cloud regions.](https://learn.microsoft.com/en-us/azure/storage/files/storage-files-identity-auth-hybrid-identities-enable#regional-availability-for-microsoft-entra-kerberos) If your storage account is not in one of those regions, use the default share-level permission, if it is, I'd recommend going the more secure approach of only members of your AVD group have access to the share.

### Assign specific RBAC roles (supported regions only): 

Navigate to the file share -> **Access Control (IAM) -> Add -> Add role assignment**. Assign **Storage File Data SMB Share Contributor** to your AVD user group.

![Set default share-level permission](/avd-fslogix-entra-kerberos/set-rbac-permissions.png)

### Set the default share-level permission

Go to **Data storage -> Classic file shares**, then under the **Essentials** section click **Disabled** next to **Default share-level permissions**.

![Set default share-level permission](/avd-fslogix-entra-kerberos/configure-default-share-permissions.png)

Set **Default share-level permissions** to **Enable permissions for all authenticated users and groups**, select **Storage File Data SMB Share Contributor** from the dropdown.

![Set default share-level permission](/avd-fslogix-entra-kerberos/set-default-share-permission.png)

## 11. Configure directory and file-level permissions

FSLogix needs specific NTFS permissions on the share root so users can create their own profile folder but not access other users profiles. Share-level RBAC controls who can connect to the share - NTFS permissions control what they can do once connected. Both layers are required.

> **Important:** For cloud-only identities, `icacls` and Windows File Explorer are not supported. Use the Azure portal Manage Access blade (below) or the [RestSetAcls PowerShell module](https://www.powershellgallery.com/packages/RestSetAcls/)

Navigate to the file share **Data storage -> Classic file shares -> *YOUR FILE SHARE* -> Browse -> Manage access**

![Set ntfs permissions](/avd-fslogix-entra-kerberos/set-ntfs-permissions.png)

and set the following permissions

| Principal                  | Permission   | Applies to                        |
|----------------------------|--------------|-----------------------------------|
| Your admin Entra group     | Full Control | This folder, subfolders and files |
| Your AVD users Entra group | Modify       | This folder only                  |
| CREATOR OWNER              | Modify       | Subfolders and subfiles only      |

![Set ntfs permissions](/avd-fslogix-entra-kerberos/set-ntfs-permissions-2.png)

## 12. Create and customise the golden image VM

Create a VM in the portal: **Virtual Machines -> Create -> Azure virtual machine**.

Use the same base image you intend to run on session hosts - Windows 11 Enterprise multi-session + Microsoft 365 Apps is the typical starting point. VM size doesn't need to match your session hosts; this is a build VM only. 

> **Important:** Do not Entra-join or Intune-enrol the VM - join state baked into the image will cause conflicts on capture.

![create VM](/avd-fslogix-entra-kerberos/create-vm.png)

To keep your resources clean and ensure outbound connectivity deploy this VM to the VNet and session host subnet you created in step 3. The rest of the tabs you can skip.

![create VM](/avd-fslogix-entra-kerberos/create-vm-2.png)

> **Important:** In production I recommend you deploy a bastion host for secure connectivity.

If you are not deploying a bastion host temporarily add the inbound rule below to your NSG and delete this rule after you have captured the golden image.

![Add temp inbound rule to NSG](/avd-fslogix-entra-kerberos/configure-nsg-2.png)

Once the VM is up, RDP in and customise:

- Run Windows Update fully and reboot
- Disable BitLocker before capture

```PowerShell
Disable-BitLocker -MountPoint "C:"
```
> **Note:** sysprep on an encrypted drive will fail

Decryption runs in the background - check the status before proceeding with sysprep:

```PowerShell
Get-BitLockerVolume -MountPoint "C:"
```

Wait until `VolumeStatus` shows `FullyDecrypted` and `EncryptionPercentage` is `0` before continuing, you can complete the remaining steps while it decrypts.

- Run [Windows Desktop Optimisation Tool (WDOT)](https://github.com/The-Virtual-Desktop-Team/Windows-Desktop-Optimization-Tool) - not required but AVD runs more efficiently after running this tool.
- If not using Intune to push FSLogix and Kerberos TGT settings, apply the registry keys from steps 13 and 14 directly to this image.
- If not deploying apps via Intune, Install your line-of-business applications.

> **Important:** Run Windows Update to completion before capture. Any pending updates will apply on first boot of every session host provisioned from the image, adding minutes to session host startup time.

## 13. Enable cloud Kerberos TGT on session hosts

By default, Entra-joined session hosts don't request the cloud Kerberos TGT needed for Azure Files. Enable this via Intune Settings Catalogue:

`Kerberos/CloudKerberosTicketRetrievalEnabled` -> Enabled

> **Important:** Without this, profile mounts will fail - the user typically gets a temporary profile, and the FSLogix event log may not make the root cause obvious.

> **Important:** For AVD multisession hosts, use the Settings Catalogue method specifically. The OMA-URI method does not work on multisession devices.

Set `LoadCredKeyFromProfile`, which ensures credential keys are stored in the user's profile rather than the machine - required for FSLogix roaming profiles to work across multiple session hosts. Unlike `CloudKerberosTicketRetrievalEnabled`, this setting has no Settings Catalogue equivalent. With Intune, deploy it via a Remediation script (recommended - detects drift) or a Platform script (runs once at enrolment).

If not using Intune, set both keys directly on your golden image:

```PowerShell
# Enable cloud Kerberos TGT retrieval
New-Item -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa\Kerberos\Parameters" -Force | Out-Null
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa\Kerberos\Parameters" -Name CloudKerberosTicketRetrievalEnabled -PropertyType DWord -Value 1 -Force

# Store credential keys in user profile (required for FSLogix roaming)
New-Item -Path "HKLM:\Software\Policies\Microsoft\AzureADAccount" -Force | Out-Null
New-ItemProperty -Path "HKLM:\Software\Policies\Microsoft\AzureADAccount" -Name LoadCredKeyFromProfile -PropertyType DWord -Value 1 -Force
```

## 14. Configure FSLogix registry keys

Set these on the session hosts via Intune or your preferred config tool:

```
HKLM\SOFTWARE\FSLogix\Profiles
  Enabled = 1
  VHDLocations = \\<storageaccount>.file.core.windows.net\<share>
  VolumeType = VHDX
```

Without Intune, set the keys directly on your golden image:

```PowerShell
# Create key if it doesn't exist
New-Item -Path "HKLM:\SOFTWARE\FSLogix\Profiles" -Force | Out-Null

# Base path
$fsLogixPath = "HKLM:\SOFTWARE\FSLogix\Profiles"

# Core settings
New-ItemProperty -Path $fsLogixPath -Name Enabled -PropertyType DWord -Value 1 -Force
New-ItemProperty -Path $fsLogixPath -Name VHDLocations -PropertyType MultiString -Value "\\YOURSTORAGEACCOUNT.file.core.windows.net\fslogixprofiles" -Force
New-ItemProperty -Path $fsLogixPath -Name VolumeType -PropertyType String -Value "VHDX" -Force
```
> **Note:** I have only added the most basic FSLogix configuration, before deploying to production review the [FSLogix documentation](https://learn.microsoft.com/en-us/fslogix/reference-configuration-settings?tabs=profiles).


## 15. Sysprep and capture

Open a terminal session and run sysprep to generalise it:

```cmd
C:\Windows\System32\Sysprep\sysprep.exe /oobe /generalize /shutdown
```

> **Important:** Sysprep is irreversible. The source VM cannot be used again after generalisation. If you need to update the image later, provision a new VM from the captured image, make your changes, and capture a new version.

Wait for the VM to disconnect your RDP session. In the portal, go to the VM blade and click Stop.

Then go to the VM blade **Capture -> Image**.

As part of the capture process create a new image definition

![Create image definition](/avd-fslogix-entra-kerberos/create-image-definition.png)

| Setting | Value |
|---------|-------|
| Share image to Azure Compute Gallery | Yes, share it to a gallery as a VM image version |
| Gallery | select an existing gallery or create a new one |
| VM image definition | select an existing definition or create a new one |
| Version number | e.g. `1.0.0` |
| Target regions | match your session host region |
| Delete this VM after creating the image | your choice - the VM is unusable after sysprep regardless |

![Capture image](/avd-fslogix-entra-kerberos/capture-image.png)
![Capture image](/avd-fslogix-entra-kerberos/capture-image-2.png)

Capture typically takes 5-15 minutes. Once complete, the image version will appear under the image definition in the gallery and can be selected when deploying session hosts in step 21.

## 16. Create the host pool

In the portal, go to **Manage -> Azure Virtual Desktop -> Host pools -> Create**.

On the **Basics** tab:

| Setting | Value |
|---------|-------|
| Host pool name | e.g. `hp-avd-demo` |
| Location | match your storage account region |
| Host pool type | Pooled |
| Load balancing algorithm | Breadth-first (spreads users across all hosts before filling any single one - better for burst workloads than Depth-first) |
| Max session limit | tune to your VM size; a starting point for Standard_D4s_v5 is 6 |

Skip the rest of the tabs for now, we'll go through each step individually.

After the host pool is deployed, add the Entra-only and SSO RDP properties. Go to the host pool -> **Settings -> RDP Properties -> Advanced** and add:

```
;targetisaadjoined:i:1;enablerdsaadauth:i:1
```

> **Important:** `targetisaadjoined:i:1` is required for non-Windows and unmanaged clients to connect. Web, macOS, iOS, and Android clients will fail without it.

> **Important:** Without `enablerdsaadauth:i:1` users will be prompted for credentials when connecting even if they're already signed in via the Windows App or AVD client.

## 17. Create the app group and workspace

An app group is created automatically with the host pool (named `<hostpoolname>-DAG` for a Desktop pool). You can use this or create a new one: **Azure Virtual Desktop -> Application groups -> Create**, type **Desktop**, linked to your host pool.

Create a workspace to surface the app group to users e.g. `avd_demo`: **Azure Virtual Desktop -> Workspaces -> Create**. On the **Application groups** tab, register your app group.

## 18. Add assignments to your application group

Now all the AVD resources are created, we need to add the assignments so within the Windows app the end users will get access to the host pool. Go to **Azure Virtual Desktop -> Application Groups -> [YOUR APPLICATION GROUP] -> Manage -> Assignments -> Add** and add the group you created that contains your AVD users e.g. `AVD Users`.

## 19. Add session hosts to Remote Connection Configuration

For SSO to work with zero prompts, the session host devices must be registered in Entra's Remote Connection Configuration. Without this, users get a credential prompt on first login even with `enablerdsaadauth:i:1` set correctly.

Go to **Microsoft Entra ID -> Devices -> Remote connection configuration** and add the `AVD Session Hosts` group created in step 1.

> **Important:** Dynamic group membership will take several minutes to populate after session hosts are deployed in step 21 - verify before testing SSO.

## 20. Assign the Virtual Machine User Login role

Users need the **Virtual Machine User Login** RBAC role on the session hosts to sign in. Without it, the connection succeeds but login fails with a permissions error.

Assign it at the resource group level to cover all current and future session hosts: **Your resource group -> Access Control (IAM) -> Add role assignment -> Virtual Machine User Login -> your AVD users group**.

> **Important:** Admins who need local administrator access to the VMs should be assigned **Virtual Machine Administrator Login** instead.

![Assign VM login RBAC role](/avd-fslogix-entra-kerberos/assign-vm-login.png)

## 21. Deploy session hosts

Go to your host pool -> **Manage -> Session hosts -> Add**.

On the **Virtual machines** tab, the key settings for an Entra-only deployment are:

| Setting            | Value                                                                                                                           |
|--------------------|---------------------------------------------------------------------------------------------------------------------------------|
| Name prefix        | e.g. `avd-sh` - portal appends a zero-padded index                                                                             |
| Image              | Your custom image                                                                                                              |
| VM size            | Standard_D4s_v5 or equivalent - size to your max session limit target                                                          |
| Number of VMs      | start with enough to cover your expected peak concurrent users at the session limit you set                                     |
| Domain to join     | Microsoft Entra ID                                                                                                            |
| Enroll VM with Intune | your choice                                                                                                                |
| Registration key   | the portal auto-generates and injects the host pool registration token                                                          |

![Deploy session hosts](/avd-fslogix-entra-kerberos/deploy-session-hosts.png)

Set your subnet to the same VNet as your other AVD resources and provide local admin credentials. These are for break-glass access only - they're not the Entra accounts used for user login.

> **Note:** If you want to manage your session hosts via Intune make sure you select the `Enroll VM with Intune` option, for this demo I will not.

![Deploy session hosts](/avd-fslogix-entra-kerberos/deploy-session-hosts-2.png)

> **Important:** Do not add any NSG details during deployment - the NSG is applied at the subnet level, so configuring it on the NIC here will result in duplicate or conflicting rules.

After the deployment finishes (usually 10-15 minutes), confirm session hosts appear as **Available** in the host pool. If any show **Unavailable** or **Needs Attention**, check the VM extension logs under **Extensions + applications** on the VM blade - the `AADLoginForWindows` and `DSC` extension statuses will indicate what failed, you can also review the deployment logs for errors.

Your users will now be able to access your AVD. To test click on this desktop and it should load using SSO so you will not get a credential prompt.

![Windows app](/avd-fslogix-entra-kerberos/windows-app.png)

## 22. Confirm FSLogix works

When logging into your AVD for the first time FSLogix will create a VHDX file in the `fslogixprofiles` file share profile we created in step 4. Which you can confirm by browsing to the **[YOURFILESHARE] -> Browse** you will see a SID followed by your username.

![FSLogix VHDX](/avd-fslogix-entra-kerberos/fslogix-vhdx.png)

The 2nd thing you can do is when you log in to AVD, create a file on your desktop, make a note of the hostname then sign out and go to your host pool **Mange -> Session hosts** select the VM you were connected to, click **Turn on drain mode** and open up a session to your AVD again, this will if you've deployed multiple VMs take you to another session host, if the file is there when you're connected to a different session host you know FSLogix is working, if its not you've got some troubleshooting to do.

## Gotchas

### Entra Kerberos silently fails if app management policies block the service principal

Enabling Entra Kerberos automatically creates a service principal for the Storage Resource Provider. If your tenant enforces [application management policies](https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/configure-app-management-policies) that block symmetric key addition or restrict key lifetime to under 366 days, this creation fails silently - Kerberos appears enabled but auth will not work. Grant an exception for the Storage Resource Provider (app ID `a6aa9161-5291-40bb-8c5c-923b567bee3b`) before running step 6.

### App group not registered to a workspace

An app group that isn't registered to a workspace won't appear in the Windows App or web client - users will see an empty feed. Double-check the workspace shows the app group under **Application groups** after creation.

### Domain to join defaults to Active Directory

"Domain to join" defaults to **Active Directory** in some portal versions. If you leave it on the default and deploy, the extension will attempt an AD domain join that never completes. The session hosts will appear in the host pool but sit in an unavailable state. Always confirm this is set to Microsoft Entra ID before deploying.

### Intune enrolment licence and connectivity

Intune enrolment requires an Intune (Endpoint Manager) licence assigned to users, and the VMs must be able to reach Intune endpoints. If enrolment silently fails, the Kerberos TGT policy from step 13 won't apply and profile mounts will fail.

### CA exclusion failure is silent

If a Conditional Access policy enforcing MFA applies to the storage account app and you haven't excluded it, profile mounts fail silently. The user gets a temporary profile and the FSLogix event log won't make the root cause obvious - there's no interactive MFA prompt to indicate what's happening. Exclude the storage account app before testing any profile mounts.

### OMA-URI doesn't work for CloudKerberosTicketRetrievalEnabled on multisession

If you configure `Kerberos/CloudKerberosTicketRetrievalEnabled` via OMA-URI in Intune, it won't apply on AVD multisession hosts. Use the Settings Catalogue method specifically. This is [documented by Microsoft](https://learn.microsoft.com/en-us/azure/storage/files/storage-files-identity-auth-hybrid-identities-enable) but easy to miss if you default to OMA-URI out of habit.

### Regional availability for specific RBAC with cloud-only identities

Specific RBAC role assignments for cloud-only identities only work in a [subset of Azure public cloud regions](https://learn.microsoft.com/en-us/azure/storage/files/storage-files-identity-auth-hybrid-identities-enable#regional-availability-for-microsoft-entra-kerberos). If your storage account is outside that list, fall back to the default share-level permission (step 10). Attempting specific RBAC in an unsupported region will result in access failures that are difficult to trace.

### One identity source per storage account

If the storage account is already configured for ADDS or Entra Domain Services authentication, you need to remove it before enabling Entra Kerberos. You can't run multiple identity sources on a single storage account.

Plan this in if you're migrating an existing hybrid deployment - you'll need a maintenance window to switch over.

### icacls doesn't work for cloud-only identities

For cloud-only Entra Kerberos, `icacls` and Windows File Explorer are not supported for setting NTFS permissions - [Microsoft's own docs](https://learn.microsoft.com/en-us/azure/storage/files/storage-files-identity-configure-file-level-permissions) are explicit on this. The supported options are the Azure portal Manage Access blade (step 11) or the [`RestSetAcls` PowerShell module](https://www.powershellgallery.com/packages/RestSetAcls/). The RestSetAcls module is useful if you need to assign ACLs in bulk or want to script the initial setup.

### Required Windows services on session hosts

`WinHttpAutoProxySvc` (WinHTTP Web Proxy Auto-Discovery) and `iphlpsvc` (IP Helper) must be running on session hosts for Entra Kerberos to function. Marketplace images have both enabled by default - if you're using a hardened or custom image and profile mounts fail with no obvious FSLogix error, check these services first.

## Summary

AVD with FSLogix and cloud-only Entra identities is now a fully supported, domain-controller-free deployment. The 21 steps cover everything from networking and storage through to image capture, AVD resource creation, and session host deployment - with Entra Kerberos handling authentication end to end.

Several of the failure modes in this stack are silent: a temporary profile with no useful event log entry is the common symptom for misconfigured Kerberos TGT policy, a missing CA exclusion, or incorrect NTFS permissions.

For migrations from an existing hybrid deployment, remember you can only have one identity source per storage account - switching to Entra Kerberos requires removing the existing ADDS or Entra Domain Services configuration first, which needs a maintenance window.
