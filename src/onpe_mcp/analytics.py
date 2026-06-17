from __future__ import annotations

import copy
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"


_DATASET_TABLE = {
    "mesa": "fact_votos_mesa",
    "ubigeo": "fact_votos_ubigeo",
    "provincia": "fact_votos_provincia",
    "departamento": "fact_votos_departamento",
    "nacional": "fact_votos_nacional",
}

_OP_SQL = {
    "eq": "=",
    "ne": "!=",
    "lt": "<",
    "lte": "<=",
    "gt": ">",
    "gte": ">=",
    "like": "LIKE",
}

_DATASET_COLUMNS = {
    "mesa": {
        "election_year", "vuelta", "codigo_mesa", "ubigeo",
        "cod_provincia", "cod_departamento", "ambito",
        "departamento", "provincia", "distrito",
        "continente", "pais", "ciudad",
        "partido_id", "nombre_partido", "candidato",
        "es_especial", "votos", "electores_habiles",
        "votos_emitidos", "votos_validos", "blancos", "nulos",
        "impugnados", "estado_acta", "is_contabilizada", "mesa_num",
    },
    "ubigeo": {
        "election_year", "vuelta", "ubigeo", "departamento", "provincia", "distrito",
        "continente", "pais", "ciudad", "partido_id", "nombre_partido", "candidato",
        "es_especial", "votos", "electores_habiles", "votos_emitidos", "votos_validos",
        "blancos", "nulos", "impugnados", "pct_partido", "is_contabilizada", "mesas",
    },
    "provincia": {
        "election_year", "vuelta", "cod_departamento", "cod_provincia", "departamento",
        "provincia", "partido_id", "nombre_partido", "candidato", "es_especial", "votos",
        "electores_habiles", "votos_emitidos", "votos_validos", "blancos", "nulos",
        "impugnados", "pct_partido", "is_contabilizada", "mesas",
    },
    "departamento": {
        "election_year", "vuelta", "cod_departamento", "departamento", "partido_id",
        "nombre_partido", "candidato", "es_especial", "votos", "electores_habiles",
        "votos_emitidos", "votos_validos", "blancos", "nulos", "impugnados",
        "pct_partido", "is_contabilizada", "mesas",
    },
    "nacional": {
        "election_year", "vuelta", "partido_id", "nombre_partido", "candidato",
        "es_especial", "votos", "electores_habiles", "votos_emitidos", "votos_validos",
        "blancos", "nulos", "impugnados", "pct_partido", "is_contabilizada", "mesas",
    },
}

_PRESET_QUERIES: dict[str, dict[str, Any]] = {
    "900k_segunda_vuelta_resumen": {
        "dataset": "mesa",
        "election_year": 2026,
        "vuelta": 2,
        "select": [
            "codigo_mesa", "departamento", "provincia", "distrito",
            "partido_id", "nombre_partido", "candidato",
            "votos", "votos_validos", "is_contabilizada",
        ],
        "where": [{"field": "codigo_mesa", "op": "like", "value": "9%"}],
        "order_by": [{"field": "votos_validos", "dir": "desc"}],
        "limit": 500,
        "offset": 0,
        "include_special": False,
        "count_only_contabilizadas": True,
    },
    "audit_estado_E_vs_C": {
        "dataset": "mesa",
        "election_year": 2026,
        "vuelta": 2,
        "select": [
            "codigo_mesa", "departamento", "provincia", "distrito",
            "estado_acta", "is_contabilizada", "votos_emitidos", "votos_validos",
        ],
        "order_by": [{"field": "codigo_mesa", "dir": "asc"}],
        "limit": 1000,
        "offset": 0,
        "include_special": True,
        "count_only_contabilizadas": False,
    },
}

_FIELD_ALIASES = {
    "codigo_estado_acta": "estado_acta",
    "contabilizada": "is_contabilizada",
    "es_contabilizada": "is_contabilizada",
}


def _parse_bool(value: Any, *, field_name: str, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    raise ValueError(f"{field_name} debe ser booleano")


@dataclass
class QuerySpec:
    dataset: str
    election_year: int
    vuelta: int
    select: list[str]
    where: list[dict[str, Any]]
    order_by: list[dict[str, str]]
    limit: int
    offset: int
    include_special: bool
    count_only_contabilizadas: bool

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "QuerySpec":
        dataset = str(payload.get("dataset", "mesa")).strip().lower()
        if dataset not in _DATASET_TABLE:
            raise ValueError(f"dataset inválido: {dataset}")

        election_year = int(payload.get("election_year", 2026))
        vuelta = int(payload.get("vuelta", 2))
        if election_year not in (2021, 2026):
            raise ValueError("election_year debe ser 2021 o 2026")
        if vuelta not in (1, 2):
            raise ValueError("vuelta debe ser 1 o 2")

        select = [str(s).strip() for s in payload.get("select", []) if str(s).strip()]
        if not select:
            select = ["partido_id", "nombre_partido", "candidato", "votos"]

        where = payload.get("where", []) or []
        if not isinstance(where, list):
            raise ValueError("where debe ser una lista")
        if any(not isinstance(cond, dict) for cond in where):
            raise ValueError("cada elemento de where debe ser un objeto")

        order_by = payload.get("order_by", []) or []
        if not isinstance(order_by, list):
            raise ValueError("order_by debe ser una lista")
        if any(not isinstance(item, dict) for item in order_by):
            raise ValueError("cada elemento de order_by debe ser un objeto")

        limit = max(1, min(int(payload.get("limit", 500)), 50_000))
        offset = max(0, int(payload.get("offset", 0)))
        include_special = _parse_bool(
            payload.get("include_special"),
            field_name="include_special",
            default=False,
        )
        count_only_contabilizadas = _parse_bool(
            payload.get("count_only_contabilizadas"),
            field_name="count_only_contabilizadas",
            default=True,
        )

        unsupported = [k for k in ("group_by", "having", "compare") if payload.get(k)]
        if unsupported:
            raise ValueError(
                f"features no soportadas aún: {', '.join(unsupported)}. "
                "Use selección + where + order_by + paginación."
            )

        return cls(
            dataset=dataset,
            election_year=election_year,
            vuelta=vuelta,
            select=select,
            where=where,
            order_by=order_by,
            limit=limit,
            offset=offset,
            include_special=include_special,
            count_only_contabilizadas=count_only_contabilizadas,
        )


class AnalyticsEngine:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._table_columns_cache: dict[str, set[str]] = {}

    def _connect(self) -> sqlite3.Connection:
        uri = f"file:{self.db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _table_columns(self, table: str) -> set[str]:
        if table in self._table_columns_cache:
            return self._table_columns_cache[table]
        with self._connect() as conn:
            cols = {
                str(r["name"])
                for r in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
        self._table_columns_cache[table] = cols
        return cols

    def _allowed_columns(self, dataset: str, table: str) -> set[str]:
        physical = self._table_columns(table)
        public = _DATASET_COLUMNS.get(dataset)
        if not public:
            return physical
        return set(public) & physical

    def _validate_columns(self, allowed: set[str], cols: list[str], table: str) -> None:
        invalid = [c for c in cols if c not in allowed]
        if invalid:
            raise ValueError(f"columnas no permitidas para {table}: {invalid}")

    def _compile_where(
        self,
        allowed: set[str],
        spec: QuerySpec,
    ) -> tuple[str, list[Any]]:
        parts = ["election_year = ?", "vuelta = ?"]
        params: list[Any] = [spec.election_year, spec.vuelta]

        if "es_especial" in allowed and not spec.include_special:
            parts.append("es_especial = 0")

        if "is_contabilizada" in allowed and spec.count_only_contabilizadas:
            parts.append("is_contabilizada = 1")

        for cond in spec.where:
            field = str(cond.get("field", "")).strip()
            op = str(cond.get("op", "")).strip().lower()
            value = cond.get("value")

            if field not in allowed:
                raise ValueError(f"field no permitido: {field}")

            if op == "between":
                if not isinstance(value, (list, tuple)) or len(value) != 2:
                    raise ValueError(f"between requiere [min,max] en field={field}")
                parts.append(f"{field} BETWEEN ? AND ?")
                params.extend([value[0], value[1]])
                continue

            if op == "in":
                if not isinstance(value, list) or not value:
                    raise ValueError(f"in requiere lista no vacía en field={field}")
                placeholders = ", ".join("?" for _ in value)
                parts.append(f"{field} IN ({placeholders})")
                params.extend(value)
                continue

            if op not in _OP_SQL:
                raise ValueError(f"op no soportado: {op}")

            parts.append(f"{field} {_OP_SQL[op]} ?")
            params.append(value)

        return " AND ".join(parts), params

    def apply_preset(self, payload: dict[str, Any]) -> dict[str, Any]:
        preset_name = str(payload.get("preset", "") or "").strip()
        if not preset_name:
            return payload
        preset_query = _PRESET_QUERIES.get(preset_name)
        if preset_query is None:
            raise ValueError(f"preset no soportado: {preset_name}")
        merged = copy.deepcopy(preset_query)
        for key, value in payload.items():
            if key == "preset":
                continue
            merged[key] = value
        merged["preset"] = preset_name
        return merged

    def available_datasets(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for dataset, table in _DATASET_TABLE.items():
            out[dataset] = sorted(self._allowed_columns(dataset, table))
        return out

    def available_presets(self) -> list[str]:
        return sorted(_PRESET_QUERIES.keys())

    def available_field_aliases(self) -> dict[str, str]:
        return dict(_FIELD_ALIASES)

    def _apply_field_aliases(self, payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
        normalized = copy.deepcopy(payload or {})
        applied: list[dict[str, str]] = []

        def _alias(field_name: str) -> str:
            canonical = _FIELD_ALIASES.get(field_name, field_name)
            if canonical != field_name:
                applied.append({"from": field_name, "to": canonical})
            return canonical

        raw_select = normalized.get("select")
        if isinstance(raw_select, list):
            select_alias = [_alias(str(c).strip()) for c in raw_select]
            dedup_select: list[str] = []
            seen_select: set[str] = set()
            for col in select_alias:
                if col in seen_select:
                    continue
                seen_select.add(col)
                dedup_select.append(col)
            normalized["select"] = dedup_select

        raw_where = normalized.get("where")
        if isinstance(raw_where, list):
            new_where: list[dict[str, Any]] = []
            for cond in raw_where:
                if isinstance(cond, dict):
                    cond_norm = dict(cond)
                    cond_norm["field"] = _alias(str(cond_norm.get("field", "")).strip())
                    new_where.append(cond_norm)
                else:
                    new_where.append(cond)
            normalized["where"] = new_where

        raw_order = normalized.get("order_by")
        if isinstance(raw_order, list):
            new_order: list[dict[str, Any]] = []
            for item in raw_order:
                if isinstance(item, dict):
                    item_norm = dict(item)
                    item_norm["field"] = _alias(str(item_norm.get("field", "")).strip())
                    new_order.append(item_norm)
                else:
                    new_order.append(item)
            normalized["order_by"] = new_order

        dedup: dict[tuple[str, str], dict[str, str]] = {}
        for item in applied:
            dedup[(item["from"], item["to"])] = item
        return normalized, list(dedup.values())

    def query(self, payload: dict[str, Any]) -> dict[str, Any]:
        effective_payload = self.apply_preset(payload or {})
        effective_payload, field_aliases_applied = self._apply_field_aliases(effective_payload)
        spec = QuerySpec.from_dict(effective_payload)
        table = _DATASET_TABLE[spec.dataset]
        allowed = self._allowed_columns(spec.dataset, table)

        self._validate_columns(allowed, spec.select, table)
        where_sql, params = self._compile_where(allowed, spec)

        order_sql = ""
        if spec.order_by:
            pieces: list[str] = []
            for it in spec.order_by:
                field = str(it.get("field", "")).strip()
                direction = str(it.get("dir", "asc")).strip().lower()
                if field not in allowed:
                    raise ValueError(f"order_by.field no permitido: {field}")
                if direction not in ("asc", "desc"):
                    raise ValueError(f"order_by.dir inválido: {direction}")
                pieces.append(f"{field} {direction.upper()}")
            order_sql = " ORDER BY " + ", ".join(pieces)

        select_sql = ", ".join(spec.select)
        base_sql = f" FROM {table} WHERE {where_sql}"
        rows_sql = f"SELECT {select_sql}{base_sql}{order_sql} LIMIT ? OFFSET ?"
        count_sql = f"SELECT COUNT(*) AS c{base_sql}"

        with self._connect() as conn:
            total = int(conn.execute(count_sql, params).fetchone()["c"])
            rows = [
                dict(r)
                for r in conn.execute(rows_sql, [*params, spec.limit, spec.offset]).fetchall()
            ]

        returned = len(rows)
        return {
            "rows": rows,
            "total": total,
            "returned": returned,
            "offset": spec.offset,
            "limit": spec.limit,
            "has_more": (spec.offset + returned) < total,
            "query_echo": {
                "dataset": spec.dataset,
                "election_year": spec.election_year,
                "vuelta": spec.vuelta,
                "select": spec.select,
                "where": spec.where,
                "order_by": spec.order_by,
                "include_special": spec.include_special,
                "count_only_contabilizadas": spec.count_only_contabilizadas,
                "preset": effective_payload.get("preset"),
            },
            "sql_explain": rows_sql,
            "data_tier": "tier_1_denorm",
            "schema_version": SCHEMA_VERSION,
            "field_aliases_applied": field_aliases_applied,
        }

    def search_entities(
        self,
        *,
        query: str,
        field: str = "any",
        election_year: int = 2026,
        vuelta: int = 2,
        limit: int = 20,
    ) -> dict[str, Any]:
        term = str(query or "").strip()
        if len(term) < 2:
            raise ValueError("query debe tener al menos 2 caracteres")
        field_norm = str(field or "any").strip().lower()
        allowed_fields = {"any", "departamento", "provincia", "distrito", "pais", "ciudad", "partido", "candidato"}
        if field_norm not in allowed_fields:
            raise ValueError(f"field inválido: {field}")
        limit_n = max(1, min(int(limit), 100))
        target_types = (
            [field_norm]
            if field_norm != "any"
            else ["departamento", "provincia", "distrito", "pais", "ciudad", "partido", "candidato"]
        )
        type_column = {
            "departamento": "departamento",
            "provincia": "provincia",
            "distrito": "distrito",
            "pais": "pais",
            "ciudad": "ciudad",
            "partido": "nombre_partido",
            "candidato": "candidato",
        }
        matches: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        per_type_limit = max(1, min(25, limit_n))
        with self._connect() as conn:
            for entity_type in target_types:
                col = type_column[entity_type]
                sql = f"""
                    SELECT DISTINCT {col} AS value
                    FROM fact_votos_mesa
                    WHERE election_year = ?
                      AND vuelta = ?
                      AND COALESCE({col}, '') != ''
                      AND UPPER({col}) LIKE UPPER(?)
                    ORDER BY value
                    LIMIT ?
                """
                rows = conn.execute(sql, (int(election_year), int(vuelta), f"%{term}%", per_type_limit)).fetchall()
                for row in rows:
                    value = str(row["value"] or "").strip()
                    if not value:
                        continue
                    key = (entity_type, value.casefold())
                    if key in seen:
                        continue
                    seen.add(key)
                    matches.append(
                        {
                            "type": entity_type,
                            "canonical_name": value,
                            "usable_in": ["db_query", "onpe_query"],
                        }
                    )
                    if len(matches) >= limit_n:
                        return {"query": term, "matches": matches, "returned": len(matches)}
        return {"query": term, "matches": matches, "returned": len(matches)}

    def filter_mesas(
        self,
        *,
        election_year: int,
        vuelta: int,
        partido: str,
        votos_op: str,
        votos_value: int | list[int],
        solo_escrutadas: bool,
        mesa_prefix: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        party = str(partido or "").strip()
        if not party:
            raise ValueError("partido no puede estar vacío")

        party_id: str
        if party.isdigit():
            party_id = party
        else:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT partido_id
                    FROM fact_votos_mesa
                    WHERE election_year = ? AND vuelta = ?
                      AND (
                        lower(nombre_partido) LIKE lower(?)
                        OR lower(candidato) LIKE lower(?)
                      )
                    ORDER BY votos DESC
                    LIMIT 1
                    """,
                    (election_year, vuelta, f"%{party}%", f"%{party}%"),
                ).fetchone()
            if not row:
                raise ValueError(f"partido no encontrado: {partido}")
            party_id = str(row["partido_id"])

        where: list[dict[str, Any]] = [{"field": "partido_id", "op": "eq", "value": party_id}]
        where.append({"field": "votos", "op": votos_op, "value": votos_value})
        if mesa_prefix:
            where.append({"field": "codigo_mesa", "op": "like", "value": f"{mesa_prefix}%"})

        return self.query(
            {
                "dataset": "mesa",
                "election_year": election_year,
                "vuelta": vuelta,
                "select": [
                    "codigo_mesa",
                    "departamento",
                    "provincia",
                    "distrito",
                    "partido_id",
                    "nombre_partido",
                    "candidato",
                    "votos",
                    "votos_validos",
                    "electores_habiles",
                    "votos_emitidos",
                    "is_contabilizada",
                ],
                "where": where,
                "order_by": [{"field": "votos_validos", "dir": "desc"}],
                "limit": limit,
                "offset": offset,
                "include_special": False,
                "count_only_contabilizadas": solo_escrutadas,
            }
        )
