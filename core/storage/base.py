from __future__ import annotations
import os
import hashlib
import secrets
import logging
import importlib
from pathlib import Path
from typing import Any, Optional, Dict, List, Callable
from concurrent.futures import ThreadPoolExecutor
import msgspec.json as mjson
from crucible.core.clustering.store import ClusterStore
from crucible.core.clustering.engine import ClusteringEngine
from crucible.core.normalisation.normaliser import Normaliser
from crucible.core.normalisation.semantic_root import _get_subtree
from crucible.core.semantic_root_engine.paths import normalize_jsonpath
from crucible.core.semantic_root_engine.developer_declared import get_declared_semantic_root
from crucible.core.config.sut_meta import get_sut_version
from crucible.core.storage.config import Config

logger = logging.getLogger("crucible.storage")

class LocalStorage:
    """
    Unified, filesystem-backed storage for Crucible.
    Handles Bronze (candidate pool), Silver (staging snapshots), and Gold (fixtures) layers.
    """
    def __init__(self, component_name: str) -> None:
        # Guarantee lowercase hyphenated directory resolution (e.g., premises-parser)
        clean_name = component_name.lower().replace("_", "-")
        self.component_name = clean_name
        self.resolver = clean_name
        self._sut: Optional[Any] = None

        env_root = os.getenv("CRUCIBLE_ROOT")
        if env_root:
            self.root = Path(env_root).resolve()
        else:
            self.root = Path(os.getcwd()).resolve() / ".crucible"

        base = self.root / "suites" / clean_name

        # Case-insensitive directory matching fallback for Linux / WSL
        silver_base = base / "Silver" if (base / "Silver").exists() else base / "silver"
        gold_base = base / "Gold" if (base / "Gold").exists() else base / "gold"
        bronze_base = base / "Bronze" if (base / "Bronze").exists() else base / "bronze"

        self.gold_path = gold_base / "fixtures.json"
        self.classes_path = gold_base / "classes.json"
        self.staging_path = silver_base / "snapshots.json"
        self.snapshot_cache_path = silver_base / "snapshot_cache.json"
        self.candidate_pool_path = bronze_base / "candidate_pool.txt"
        self.silver_path = self.staging_path
        self.golden_path = self.gold_path

        bronze_base.mkdir(parents=True, exist_ok=True)
        silver_base.mkdir(parents=True, exist_ok=True)
        gold_base.mkdir(parents=True, exist_ok=True)

        if not self.candidate_pool_path.exists():
            self._safe_write_bytes(self.candidate_pool_path, b"")

        if not self.classes_path.exists():
            self._safe_write_bytes(self.classes_path, b'{"classes": {}}\n')

        self.cluster_store = ClusterStore()
        self.clustering_engine = ClusteringEngine(self.cluster_store)

    def _safe_write_bytes(self, path: Path, content: bytes) -> None:
        rand_token = secrets.token_hex(4)
        tmp_path = path.with_suffix(f".{rand_token}.tmp")
        try:
            tmp_path.write_bytes(content)
            os.replace(tmp_path, path)
        except Exception as e:
            if tmp_path.exists():
                tmp_path.unlink()
            raise e

    def get_active_semantic_roots(self) -> List[str]:
        try:
            module_name, _, _ = self.resolver.partition(":")
            mod = importlib.import_module(module_name)
            declared = get_declared_semantic_root(mod)
            if declared:
                return [declared]
        except Exception:
            pass
        return getattr(self, "active_roots", ["meta"])

    def clear_all(self) -> None:
        self._safe_write_bytes(self.staging_path, b'{"meta": {}, "cases": []}\n')
        self._safe_write_bytes(self.gold_path, b'{"meta": {}, "cases": []}\n')
        self._safe_write_bytes(self.classes_path, b'{"classes": {}}\n')
        self._safe_write_bytes(self.candidate_pool_path, b"")
        if self.snapshot_cache_path.exists():
            self.snapshot_cache_path.unlink()

    def read_candidate_pool(self) -> List[str]:
        if not self.candidate_pool_path.exists():
            return []
        try:
            content = self.candidate_pool_path.read_text(encoding="utf-8", errors="replace")
            return content.splitlines()
        except Exception:
            return []

    def sync_and_dedupe_candidate_pool(self) -> Dict[str, int]:
        raw_lines = self.read_candidate_pool()
        cleaned = []
        for line in raw_lines:
            stripped = line.strip().strip("\u200b\ufeff")
            if stripped:
                cleaned.append(stripped)
        unique_lines = list(dict.fromkeys(cleaned))
        self.write_candidate_pool(unique_lines)
        return {
            "total_raw": len(raw_lines),
            "unique_count": len(unique_lines),
            "removed_duplicates": len(cleaned) - len(unique_lines),
            "empty_lines_purged": len(raw_lines) - len(cleaned),
        }

    def write_candidate_pool(self, lines: List[str]) -> None:
        content = "\n".join(lines) + ("\n" if lines else "")
        self._safe_write_bytes(self.candidate_pool_path, content.encode("utf-8"))

    def append_candidate(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        lines = self.read_candidate_pool()
        lines.append(line)
        self.write_candidate_pool(lines)

    def clear_candidate_pool(self) -> None:
        self.write_candidate_pool([])

    def validate_and_stage_bronze_upload(self, incoming_lines: List[str]) -> Dict[str, Any]:
        existing_pool = set(self.read_candidate_pool())
        GLOBAL_MAX_LIMIT = 1000
        new_unique_lines = [
            line.strip() for line in incoming_lines if line.strip() and line.strip() not in existing_pool
        ]
        current_count = len(existing_pool)
        remaining_capacity = max(0, GLOBAL_MAX_LIMIT - current_count)
        allowed_to_import = new_unique_lines[:remaining_capacity]
        return {
            "detected": len(incoming_lines),
            "duplicates_removed": len(incoming_lines) - len(new_unique_lines),
            "new_unique": len(new_unique_lines),
            "remaining_capacity": remaining_capacity,
            "allowed_to_import": allowed_to_import,
        }

    def load_staging(self) -> Dict[str, Any]:
        if not self.silver_path.exists():
            return {"meta": {}, "cases": []}
        raw = self.silver_path.read_bytes()
        if not raw.strip():
            return {"meta": {}, "cases": []}
        return mjson.decode(raw, type=dict)

    def _write_staging(self, data: Dict[str, Any]) -> None:
        # self._safe_write_bytes(self.silver_path, mjson.encode(data) + b"\n")
        packed_bytes = mjson.encode(data)
        pretty_bytes = mjson.format(packed_bytes, indent=2)
        self._safe_write_bytes(self.silver_path, pretty_bytes + b"\n")


    def _load_snapshot_cache(self) -> Dict[str, Any]:
        if not self.snapshot_cache_path.exists():
            return {"sut_version": None, "command_signature": None, "entries": {}}
        try:
            raw_bytes = self.snapshot_cache_path.read_bytes()
            if not raw_bytes.strip():
                return {"sut_version": None, "command_signature": None, "entries": {}}
            data = mjson.decode(raw_bytes)
            return {
                "sut_version": data.get("sut_version"),
                "command_signature": data.get("command_signature"),
                "entries": data.get("entries") or {},
            }
        except Exception as e:
            logger.error(f"Failed to read snapshot cache via msgspec: {e}")
            return {"sut_version": None, "command_signature": None, "entries": {}}

    def _write_snapshot_cache(
        self, cache: Dict[str, Any], cached_sut_version: str, command_signature: str
    ) -> None:
        cache["sut_version"] = cached_sut_version
        cache["command_signature"] = command_signature
        try:
            raw_bytes = mjson.encode(cache)
            self._safe_write_bytes(self.snapshot_cache_path, raw_bytes)
        except Exception as e:
            logger.error(f"Failed to write snapshot cache securely via msgspec: {e}")

    def get_snapshot(self, cluster_id: Any) -> Optional[Any]:
        data = self.load_staging()
        for case in data.get("cases", []):
            meta = case.get("meta", {})
            if meta.get("cluster_id") == cluster_id:
                return case.get("snapshot")
        return None

    def get_hydrated_case_data(self, case_dict: dict, sut_adapter: Optional[Callable]) -> dict:
        input_str = case_dict.get("input", "")
        cache = self._load_snapshot_cache()
        entries = cache.get("entries", {})
        if input_str in entries:
            live_output = entries[input_str]
        elif sut_adapter:
            live_output = sut_adapter(input_str) or {}
        else:
            live_output = {}
        return {
            "case_id": case_dict.get("id"),
            "raw_input": input_str,
            "live_output": live_output,
            "tokens": live_output.get("original_tokens", []),
        }

    def generate_snapshots(self, sut: Callable[[str], Any], component_config: dict) -> None:
        logger.info("============================================================")
        logger.info("SILVER LAYER GENERATION START (DECOUPLED ALIGNMENT MODE)")
        cached_sut_version = get_sut_version(component_config)
        cmd_str = component_config.get("command", "")
        cmd_sig = hashlib.sha1(cmd_str.encode()).hexdigest()[:8]
        lines = self.read_candidate_pool()
        golden = self.load_golden()
        golden_cases = golden.get("cases", [])
        staging = self.load_staging()
        existing_cases = {c["id"]: c for c in staging.get("cases", [])}
        unique_inputs: Dict[str, str] = {}
        for input_str in lines:
            cid = Config.make_id(input_str)
            unique_inputs[cid] = input_str
        for g in golden_cases:
            unique_inputs[g["id"]] = g["input"]

        MAX_FREE_CASES = 1000
        if len(unique_inputs) > MAX_FREE_CASES:
            logger.warning(f"⚠️ Free Tier Limit Exceeded: Truncating to {MAX_FREE_CASES} cases.")
            unique_inputs = dict(list(unique_inputs.items())[:MAX_FREE_CASES])

        cache = self._load_snapshot_cache()
        if (
            cache.get("sut_version") != cached_sut_version
            or cache.get("command_signature") != cmd_sig
        ):
            logger.info("🔄 SUT Version or Command config change detected. Invalidating snapshot cache.")
            cache["entries"] = {}

        cache_entries = cache["entries"]
        roots = self.get_active_semantic_roots()
        target_root = normalize_jsonpath(roots[0]) if roots else ""
        normaliser = Normaliser(semantic_roots=roots, adapter_id=self.resolver)
        clustering_engine = self.clustering_engine

        raw_payloads: Dict[str, dict] = {}
        pending_inputs = []
        for cid, input_str in unique_inputs.items():
            if input_str in cache_entries:
                raw_payloads[cid] = cache_entries[input_str]
            else:
                pending_inputs.append((cid, input_str))

        if pending_inputs:
            logger.info(f"Computing {len(pending_inputs)} raw payloads via ThreadPoolExecutor.")
            def _fetch_payload(pair: tuple[str, str]) -> tuple[str, str, dict]:
                c_id, inp_str = pair
                try:
                    res = sut(inp_str)
                    return c_id, inp_str, (res if res is not None else {})
                except Exception as ex:
                    return c_id, inp_str, {
                        "__error__": True,
                        "type": "UNHANDLED_EXCEPTION",
                        "reason": str(ex),
                    }

            max_workers = min(4, os.cpu_count() or 1)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for c_id, inp_str, payload in executor.map(_fetch_payload, pending_inputs):
                    raw_payloads[c_id] = payload
                    if not (isinstance(payload, dict) and payload.get("__error__")):
                        cache_entries[inp_str] = payload

        final_cases = []
        for cid, input_str in unique_inputs.items():
            raw_payload = raw_payloads[cid]
            if isinstance(raw_payload, dict) and raw_payload.get("__error__"):
                error_type = raw_payload.get("type", "UNKNOWN_EXECUTION_FAILURE")
                final_cases.append({
                    "id": cid,
                    "input": input_str,
                    "snapshot": {
                        "CRITICAL_SUT_ERROR": error_type,
                        "details": raw_payload.get("reason" if "reason" in raw_payload else "stderr", ""),
                    },
                    "meta": {
                        "sut_version": cached_sut_version,
                        "state": "error",
                        "class": "CRASHED_EXECUTION",
                        "signature": f"CRASH-{error_type}",
                    },
                })
                continue

            entries_block = raw_payload.get("entries", {})
            address_node = entries_block.get(input_str, raw_payload)
            norm_snap = normaliser.normalise(address_node)
            deterministic_sig = norm_snap.identity

            visual_snapshot = raw_payload
            try:
                if isinstance(address_node, dict) and target_root:
                    clean_path = target_root.replace("$.", "")
                    resolved_sub = _get_subtree(address_node, clean_path)
                    if resolved_sub != address_node:
                        visual_snapshot = resolved_sub
                    else:
                        leaf_key = clean_path.split(".")[-1]
                        if leaf_key in address_node:
                            visual_snapshot = address_node[leaf_key]
                        elif clean_path in address_node:
                            visual_snapshot = address_node[clean_path]
                        elif isinstance(address_node, dict):
                            visual_snapshot = address_node
            except Exception as e:
                logger.warning(f"Failed targeted schema projection for {input_str}: {e}")

            assignment = clustering_engine.assign_snapshot(norm_snap, adapter_id=self.resolver)
            prev_state = existing_cases.get(cid, {}).get("meta", {}).get("state", "pending")
            prev_class = existing_cases.get(cid, {}).get("meta", {}).get("class", None)

            final_cases.append({
                "id": cid,
                "input": input_str,
                "snapshot": visual_snapshot,
                "meta": {
                    "sut_version": cached_sut_version,
                    "state": prev_state,
                    "class": prev_class,
                    "signature": deterministic_sig,
                    "cluster_id": assignment.cluster_id,
                },
            })

        output_payload = {
            "meta": {
                "generated_at": Config.now(),
                "sut_version": cached_sut_version,
                "resolver": self.resolver,
            },
            "cases": final_cases,
        }

        self._realign_staging_with_gold(output_payload, golden)
        packed_bytes = mjson.encode(output_payload)
        pretty_bytes = mjson.format(packed_bytes, indent=2)
        self._safe_write_bytes(self.silver_path, pretty_bytes + b"\n")
        self._write_snapshot_cache(cache, cached_sut_version, cmd_sig)
        logger.info("SILVER LAYER (SNAPSHOTS.JSON) COHERENTLY ALIGNED WITH GOLD")

    def _realign_staging_with_gold(self, staging_payload: dict, golden_payload: dict) -> None:
        gold_by_cluster = {}
        for g in golden_payload.get("cases", []):
            cid = g.get("meta", {}).get("cluster_id")
            if cid:
                gold_by_cluster[cid] = g

        for case in staging_payload.get("cases", []):
            if case["meta"].get("state") == "error":
                continue

            cluster_id = case["meta"].get("cluster_id")
            if cluster_id in gold_by_cluster:
                gold_case = gold_by_cluster[cluster_id]
                if case["meta"]["signature"] == gold_case["meta"].get("signature"):
                    case["meta"]["state"] = "accepted"
                    case["meta"]["class"] = gold_case["meta"].get("class")
                    case["meta"]["semantic_drift"] = False
                else:
                    case["meta"]["state"] = "pending"
                    case["meta"]["class"] = None
                    case["meta"]["semantic_drift"] = True
            else:
                case["meta"]["state"] = "pending"
                case["meta"]["class"] = None
                case["meta"]["semantic_drift"] = False

    def load_golden(self) -> Dict[str, Any]:
        if not self.gold_path.exists():
            return {"meta": {}, "cases": []}
        raw = self.gold_path.read_bytes()
        if not raw.strip():
            return {"meta": {}, "cases": []}
        return mjson.decode(raw, type=dict)

    def _write_golden(self, data: Dict[str, Any]) -> None:
        # self._safe_write_bytes(self.gold_path, mjson.encode(data) + b"\n")
        packed_bytes = mjson.encode(data)
        pretty_bytes = mjson.format(packed_bytes, indent=2)
        self._safe_write_bytes(self.gold_path, pretty_bytes + b"\n")
        
    def load_classes(self) -> Dict[str, Any]:
        if not self.classes_path.exists():
            return {"classes": {}}
        raw = self.classes_path.read_bytes()
        if not raw.strip():
            return {"classes": {}}
        return mjson.decode(raw, type=dict)

    def write_classes(self, data: Dict[str, Any]) -> None:
        # self._safe_write_bytes(self.classes_path, mjson.encode(data) + b"\n")
        packed_bytes = mjson.encode(data)
        pretty_bytes = mjson.format(packed_bytes, indent=2)
        self._safe_write_bytes(self.classes_path, pretty_bytes + b"\n")

    def bulk_approve(self, case_ids: List[str], component_config: Optional[dict] = None) -> None:
        if not case_ids:
            return
        staging = self.load_staging()
        staging_by_id = {c["id"]: c for c in staging.get("cases", [])}
        sut_ver = get_sut_version(component_config) if component_config else "UNKNOWN_SUT_VERSION"
        for cid in case_ids:
            case = staging_by_id.get(cid)
            if not case:
                continue
            meta = case.setdefault("meta", {})
            meta["state"] = "accepted"
            meta["sut_version"] = sut_ver
        self._write_staging(staging)

    def bulk_reject(self, case_ids: List[str], component_config: Optional[dict] = None) -> None:
        if not case_ids:
            return
        staging = self.load_staging()
        staging_by_id = {c["id"]: c for c in staging.get("cases", [])}
        sut_ver = get_sut_version(component_config) if component_config else "UNKNOWN_SUT_VERSION"
        for cid in case_ids:
            case = staging_by_id.get(cid)
            if not case:
                continue
            meta = case.setdefault("meta", {})
            meta["state"] = "rejected"
            meta["sut_version"] = sut_ver
        self._write_staging(staging)

    def mark_accepted(self, case_id: str, component_config: Optional[dict] = None) -> None:
        self.bulk_approve([case_id], component_config=component_config)

    def mark_rejected(self, case_id: str, component_config: Optional[dict] = None) -> None:
        self.bulk_reject([case_id], component_config=component_config)