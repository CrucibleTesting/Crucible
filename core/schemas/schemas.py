GOLDEN_SCHEMA = {
    "type": "object",
    "properties": {
        "meta": {
            "type": "object",
            "properties": {
                "state": {"type": "string", "enum": ["golden"]},
                "promoted_at": {"type": "string"},
                "resolver": {"type": "string"},
                "sut_version": {"type": "string"},
            },
            "additionalProperties": True,
        },
        "cases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "input": {"type": "string"},
                    # "expected": {"type": ["object", "null"]},
                    "expected": {},
                    "meta": {
                        "type": "object",
                        "properties": {
                            "state": {"type": "string", "enum": ["golden"]},
                            "promoted_at": {"type": "string"},
                            "resolver": {"type": "string"},
                            "sut_version": {"type": "string"},
                            "cluster_id": {"type": "string"},
                        },
                        "additionalProperties": True,
                    },
                },
                "required": ["id", "input", "expected"],
            },
        },
    },
    "required": ["cases"],
}


STAGING_SCHEMA = {
    "type": "object",
    "properties": {
        "meta": {
            "type": "object",
            "properties": {
                "generated_at": {"type": "string"},
                "sut_version": {"type": "string"},
                "resolver": {"type": "string"},
            },
            "additionalProperties": True,
        },
        "cases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "input": {"type": "string"},
                    "snapshot": {"type": "object"},
                    "meta": {
                        "type": "object",
                        "properties": {
                            "sut_version": {"type": "string"},
                            "state": {
                                "type": "string",
                                "enum": ["pending", "accepted", "rejected"],
                            },
                            "cluster_id": {"type": "string"},
                            "cluster_label": {"type": "string"},
                            "is_quarantine_cluster": {"type": "boolean"},
                        },
                        "additionalProperties": True,
                    },
                },
                "required": ["id", "input", "snapshot"],
            },
        },
    },
    "required": ["cases"],
}
