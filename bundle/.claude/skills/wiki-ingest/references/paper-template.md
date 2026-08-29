# Paper Deep-Dive Template

**This file is the canonical Paper Deep-Dive Template.** `wiki-ingest` is its only consumer —
nothing else in the bundle defines or copies it.

The generic page template (see `~/.claude/doc/doc_wiki_schema.md`) suits most sources.
**Academic papers are the exception.** For ML/AI/LLM/VLM (and similar) papers landing in
`references/`, the substance lives in the architecture, the equations, and the results table —
exactly what a terse "Key Ideas" list flattens away. For these, use the richer template below.
This is the one place where *"compile, don't retrieve"* yields to a thorough, self-contained
walkthrough a reader could study instead of the paper.

Obsidian renders the needed primitives natively, so no extra tooling is required: Mermaid fenced
diagrams, `$$…$$` LaTeX (MathJax), markdown tables, and `![[image]]` / `![[paper.pdf#page=N]]`
embeds.

Use this template only when the source is an academic paper (arXiv/conference) with load-bearing
figures or equations. Everything else uses the generic page template. Frontmatter, provenance
markers, confidence, lifecycle, and `relationships:` are unchanged — only the body sections
differ.

````markdown
---
# ...required frontmatter, same as the generic template; category: references...
---

# Paper Title

> [!tldr] One sentence: what's new, plus the headline result.

## Problem & Motivation

What's broken or missing that this paper addresses.

## Method / Architecture

Prose walkthrough. Embed the paper's real architecture figure as the primary
visual (see *Academic papers* in SKILL.md for the PyMuPDF extraction recipe).
Fall back to a Mermaid flowchart only when no figure can be extracted.

![[attachments/<slug>-fig1.png]]
*Figure N (Author Year): one-line caption.*

## Key Equations

The 1–3 core equations as display math, not backtick code:

$$ \mathcal{L} = \mathbb{E}_{x}\!\left[-\log p_\theta(y \mid z)\right] $$

## Results

Headline numbers as a table, not a comma-separated blob — and embed a key
results/motivating figure (scaling plot, benchmark chart, capability collage)
when the paper has one:

| Method | Benchmark | Metric | Cost |
|---|---|---|---|
| Baseline | … | … | … |
| **This paper** | … | … | … |

![[attachments/<slug>-resultsN.png]]
*Figure N (Author Year): one-line caption.*

## Limitations

What the paper concedes or sidesteps. Mark reading-between-the-lines as ^[inferred].

## Related

Typed `[[wikilinks]]` to neighbouring work.

## Sources

- Clickable canonical link, e.g. <https://arxiv.org/abs/XXXX.XXXXX>
````

A Mermaid diagram reconstructed from the paper's prose is a synthesis, not a transcription —
treat it as `^[inferred]` when the interpretation is non-trivial.
