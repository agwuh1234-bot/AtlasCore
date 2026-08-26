# Atlas Ecommerce Orchestrator Skill

Purpose: coordinate Shopify + n8n + AI into one ecommerce execution loop.

## Core loop
Goal -> inspect Shopify -> plan -> build/update n8n workflow -> generate store assets/config -> validate -> request approval where required -> execute -> verify -> record result.

## First-store MVP
For a one-product test store:
1. Product brief and positioning.
2. Product draft with title, description, price, media and SEO.
3. Homepage/product-page structure optimized for mobile.
4. Trust, FAQ, shipping/returns and CTA sections.
5. Collection/navigation setup where useful.
6. End-to-end link and checkout-path validation.
7. Keep storefront unpublished until review.

## Autonomy policy
Atlas may autonomously inspect, analyze, draft, create test workflows and perform reversible non-destructive changes. Publishing, deletion, irreversible changes and sensitive customer/order actions require explicit approval.
