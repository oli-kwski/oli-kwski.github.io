---
title: "{{ replace .File.ContentBaseName "-" " " | title }}"
date: {{ .Date }}
draft: true
description: ""          # short summary shown in post list & SEO meta

# ---------------------------------------------------------------------------
# Taxonomy — at least one tag and one category
# ---------------------------------------------------------------------------
tags:
  - Azure
categories:
  - General                # e.g. Architecture | DevOps | Security | Networking

# Optional: group related posts into a series
# series:
#   - "Getting started with Azure"

# ---------------------------------------------------------------------------
# Cover image (optional)
# ---------------------------------------------------------------------------
# cover:
#   image: "cover.png"       # place in the same directory as the post
#   alt: "A descriptive alt text"
#   caption: "Caption shown below the image"
#   relative: true           # set true if image is in the same folder as the post

# ---------------------------------------------------------------------------
# Per-post toggles (all default to the site-wide value in hugo.toml)
# ---------------------------------------------------------------------------
comments: true             # set false to disable Giscus on this post
ShowToc: true
TocOpen: false
ShowReadingTime: true
ShowBreadCrumbs: true
ShowPostNavLinks: true
ShowWordCount: false
---

<!-- Write your post here. Delete this comment when you start. -->
