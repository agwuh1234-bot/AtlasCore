# Atlas autonomy 0.1.0-lifecycle-gated

This checkpoint introduces the durable autonomous execution foundation needed for long-running work independent of individual chat turns. It is intentionally not marked production-ready yet: lifecycle wiring must pass branch CI, then the actual patched source must pass CI again, followed by Railway health, read-only browser canary, and restart-recovery validation.

No authenticated Shopify write automation should be enabled before those gates pass.