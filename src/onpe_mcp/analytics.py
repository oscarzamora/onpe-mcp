from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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

        order_by = payload.get("order_by", []) or []
        if not isinstance(order_by, list):
            raise ValueError("order_by debe ser una lista")

        limit = max(1, min(int(payload.get("limit", 500)), 50_000))
        offset = max(0, int(payload.get("offset", 0)))
        include_special = bool(payload.get("include_special", False))
        count_only_contabilizadas = bool(payload.get("count_only_contabilizadas", True))

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

    def _validate_columns(self, table: str, cols: list[str]) -> None:
        allowed = self._table_columns(table)
        invalid = [c for c in cols if c not in allowed]
        if invalid:
            raise ValueError(f"columnas no permitidas para {table}: {invalid}")

    def _compile_where(
        self,
        table: str,
        spec: QuerySpec,
    ) -> tuple[str, list[Any]]:
        allowed = self._table_columns(table)
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

    def query(self, payload: dict[str, Any]) -> dict[str, Any]:
        spec = QuerySpec.from_dict(payload)
        table = _DATASET_TABLE[spec.dataset]

        self._validate_columns(table, spec.select)
        where_sql, params = self._compile_where(table, spec)

        order_sql = ""
        if spec.order_by:
            pieces: list[str] = []
            for it in spec.order_by:
                field = str(it.get("field", "")).strip()
                direction = str(it.get("dir", "asc")).strip().lower()
                if field not in self._table_columns(table):
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
            },
            "sql_explain": rows_sql,
            "data_tier": "tier_1_denorm",
        }

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
