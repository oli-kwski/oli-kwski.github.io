---
title: "{{ replace .File.ContentBaseName "-" " " | title }}"
date: {{ .Date }}
draft: true
description: "One-liner that becomes the meta description and link-preview blurb. Aim for 140–160 chars."

tags:
  -
categories:
  -
series:
  -

comments: true
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: false
ShowPostNavLinks: true
---

<!-- Short intro: 2–4 sentences. Frame the problem in plain language, no preamble. End on a "here's why this matters" hook. -->

---

## The problem they solve

<!-- Concrete scenario the reader will recognise. Bullet the consequences (attack surface, cost, compliance, ops pain). Real numbers > generic hand-waving. -->

- **Pain point one** —
- **Pain point two** —
- **Pain point three** —

## What is it / How it works

<!-- The explanation. Start with the one-sentence definition, then unpack. Use a table for any mapping (service → zone, group → endpoint, etc.). -->

| Thing | Maps to |
|---|---|
|  |  |

<!-- Diagram(s) go here. Use the figure.diagram pattern: -->
<!--
<figure class="diagram">
  <img src="/POST-SLUG/diagram-name.png" alt="Descriptive alt text" style="display: block; width: 100%; height: auto;" />
  <figcaption style="margin-top: 0.75rem; font-size: 0.875rem;">Caption</figcaption>
</figure>
-->

## When to use it

<!-- Opinionated guidance on when this is the right tool — and when it isn't. Avoid "it depends". -->

- **Use it when** —
- **Skip it when** —

## Show me the code

<!-- IaC snippet. Bicep first, then Terraform if relevant. Keep snippets minimal — no unrelated noise. -->

```bicep
// Bicep snippet
```

```hcl
# Terraform equivalent
```

## Common gotchas

**1. First gotcha**
What it looks like, why it bites, how to avoid it. One paragraph.

**2. Second gotcha**

**3. Cost**
GBP per-month numbers if applicable.

---

## Summary

<!-- 2–3 sentences. Restate the takeaway, not the whole post. End on a forward-looking line tying back to landing zones / production patterns where it fits. -->
