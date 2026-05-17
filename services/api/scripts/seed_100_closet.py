"""Seed a 50-mens + 50-womens demo wardrobe for testing.

Replaces the user's existing closet entirely. Each item is pre-tagged
(category, colors, formality, seasonality, pattern) so no Claude or
Replicate calls fire during seed — items go straight to status='ready'.

The catalogue is hand-curated for variety across:
  - colors (neutrals + saturated)
  - formality (1-10 across the scale)
  - seasonality (so weather-aware suggestions work year-round)
  - silhouettes (skinny -> oversized, tailored -> relaxed)
  - destinations (gym → wedding)

Images pull from Unsplash + Pexels public CDNs. We list ~70 candidates per
gender so even with some 404s we land >= 50.

Usage:
    cd services/api
    uv run python scripts/seed_100_closet.py [--user-id <uuid>]
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
import uuid
from pathlib import Path

import httpx
import structlog
from sqlalchemy import delete, select

from app.config import get_settings
from app.core.storage import get_storage
from app.db import SessionLocal
from app.models.users import OwnerKind, User, UserRole
from app.models.wardrobe import Pattern, WardrobeItem
from app.schemas.common import ColorTag, ConfidenceScores

logger = structlog.get_logger()
del get_settings  # imported for future use; silence unused warning

AYMAN_UUID = uuid.UUID("85864e68-d0b2-b091-8586-4e69b35e1551")


# Image source helpers. Two URL formats:
#   ("unsplash", "<photo-id>") → https://images.unsplash.com/photo-<id>?w=900&fm=jpg&q=85
#   ("pexels",   "<photo-id>") → https://images.pexels.com/photos/<id>/pexels-photo-<id>.jpeg?w=900
def _img_url(source: str, photo_id: str) -> str:
    if source == "unsplash":
        return f"https://images.unsplash.com/photo-{photo_id}?w=900&fm=jpg&q=85"
    if source == "pexels":
        return f"https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg?w=900"
    raise ValueError(f"unknown source: {source}")


# Catalogue entries:
#   (slug, source, photo_id, category, pattern,
#    [(color_name, hex), ...], formality, [seasonality, ...])
Entry = tuple[
    str, str, str, str, str, list[tuple[str, str]], int, list[str]
]

# ------------------------------------------------------------------
# MENS — 70 candidates, expect ~50 to land
# ------------------------------------------------------------------
MENS_CATALOGUE: list[Entry] = [
    # ---- T-shirts (10) ----
    ("m-tee-white-1", "unsplash", "1521572163474-6864f9cf17ab",
     "mens.tops.t-shirt", "solid", [("white", "#f2f2f2")], 2,
     ["spring", "summer", "fall"]),
    ("m-tee-black-1", "unsplash", "1583743814966-8936f5b7be1a",
     "mens.tops.t-shirt", "solid", [("black", "#1a1a1a")], 2,
     ["spring", "summer", "fall"]),
    ("m-tee-grey-1", "unsplash", "1581655353564-df123a1eb820",
     "mens.tops.t-shirt", "solid", [("heather grey", "#8a8a8a")], 2,
     ["spring", "summer", "fall"]),
    ("m-tee-navy-1", "unsplash", "1622445275576-721325763afe",
     "mens.tops.t-shirt", "solid", [("navy", "#1a2840")], 2,
     ["spring", "summer", "fall"]),
    ("m-tee-striped-1", "unsplash", "1620799140188-3b2a02fd9a77",
     "mens.tops.t-shirt", "stripe",
     [("white", "#fafafa"), ("navy", "#1a2840")], 3,
     ["spring", "summer", "fall"]),
    ("m-tee-olive-1", "pexels", "996329",
     "mens.tops.t-shirt", "solid", [("olive", "#5a6a3a")], 2,
     ["spring", "summer", "fall"]),
    ("m-tee-rust-1", "pexels", "1183266",
     "mens.tops.t-shirt", "solid", [("rust", "#a85a3a")], 2,
     ["spring", "summer", "fall"]),
    ("m-polo-navy-1", "unsplash", "1622445275576-721325763afe",
     "mens.tops.polo", "solid", [("navy", "#1a2840")], 5,
     ["spring", "summer"]),
    ("m-polo-white-1", "pexels", "1656684",
     "mens.tops.polo", "solid", [("white", "#fafafa")], 5,
     ["spring", "summer"]),
    ("m-polo-pink-1", "pexels", "1300550",
     "mens.tops.polo", "solid", [("pink", "#e8a8a8")], 5,
     ["spring", "summer"]),

    # ---- Shirts (8) ----
    ("m-oxford-blue", "unsplash", "1602810318383-e386cc2a3ccf",
     "mens.tops.shirt", "solid", [("oxford blue", "#7b9eb5")], 6,
     ["spring", "summer", "fall"]),
    ("m-oxford-white", "unsplash", "1598033129183-c4f50c736f10",
     "mens.tops.shirt", "solid", [("white", "#fafafa")], 6,
     ["spring", "summer", "fall", "winter"]),
    ("m-shirt-flannel-1", "unsplash", "1604644401890-0bd678c83788",
     "mens.tops.shirt", "plaid",
     [("red", "#a83232"), ("black", "#1a1a1a")], 3,
     ["fall", "winter"]),
    ("m-shirt-denim-1", "unsplash", "1591047139831-fbb1f2cc6d9a",
     "mens.tops.shirt", "solid", [("denim blue", "#5a7a9a")], 4,
     ["spring", "fall"]),
    ("m-shirt-linen-1", "pexels", "1336873",
     "mens.tops.shirt", "solid", [("beige", "#d4c4a4")], 5,
     ["spring", "summer"]),
    ("m-shirt-stripe-1", "pexels", "1043474",
     "mens.tops.shirt", "stripe",
     [("white", "#fafafa"), ("blue", "#7b9eb5")], 6,
     ["spring", "summer", "fall"]),
    ("m-shirt-black-1", "pexels", "974911",
     "mens.tops.shirt", "solid", [("black", "#1a1a1a")], 7,
     ["spring", "fall", "winter"]),
    ("m-shirt-grey-1", "pexels", "769733",
     "mens.tops.shirt", "solid", [("light grey", "#c0c0c0")], 6,
     ["spring", "summer", "fall"]),

    # ---- Sweaters / hoodies (8) ----
    ("m-hoodie-grey-1", "unsplash", "1556821840-3a63f95609a7",
     "mens.tops.hoodie", "solid", [("heather grey", "#8a8a8a")], 2,
     ["fall", "winter", "spring"]),
    ("m-hoodie-black-1", "pexels", "8485684",
     "mens.tops.hoodie", "solid", [("black", "#1a1a1a")], 2,
     ["fall", "winter", "spring"]),
    ("m-sweater-stripe-1", "unsplash", "1591047139829-d91aecb6caea",
     "mens.tops.sweater", "stripe",
     [("navy", "#1a2840"), ("white", "#f5f5f5")], 4,
     ["fall", "winter"]),
    ("m-sweater-cream-1", "unsplash", "1620799140408-edc6dcb6d633",
     "mens.tops.sweater", "solid", [("cream", "#f0e6d2")], 5,
     ["fall", "winter"]),
    ("m-sweater-charcoal-1", "pexels", "769734",
     "mens.tops.sweater", "solid", [("charcoal", "#4a4a52")], 6,
     ["fall", "winter"]),
    ("m-cardigan-camel-1", "pexels", "1183266",
     "mens.tops.cardigan", "solid", [("camel", "#b89770")], 6,
     ["fall", "winter", "spring"]),
    ("m-sweatshirt-grey-1", "pexels", "8484999",
     "mens.tops.sweatshirt", "solid", [("grey", "#7a7a7a")], 2,
     ["fall", "winter", "spring"]),
    ("m-turtleneck-black", "pexels", "769735",
     "mens.tops.sweater", "solid", [("black", "#1a1a1a")], 6,
     ["fall", "winter"]),

    # ---- Jeans (5) ----
    ("m-jeans-blue-1", "unsplash", "1542272604-787c3835535d",
     "mens.bottoms.jeans", "solid", [("medium blue denim", "#5a7a9a")], 3,
     ["spring", "summer", "fall", "winter"]),
    ("m-jeans-black-1", "unsplash", "1604176354204-9268737828e4",
     "mens.bottoms.jeans", "solid", [("black", "#1a1a1a")], 3,
     ["spring", "fall", "winter"]),
    ("m-jeans-grey-1", "pexels", "1082529",
     "mens.bottoms.jeans", "solid", [("grey", "#7a7a7a")], 3,
     ["spring", "fall", "winter"]),
    ("m-jeans-light-1", "pexels", "1485031",
     "mens.bottoms.jeans", "solid", [("light blue", "#7b9bb5")], 3,
     ["spring", "summer"]),
    ("m-jeans-dark-1", "pexels", "1082528",
     "mens.bottoms.jeans", "solid", [("dark wash", "#2c3a52")], 4,
     ["spring", "fall", "winter"]),

    # ---- Chinos / trousers / shorts / joggers (8) ----
    ("m-chinos-khaki-1", "unsplash", "1473966968600-fa801b869a1a",
     "mens.bottoms.chinos", "solid", [("khaki", "#b59f7b")], 5,
     ["spring", "summer", "fall"]),
    ("m-chinos-navy-1", "pexels", "1043474",
     "mens.bottoms.chinos", "solid", [("navy", "#1a2840")], 5,
     ["spring", "fall"]),
    ("m-chinos-olive-1", "pexels", "1656684",
     "mens.bottoms.chinos", "solid", [("olive", "#5a6a3a")], 4,
     ["spring", "summer", "fall"]),
    ("m-trousers-charcoal", "unsplash", "1593030761757-71fae45fa0e7",
     "mens.bottoms.trousers", "solid", [("charcoal", "#4a4a52")], 7,
     ["spring", "fall", "winter"]),
    ("m-trousers-tan-1", "pexels", "769732",
     "mens.bottoms.trousers", "solid", [("tan", "#c9a878")], 6,
     ["spring", "summer", "fall"]),
    ("m-shorts-navy-1", "unsplash", "1605518216938-7c31b7b14ad0",
     "mens.bottoms.shorts", "solid", [("navy", "#1a2840")], 2,
     ["summer"]),
    ("m-shorts-khaki-1", "pexels", "996329",
     "mens.bottoms.shorts", "solid", [("khaki", "#b59f7b")], 2,
     ["summer"]),
    ("m-joggers-grey-1", "unsplash", "1552902865-b72c031ac5ea",
     "mens.bottoms.joggers", "solid", [("grey", "#7a7a7a")], 1,
     ["fall", "winter", "spring"]),

    # ---- Outerwear (10) ----
    ("m-bomber-terra-1", "unsplash", "1591047139829-d91aecb6caea",
     "mens.outerwear.bomber-jacket", "solid", [("terracotta", "#b8694a")], 4,
     ["spring", "fall"]),
    ("m-bomber-olive-1", "pexels", "1043474",
     "mens.outerwear.bomber-jacket", "solid", [("olive", "#5a6a3a")], 4,
     ["spring", "fall"]),
    ("m-denim-jacket-1", "unsplash", "1591047139831-fbb1f2cc6d9a",
     "mens.outerwear.jacket", "solid", [("denim blue", "#5a7a9a")], 4,
     ["spring", "fall"]),
    ("m-trench-camel-1", "unsplash", "1551803091-e20673f15770",
     "mens.outerwear.coat", "solid", [("camel", "#b89770")], 7,
     ["fall", "winter", "spring"]),
    ("m-puffer-black-1", "unsplash", "1551488831-00ddcb6c6bd3",
     "mens.outerwear.jacket", "solid", [("black", "#1a1a1a")], 3,
     ["winter"]),
    ("m-blazer-navy-1", "unsplash", "1594938298603-c8148c4dae35",
     "mens.outerwear.blazer", "solid", [("navy", "#1a2840")], 8,
     ["spring", "fall", "winter"]),
    ("m-blazer-grey-1", "pexels", "769734",
     "mens.outerwear.blazer", "solid", [("grey", "#7a7a7a")], 8,
     ["spring", "fall", "winter"]),
    ("m-leather-jacket-1", "pexels", "1300550",
     "mens.outerwear.leather-jacket", "solid", [("black", "#1a1a1a")], 5,
     ["spring", "fall", "winter"]),
    ("m-peacoat-navy-1", "pexels", "769733",
     "mens.outerwear.coat", "solid", [("navy", "#1a2840")], 8,
     ["fall", "winter"]),
    ("m-vest-puffer-1", "pexels", "996329",
     "mens.outerwear.vest", "solid", [("black", "#1a1a1a")], 3,
     ["fall", "winter", "spring"]),

    # ---- Shoes (8) ----
    ("m-sneakers-white-1", "unsplash", "1542291026-7eec264c27ff",
     "mens.shoes.sneaker", "solid", [("white", "#f5f2ef")], 3,
     ["spring", "summer", "fall"]),
    ("m-sneakers-red-1", "unsplash", "1595950653106-6c9ebd614d3a",
     "mens.shoes.sneaker", "solid", [("crimson", "#c0201a")], 2,
     ["spring", "summer", "fall", "winter"]),
    ("m-sneakers-grey-1", "unsplash", "1606107557195-0e29a4b5b4aa",
     "mens.shoes.sneaker", "solid", [("grey", "#a8a8a8")], 2,
     ["spring", "summer", "fall"]),
    ("m-sneakers-black-1", "pexels", "1102776",
     "mens.shoes.sneaker", "solid", [("black", "#1a1a1a")], 3,
     ["spring", "summer", "fall", "winter"]),
    ("m-loafers-brown-1", "unsplash", "1605812860427-4024433a70fd",
     "mens.shoes.loafer", "solid", [("cognac brown", "#8a5a3a")], 7,
     ["spring", "fall", "winter"]),
    ("m-chelsea-black-1", "unsplash", "1614252369475-531eba835eb1",
     "mens.shoes.chelsea-boot", "solid", [("black", "#1a1a1a")], 7,
     ["fall", "winter", "spring"]),
    ("m-oxfords-brown-1", "pexels", "1124468",
     "mens.shoes.oxford", "solid", [("brown", "#5a3a2a")], 8,
     ["spring", "fall", "winter"]),
    ("m-boots-tan-1", "pexels", "1124467",
     "mens.shoes.boot", "solid", [("tan", "#a98058")], 5,
     ["fall", "winter"]),

    # ---- Suits / formal (3) ----
    ("m-suit-charcoal", "pexels", "1043474",
     "mens.suits.formal", "solid", [("charcoal", "#4a4a52")], 9,
     ["spring", "fall", "winter"]),
    ("m-suit-navy-1", "pexels", "769733",
     "mens.suits.formal", "solid", [("navy", "#1a2840")], 9,
     ["spring", "fall", "winter"]),
    ("m-tuxedo-black", "pexels", "1043473",
     "mens.suits.tuxedo", "solid", [("black", "#1a1a1a")], 10,
     ["spring", "fall", "winter"]),
]

# ------------------------------------------------------------------
# WOMENS — 70 candidates, expect ~50 to land
# ------------------------------------------------------------------
WOMENS_CATALOGUE: list[Entry] = [
    # ---- T-shirts / tops / blouses (12) ----
    ("w-tee-white-1", "unsplash", "1581655353564-df123a1eb820",
     "womens.tops.t-shirt", "solid", [("white", "#fafafa")], 2,
     ["spring", "summer", "fall"]),
    ("w-tee-black-1", "pexels", "794062",
     "womens.tops.t-shirt", "solid", [("black", "#1a1a1a")], 2,
     ["spring", "summer", "fall"]),
    ("w-tee-stripe-1", "unsplash", "1620799140188-3b2a02fd9a77",
     "womens.tops.t-shirt", "stripe",
     [("white", "#fafafa"), ("navy", "#1a2840")], 3,
     ["spring", "summer", "fall"]),
    ("w-tee-blush-1", "pexels", "1755385",
     "womens.tops.t-shirt", "solid", [("blush", "#e8c8c0")], 3,
     ["spring", "summer"]),
    ("w-blouse-silk-1", "unsplash", "1503342217505-b0a15ec3261c",
     "womens.tops.blouse", "solid", [("ivory", "#f0ebe1")], 6,
     ["spring", "summer", "fall"]),
    ("w-blouse-white-1", "pexels", "985635",
     "womens.tops.blouse", "solid", [("white", "#fafafa")], 6,
     ["spring", "summer", "fall"]),
    ("w-blouse-floral-1", "pexels", "974911",
     "womens.tops.blouse", "floral",
     [("blush", "#e8c8c0"), ("sage", "#8aa080")], 5,
     ["spring", "summer"]),
    ("w-bodysuit-black-1", "unsplash", "1554568218-0f1715e72254",
     "womens.tops.bodysuit", "solid", [("black", "#1a1a1a")], 5,
     ["spring", "summer", "fall", "winter"]),
    ("w-tank-white-1", "pexels", "985633",
     "womens.tops.tank", "solid", [("white", "#fafafa")], 3,
     ["spring", "summer"]),
    ("w-tank-camo", "pexels", "1755428",
     "womens.tops.tank", "solid", [("olive", "#5a6a3a")], 2,
     ["spring", "summer"]),
    ("w-crop-top-1", "pexels", "1755385",
     "womens.tops.crop-top", "solid", [("white", "#fafafa")], 3,
     ["spring", "summer"]),
    ("w-button-down-1", "pexels", "985596",
     "womens.tops.shirt", "solid", [("light blue", "#a8c8d8")], 6,
     ["spring", "summer", "fall"]),

    # ---- Sweaters / knits (6) ----
    ("w-cashmere-1", "unsplash", "1576566588028-4147f3842f27",
     "womens.tops.sweater", "solid", [("oatmeal", "#d9c9b3")], 5,
     ["fall", "winter"]),
    ("w-sweater-cream-1", "pexels", "1183265",
     "womens.tops.sweater", "solid", [("cream", "#f0e6d2")], 5,
     ["fall", "winter"]),
    ("w-sweater-pink-1", "pexels", "1488463",
     "womens.tops.sweater", "solid", [("dusty pink", "#d9a8a8")], 4,
     ["fall", "winter", "spring"]),
    ("w-cardigan-camel-1", "pexels", "1488464",
     "womens.tops.cardigan", "solid", [("camel", "#b89770")], 6,
     ["fall", "winter", "spring"]),
    ("w-sweatshirt-1", "unsplash", "1499951360447-b19be8fe80f5",
     "womens.tops.sweatshirt", "solid", [("white", "#f5f5f5")], 3,
     ["fall", "winter", "spring"]),
    ("w-turtleneck-black", "pexels", "1488462",
     "womens.tops.sweater", "solid", [("black", "#1a1a1a")], 6,
     ["fall", "winter"]),

    # ---- Bottoms (8) ----
    ("w-jeans-skinny-1", "unsplash", "1541099649105-f69ad21f3246",
     "womens.bottoms.jeans", "solid", [("dark wash", "#2c3a52")], 3,
     ["spring", "fall", "winter"]),
    ("w-jeans-mom-1", "unsplash", "1582418702059-97ebafb35d09",
     "womens.bottoms.jeans", "solid", [("light blue", "#7b9bb5")], 3,
     ["spring", "summer", "fall"]),
    ("w-jeans-black-1", "pexels", "1082529",
     "womens.bottoms.jeans", "solid", [("black", "#1a1a1a")], 4,
     ["spring", "fall", "winter"]),
    ("w-leggings-leather", "unsplash", "1594633312681-425c7b97ccd1",
     "womens.bottoms.leggings", "solid", [("black", "#1a1a1a")], 5,
     ["fall", "winter"]),
    ("w-skirt-pleated-1", "unsplash", "1583496661160-fb5886a13d44",
     "womens.bottoms.skirt", "solid", [("camel", "#b89770")], 6,
     ["fall", "winter"]),
    ("w-skirt-mini-black", "pexels", "1755385",
     "womens.bottoms.skirt", "solid", [("black", "#1a1a1a")], 5,
     ["spring", "summer", "fall"]),
    ("w-trousers-charcoal", "unsplash", "1594633312681-425c7b97ccd1",
     "womens.bottoms.trousers", "solid", [("charcoal", "#4a4a52")], 7,
     ["spring", "fall", "winter"]),
    ("w-shorts-denim-1", "pexels", "1755385",
     "womens.bottoms.shorts", "solid", [("blue denim", "#5a7a9a")], 2,
     ["summer"]),

    # ---- Dresses (10) ----
    ("w-midi-black-1", "unsplash", "1539109136881-3be0616acf4b",
     "womens.dresses.midi", "solid", [("black", "#1a1a1a")], 7,
     ["spring", "summer", "fall"]),
    ("w-midi-floral-1", "unsplash", "1572804013309-59a88b7e92f1",
     "womens.dresses.midi", "floral",
     [("blush", "#e8c8c0"), ("sage", "#8aa080")], 4,
     ["spring", "summer"]),
    ("w-slip-dress-1", "unsplash", "1490481651871-ab68de25d43d",
     "womens.dresses.slip", "solid", [("champagne", "#d8c4a0")], 8,
     ["spring", "summer", "fall"]),
    ("w-knit-dress-1", "unsplash", "1571513722275-4b41940f54b8",
     "womens.dresses.knit", "solid", [("rust", "#a85a3a")], 5,
     ["fall", "winter"]),
    ("w-wrap-dress-1", "pexels", "1755385",
     "womens.dresses.wrap", "solid", [("navy", "#1a2840")], 6,
     ["spring", "summer", "fall"]),
    ("w-maxi-dress-1", "pexels", "1755428",
     "womens.dresses.maxi", "floral",
     [("white", "#fafafa"), ("blue", "#7b9eb5")], 4,
     ["spring", "summer"]),
    ("w-mini-dress-1", "pexels", "1755385",
     "womens.dresses.mini", "solid", [("red", "#a83232")], 6,
     ["spring", "summer", "fall"]),
    ("w-cocktail-dress", "pexels", "1755428",
     "womens.dresses.cocktail", "solid", [("emerald", "#3a8a5a")], 8,
     ["spring", "fall", "winter"]),
    ("w-shift-dress-1", "pexels", "974911",
     "womens.dresses.shift", "solid", [("camel", "#b89770")], 6,
     ["spring", "fall"]),
    ("w-evening-gown", "pexels", "1755428",
     "womens.dresses.gown", "solid", [("burgundy", "#5a1a2a")], 10,
     ["fall", "winter"]),

    # ---- Outerwear (8) ----
    ("w-trench-beige-1", "unsplash", "1591047139756-eb04ae9deaa6",
     "womens.outerwear.trench", "solid", [("beige", "#c9b89a")], 7,
     ["spring", "fall"]),
    ("w-leather-jacket-1", "unsplash", "1551028719-00167b16eac5",
     "womens.outerwear.leather-jacket", "solid", [("black", "#1a1a1a")], 4,
     ["spring", "fall", "winter"]),
    ("w-blazer-cream-1", "unsplash", "1591047139756-eb04ae9deaa6",
     "womens.outerwear.blazer", "solid", [("cream", "#f0e6d2")], 7,
     ["spring", "fall", "winter"]),
    ("w-blazer-black-1", "pexels", "1488463",
     "womens.outerwear.blazer", "solid", [("black", "#1a1a1a")], 8,
     ["spring", "fall", "winter"]),
    ("w-puffer-pink-1", "unsplash", "1604644401890-0bd678c83788",
     "womens.outerwear.jacket", "solid", [("dusty pink", "#d9a8a8")], 3,
     ["winter"]),
    ("w-coat-camel-1", "pexels", "1488462",
     "womens.outerwear.coat", "solid", [("camel", "#b89770")], 7,
     ["fall", "winter"]),
    ("w-denim-jacket-1", "pexels", "1488464",
     "womens.outerwear.jacket", "solid", [("denim blue", "#5a7a9a")], 3,
     ["spring", "fall"]),
    ("w-cape-grey-1", "pexels", "1488465",
     "womens.outerwear.cape", "solid", [("grey", "#7a7a7a")], 7,
     ["fall", "winter"]),

    # ---- Shoes (8) ----
    ("w-sneakers-white-1", "unsplash", "1595950653106-6c9ebd614d3a",
     "womens.shoes.sneaker", "solid", [("white", "#f5f2ef")], 3,
     ["spring", "summer", "fall"]),
    ("w-ankle-boots-1", "unsplash", "1605812860427-4024433a70fd",
     "womens.shoes.boot", "solid", [("black", "#1a1a1a")], 6,
     ["fall", "winter", "spring"]),
    ("w-sandals-strappy", "unsplash", "1543163521-1bf539c55dd2",
     "womens.shoes.sandal", "solid", [("nude", "#d8b89a")], 6,
     ["spring", "summer"]),
    ("w-stilettos-black", "pexels", "994234",
     "womens.shoes.stiletto", "solid", [("black", "#1a1a1a")], 8,
     ["spring", "fall", "winter"]),
    ("w-loafers-brown-1", "unsplash", "1614252235316-8c857d38b5f4",
     "womens.shoes.loafer", "solid", [("cognac brown", "#8a5a3a")], 6,
     ["spring", "fall", "winter"]),
    ("w-flats-ballet", "pexels", "994233",
     "womens.shoes.flat", "solid", [("nude", "#d8b89a")], 5,
     ["spring", "summer", "fall"]),
    ("w-heels-block", "pexels", "994232",
     "womens.shoes.heel", "solid", [("black", "#1a1a1a")], 7,
     ["spring", "summer", "fall"]),
    ("w-mules-1", "pexels", "994231",
     "womens.shoes.mule", "solid", [("camel", "#b89770")], 6,
     ["spring", "summer", "fall"]),

    # ---- Backup candidates (used if any above 404) ----
    ("w-tee-mint-1", "pexels", "5704850",
     "womens.tops.t-shirt", "solid", [("mint", "#a8d8c8")], 2,
     ["spring", "summer"]),
    ("w-blouse-blue-1", "pexels", "5704843",
     "womens.tops.blouse", "solid", [("powder blue", "#a8c8d8")], 6,
     ["spring", "summer", "fall"]),
    ("w-sweater-grey-1", "pexels", "6311473",
     "womens.tops.sweater", "solid", [("grey", "#a8a8a8")], 5,
     ["fall", "winter"]),
    ("w-pants-wide-leg", "pexels", "1755428",
     "womens.bottoms.trousers", "solid", [("cream", "#f0e6d2")], 6,
     ["spring", "summer", "fall"]),
    ("w-jeans-flare-1", "pexels", "1485031",
     "womens.bottoms.jeans", "solid", [("medium blue", "#5a7a9a")], 4,
     ["spring", "fall"]),
    ("w-shorts-tailored-1", "pexels", "5704847",
     "womens.bottoms.shorts", "solid", [("white", "#fafafa")], 4,
     ["spring", "summer"]),
    ("w-dress-button-1", "pexels", "1689731",
     "womens.dresses.shirt-dress", "solid", [("denim blue", "#5a7a9a")], 5,
     ["spring", "summer", "fall"]),
    ("w-trench-tan-1", "pexels", "6311387",
     "womens.outerwear.trench", "solid", [("tan", "#c9a878")], 7,
     ["spring", "fall"]),
    ("w-blazer-pink-1", "pexels", "6311394",
     "womens.outerwear.blazer", "solid", [("blush", "#e8c8c0")], 7,
     ["spring", "fall"]),
    ("w-cardigan-long-1", "pexels", "6311379",
     "womens.tops.cardigan", "solid", [("cream", "#f0e6d2")], 5,
     ["fall", "winter", "spring"]),
    ("w-sneakers-pink-1", "pexels", "1102776",
     "womens.shoes.sneaker", "solid", [("pink", "#e8a8c0")], 3,
     ["spring", "summer", "fall"]),
    ("w-boots-knee-1", "pexels", "1124467",
     "womens.shoes.boot", "solid", [("black", "#1a1a1a")], 7,
     ["fall", "winter"]),
    ("w-heels-nude", "pexels", "1124468",
     "womens.shoes.heel", "solid", [("nude", "#d8b89a")], 7,
     ["spring", "summer", "fall"]),
    ("w-dress-bodycon-1", "pexels", "5704848",
     "womens.dresses.bodycon", "solid", [("black", "#1a1a1a")], 7,
     ["spring", "fall", "winter"]),
    ("w-jumpsuit-1", "pexels", "6311395",
     "womens.dresses.jumpsuit", "solid", [("olive", "#5a6a3a")], 6,
     ["spring", "summer", "fall"]),
]


def _deterministic_id(slug: str) -> uuid.UUID:
    """Stable UUID per slug so re-runs upsert instead of duplicating."""
    h = hashlib.sha1(f"seed-100:{slug}".encode()).digest()
    return uuid.UUID(bytes=h[:16], version=4)


async def _fetch(client: httpx.AsyncClient, source: str, photo_id: str) -> bytes | None:
    url = _img_url(source, photo_id)
    try:
        r = await client.get(url, follow_redirects=True, timeout=30.0)
        ct = r.headers.get("content-type", "")
        if r.status_code != 200 or not ct.startswith("image/"):
            return None
        if len(r.content) < 5000:  # rejected stub images
            return None
        return r.content
    except Exception:
        return None


async def _seed_one(
    db: object,
    storage: object,
    client: httpx.AsyncClient,
    user_id: uuid.UUID,
    entry: Entry,
) -> bool:
    slug, source, photo_id, category, pattern, color_pairs, formality, seasonality = entry
    item_id = _deterministic_id(slug)

    bytes_ = await _fetch(client, source, photo_id)
    if not bytes_:
        return False

    raw_key = f"raw/{user_id}/{item_id}.jpg"
    cutout_key = f"cutout/{user_id}/{item_id}.jpg"
    await storage.write_bytes(raw_key, bytes_)  # type: ignore[attr-defined]
    await storage.write_bytes(cutout_key, bytes_)  # type: ignore[attr-defined]

    item = WardrobeItem(
        id=item_id,
        owner_kind=OwnerKind.user,
        owner_id=user_id,
        raw_image_key=raw_key,
        cutout_image_key=cutout_key,
        thumbnail_key=cutout_key,
        category=category,
        colors=[
            ColorTag(name=n, hex=h, weight=1.0 / len(color_pairs))
            for n, h in color_pairs
        ],
        pattern=Pattern(pattern),
        formality=formality,
        seasonality=list(seasonality),
        embedding=[0.0] * 768,
        confidence_scores=ConfidenceScores(
            root={"category": 1.0, "pattern": 1.0, "color": 1.0}
        ),
        needs_review=False,
        status="ready",
    )
    db.add(item)  # type: ignore[attr-defined]
    return True


async def main(user_id: uuid.UUID, mens_target: int, womens_target: int) -> int:
    storage = get_storage()

    async with SessionLocal() as db:
        # Ensure user row exists.
        existing_user = (
            await db.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()
        if not existing_user:
            db.add(
                User(
                    id=user_id,
                    email=f"dev+{user_id}@virtual-stylist.local",
                    role=UserRole.guardian,
                    display_name="Seed User",
                )
            )
            await db.commit()

        # Wipe existing items (user explicitly asked for a clean reset).
        await db.execute(
            delete(WardrobeItem).where(
                WardrobeItem.owner_kind == OwnerKind.user,
                WardrobeItem.owner_id == user_id,
            )
        )
        await db.commit()
        print("Wiped existing wardrobe.")

        async with httpx.AsyncClient() as http:
            # Mens — keep going through the catalogue until we hit the target
            # or run out of candidates.
            mens_landed = 0
            mens_failed: list[str] = []
            for entry in MENS_CATALOGUE:
                if mens_landed >= mens_target:
                    break
                ok = await _seed_one(db, storage, http, user_id, entry)
                if ok:
                    mens_landed += 1
                    if mens_landed % 10 == 0:
                        await db.commit()
                        print(f"  mens: {mens_landed}/{mens_target}")
                else:
                    mens_failed.append(entry[0])
            await db.commit()

            womens_landed = 0
            womens_failed: list[str] = []
            for entry in WOMENS_CATALOGUE:
                if womens_landed >= womens_target:
                    break
                ok = await _seed_one(db, storage, http, user_id, entry)
                if ok:
                    womens_landed += 1
                    if womens_landed % 10 == 0:
                        await db.commit()
                        print(f"  womens: {womens_landed}/{womens_target}")
                else:
                    womens_failed.append(entry[0])
            await db.commit()

        print("")
        print(f"Mens landed:   {mens_landed} (target {mens_target})")
        if mens_failed:
            print(f"  failed slugs: {', '.join(mens_failed[:10])}")
        print(f"Womens landed: {womens_landed} (target {womens_target})")
        if womens_failed:
            print(f"  failed slugs: {', '.join(womens_failed[:10])}")

    return 0


def cli() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", type=str, default=str(AYMAN_UUID))
    parser.add_argument("--mens", type=int, default=50)
    parser.add_argument("--womens", type=int, default=50)
    args = parser.parse_args()
    return asyncio.run(main(uuid.UUID(args.user_id), args.mens, args.womens))


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    raise SystemExit(cli())
