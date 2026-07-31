# --- V4 ENHANCEMENT NOTES ---
# Hybrid Similarity Mode (v4):
#   - Add config flag to enable hybrid similarity for arrays/identity.
# --------------------------------

from __future__ import annotations

from typing import Any, Dict, List

from .types import NormalisedSnapshot
from .semantic_root import resolve_semantic_roots
from .blocklist import remove_blocklisted_fields
from .meta_ignore import strip_meta
from .array_canonicaliser import canonicalise_array
from .structural_signature import structural_signature
from .truncation import truncate_snapshot
# from .noise_detector import NoiseDetector
# from .drift_detector import DriftDetector
from .identity_builder import build_root_identity, fuse_identities


class Normaliser:
    """
    v3.3 Semantic Normaliser

    Responsibilities:
      - semantic root resolution (Strict Single-Root Anchor Fix)
      - blocklist + nested meta stripping (identity only)
      - dynamic noise (committed, versioned)
      - canonical array handling
      - structural signatures bound to static key templates
      - identity hashing stability across config adjustments
      - pre-diff truncation
    """

    def __init__(
        self,
        semantic_roots: List[str] | None = None,
        adapter_id: str | None = None,
    ):
        self.semantic_roots = semantic_roots or []
        self.adapter_id = adapter_id or "default_adapter"

    def normalise(self, raw: Dict[str, Any]) -> NormalisedSnapshot:
        """
        Main entrypoint for normalisation.
        """

        # 1. Resolve semantic roots
        roots, root_meta = resolve_semantic_roots(
            adapter_id=self.adapter_id,
            adapter_fn=lambda _: raw,
            raw=raw,
            declared_roots=self.semantic_roots or None,
        )

        # 2. Build identities utilizing static layout wrapping to ensure hash stability
        per_root_identities: Dict[str, Dict[str, Any]] = {}
        root_struct_sigs: Dict[str, str] = {}

        if not roots:
            # Fallback placeholder to anchor the layout structure if no roots are resolved
            per_root_identities["root"] = build_root_identity(
                root_value={},
                struct_sig="EMPTY_FALLBACK",
            )
            root_struct_sigs["root"] = "EMPTY_FALLBACK"
        else:
            # Crucible v3.3 enforces exactly one semantic root block per adapter workspace.
            # We take the first active root segment, extract the payload behavior, and bind
            # it to a static "root" key template to decouple the configuration name from the hash.
            active_path = list(roots.keys())[0]
            value = roots[active_path]

            # Compute structural footprint
            struct_sig = structural_signature(value)
            root_struct_sigs["root"] = struct_sig

            # Clean identity payload
            cleaned = value
            if isinstance(cleaned, dict):
                cleaned = remove_blocklisted_fields(cleaned)
                cleaned = strip_meta(cleaned)

                # Apply committed noise filter at top-level
                # cleaned = self.noise_detector.filter_committed_noise(cleaned)

                # Canonicalise arrays inside this root for identity
                cleaned = self._canonicalise_arrays_for_identity(cleaned)

            # Map to a hardcoded string key to block configuration string pollution inside fuse_identities
            per_root_identities["root"] = build_root_identity(
                root_value=cleaned,
                struct_sig=struct_sig,
            )

        # 3. Fused identity (cluster key)
        fused_identity = fuse_identities(per_root_identities)

        # 4. Pre-diff truncation
        canonical_snapshot, truncated_fields = truncate_snapshot(raw)

        # 5. Meta
        meta: Dict[str, Any] = {
            "semantic_roots": roots,
            "root_struct_signatures": root_struct_sigs,
            # "noise_version": self.noise_detector.noise_version,
            "truncated_fields": truncated_fields,
            "ranked_candidates": root_meta.get("ranked_candidates"),
            "learned_root": root_meta.get("learned_root"),
            "learning_failures": root_meta.get("failures"),
        }

        return NormalisedSnapshot(
            canonical=canonical_snapshot,
            identity=fused_identity,
            # drift=drifted,
            # quarantine=quarantined,
            meta=meta,
        )

    def _canonicalise_arrays_for_identity(self, obj: Any) -> Any:
        """
        Recursively canonicalise arrays for identity purposes:
          - for lists of dicts/scalars, use canonicalise_array
          - for nested dicts, recurse
        """
        if isinstance(obj, dict):
            out: Dict[str, Any] = {}
            for k, v in obj.items():
                out[k] = self._canonicalise_arrays_for_identity(v)
            return out

        if isinstance(obj, list):
            # If it's a list of simple/structured elements, canonicalise
            return canonicalise_array(obj)

        return obj