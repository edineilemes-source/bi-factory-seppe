"""Pure helpers for deterministic Business Context fingerprinting."""

import hashlib
import json

from core.business.models import BusinessContext


def business_context_fingerprint(context: BusinessContext) -> str:
    """Hash semantic content and lineage, excluding persistence metadata."""
    payload = context.model_dump(
        mode="json",
        exclude={
            "business_context_id",
            "version",
            "fingerprint",
            "created_at",
            "updated_at",
        },
    )
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
