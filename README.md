# Virtual Stylist

An AI-powered virtual stylist and digital wardrobe for women, men, and kids.
Upload your closet once, then get outfit suggestions tuned to your destination,
mood, and the weather — with a family-friendly mode for parents and kids.

## Vision

Solve the universal "what to wear" problem with zero friction. Users photograph
their clothes; computer vision tags them; an LLM-driven stylist composes 2–3
complete outfits on demand. A monetization layer surfaces affiliate-shoppable
staples that fill genuine gaps in the user's wardrobe.

## Design Documents

- [Product Requirements (PRD)](docs/PRD.md) — features, user stories, KPIs, compliance
- [System Architecture](docs/ARCHITECTURE.md) — tech stack, AI pipeline, infra
- [Database Schema](docs/SCHEMA.md) — entities, relationships, indexing
- [MVP Roadmap](docs/ROADMAP.md) — 4-phase plan to a working iOS + Android prototype

## Other Services in this Monorepo

- [`services/compliance`](services/compliance/README.md) — **BFL Group Elite
  Compliance & Audit AI Agent**: validates authenticity, sourcing legitimacy,
  and chain of title of goods from sanitized invoice documentation. Buyers
  drag-and-drop the deal documents (PDFs, Excel, photos) and get a
  Green / Amber / Red risk signal with a full red-flag report.

## Status

Pre-implementation. This branch holds the design blueprint that engineering
will build against in Phase 1.
