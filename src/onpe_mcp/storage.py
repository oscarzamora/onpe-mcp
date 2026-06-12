from __future__ import annotations

import csv
import logging
import json
import sqlite3
import unicodedata
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


_logger = logging.getLogger("onpe_mcp.storage")


def _norm_text(text: str) -> str:
    base = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in base if not unicodedata.combining(ch)).casefold().strip()


# Mapa de nombres populares de ciudades peruanas → nombres administrativos oficiales en ubigeo_reniec.
# Clave: nombre normalizado (sin tildes, minúsculas). Valor: nombre de provincia o departamento.
_CITY_ALIASES: dict[str, str] = {
    # Ucayali
    "pucallpa": "coronel portillo",
    # Loreto
    "iquitos": "maynas",
    "yurimaguas": "alto amazonas",
    "nauta": "loreto",
    # San Martín
    "tarapoto": "san martin",
    "moyobamba": "moyobamba",
    # Madre de Dios
    "puerto maldonado": "tambopata",
    # Amazonas
    "chachapoyas": "chachapoyas",
    # La Libertad
    "trujillo": "trujillo",
    # Lambayeque
    "chiclayo": "chiclayo",
    "lambayeque": "lambayeque",
    # Piura
    "piura": "piura",
    "sullana": "sullana",
    "tumbes": "tumbes",
    # Ancash
    "chimbote": "santa",
    "huaraz": "huaraz",
    # Lima
    "lima": "lima",
    "callao": "callao",
    # Ica
    "ica": "ica",
    "nazca": "nazca",
    # Arequipa
    "arequipa": "arequipa",
    # Tacna
    "tacna": "tacna",
    # Puno
    "puno": "puno",
    "juliaca": "san roman",
    # Cusco
    "cusco": "cusco",
    "cuzco": "cusco",
    # Apurimac
    "abancay": "abancay",
    "andahuaylalas": "andahuaylas",
    # Ayacucho — «ayacucho» es nombre de departamento; se resuelve por lookup RENIEC departamental.
    # No se alias: «ayacucho» → «huamanga» porque perdería el resto de provincias del dept.
    "huamanga": "huamanga",
    # Huancavelica
    "huancavelica": "huancavelica",
    # Junin
    "huancayo": "huancayo",
    # Pasco
    "cerro de pasco": "pasco",
    # Huanuco
    "huanuco": "huanuco",
    # Cajamarca
    "cajamarca": "cajamarca",
    "jaen": "jaen",
    # Lima — distritos urbanos frecuentes
    "la victoria": "la victoria",
    "buenos aires": "buenos aires",
    "miraflores": "miraflores",
    "san isidro": "san isidro",
    "lince": "lince",
    "barranco": "barranco",
    "surco": "santiago de surco",
    "surquillo": "surquillo",
    "la molina": "la molina",
    "san borja": "san borja",
    "pueblo libre": "pueblo libre",
    "jesus maria": "jesus maria",
    "magdalena": "magdalena del mar",
    "san miguel": "san miguel",
    "breña": "breña",
    "rimac": "rimac",
    "los olivos": "los olivos",
    "san martin de porres": "san martin de porres",
    "independencia": "independencia",
    "comas": "comas",
    "carabayllo": "carabayllo",
    "ate": "ate",
    "santa anita": "santa anita",
    "el agustino": "el agustino",
    "san juan de lurigancho": "san juan de lurigancho",
    "san juan de miraflores": "san juan de miraflores",
    "villa maria del triunfo": "villa maria del triunfo",
    "villa el salvador": "villa el salvador",
    "lurin": "lurin",
    "chorrillos": "chorrillos",
    "puente piedra": "puente piedra",
    "ventanilla": "ventanilla",
}

class DataStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.db_path = data_dir / "onpe.db"
        self.raw_dir = data_dir / "raw"
        self.reports_dir = data_dir / "reports"

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _payload_hash(payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return sha256(canonical.encode("utf-8")).hexdigest()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA cache_size=-65536")   # 64 MB page cache
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS mesa_cache (
                    codigo_mesa TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    id_eleccion INTEGER NOT NULL,
                    payload_hash TEXT NOT NULL,
                    schema_version INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS mesas_data (
                    codigo_mesa TEXT PRIMARY KEY,
                    ubigeo TEXT,
                    local_votacion TEXT,
                    electores_habiles INTEGER,
                    votos_emitidos INTEGER,
                    votos_validos INTEGER,
                    blancos INTEGER,
                    nulos INTEGER,
                    impugnados INTEGER,
                    estado_acta TEXT,
                    fetched_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS votos (
                    codigo_mesa TEXT NOT NULL,
                    partido_id TEXT NOT NULL,
                    votos INTEGER,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY (codigo_mesa, partido_id)
                );

                CREATE TABLE IF NOT EXISTS agrupaciones (
                    partido_id TEXT PRIMARY KEY,
                    nombre TEXT,
                    fetched_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS foreign_catalog (
                    ubigeo TEXT PRIMARY KEY,
                    continente TEXT,
                    pais TEXT,
                    ciudad TEXT,
                    fetched_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ubigeo_location_cache (
                    ubigeo TEXT PRIMARY KEY,
                    ambito TEXT,
                    departamento TEXT,
                    ciudad TEXT,
                    pais TEXT,
                    fetched_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS votos_by_ubigeo_partido (
                    ubigeo TEXT NOT NULL,
                    partido_id TEXT NOT NULL,
                    total_votos INTEGER NOT NULL,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY (ubigeo, partido_id)
                );

                CREATE TABLE IF NOT EXISTS geo_query_cache (
                    query_key TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    fetched_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_mesas_ubigeo ON mesas_data (ubigeo);
                CREATE INDEX IF NOT EXISTS idx_mesas_estado ON mesas_data (estado_acta);
                CREATE INDEX IF NOT EXISTS idx_votos_partido ON votos (partido_id);
                CREATE INDEX IF NOT EXISTS idx_foreign_pais ON foreign_catalog (pais);
                CREATE INDEX IF NOT EXISTS idx_foreign_ciudad ON foreign_catalog (ciudad);
                CREATE INDEX IF NOT EXISTS idx_ubigeo_location_depto ON ubigeo_location_cache (departamento);
                CREATE INDEX IF NOT EXISTS idx_ubigeo_location_ciudad ON ubigeo_location_cache (ciudad);
                CREATE INDEX IF NOT EXISTS idx_votos_ubigeo_partido ON votos_by_ubigeo_partido (ubigeo, partido_id);

                CREATE TABLE IF NOT EXISTS mesa_prefix_totals (
                    prefix TEXT PRIMARY KEY,
                    n_mesas INTEGER NOT NULL DEFAULT 0,
                    mesas_con_votos INTEGER NOT NULL DEFAULT 0,
                    votos_emitidos INTEGER NOT NULL DEFAULT 0,
                    votos_validos INTEGER NOT NULL DEFAULT 0,
                    rebuilt_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS mesa_prefix_party_summary (
                    prefix TEXT NOT NULL,
                    partido_id TEXT NOT NULL,
                    total_votos INTEGER NOT NULL DEFAULT 0,
                    n_mesas INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (prefix, partido_id)
                );
                CREATE INDEX IF NOT EXISTS idx_prefix_party ON mesa_prefix_party_summary (prefix, total_votos DESC);

                CREATE TABLE IF NOT EXISTS mesa_winner (
                    codigo_mesa TEXT PRIMARY KEY,
                    partido_id TEXT NOT NULL,
                    max_votos INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_mesa_winner_partido ON mesa_winner (partido_id);
                CREATE INDEX IF NOT EXISTS idx_mesa_winner_mesa_partido ON mesa_winner (codigo_mesa, partido_id);

                CREATE TABLE IF NOT EXISTS ubigeo_reniec (
                    ubigeo TEXT PRIMARY KEY,
                    distrito TEXT,
                    provincia TEXT,
                    departamento TEXT,
                    distrito_norm TEXT,
                    provincia_norm TEXT,
                    departamento_norm TEXT,
                    fetched_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_reniec_dept_norm ON ubigeo_reniec (departamento_norm);
                CREATE INDEX IF NOT EXISTS idx_reniec_prov_norm ON ubigeo_reniec (provincia_norm);
                CREATE INDEX IF NOT EXISTS idx_reniec_dist_norm ON ubigeo_reniec (distrito_norm);

                CREATE TABLE IF NOT EXISTS ubigeo_onpe_api (
                    ubigeo TEXT PRIMARY KEY,
                    distrito TEXT,
                    provincia TEXT,
                    departamento TEXT,
                    distrito_norm TEXT,
                    provincia_norm TEXT,
                    departamento_norm TEXT,
                    fetched_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_onpe_api_dept_norm ON ubigeo_onpe_api (departamento_norm);
                CREATE INDEX IF NOT EXISTS idx_onpe_api_prov_norm ON ubigeo_onpe_api (provincia_norm);
                CREATE INDEX IF NOT EXISTS idx_onpe_api_dist_norm ON ubigeo_onpe_api (distrito_norm);

                -- ═══ SEGUNDA VUELTA (SV) ═══════════════════════════════════════════════════

                CREATE TABLE IF NOT EXISTS mesas_sv (
                    codigo_mesa TEXT PRIMARY KEY,
                    id_ubigeo TEXT,
                    nombre_local TEXT,
                    id_ambito INTEGER,
                    electores_habiles INTEGER,
                    votos_emitidos INTEGER,
                    votos_validos INTEGER,
                    total_asistentes INTEGER,
                    codigo_estado_acta TEXT,
                    fetched_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_mesas_sv_ubigeo ON mesas_sv (id_ubigeo);
                CREATE INDEX IF NOT EXISTS idx_mesas_sv_estado ON mesas_sv (codigo_estado_acta);

                CREATE TABLE IF NOT EXISTS votos_sv (
                    codigo_mesa TEXT NOT NULL,
                    partido_id TEXT NOT NULL,
                    votos INTEGER,
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY (codigo_mesa, partido_id)
                );
                CREATE INDEX IF NOT EXISTS idx_votos_sv_partido ON votos_sv (partido_id);
                CREATE INDEX IF NOT EXISTS idx_votos_sv_mesa ON votos_sv (codigo_mesa);

                CREATE TABLE IF NOT EXISTS agrupaciones_sv (
                    partido_id TEXT PRIMARY KEY,
                    nombre TEXT,
                    fetched_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ubicaciones_sv (
                    ubigeo TEXT PRIMARY KEY,
                    ambito TEXT,
                    departamento TEXT,
                    provincia TEXT,
                    distrito TEXT,
                    continente TEXT,
                    pais TEXT,
                    ciudad TEXT,
                    fetched_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_ubicaciones_sv_dep ON ubicaciones_sv (departamento);
                CREATE INDEX IF NOT EXISTS idx_ubicaciones_sv_prov ON ubicaciones_sv (provincia);

                CREATE TABLE IF NOT EXISTS locales_reasignados_sv (
                    nro INTEGER PRIMARY KEY,
                    odpe TEXT,
                    dpto TEXT,
                    provincia TEXT,
                    distrito TEXT,
                    ccpp TEXT,
                    nombre_local_original TEXT,
                    nombre_local_nuevo TEXT,
                    motivo TEXT,
                    mesas_afectadas INTEGER,
                    estado_parseo TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_reasignados_dpto ON locales_reasignados_sv (dpto);
                CREATE INDEX IF NOT EXISTS idx_reasignados_motivo ON locales_reasignados_sv (motivo);

                -- sv_resumen_* tables loaded from scraper's resumen/ files

                CREATE TABLE IF NOT EXISTS sv_resumen_nacional (
                    partido_id TEXT PRIMARY KEY,
                    nombre_candidato TEXT,
                    nombre_agrupacion TEXT,
                    votos_validos INTEGER,
                    pct_votos_validos REAL,
                    pct_votos_emitidos REAL,
                    actas_contabilizadas_pct REAL,
                    contabilizadas INTEGER,
                    total_actas INTEGER,
                    participacion_ciudadana REAL,
                    fecha_actualizacion TEXT,
                    fuente TEXT,
                    loaded_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sv_resumen_departamentos (
                    ubigeo TEXT NOT NULL,
                    partido_id TEXT NOT NULL,
                    nombre_candidato TEXT,
                    nombre_agrupacion TEXT,
                    votos_validos INTEGER,
                    pct_votos_validos REAL,
                    pct_votos_emitidos REAL,
                    total_votos_validos_geo INTEGER,
                    total_votos_emitidos_geo INTEGER,
                    fuente TEXT,
                    loaded_at TEXT NOT NULL,
                    PRIMARY KEY (ubigeo, partido_id)
                );
                CREATE INDEX IF NOT EXISTS idx_sv_rdept_ubigeo ON sv_resumen_departamentos (ubigeo);

                CREATE TABLE IF NOT EXISTS sv_resumen_provincias (
                    ubigeo TEXT NOT NULL,
                    partido_id TEXT NOT NULL,
                    nombre_candidato TEXT,
                    nombre_agrupacion TEXT,
                    nombre_geo TEXT,
                    votos_validos INTEGER,
                    pct_votos_validos REAL,
                    pct_votos_emitidos REAL,
                    total_votos_validos_geo INTEGER,
                    total_votos_emitidos_geo INTEGER,
                    fuente TEXT,
                    loaded_at TEXT NOT NULL,
                    PRIMARY KEY (ubigeo, partido_id)
                );
                CREATE INDEX IF NOT EXISTS idx_sv_rprov_ubigeo ON sv_resumen_provincias (ubigeo);
                CREATE INDEX IF NOT EXISTS idx_sv_rprov_nombre_geo ON sv_resumen_provincias (nombre_geo);

                CREATE TABLE IF NOT EXISTS sv_resumen_cobertura (
                    ubigeo TEXT PRIMARY KEY,
                    nombre_departamento TEXT,
                    actas_contabilizadas INTEGER,
                    pct_actas_contabilizadas REAL,
                    fuente TEXT,
                    loaded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sv_rcob_ubigeo ON sv_resumen_cobertura (ubigeo);

                -- CTAS aggregation tables (distrito and ciudad level — scraper doesn't pre-compute these)

                CREATE TABLE IF NOT EXISTS sv_agg_distrito (
                    ubigeo TEXT NOT NULL,
                    partido_id TEXT NOT NULL,
                    nombre_candidato TEXT,
                    votos INTEGER,
                    total_mesas INTEGER,
                    mesas_contabilizadas INTEGER,
                    rebuilt_at TEXT NOT NULL,
                    PRIMARY KEY (ubigeo, partido_id)
                );
                CREATE INDEX IF NOT EXISTS idx_sv_agg_distrito_ubigeo ON sv_agg_distrito (ubigeo);

                CREATE TABLE IF NOT EXISTS sv_agg_ciudad (
                    ubigeo TEXT NOT NULL,
                    ciudad TEXT NOT NULL,
                    partido_id TEXT NOT NULL,
                    nombre_candidato TEXT,
                    votos INTEGER,
                    total_mesas INTEGER,
                    mesas_contabilizadas INTEGER,
                    rebuilt_at TEXT NOT NULL,
                    PRIMARY KEY (ubigeo, ciudad, partido_id)
                );
                CREATE INDEX IF NOT EXISTS idx_sv_agg_ciudad_ubigeo ON sv_agg_ciudad (ubigeo);
                CREATE INDEX IF NOT EXISTS idx_sv_agg_ciudad_nombre ON sv_agg_ciudad (ciudad);

                -- Vote transfer projection table
                CREATE TABLE IF NOT EXISTS proyeccion_sv_by_ubigeo (
                    ubigeo TEXT PRIMARY KEY,
                    votos_1v_total INTEGER,
                    votos_proyectados_keiko INTEGER,
                    votos_proyectados_sanchez INTEGER,
                    votos_proyectados_bn INTEGER,
                    votos_abstencion_estimada INTEGER,
                    rebuilt_at TEXT NOT NULL
                );

                -- Transfer map seeds (static knowledge)
                CREATE TABLE IF NOT EXISTS voto_transfer_map (
                    partido_nombre_norm TEXT PRIMARY KEY,
                    peso_keiko REAL NOT NULL,
                    peso_sanchez REAL NOT NULL,
                    peso_bn REAL NOT NULL,
                    fuente TEXT NOT NULL,
                    loaded_at TEXT NOT NULL
                );

                -- Scraper commit guard (avoid redundant full rebuilds)
                CREATE TABLE IF NOT EXISTS sv_sync_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _mesa_prefix_like(prefix: str) -> str:
        normalized = str(prefix or "").strip()
        # Convención conversacional: 900K => 900000, que representa el bloque 900xxx.
        if len(normalized) == 6 and normalized.endswith("000"):
            return normalized[:3]
        return normalized

    def append_raw_event(self, event_type: str, payload: dict[str, Any]) -> None:
        line = {
            "timestamp": self.now_iso(),
            "event_type": event_type,
            "payload": payload,
        }
        path = self.raw_dir / "events.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")

    def get_cached_mesa(self, codigo_mesa: str, max_age_seconds: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json, fetched_at FROM mesa_cache WHERE codigo_mesa = ?",
                (codigo_mesa,),
            ).fetchone()

        if row is None:
            return None

        fetched_at = datetime.fromisoformat(str(row["fetched_at"]).replace("Z", "+00:00"))
        age_seconds = (datetime.now(timezone.utc) - fetched_at).total_seconds()
        if age_seconds > max_age_seconds:
            return None

        return json.loads(str(row["payload_json"]))

    def get_mesa_from_local(self, codigo_mesa: str) -> dict[str, Any] | None:
        """Construye bundle de mesa desde tablas locales (mesas_data + votos + agrupaciones).

        Evita llamada al API live cuando los datos ya están hidratados.
        Retorna None si la mesa no existe en mesas_data.
        """
        with self._connect() as conn:
            mesa_row = conn.execute(
                "SELECT * FROM mesas_data WHERE codigo_mesa = ?",
                (codigo_mesa,),
            ).fetchone()
            if mesa_row is None:
                return None

            votos_rows = conn.execute(
                """SELECT v.partido_id, COALESCE(a.nombre,'') AS nombre_partido, v.votos
                   FROM votos v
                   LEFT JOIN agrupaciones a ON a.partido_id = v.partido_id
                   WHERE v.codigo_mesa = ?
                   ORDER BY v.votos DESC""",
                (codigo_mesa,),
            ).fetchall()

            location_row = conn.execute(
                "SELECT departamento, ciudad, pais FROM ubigeo_location_cache WHERE ubigeo = ?",
                (str(mesa_row["ubigeo"] or ""),),
            ).fetchone()

        mesa_data: dict[str, Any] = {
            "codigo_mesa": codigo_mesa,
            "ubigeo": str(mesa_row["ubigeo"] or ""),
            "local_votacion": str(mesa_row["local_votacion"] or ""),
            "electores_habiles": int(mesa_row["electores_habiles"] or 0),
            "votos_emitidos": int(mesa_row["votos_emitidos"] or 0),
            "votos_validos": int(mesa_row["votos_validos"] or 0),
            "blancos": int(mesa_row["blancos"] or 0),
            "nulos": int(mesa_row["nulos"] or 0),
            "impugnados": int(mesa_row["impugnados"] or 0),
            "estado_acta": str(mesa_row["estado_acta"] or ""),
        }
        if location_row:
            mesa_data.update({
                "departamento": str(location_row["departamento"] or ""),
                "ciudad": str(location_row["ciudad"] or ""),
            })

        votos = [
            {
                "partido_id": str(r["partido_id"]),
                "nombre_partido": str(r["nombre_partido"]),
                "votos": int(r["votos"] or 0),
            }
            for r in votos_rows
        ]

        return {
            "codigo_mesa": codigo_mesa,
            "found": True,
            "mesa_data": mesa_data,
            "agrupaciones": [{"partido_id": v["partido_id"], "nombre": v["nombre_partido"]} for v in votos],
            "votos": votos,
            "source": "local_db",
        }

    def upsert_mesa_bundle(
        self,
        codigo_mesa: str,
        mesa_payload: dict[str, Any],
        *,
        source: str,
        id_eleccion: int,
    ) -> None:
        now = self.now_iso()
        payload_hash = self._payload_hash(mesa_payload)

        mesa_data = mesa_payload.get("mesa_data") or {}
        votos = mesa_payload.get("votos") or []
        agrupaciones = mesa_payload.get("agrupaciones") or []

        with self._connect() as conn:
            prev_mesa_row = conn.execute(
                "SELECT ubigeo FROM mesas_data WHERE codigo_mesa = ?",
                (codigo_mesa,),
            ).fetchone()
            prev_ubigeo = str(prev_mesa_row["ubigeo"] or "") if prev_mesa_row else ""

            prev_votes_rows = conn.execute(
                "SELECT partido_id, votos FROM votos WHERE codigo_mesa = ?",
                (codigo_mesa,),
            ).fetchall()
            prev_votes: dict[str, int] = {
                str(row["partido_id"]): int(row["votos"] or 0)
                for row in prev_votes_rows
            }

            conn.execute(
                """
                INSERT INTO mesa_cache (codigo_mesa, payload_json, fetched_at, source, id_eleccion, payload_hash, schema_version)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(codigo_mesa) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    fetched_at=excluded.fetched_at,
                    source=excluded.source,
                    id_eleccion=excluded.id_eleccion,
                    payload_hash=excluded.payload_hash
                """,
                (
                    codigo_mesa,
                    json.dumps(mesa_payload, ensure_ascii=False),
                    now,
                    source,
                    id_eleccion,
                    payload_hash,
                ),
            )

            if mesa_data:
                conn.execute(
                    """
                    INSERT INTO mesas_data (
                        codigo_mesa, ubigeo, local_votacion, electores_habiles, votos_emitidos, votos_validos,
                        blancos, nulos, impugnados, estado_acta, fetched_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(codigo_mesa) DO UPDATE SET
                        ubigeo=excluded.ubigeo,
                        local_votacion=excluded.local_votacion,
                        electores_habiles=excluded.electores_habiles,
                        votos_emitidos=excluded.votos_emitidos,
                        votos_validos=excluded.votos_validos,
                        blancos=excluded.blancos,
                        nulos=excluded.nulos,
                        impugnados=excluded.impugnados,
                        estado_acta=excluded.estado_acta,
                        fetched_at=excluded.fetched_at
                    """,
                    (
                        mesa_data.get("codigo_mesa"),
                        mesa_data.get("ubigeo"),
                        mesa_data.get("local_votacion"),
                        mesa_data.get("electores_habiles") or 0,
                        mesa_data.get("votos_emitidos") or 0,
                        mesa_data.get("votos_validos") or 0,
                        mesa_data.get("blancos") or 0,
                        mesa_data.get("nulos") or 0,
                        mesa_data.get("impugnados") or 0,
                        mesa_data.get("estado_acta"),
                        now,
                    ),
                )

            for item in agrupaciones:
                conn.execute(
                    """
                    INSERT INTO agrupaciones (partido_id, nombre, fetched_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(partido_id) DO UPDATE SET
                        nombre=excluded.nombre,
                        fetched_at=excluded.fetched_at
                    """,
                    (str(item.get("partido_id", "")), str(item.get("nombre", "")), now),
                )

            for item in votos:
                conn.execute(
                    """
                    INSERT INTO votos (codigo_mesa, partido_id, votos, fetched_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(codigo_mesa, partido_id) DO UPDATE SET
                        votos=excluded.votos,
                        fetched_at=excluded.fetched_at
                    """,
                    (
                        str(item.get("codigo_mesa", codigo_mesa)),
                        str(item.get("partido_id", "")),
                        int(item.get("votos") or 0),
                        now,
                    ),
                )

            new_ubigeo = str(mesa_data.get("ubigeo") or prev_ubigeo or "")
            new_votes: dict[str, int] = {}
            for item in votos:
                partido_id = str(item.get("partido_id", ""))
                if not partido_id:
                    continue
                new_votes[partido_id] = int(item.get("votos") or 0)

            self._apply_votes_aggregate_delta(
                conn,
                prev_ubigeo=prev_ubigeo,
                prev_votes=prev_votes,
                new_ubigeo=new_ubigeo,
                new_votes=new_votes,
                now=now,
            )

    @staticmethod
    def _apply_votes_aggregate_delta(
        conn: sqlite3.Connection,
        *,
        prev_ubigeo: str,
        prev_votes: dict[str, int],
        new_ubigeo: str,
        new_votes: dict[str, int],
        now: str,
    ) -> None:
        def _accumulate(ubigeo: str, delta_map: dict[str, int]) -> None:
            if not ubigeo or not delta_map:
                return
            for partido_id, delta in delta_map.items():
                if not partido_id or delta == 0:
                    continue
                conn.execute(
                    """
                    INSERT INTO votos_by_ubigeo_partido (ubigeo, partido_id, total_votos, fetched_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(ubigeo, partido_id) DO UPDATE SET
                        total_votos=votos_by_ubigeo_partido.total_votos + excluded.total_votos,
                        fetched_at=excluded.fetched_at
                    """,
                    (ubigeo, partido_id, int(delta), now),
                )

        if prev_ubigeo:
            prev_delta = {pid: -int(v) for pid, v in prev_votes.items() if int(v) != 0}
            _accumulate(prev_ubigeo, prev_delta)

        if new_ubigeo:
            new_delta = {pid: int(v) for pid, v in new_votes.items() if int(v) != 0}
            _accumulate(new_ubigeo, new_delta)

        conn.execute("DELETE FROM votos_by_ubigeo_partido WHERE total_votos <= 0")

    def _ensure_votes_by_ubigeo_partido_backfilled(self, conn: sqlite3.Connection) -> None:
        row = conn.execute("SELECT COUNT(*) AS c FROM votos_by_ubigeo_partido").fetchone()
        if row and int(row["c"] or 0) > 0:
            return

        votos_row = conn.execute("SELECT COUNT(*) AS c FROM votos").fetchone()
        if not votos_row or int(votos_row["c"] or 0) == 0:
            return

        now = self.now_iso()
        conn.execute(
            """
            INSERT INTO votos_by_ubigeo_partido (ubigeo, partido_id, total_votos, fetched_at)
            SELECT m.ubigeo, v.partido_id, SUM(v.votos) AS total_votos, ?
            FROM votos v
            INNER JOIN mesas_data m ON m.codigo_mesa = v.codigo_mesa
            WHERE COALESCE(m.ubigeo, '') <> ''
            GROUP BY m.ubigeo, v.partido_id
            """,
            (now,),
        )


    @staticmethod
    def _norm(text: str) -> str:
        base = unicodedata.normalize("NFKD", text or "")
        stripped = "".join(ch for ch in base if not unicodedata.combining(ch))
        return stripped.casefold().strip()

    @staticmethod
    def load_candidate_map(path: Path) -> dict[str, str]:
        if not path.exists():
            return {}

        result: dict[str, str] = {}
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            for row in reader:
                partido_id = str(row.get("partido_id", "")).strip()
                candidato = str(row.get("Candidato", "")).strip()
                if not partido_id:
                    continue
                result[partido_id] = candidato
        return result

    @staticmethod
    def load_foreign_catalog(path: Path) -> list[dict[str, str]]:
        if not path.exists():
            return []

        rows: list[dict[str, str]] = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            for row in reader:
                ubigeo = str(row.get("ubigeo", "")).strip()
                if not ubigeo:
                    continue
                rows.append(
                    {
                        "ubigeo": ubigeo,
                        "Continente": str(row.get("Continente", "")).strip(),
                        "pais": str(row.get("pais", "")).strip(),
                        "ciudad": str(row.get("ciudad", "")).strip(),
                    }
                )
        return rows

    def upsert_foreign_catalog(self, rows: list[dict[str, str]]) -> int:
        if not rows:
            return 0

        now = self.now_iso()
        count = 0
        with self._connect() as conn:
            for row in rows:
                ubigeo = str(row.get("ubigeo", "")).strip()
                if not ubigeo:
                    continue
                conn.execute(
                    """
                    INSERT INTO foreign_catalog (ubigeo, continente, pais, ciudad, fetched_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(ubigeo) DO UPDATE SET
                        continente=excluded.continente,
                        pais=excluded.pais,
                        ciudad=excluded.ciudad,
                        fetched_at=excluded.fetched_at
                    """,
                    (
                        ubigeo,
                        str(row.get("Continente", "")).strip(),
                        str(row.get("pais", "")).strip(),
                        str(row.get("ciudad", "")).strip(),
                        now,
                    ),
                )
                count += 1
        return count

    def upsert_ubigeo_location(self, row: dict[str, str]) -> bool:
        ubigeo = str(row.get("ubigeo", "")).strip()
        if not ubigeo:
            return False

        ambito = str(row.get("ambito", "")).strip()
        departamento = str(row.get("departamento", "")).strip()
        ciudad = str(row.get("ciudad", "")).strip()
        pais = str(row.get("pais", "")).strip()
        if not departamento and not ciudad and not pais:
            return False

        now = self.now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ubigeo_location_cache (ubigeo, ambito, departamento, ciudad, pais, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(ubigeo) DO UPDATE SET
                    ambito=excluded.ambito,
                    departamento=excluded.departamento,
                    ciudad=excluded.ciudad,
                    pais=excluded.pais,
                    fetched_at=excluded.fetched_at
                """,
                (ubigeo, ambito, departamento, ciudad, pais, now),
            )
        return True

    def find_ubigeos_missing_city_or_department_by_mesa_prefix(
        self,
        mesa_prefix: str,
        *,
        limit: int = 50,
    ) -> list[str]:
        prefix = str(mesa_prefix or "").strip()
        if not prefix:
            return []

        like_prefix = self._mesa_prefix_like(prefix)
        limit = max(1, min(int(limit), 500))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT m.ubigeo AS ubigeo
                FROM mesas_data m
                LEFT JOIN foreign_catalog f ON f.ubigeo = m.ubigeo
                LEFT JOIN ubigeo_location_cache ul ON ul.ubigeo = m.ubigeo
                WHERE m.codigo_mesa LIKE ?
                  AND COALESCE(m.ubigeo, '') <> ''
                  AND (
                        COALESCE(NULLIF(TRIM(COALESCE(f.ciudad, ul.ciudad, '')), ''), '') = ''
                     OR COALESCE(NULLIF(TRIM(COALESCE(ul.departamento, '')), ''), '') = ''
                  )
                LIMIT ?
                """,
                (f"{like_prefix}%", limit),
            ).fetchall()
        return [str(row["ubigeo"] or "") for row in rows if str(row["ubigeo"] or "").strip()]

    def find_ubigeos_missing_city_or_department_by_ubigeo_prefix(
        self,
        ubigeo_prefix: str,
        *,
        limit: int = 50,
    ) -> list[str]:
        prefix = str(ubigeo_prefix or "").strip()
        if not prefix:
            return []

        limit = max(1, min(int(limit), 500))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT m.ubigeo AS ubigeo
                FROM mesas_data m
                LEFT JOIN foreign_catalog f ON f.ubigeo = m.ubigeo
                LEFT JOIN ubigeo_location_cache ul ON ul.ubigeo = m.ubigeo
                WHERE COALESCE(m.ubigeo, '') LIKE ?
                  AND (
                        COALESCE(NULLIF(TRIM(COALESCE(f.ciudad, ul.ciudad, '')), ''), '') = ''
                     OR COALESCE(NULLIF(TRIM(COALESCE(ul.departamento, '')), ''), '') = ''
                  )
                LIMIT ?
                """,
                (f"{prefix}%", limit),
            ).fetchall()
        return [str(row["ubigeo"] or "") for row in rows if str(row["ubigeo"] or "").strip()]

    def summarize_ubigeo_prefix(self, ubigeo_prefix: str, sample_size: int = 5) -> dict[str, Any]:
        prefix = str(ubigeo_prefix or "").strip()
        if not prefix:
            raise ValueError("ubigeo_prefix no puede estar vacío")

        sample_size = max(1, min(int(sample_size), 20))
        like_value = f"{prefix}%"

        with self._connect() as conn:
            sample_rows = conn.execute(
                """
                SELECT
                    m.ubigeo AS ubigeo,
                    COALESCE(ul.departamento, '') AS departamento,
                    COALESCE(f.continente, '') AS continente,
                    COALESCE(f.pais, ul.pais, '') AS pais,
                    COALESCE(f.ciudad, ul.ciudad, '') AS ciudad,
                    COUNT(*) AS mesas,
                    COALESCE(SUM(COALESCE(m.votos_emitidos, 0)), 0) AS votos_emitidos,
                    COALESCE(SUM(COALESCE(m.votos_validos, 0)), 0) AS votos_validos
                FROM mesas_data m
                LEFT JOIN foreign_catalog f ON f.ubigeo = m.ubigeo
                LEFT JOIN ubigeo_location_cache ul ON ul.ubigeo = m.ubigeo
                WHERE COALESCE(m.ubigeo, '') LIKE ?
                GROUP BY m.ubigeo, ul.departamento, f.continente, f.pais, ul.pais, f.ciudad, ul.ciudad
                ORDER BY mesas DESC, votos_validos DESC, m.ubigeo ASC
                LIMIT ?
                """,
                (like_value, sample_size),
            ).fetchall()

        sample: list[dict[str, Any]] = []
        for row in sample_rows:
            sample.append(
                {
                    "ubigeo": str(row["ubigeo"] or ""),
                    "departamento": str(row["departamento"] or ""),
                    "continente": str(row["continente"] or ""),
                    "pais": str(row["pais"] or ""),
                    "ciudad": str(row["ciudad"] or ""),
                    "mesas": int(row["mesas"] or 0),
                    "votos_emitidos": int(row["votos_emitidos"] or 0),
                    "votos_validos": int(row["votos_validos"] or 0),
                }
            )

        return {
            "ubigeo_prefix": prefix,
            "sample": sample,
        }

    def find_foreign_ubigeos(self, query: str, field: str | None = None) -> list[dict[str, str]]:
        q_norm = self._norm(query)
        if not q_norm:
            return []

        field_norm = self._norm(field or "")
        allowed_fields = {"pais", "ciudad", "any"}
        if field_norm and field_norm not in allowed_fields:
            raise ValueError("field debe ser 'pais', 'ciudad' o None")

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ubigeo, continente, pais, ciudad FROM foreign_catalog"
            ).fetchall()

        def _project(row: sqlite3.Row) -> dict[str, str]:
            return {
                "ubigeo": str(row["ubigeo"]),
                "Continente": str(row["continente"] or ""),
                "pais": str(row["pais"] or ""),
                "ciudad": str(row["ciudad"] or ""),
            }

        exact: list[dict[str, str]] = []
        partial: list[dict[str, str]] = []

        for row in rows:
            pais = str(row["pais"] or "")
            ciudad = str(row["ciudad"] or "")
            pais_norm = self._norm(pais)
            ciudad_norm = self._norm(ciudad)

            if field_norm == "pais":
                is_exact = pais_norm == q_norm
                is_partial = q_norm in pais_norm
            elif field_norm == "ciudad":
                is_exact = ciudad_norm == q_norm
                is_partial = q_norm in ciudad_norm
            else:
                is_exact = pais_norm == q_norm or ciudad_norm == q_norm
                is_partial = q_norm in pais_norm or q_norm in ciudad_norm

            if is_exact:
                exact.append(_project(row))
            elif is_partial:
                partial.append(_project(row))

        # Prioriza coincidencia exacta para evitar mezclar entidades parecidas.
        return exact if exact else partial

    def total_mesas_local(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM mesas_data").fetchone()
        return int(row["c"] if row else 0)

    def get_geo_query_cache(self, query_key: str, max_age_seconds: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json, fetched_at FROM geo_query_cache WHERE query_key = ?",
                (query_key,),
            ).fetchone()

        if row is None:
            return None

        fetched_at = datetime.fromisoformat(str(row["fetched_at"]).replace("Z", "+00:00"))
        age_seconds = (datetime.now(timezone.utc) - fetched_at).total_seconds()
        if age_seconds > max_age_seconds:
            return None

        return json.loads(str(row["payload_json"]))

    def upsert_geo_query_cache(self, query_key: str, payload: dict[str, Any]) -> None:
        now = self.now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO geo_query_cache (query_key, payload_json, fetched_at)
                VALUES (?, ?, ?)
                ON CONFLICT(query_key) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    fetched_at=excluded.fetched_at
                """,
                (query_key, json.dumps(payload, ensure_ascii=False), now),
            )

    def fill_ubigeo_location_cache_from_reniec(self, source_dir: Path) -> dict[str, int]:
        """Populates ubigeo_location_cache from geodir-ubigeo-reniec.xlsx.

        Strategy:
        1. Load all 6-digit ubigeos from Excel → ubigeo_location_cache.
        2. For 5-digit ubigeos in mesas_data, try zero-padded match.
        3. For still-missing ones, fill by province prefix (first 4 digits).
        """
        try:
            import openpyxl  # type: ignore[import]
        except ImportError:
            return {"excel": 0, "padded": 0, "prefix": 0}

        xlsx_path = source_dir / "geodir-ubigeo-reniec.xlsx"
        if not xlsx_path.exists():
            return {"excel": 0, "padded": 0, "prefix": 0}

        now = self.now_iso()
        excel_inserted = 0
        padded_fixed = 0
        prefix_fixed = 0

        try:
            wb = openpyxl.load_workbook(str(xlsx_path), read_only=True, data_only=True)
            ws = wb.active
            headers = [str(c.value or "").strip().lower() for c in next(ws.iter_rows(max_row=1))]  # type: ignore

            def _col(name: str) -> int:
                return headers.index(name)

            ubigeo_col = _col("ubigeo")
            distrito_col = _col("distrito")
            provincia_col = _col("provincia")
            departamento_col = _col("departamento")

            with self._connect() as conn:
                # Step 1: load from Excel
                for row in ws.iter_rows(min_row=2, values_only=True):  # type: ignore
                    ubigeo = str(row[ubigeo_col] or "").strip()
                    if not ubigeo:
                        continue
                    distrito = str(row[distrito_col] or "").strip()
                    provincia = str(row[provincia_col] or "").strip()
                    departamento = str(row[departamento_col] or "").strip()
                    ciudad = f"{distrito}, {provincia}" if provincia else distrito
                    conn.execute(
                        """INSERT OR IGNORE INTO ubigeo_location_cache (ubigeo, ciudad, departamento, fetched_at)
                           VALUES (?, ?, ?, ?)""",
                        (ubigeo, ciudad, departamento, now),
                    )
                    excel_inserted += 1

                # Step 2: fill 5-digit ubigeos using zero-padded lookup
                missing = conn.execute("""
                    SELECT DISTINCT m.ubigeo FROM mesas_data m
                    LEFT JOIN ubigeo_location_cache ul ON ul.ubigeo = m.ubigeo
                    LEFT JOIN foreign_catalog fc ON fc.ubigeo = m.ubigeo
                    WHERE ul.ubigeo IS NULL AND fc.ubigeo IS NULL AND m.ubigeo != ''
                """).fetchall()

                for (ubigeo,) in missing:
                    padded = ubigeo.zfill(6)
                    if padded == ubigeo:
                        continue
                    row_data = conn.execute(
                        "SELECT ciudad, departamento FROM ubigeo_location_cache WHERE ubigeo=?",
                        (padded,),
                    ).fetchone()
                    if row_data:
                        conn.execute(
                            """INSERT OR IGNORE INTO ubigeo_location_cache (ubigeo, ciudad, departamento, fetched_at)
                               VALUES (?, ?, ?, ?)""",
                            (ubigeo, row_data[0], row_data[1], now),
                        )
                        padded_fixed += 1

                # Step 3: fill remaining by province prefix (first 4 digits)
                still_missing = conn.execute("""
                    SELECT DISTINCT m.ubigeo FROM mesas_data m
                    LEFT JOIN ubigeo_location_cache ul ON ul.ubigeo = m.ubigeo
                    LEFT JOIN foreign_catalog fc ON fc.ubigeo = m.ubigeo
                    WHERE ul.ubigeo IS NULL AND fc.ubigeo IS NULL AND m.ubigeo != ''
                """).fetchall()

                for (ubigeo,) in still_missing:
                    padded = ubigeo.zfill(6)
                    resolved = None
                    for prefix_len in [4, 2]:
                        prefix = padded[:prefix_len]
                        row_data = conn.execute(
                            """SELECT ciudad, departamento FROM ubigeo_location_cache
                               WHERE ubigeo LIKE ? AND departamento != '' LIMIT 1""",
                            (prefix + "%",),
                        ).fetchone()
                        if row_data:
                            resolved = row_data
                            break
                    if resolved:
                        conn.execute(
                            """INSERT OR IGNORE INTO ubigeo_location_cache (ubigeo, ciudad, departamento, fetched_at)
                               VALUES (?, ?, ?, ?)""",
                            (ubigeo, resolved[0], resolved[1], now),
                        )
                        prefix_fixed += 1

            wb.close()
            _logger.info(
                "ubigeo_location_cache: excel=%d padded=%d prefix=%d",
                excel_inserted, padded_fixed, prefix_fixed,
            )
        except Exception:
            _logger.exception("Error en fill_ubigeo_location_cache_from_reniec")

        return {"excel": excel_inserted, "padded": padded_fixed, "prefix": prefix_fixed}

    def try_bootstrap_reniec(self, source_dir: Path) -> int:
        """Pobla ubigeo_reniec desde geodir-ubigeo-reniec.xlsx (requiere openpyxl).
        Retorna filas insertadas/actualizadas. Silencia si openpyxl no está disponible.
        No re-lee el xlsx si la tabla ya tiene datos (evita costosa carga en arranque)."""
        # Skip rápido si ya hay filas en la tabla (opción de refresco: borrar tabla manualmente)
        try:
            with self._connect() as conn:
                cnt = conn.execute("SELECT COUNT(*) AS c FROM ubigeo_reniec").fetchone()["c"]
            if cnt > 0:
                return cnt
        except Exception:
            pass

        try:
            import openpyxl  # type: ignore[import]
        except ImportError:
            _logger.debug("openpyxl no disponible; salteando bootstrap de ubigeo_reniec")
            return 0

        xlsx_path = source_dir / "geodir-ubigeo-reniec.xlsx"
        if not xlsx_path.exists():
            _logger.debug("geodir-ubigeo-reniec.xlsx no encontrado en %s", source_dir)
            return 0

        try:
            wb = openpyxl.load_workbook(str(xlsx_path), read_only=True, data_only=True)
            ws = wb.active
            headers = [str(cell.value or "").strip().lower() for cell in next(ws.iter_rows(max_row=1))]  # type: ignore[arg-type]

            def _col(name: str) -> int:
                return headers.index(name)

            ubigeo_col = _col("ubigeo")
            distrito_col = _col("distrito")
            provincia_col = _col("provincia")
            departamento_col = _col("departamento")

            now = self.now_iso()
            inserted = 0
            with self._connect() as conn:
                for row in ws.iter_rows(min_row=2, values_only=True):  # type: ignore[union-attr]
                    ubigeo = str(row[ubigeo_col] or "").strip()
                    if not ubigeo:
                        continue
                    distrito = str(row[distrito_col] or "").strip()
                    provincia = str(row[provincia_col] or "").strip()
                    departamento = str(row[departamento_col] or "").strip()
                    conn.execute(
                        """
                        INSERT INTO ubigeo_reniec (
                            ubigeo, distrito, provincia, departamento,
                            distrito_norm, provincia_norm, departamento_norm, fetched_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(ubigeo) DO UPDATE SET
                            distrito=excluded.distrito,
                            provincia=excluded.provincia,
                            departamento=excluded.departamento,
                            distrito_norm=excluded.distrito_norm,
                            provincia_norm=excluded.provincia_norm,
                            departamento_norm=excluded.departamento_norm,
                            fetched_at=excluded.fetched_at
                        """,
                        (
                            ubigeo, distrito, provincia, departamento,
                            _norm_text(distrito), _norm_text(provincia), _norm_text(departamento),
                            now,
                        ),
                    )
                    inserted += 1

            wb.close()
            _logger.info("ubigeo_reniec: %d filas desde %s", inserted, xlsx_path)
            return inserted
        except Exception:
            _logger.exception("Error en try_bootstrap_reniec")
            return 0

    def rebuild_prefix_summaries(self, prefix_lengths: tuple[int, ...] = (1, 2, 3, 4)) -> dict[str, int]:
        """Pre-computes mesa_prefix_totals and mesa_prefix_party_summary for fast prefix queries.

        Covering prefixes of 1–4 digits lets all '9%', '90%', '900%', '9000%' queries
        skip the 3.8M-row votos scan and return in <1ms.
        """
        now = self.now_iso()
        totals_inserted = 0
        party_inserted = 0

        with self._connect() as conn:
            conn.execute("DELETE FROM mesa_prefix_totals")
            conn.execute("DELETE FROM mesa_prefix_party_summary")

            # Pre-compute the winner of each mesa (partido with max votes)
            conn.execute("DELETE FROM mesa_winner")
            conn.execute(
                """
                INSERT INTO mesa_winner (codigo_mesa, partido_id, max_votos)
                SELECT v.codigo_mesa, v.partido_id, v.votos
                FROM votos v
                INNER JOIN (
                    SELECT codigo_mesa, MAX(votos) AS max_votos
                    FROM votos GROUP BY codigo_mesa
                ) mx ON mx.codigo_mesa = v.codigo_mesa AND mx.max_votos = v.votos
                ON CONFLICT(codigo_mesa) DO UPDATE SET
                    partido_id=excluded.partido_id,
                    max_votos=excluded.max_votos
                """
            )
            _logger.info("mesa_winner: populated")

            for length in prefix_lengths:
                # Totals per prefix
                conn.execute(
                    f"""
                    INSERT INTO mesa_prefix_totals (prefix, n_mesas, mesas_con_votos, votos_emitidos, votos_validos, rebuilt_at)
                    SELECT
                        SUBSTR(codigo_mesa, 1, {length}) AS prefix,
                        COUNT(*) AS n_mesas,
                        SUM(CASE WHEN votos_emitidos > 0 THEN 1 ELSE 0 END) AS mesas_con_votos,
                        SUM(COALESCE(votos_emitidos, 0)) AS votos_emitidos,
                        SUM(COALESCE(votos_validos, 0)) AS votos_validos,
                        ? AS rebuilt_at
                    FROM mesas_data
                    GROUP BY 1
                    ON CONFLICT(prefix) DO UPDATE SET
                        n_mesas=excluded.n_mesas,
                        mesas_con_votos=excluded.mesas_con_votos,
                        votos_emitidos=excluded.votos_emitidos,
                        votos_validos=excluded.votos_validos,
                        rebuilt_at=excluded.rebuilt_at
                    """,
                    (now,),
                )
                n = conn.execute(f"SELECT CHANGES()").fetchone()[0]
                totals_inserted += n

                # Party aggregation per prefix
                conn.execute(
                    f"""
                    INSERT INTO mesa_prefix_party_summary (prefix, partido_id, total_votos, n_mesas)
                    SELECT
                        SUBSTR(v.codigo_mesa, 1, {length}) AS prefix,
                        v.partido_id,
                        SUM(v.votos) AS total_votos,
                        COUNT(DISTINCT v.codigo_mesa) AS n_mesas
                    FROM votos v
                    GROUP BY 1, 2
                    ON CONFLICT(prefix, partido_id) DO UPDATE SET
                        total_votos=excluded.total_votos,
                        n_mesas=excluded.n_mesas
                    """,
                )
                n = conn.execute("SELECT CHANGES()").fetchone()[0]
                party_inserted += n

        _logger.info("rebuild_prefix_summaries: totals=%d party=%d", totals_inserted, party_inserted)
        return {"totals": totals_inserted, "party": party_inserted}

    def bootstrap_from_onpescraper(
        self,
        *,
        output_dir: Path,
        source_dir: Path | None = None,
        include_votes: bool = True,
        source: str = "onpescraper_snapshot",
        id_eleccion: int = 10,
        force: bool = False,
    ) -> dict[str, int | bool]:
        if source_dir is None:
            source_dir = output_dir.parent / "source_data"

        with self._connect() as conn:
            mesas_existing = int(
                (conn.execute("SELECT COUNT(*) AS c FROM mesas_data").fetchone() or {"c": 0})["c"]
            )
            votos_existing = int(
                (conn.execute("SELECT COUNT(*) AS c FROM votos").fetchone() or {"c": 0})["c"]
            )

            if not force and (mesas_existing > 0 or (include_votes and votos_existing > 0)):
                reniec_inserted = self.try_bootstrap_reniec(source_dir)
                return {
                    "skipped": True,
                    "mesas": 0,
                    "votos": 0,
                    "agrupaciones": 0,
                    "foreign_catalog": 0,
                    "reniec_ubigeos": reniec_inserted,
                }

            now = self.now_iso()
            mesas_inserted = 0
            votos_inserted = 0
            agrupaciones_inserted = 0
            foreign_inserted = 0

            mesas_file = output_dir / "mesas_data.txt"
            if mesas_file.exists():
                with mesas_file.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle, delimiter="\t")
                    for row in reader:
                        codigo_mesa = str(row.get("codigo_mesa", "")).strip()
                        if not codigo_mesa:
                            continue
                        conn.execute(
                            """
                            INSERT INTO mesas_data (
                                codigo_mesa, ubigeo, local_votacion, electores_habiles, votos_emitidos, votos_validos,
                                blancos, nulos, impugnados, estado_acta, fetched_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(codigo_mesa) DO UPDATE SET
                                ubigeo=excluded.ubigeo,
                                local_votacion=excluded.local_votacion,
                                electores_habiles=excluded.electores_habiles,
                                votos_emitidos=excluded.votos_emitidos,
                                votos_validos=excluded.votos_validos,
                                blancos=excluded.blancos,
                                nulos=excluded.nulos,
                                impugnados=excluded.impugnados,
                                estado_acta=excluded.estado_acta,
                                fetched_at=excluded.fetched_at
                            """,
                            (
                                codigo_mesa,
                                str(row.get("ubigeo", "")).strip(),
                                str(row.get("local_votacion", "")).strip(),
                                int(str(row.get("electores_habiles", "0")).strip() or 0),
                                int(str(row.get("votos_emitidos", "0")).strip() or 0),
                                int(str(row.get("votos_validos", "0")).strip() or 0),
                                int(str(row.get("blancos", "0")).strip() or 0),
                                int(str(row.get("nulos", "0")).strip() or 0),
                                int(str(row.get("impugnados", "0")).strip() or 0),
                                str(row.get("estado_acta", "")).strip(),
                                now,
                            ),
                        )
                        mesas_inserted += 1

            agrupaciones_file = output_dir / "agrupaciones.txt"
            if agrupaciones_file.exists():
                with agrupaciones_file.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle, delimiter="\t")
                    for row in reader:
                        partido_id = str(row.get("partido_id", "")).strip()
                        if not partido_id:
                            continue
                        conn.execute(
                            """
                            INSERT INTO agrupaciones (partido_id, nombre, fetched_at)
                            VALUES (?, ?, ?)
                            ON CONFLICT(partido_id) DO UPDATE SET
                                nombre=excluded.nombre,
                                fetched_at=excluded.fetched_at
                            """,
                            (partido_id, str(row.get("nombre", "")).strip(), now),
                        )
                        agrupaciones_inserted += 1

            if include_votes:
                votos_file = output_dir / "votos.txt"
                if votos_file.exists():
                    with votos_file.open("r", encoding="utf-8-sig", newline="") as handle:
                        reader = csv.DictReader(handle, delimiter="\t")
                        for row in reader:
                            codigo_mesa = str(row.get("codigo_mesa", "")).strip()
                            partido_id = str(row.get("partido_id", "")).strip()
                            votos_raw = str(row.get("votos", "0")).strip()
                            # Saltar filas de cabecera repetidas o malformadas
                            if not codigo_mesa or not partido_id or not votos_raw.lstrip("-").isdigit():
                                continue
                            conn.execute(
                                """
                                INSERT INTO votos (codigo_mesa, partido_id, votos, fetched_at)
                                VALUES (?, ?, ?, ?)
                                ON CONFLICT(codigo_mesa, partido_id) DO UPDATE SET
                                    votos=excluded.votos,
                                    fetched_at=excluded.fetched_at
                                """,
                                (
                                    codigo_mesa,
                                    partido_id,
                                    int(votos_raw),
                                    now,
                                ),
                            )
                            votos_inserted += 1

            foreign_file = output_dir / "ubigeo_extranjero.txt"
            if foreign_file.exists():
                with foreign_file.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle, delimiter="\t")
                    for row in reader:
                        ubigeo = str(row.get("ubigeo", "")).strip()
                        if not ubigeo:
                            continue
                        conn.execute(
                            """
                            INSERT INTO foreign_catalog (ubigeo, continente, pais, ciudad, fetched_at)
                            VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT(ubigeo) DO UPDATE SET
                                continente=excluded.continente,
                                pais=excluded.pais,
                                ciudad=excluded.ciudad,
                                fetched_at=excluded.fetched_at
                            """,
                            (
                                ubigeo,
                                str(row.get("Continente", "")).strip(),
                                str(row.get("pais", "")).strip(),
                                str(row.get("ciudad", "")).strip(),
                                now,
                            ),
                        )
                        foreign_inserted += 1

            conn.execute("DELETE FROM votos_by_ubigeo_partido")
            self._ensure_votes_by_ubigeo_partido_backfilled(conn)

            self.append_raw_event(
                "bootstrap_onpescraper_snapshot",
                {
                    "source": source,
                    "id_eleccion": id_eleccion,
                    "include_votes": include_votes,
                    "mesas": mesas_inserted,
                    "votos": votos_inserted,
                    "agrupaciones": agrupaciones_inserted,
                    "foreign_catalog": foreign_inserted,
                },
            )

        reniec_inserted = self.try_bootstrap_reniec(source_dir)
        self.fill_ubigeo_location_cache_from_reniec(source_dir)
        self.rebuild_prefix_summaries()

        return {
            "skipped": False,
            "mesas": mesas_inserted,
            "votos": votos_inserted,
            "agrupaciones": agrupaciones_inserted,
            "foreign_catalog": foreign_inserted,
            "reniec_ubigeos": reniec_inserted,
        }

    def bootstrap_from_atu_manera_csv(
        self,
        csv_path: Path | None = None,
        *,
        url: str = (
            "https://media.githubusercontent.com/media/ATuManera/"
            "Peru_elecciones2026/main/data/output/por_votacion/mesas_presidencial.csv"
        ),
        id_eleccion: int = 12,
        force: bool = False,
        timeout: int = 300,
    ) -> dict[str, int | bool]:
        """Carga 92,766 mesas presidenciales desde el CSV público de ATuManera/Peru_elecciones2026.

        Si csv_path es None, intenta descargarlo desde `url` (archivo Git-LFS).
        Requiere que curl_cffi o urllib esté disponible para la descarga.

        Columns esperadas: codigoMesa, ubigeoNivel03, nombreLocalVotacion,
        totalElectoresHabiles, totalVotosEmitidos, totalVotosValidos, estadoActa,
        detalle_N_nposicion, detalle_N_nvotos, detalle_N_descripcion (N=1..82).
        """
        with self._connect() as conn:
            mesas_existing = int(
                (conn.execute("SELECT COUNT(*) AS c FROM mesas_data").fetchone() or {"c": 0})["c"]
            )
            if not force and mesas_existing > 0:
                return {"skipped": True, "mesas": 0, "votos": 0, "agrupaciones": 0}

        # Descarga si no se proveyó ruta local
        _tmp_path: Path | None = None
        if csv_path is None or not csv_path.exists():
            import tempfile
            try:
                try:
                    from curl_cffi import requests as cffi_req
                    resp = cffi_req.get(url, impersonate="chrome124", timeout=timeout, stream=True)
                    resp.raise_for_status()
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
                    for chunk in resp.iter_content(chunk_size=1 << 20):
                        tmp.write(chunk)
                    tmp.close()
                    _tmp_path = Path(tmp.name)
                    csv_path = _tmp_path
                except ImportError:
                    from urllib.request import urlretrieve
                    tmp_file, _ = urlretrieve(url)  # noqa: S310
                    _tmp_path = Path(tmp_file)
                    csv_path = _tmp_path
            except Exception as exc:
                _logger.warning("bootstrap_from_atu_manera_csv: descarga falló: %s", exc)
                return {"skipped": True, "mesas": 0, "votos": 0, "agrupaciones": 0, "error": str(exc)}

        now = self.now_iso()
        mesas_inserted = 0
        votos_inserted = 0
        agrupaciones_seen: dict[str, str] = {}  # partido_id → nombre

        try:
            with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                fieldnames = reader.fieldnames or []
                # Detectar columnas detalle_N_* dinámicamente
                detalle_indices: list[int] = sorted(
                    {
                        int(m.group(1))
                        for name in fieldnames
                        if (m := __import__("re").match(r"detalle_(\d+)_nvotos", name))
                    }
                )
                with self._connect() as conn:
                    for row in reader:
                        codigo_mesa = str(row.get("codigoMesa", "")).strip().zfill(6)
                        if not codigo_mesa or codigo_mesa == "000000":
                            continue
                        ubigeo = str(row.get("ubigeoNivel03", "")).strip()
                        local_votacion = str(row.get("nombreLocalVotacion", "")).strip()
                        electores = int(str(row.get("totalElectoresHabiles", "0")).strip() or 0)
                        votos_emitidos = int(str(row.get("totalVotosEmitidos", "0")).strip() or 0)
                        votos_validos = int(str(row.get("totalVotosValidos", "0")).strip() or 0)
                        estado_acta = str(row.get("estadoActa", "")).strip()

                        # Calcular blancos + nulos + impugnados desde detalle 80/81/82
                        blancos = int(str(row.get("detalle_80_nvotos", "0")).strip() or 0)
                        nulos = int(str(row.get("detalle_81_nvotos", "0")).strip() or 0)
                        impugnados = int(str(row.get("detalle_82_nvotos", "0")).strip() or 0)

                        conn.execute(
                            """INSERT INTO mesas_data (
                                codigo_mesa, ubigeo, local_votacion, electores_habiles,
                                votos_emitidos, votos_validos, blancos, nulos, impugnados,
                                estado_acta, fetched_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(codigo_mesa) DO UPDATE SET
                                ubigeo=excluded.ubigeo,
                                local_votacion=excluded.local_votacion,
                                electores_habiles=excluded.electores_habiles,
                                votos_emitidos=excluded.votos_emitidos,
                                votos_validos=excluded.votos_validos,
                                blancos=excluded.blancos,
                                nulos=excluded.nulos,
                                impugnados=excluded.impugnados,
                                estado_acta=excluded.estado_acta,
                                fetched_at=excluded.fetched_at""",
                            (
                                codigo_mesa, ubigeo, local_votacion, electores,
                                votos_emitidos, votos_validos, blancos, nulos, impugnados,
                                estado_acta, now,
                            ),
                        )
                        mesas_inserted += 1

                        # Insertar votos por partido (columnas detalle_N_*)
                        for n in detalle_indices:
                            pid_raw = str(row.get(f"detalle_{n}_nposicion", "")).strip()
                            votos_raw = str(row.get(f"detalle_{n}_nvotos", "")).strip()
                            nombre = str(row.get(f"detalle_{n}_descripcion", "")).strip()
                            if not pid_raw or not votos_raw:
                                continue
                            try:
                                pid = str(int(pid_raw))
                                nvotos = int(votos_raw)
                            except ValueError:
                                continue
                            if pid not in agrupaciones_seen and nombre:
                                agrupaciones_seen[pid] = nombre
                            conn.execute(
                                """INSERT INTO votos (codigo_mesa, partido_id, votos, fetched_at)
                                   VALUES (?, ?, ?, ?)
                                   ON CONFLICT(codigo_mesa, partido_id) DO UPDATE SET
                                       votos=excluded.votos, fetched_at=excluded.fetched_at""",
                                (codigo_mesa, pid, nvotos, now),
                            )
                            votos_inserted += 1

                    # Insertar agrupaciones descubiertas
                    for pid, nombre in agrupaciones_seen.items():
                        conn.execute(
                            """INSERT INTO agrupaciones (partido_id, nombre, fetched_at)
                               VALUES (?, ?, ?)
                               ON CONFLICT(partido_id) DO UPDATE SET
                                   nombre=excluded.nombre, fetched_at=excluded.fetched_at""",
                            (pid, nombre, now),
                        )
                    conn.execute("DELETE FROM votos_by_ubigeo_partido")
                    self._ensure_votes_by_ubigeo_partido_backfilled(conn)
        finally:
            if _tmp_path and _tmp_path.exists():
                try:
                    _tmp_path.unlink()
                except OSError:
                    pass

        self.append_raw_event(
            "bootstrap_atu_manera_csv",
            {"id_eleccion": id_eleccion, "mesas": mesas_inserted, "votos": votos_inserted,
             "agrupaciones": len(agrupaciones_seen)},
        )
        return {
            "skipped": False,
            "mesas": mesas_inserted,
            "votos": votos_inserted,
            "agrupaciones": len(agrupaciones_seen),
        }

    def aggregate_votes_by_party(self, ubigeos: set[str] | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            self._ensure_votes_by_ubigeo_partido_backfilled(conn)

            # Excluir siempre blancos (80), nulos (81) y viciados (82):
            # no son candidatos y distorsionan el ranking de partidos/candidatos.
            _NON_CANDIDATE_IDS = ("80", "81", "82")
            sql = (
                "SELECT v.partido_id AS partido_id, "
                "COALESCE(a.nombre, '') AS nombre_partido, "
                "SUM(v.total_votos) AS total_votos "
                "FROM votos_by_ubigeo_partido v "
                "LEFT JOIN agrupaciones a ON a.partido_id = v.partido_id "
                f"WHERE v.partido_id NOT IN ({','.join('?' for _ in _NON_CANDIDATE_IDS)}) "
            )
            params: list[Any] = list(_NON_CANDIDATE_IDS)
            if ubigeos:
                placeholders = ",".join("?" for _ in ubigeos)
                sql += f"AND v.ubigeo IN ({placeholders}) "
                params.extend(sorted(ubigeos))
            sql += "GROUP BY v.partido_id, a.nombre ORDER BY total_votos DESC"

            rows = conn.execute(sql, params).fetchall()

        result: list[dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "partido_id": str(row["partido_id"]),
                    "nombre_partido": str(row["nombre_partido"] or ""),
                    "total_votos": int(row["total_votos"] or 0),
                }
            )
        return result

    def count_mesas_by_ubigeos(self, ubigeos: set[str]) -> int:
        if not ubigeos:
            return 0

        placeholders = ",".join("?" for _ in ubigeos)
        sql = f"SELECT COUNT(*) AS c FROM mesas_data WHERE ubigeo IN ({placeholders})"
        with self._connect() as conn:
            row = conn.execute(sql, sorted(ubigeos)).fetchone()
        return int(row["c"] if row else 0)

    def find_ubigeos_by_prefix(self, prefix: str) -> list[str]:
        """Retorna ubigeos únicos de mesas_data que comienzan con el prefijo dado."""
        if not prefix:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT ubigeo FROM mesas_data WHERE ubigeo LIKE ?",
                (prefix + "%",),
            ).fetchall()
        return [str(row["ubigeo"]) for row in rows if row["ubigeo"]]

    def find_domestic_ubigeos_by_geo_name(self, query: str) -> tuple[str, list[str]] | None:
        """Busca ubigeos en ubigeo_reniec + ubigeo_onpe_api (departamento > provincia > distrito).
        Retorna (nombre_geo, lista_ubigeos) o None si no se encuentran coincidencias.
        Primero resuelve alias de ciudades populares (pucallpa → coronel portillo, etc.),
        luego prueba el query completo y por tokens."""
        q_norm = _norm_text(query)
        if not q_norm:
            return None

        # 0. Alias de ciudad popular → nombre administrativo oficial
        alias_term = _CITY_ALIASES.get(q_norm)
        if alias_term is None:
            # Intentar encontrar alias dentro de tokens del query
            for word in sorted(q_norm.split(), key=len, reverse=True):
                if word in _CITY_ALIASES:
                    alias_term = _CITY_ALIASES[word]
                    break

        with self._connect() as conn:
            # Verificar si las tablas tienen datos
            count_reniec = int(
                (conn.execute("SELECT COUNT(*) AS c FROM ubigeo_reniec").fetchone() or {"c": 0})["c"]
            )
            count_onpe = int(
                (conn.execute("SELECT COUNT(*) AS c FROM ubigeo_onpe_api").fetchone() or {"c": 0})["c"]
            )
            if count_reniec == 0 and count_onpe == 0:
                return None

            def _search_table(table: str, term: str) -> tuple[str, list[str]] | None:
                like_sub = f"%{term}%" if len(term) >= 6 else f"{term}%"
                rows = conn.execute(
                    f"SELECT ubigeo, departamento FROM {table} WHERE departamento_norm LIKE ? LIMIT 2000",
                    (like_sub,),
                ).fetchall()
                if rows:
                    return str(rows[0]["departamento"]).lower(), [str(r["ubigeo"]).lstrip("0") for r in rows]
                rows = conn.execute(
                    f"SELECT ubigeo, provincia FROM {table} WHERE provincia_norm LIKE ? LIMIT 2000",
                    (like_sub,),
                ).fetchall()
                if rows:
                    return str(rows[0]["provincia"]).lower(), [str(r["ubigeo"]).lstrip("0") for r in rows]
                rows = conn.execute(
                    f"SELECT ubigeo, distrito FROM {table} WHERE distrito_norm LIKE ? LIMIT 500",
                    (like_sub,),
                ).fetchall()
                if rows:
                    return str(rows[0]["distrito"]).lower(), [str(r["ubigeo"]).lstrip("0") for r in rows]
                return None

            def _search(term: str) -> tuple[str, list[str]] | None:
                if count_reniec > 0:
                    result = _search_table("ubigeo_reniec", term)
                    if result:
                        return result
                if count_onpe > 0:
                    result = _search_table("ubigeo_onpe_api", term)
                    if result:
                        return result
                return None

            # 1. Si hay un alias de ciudad conocida, usar ese término directamente
            if alias_term:
                result = _search(alias_term)
                if result:
                    return result

            # 2. Intento con el query completo normalizado
            result = _search(q_norm)
            if result:
                return result

            # 3. Fallback: probar tokens individuales (≥4 chars), más largos primero
            _STOPWORDS = {
                "dame", "de", "del", "el", "en", "es", "la", "las", "los",
                "para", "que", "quienes", "son", "hay", "quien", "una", "uno",
                "mesas", "resumen", "top", "fueron", "gano", "cuantas", "cuanto",
                "saco", "votos", "voto", "nivel", "total", "suma", "dato", "gana",
                "vote", "nacional", "ganador", "ganaron", "obtuvo",
                "cuantos", "cuanta", "tiene", "tuvo", "habia", "hubo",
                "cual", "como", "donde", "cuando", "cada", "hubo",
            }
            tokens = sorted(
                [t for t in q_norm.split() if len(t) >= 4 and t not in _STOPWORDS],
                key=len,
                reverse=True,
            )
            for token in tokens:
                result = _search(token)
                if result:
                    return result
        return None

    def upsert_domestic_ubigeos_from_api(self, rows: list[dict[str, str]]) -> int:
        """Inserta o actualiza ubigeos domésticos obtenidos de la API ONPE en ubigeo_onpe_api.
        Cada fila debe tener: ubigeo, distrito, provincia, departamento."""
        if not rows:
            return 0
        now = self.now_iso()
        inserted = 0
        with self._connect() as conn:
            for row in rows:
                ubigeo = str(row.get("ubigeo") or "").strip()
                if not ubigeo:
                    continue
                distrito = str(row.get("distrito") or "").strip()
                provincia = str(row.get("provincia") or "").strip()
                departamento = str(row.get("departamento") or "").strip()
                conn.execute(
                    """
                    INSERT INTO ubigeo_onpe_api (
                        ubigeo, distrito, provincia, departamento,
                        distrito_norm, provincia_norm, departamento_norm, fetched_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ubigeo) DO UPDATE SET
                        distrito=excluded.distrito,
                        provincia=excluded.provincia,
                        departamento=excluded.departamento,
                        distrito_norm=excluded.distrito_norm,
                        provincia_norm=excluded.provincia_norm,
                        departamento_norm=excluded.departamento_norm,
                        fetched_at=excluded.fetched_at
                    """,
                    (
                        ubigeo, distrito, provincia, departamento,
                        _norm_text(distrito), _norm_text(provincia), _norm_text(departamento),
                        now,
                    ),
                )
                inserted += 1
        return inserted

    def candidate_first_places_by_mesa_prefix(
        self,
        *,
        mesa_prefix: str,
        partido_ids: set[str],
        top_n: int = 10,
    ) -> dict[str, Any]:
        prefix = str(mesa_prefix or "").strip()
        if not prefix:
            raise ValueError("mesa_prefix no puede estar vacío")
        like_prefix = self._mesa_prefix_like(prefix)
        if not partido_ids:
            return {
                "mesa_prefix": prefix,
                "total_mesas_prefijo": 0,
                "mesas_con_votos": 0,
                "mesas_primero": 0,
                "lugares": [],
            }

        top_n = max(1, min(int(top_n), 50))

        with self._connect() as conn:
            # Use pre-computed totals if available (O(1))
            pt_row = conn.execute(
                "SELECT n_mesas, mesas_con_votos FROM mesa_prefix_totals WHERE prefix=?",
                (like_prefix,),
            ).fetchone() if 1 <= len(like_prefix) <= 4 else None

            if pt_row:
                total_mesas_prefijo = int(pt_row["n_mesas"] or 0)
                mesas_con_votos = int(pt_row["mesas_con_votos"] or 0)
            else:
                total_row = conn.execute(
                    "SELECT COUNT(*) AS c FROM mesas_data WHERE codigo_mesa LIKE ?",
                    (f"{like_prefix}%",),
                ).fetchone()
                total_mesas_prefijo = int(total_row["c"] if total_row else 0)
                mesas_con_votos = total_mesas_prefijo  # approx; full count not needed here

            placeholders = ",".join("?" for _ in partido_ids)

            # Fast path: use pre-computed mesa_winner table
            winner_check = conn.execute(
                "SELECT COUNT(*) AS c FROM mesa_winner LIMIT 1"
            ).fetchone()
            use_winner_table = winner_check and int(winner_check["c"] or 0) > 0

            if use_winner_table:
                rows = conn.execute(
                    f"""
                    SELECT
                        m.ubigeo,
                        COALESCE(m.local_votacion, '') AS local_votacion,
                        COALESCE(fc.continente, '') AS continente,
                        COALESCE(fc.pais, ul.pais, '') AS pais,
                        COALESCE(fc.ciudad, ul.ciudad, '') AS ciudad,
                        COALESCE(ul.departamento, '') AS departamento,
                        COUNT(*) AS mesas_primero
                    FROM mesa_winner mw
                    INNER JOIN mesas_data m ON m.codigo_mesa = mw.codigo_mesa
                    LEFT JOIN foreign_catalog fc ON fc.ubigeo = m.ubigeo
                    LEFT JOIN ubigeo_location_cache ul ON ul.ubigeo = m.ubigeo
                    WHERE m.codigo_mesa LIKE ?
                      AND mw.partido_id IN ({placeholders})
                    GROUP BY m.ubigeo, m.local_votacion, fc.continente, fc.pais, fc.ciudad, ul.pais, ul.ciudad, ul.departamento
                    ORDER BY mesas_primero DESC, pais ASC, ciudad ASC, m.ubigeo ASC
                    LIMIT ?
                    """,
                    [f"{like_prefix}%", *sorted(partido_ids), top_n],
                ).fetchall()

                mesas_primero_row = conn.execute(
                    f"""SELECT COUNT(*) AS c FROM mesa_winner mw
                        INNER JOIN mesas_data m ON m.codigo_mesa = mw.codigo_mesa
                        WHERE m.codigo_mesa LIKE ? AND mw.partido_id IN ({placeholders})""",
                    [f"{like_prefix}%", *sorted(partido_ids)],
                ).fetchone()
                mesas_primero = int(mesas_primero_row["c"] if mesas_primero_row else 0)
            else:
                # Fallback: slow CTE scan
                rows = conn.execute(
                    f"""
                    WITH mesas_pref AS (
                        SELECT m.codigo_mesa, m.ubigeo, m.local_votacion
                        FROM mesas_data m WHERE m.codigo_mesa LIKE ?
                    ),
                    mesa_top AS (
                        SELECT v.codigo_mesa, MAX(v.votos) AS max_votos
                        FROM votos v INNER JOIN mesas_pref mp ON mp.codigo_mesa = v.codigo_mesa
                        GROUP BY v.codigo_mesa
                    ),
                    candidate_hits AS (
                        SELECT DISTINCT mp.codigo_mesa, mp.ubigeo, mp.local_votacion
                        FROM mesas_pref mp
                        INNER JOIN mesa_top mt ON mt.codigo_mesa = mp.codigo_mesa
                        INNER JOIN votos v ON v.codigo_mesa = mt.codigo_mesa
                            AND v.votos = mt.max_votos AND v.partido_id IN ({placeholders})
                    )
                    SELECT
                        ch.ubigeo, COALESCE(ch.local_votacion,'') AS local_votacion,
                        COALESCE(fc.continente,'') AS continente,
                        COALESCE(fc.pais,ul.pais,'') AS pais,
                        COALESCE(fc.ciudad,ul.ciudad,'') AS ciudad,
                        COALESCE(ul.departamento,'') AS departamento,
                        COUNT(*) AS mesas_primero
                    FROM candidate_hits ch
                    LEFT JOIN foreign_catalog fc ON fc.ubigeo = ch.ubigeo
                    LEFT JOIN ubigeo_location_cache ul ON ul.ubigeo = ch.ubigeo
                    GROUP BY ch.ubigeo, ch.local_votacion, fc.continente, fc.pais, fc.ciudad, ul.pais, ul.ciudad, ul.departamento
                    ORDER BY mesas_primero DESC LIMIT ?
                    """,
                    [f"{like_prefix}%", *sorted(partido_ids), top_n],
                ).fetchall()
                mesas_primero = sum(int(r["mesas_primero"] or 0) for r in rows)

        lugares: list[dict[str, Any]] = []
        for row in rows:
            lugares.append(
                {
                    "ubigeo": str(row["ubigeo"] or ""),
                    "local_votacion": str(row["local_votacion"] or ""),
                    "continente": str(row["continente"] or ""),
                    "pais": str(row["pais"] or ""),
                    "ciudad": str(row["ciudad"] or ""),
                    "departamento": str(row["departamento"] or ""),
                    "mesas_primero": int(row["mesas_primero"] or 0),
                }
            )

        return {
            "mesa_prefix": prefix,
            "total_mesas_prefijo": total_mesas_prefijo,
            "mesas_con_votos": mesas_con_votos,
            "mesas_primero": mesas_primero,
            "lugares": lugares,
        }

    def all_first_places_by_prefix(self, mesa_prefix: str, top_n: int = 20) -> dict[str, Any]:
        """Ranking completo de candidatos por mesas donde quedaron primero en el prefijo dado."""
        prefix = str(mesa_prefix or "").strip()
        if not prefix:
            raise ValueError("mesa_prefix no puede estar vacío")
        top_n = max(1, min(int(top_n), 50))
        like_prefix = self._mesa_prefix_like(prefix)

        with self._connect() as conn:
            # Use pre-computed tables if available
            pt_row = conn.execute(
                "SELECT n_mesas, mesas_con_votos FROM mesa_prefix_totals WHERE prefix=?",
                (like_prefix,),
            ).fetchone() if 1 <= len(like_prefix) <= 4 else None

            total_mesas = int(pt_row["n_mesas"] or 0) if pt_row else int(
                (conn.execute(
                    "SELECT COUNT(*) AS c FROM mesas_data WHERE codigo_mesa LIKE ?",
                    (f"{like_prefix}%",),
                ).fetchone() or {"c": 0})["c"]
            )
            mesas_con_votos = int(pt_row["mesas_con_votos"] or 0) if pt_row else total_mesas

            winner_check = conn.execute("SELECT COUNT(*) AS c FROM mesa_winner LIMIT 1").fetchone()
            if winner_check and int(winner_check["c"] or 0) > 0:
                rows = conn.execute(
                    """
                    SELECT mw.partido_id, COALESCE(a.nombre,'') AS nombre_partido,
                           COUNT(*) AS mesas_primero
                    FROM mesa_winner mw
                    INNER JOIN mesas_data m ON m.codigo_mesa = mw.codigo_mesa
                    LEFT JOIN agrupaciones a ON a.partido_id = mw.partido_id
                    WHERE m.codigo_mesa LIKE ?
                      AND mw.partido_id NOT IN ('80','81','82')
                    GROUP BY mw.partido_id, a.nombre
                    ORDER BY mesas_primero DESC LIMIT ?
                    """,
                    (f"{like_prefix}%", top_n),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    WITH mesas_pref AS (SELECT codigo_mesa FROM mesas_data WHERE codigo_mesa LIKE ?),
                    mesa_max AS (
                        SELECT v.codigo_mesa, MAX(v.votos) AS max_votos
                        FROM votos v INNER JOIN mesas_pref mp ON mp.codigo_mesa = v.codigo_mesa
                        WHERE v.votos > 0 GROUP BY v.codigo_mesa
                    ),
                    winners AS (
                        SELECT v.codigo_mesa, v.partido_id FROM votos v
                        INNER JOIN mesa_max mm ON mm.codigo_mesa = v.codigo_mesa AND mm.max_votos = v.votos
                        WHERE v.partido_id NOT IN ('80','81','82')
                    )
                    SELECT w.partido_id, COALESCE(a.nombre,'') AS nombre_partido,
                           COUNT(DISTINCT w.codigo_mesa) AS mesas_primero
                    FROM winners w LEFT JOIN agrupaciones a ON a.partido_id = w.partido_id
                    GROUP BY w.partido_id, a.nombre ORDER BY mesas_primero DESC LIMIT ?
                    """,
                    (f"{like_prefix}%", top_n),
                ).fetchall()
        ranking = [
            {
                "partido_id": str(row["partido_id"]),
                "nombre_partido": str(row["nombre_partido"] or ""),
                "mesas_primero": int(row["mesas_primero"] or 0),
            }
            for row in rows
        ]
        return {
            "mesa_prefix": prefix,
            "total_mesas": total_mesas,
            "mesas_con_votos": mesas_con_votos,
            "ranking": ranking,
        }

    def describe_mesa_prefix(self, mesa_prefix: str, top_n_locations: int = 10) -> dict[str, Any]:
        """Describe las mesas de un prefijo: cuántas hay, dónde están, cuántos votos."""
        prefix = str(mesa_prefix or "").strip()
        if not prefix:
            raise ValueError("mesa_prefix no puede estar vacío")
        top_n_locations = max(1, min(int(top_n_locations), 50))
        with self._connect() as conn:
            total_row = conn.execute(
                "SELECT COUNT(*) AS c FROM mesas_data WHERE codigo_mesa LIKE ?",
                (f"{prefix}%",),
            ).fetchone()
            total_mesas = int(total_row["c"] if total_row else 0)
            votos_row = conn.execute(
                """
                SELECT SUM(m.votos_emitidos) AS total_votos, SUM(m.electores_habiles) AS total_electores
                FROM mesas_data m
                WHERE m.codigo_mesa LIKE ?
                """,
                (f"{prefix}%",),
            ).fetchone()
            total_votos = int((votos_row["total_votos"] or 0) if votos_row else 0)
            total_electores = int((votos_row["total_electores"] or 0) if votos_row else 0)
            loc_rows = conn.execute(
                """
                SELECT m.ubigeo, m.local_votacion,
                       COALESCE(fc.pais, '') AS pais,
                       COALESCE(fc.ciudad, '') AS ciudad,
                       COUNT(*) AS num_mesas,
                       SUM(m.votos_emitidos) AS votos_emitidos,
                       SUM(m.electores_habiles) AS electores_habiles
                FROM mesas_data m
                LEFT JOIN foreign_catalog fc ON fc.ubigeo = m.ubigeo
                WHERE m.codigo_mesa LIKE ?
                GROUP BY m.ubigeo, m.local_votacion, fc.pais, fc.ciudad
                ORDER BY num_mesas DESC
                LIMIT ?
                """,
                (f"{prefix}%", top_n_locations),
            ).fetchall()
        locations = [
            {
                "ubigeo": str(row["ubigeo"] or ""),
                "local_votacion": str(row["local_votacion"] or ""),
                "pais": str(row["pais"] or ""),
                "ciudad": str(row["ciudad"] or ""),
                "num_mesas": int(row["num_mesas"] or 0),
                "votos_emitidos": int(row["votos_emitidos"] or 0),
                "electores_habiles": int(row["electores_habiles"] or 0),
            }
            for row in loc_rows
        ]

        # Extra: breakdown by departamento (via ubigeo_location_cache)
        with self._connect() as conn:
            depto_rows = conn.execute(
                """
                SELECT
                  COALESCE(u.departamento, 'Sin departamento') AS depto,
                  COUNT(DISTINCT m.codigo_mesa) AS n_mesas,
                  SUM(m.electores_habiles) AS total_eh,
                  SUM(m.votos_emitidos) AS total_votos
                FROM mesas_data m
                LEFT JOIN ubigeo_location_cache u ON m.ubigeo = u.ubigeo
                WHERE m.codigo_mesa LIKE ?
                GROUP BY depto ORDER BY n_mesas DESC LIMIT 20
                """,
                (f"{prefix}%",),
            ).fetchall()
            eh_stats = conn.execute(
                """SELECT MIN(electores_habiles) as min_eh, MAX(electores_habiles) as max_eh,
                   ROUND(AVG(electores_habiles),1) as avg_eh
                   FROM mesas_data WHERE codigo_mesa LIKE ?""",
                (f"{prefix}%",),
            ).fetchone()

        departamentos = [
            {
                "departamento": str(r["depto"]),
                "n_mesas": int(r["n_mesas"] or 0),
                "total_electores_habiles": int(r["total_eh"] or 0),
                "total_votos_emitidos": int(r["total_votos"] or 0),
            }
            for r in depto_rows
        ]
        eh_min = int(eh_stats["min_eh"] or 0) if eh_stats else 0
        eh_max = int(eh_stats["max_eh"] or 0) if eh_stats else 0
        eh_avg = float(eh_stats["avg_eh"] or 0) if eh_stats else 0.0

        return {
            "mesa_prefix": prefix,
            "total_mesas": total_mesas,
            "total_votos_emitidos": total_votos,
            "total_electores_habiles": total_electores,
            "electores_min": eh_min,
            "electores_max": eh_max,
            "electores_avg": eh_avg,
            "locations": locations,
            "departamentos": departamentos,
        }

    def summarize_mesa_prefix(self, mesa_prefix: str, sample_size: int = 5) -> dict[str, Any]:
        """Resumen factual de un segmento de mesas: métricas, países, ciudades y muestra."""
        lp = self._mesa_prefix_like(mesa_prefix)
        pat = f"{lp}%"
        with self._connect() as conn:
            # Fast path for totals via pre-computed table
            counts = None
            if 1 <= len(lp) <= 4:
                row_pt = conn.execute(
                    "SELECT n_mesas, mesas_con_votos, votos_emitidos, votos_validos FROM mesa_prefix_totals WHERE prefix=?",
                    (lp,),
                ).fetchone()
                if row_pt:
                    counts = row_pt

            if counts is None:
                counts = conn.execute(
                    """SELECT COUNT(*) AS n_mesas,
                              SUM(CASE WHEN votos_emitidos>0 THEN 1 ELSE 0 END) AS mesas_con_votos,
                              COALESCE(SUM(votos_emitidos),0) AS votos_emitidos,
                              COALESCE(SUM(votos_validos),0) AS votos_validos
                       FROM mesas_data WHERE codigo_mesa LIKE ?""",
                    (pat,),
                ).fetchone()

            # Agrupar por ciudad/país (join con ubigeo_location_cache y foreign_catalog)
            city_rows = conn.execute(
                """SELECT COALESCE(ul.ciudad, fc.ciudad, '') AS geo_ciudad,
                          COALESCE(ul.pais, fc.pais, '') AS geo_pais,
                          COALESCE(ul.departamento, '') AS geo_departamento,
                          COUNT(*) AS num_mesas,
                          COALESCE(SUM(m.votos_emitidos), 0) AS votos_emitidos
                   FROM mesas_data m
                   LEFT JOIN ubigeo_location_cache ul ON ul.ubigeo = m.ubigeo
                   LEFT JOIN foreign_catalog fc ON fc.ubigeo = m.ubigeo
                   WHERE m.codigo_mesa LIKE ?
                   GROUP BY geo_ciudad, geo_pais, geo_departamento
                   ORDER BY num_mesas DESC
                   LIMIT 20""",
                (pat,),
            ).fetchall()
            # Muestra de mesas con ubicación
            sample_rows = conn.execute(
                """SELECT m.codigo_mesa, m.ubigeo, m.local_votacion,
                          m.votos_emitidos, m.votos_validos, m.estado_acta,
                          COALESCE(ul.ciudad, fc.ciudad, '') AS geo_ciudad,
                          COALESCE(ul.pais, fc.pais, '') AS geo_pais,
                          COALESCE(ul.departamento, '') AS geo_departamento
                   FROM mesas_data m
                   LEFT JOIN ubigeo_location_cache ul ON ul.ubigeo = m.ubigeo
                   LEFT JOIN foreign_catalog fc ON fc.ubigeo = m.ubigeo
                   WHERE m.codigo_mesa LIKE ?
                   ORDER BY m.codigo_mesa
                   LIMIT ?""",
                (pat, max(1, int(sample_size))),
            ).fetchall()

        # counts may come from mesa_prefix_totals (n_mesas) or fallback (total_mesas)
        def _ci(key1: str, key2: str) -> int:
            if counts is None:
                return 0
            try:
                v = counts[key1]
            except (IndexError, KeyError):
                try:
                    v = counts[key2]
                except (IndexError, KeyError):
                    v = 0
            return int(v or 0)

        total_mesas = _ci("n_mesas", "total_mesas")
        mesas_con_votos = _ci("mesas_con_votos", "mesas_con_votos")
        votos_emitidos = _ci("votos_emitidos", "votos_emitidos")
        votos_validos = _ci("votos_validos", "votos_validos")

        top_ciudades = [
            {
                "ciudad": row["geo_ciudad"],
                "pais": row["geo_pais"],
                "departamento": row["geo_departamento"],
                "num_mesas": row["num_mesas"],
                "votos_emitidos": row["votos_emitidos"],
            }
            for row in city_rows
        ]
        total_ciudades = len({(r["geo_ciudad"], r["geo_pais"]) for r in city_rows if r["geo_ciudad"] or r["geo_pais"]})
        total_paises = len({r["geo_pais"] for r in city_rows if r["geo_pais"]})

        sample = [
            {
                "codigo_mesa": row["codigo_mesa"],
                "ubigeo": row["ubigeo"],
                "local_votacion": row["local_votacion"],
                "votos_emitidos": row["votos_emitidos"],
                "votos_validos": row["votos_validos"],
                "estado_acta": row["estado_acta"],
                "ciudad": row["geo_ciudad"],
                "pais": row["geo_pais"],
                "departamento": row["geo_departamento"],
            }
            for row in sample_rows
        ]

        return {
            "mesa_prefix": mesa_prefix,
            "total_mesas": total_mesas,
            "mesas_con_votos": mesas_con_votos,
            "votos_emitidos": votos_emitidos,
            "votos_validos": votos_validos,
            "total_ciudades": total_ciudades,
            "total_paises": total_paises,
            "top_ciudades": top_ciudades,
            "sample": sample,
        }

    def get_top_candidates_for_prefix(
        self, mesa_prefix: str, top_n: int = 5, *, exclude_blancos_nulos: bool = True
    ) -> list[dict[str, Any]]:
        """Ranking de candidatos para un prefijo de mesa usando tabla pre-computada (O(1)).

        Fallback a scan de votos si la tabla no tiene datos para ese prefijo.
        """
        lp = self._mesa_prefix_like(mesa_prefix)
        top_n = max(1, min(int(top_n), 50))

        with self._connect() as conn:
            plen = len(lp)
            rows = None
            if 1 <= plen <= 4:
                rows = conn.execute(
                    """SELECT ps.partido_id, a.nombre, ps.total_votos, ps.n_mesas
                       FROM mesa_prefix_party_summary ps
                       LEFT JOIN agrupaciones a ON a.partido_id = ps.partido_id
                       WHERE ps.prefix = ?
                       ORDER BY ps.total_votos DESC""",
                    (lp,),
                ).fetchall()

            if not rows:
                # Fallback: scan votos (slow but correct)
                pat = f"{lp}%"
                rows = conn.execute(
                    """SELECT v.partido_id, a.nombre, SUM(v.votos) AS total_votos,
                              COUNT(DISTINCT v.codigo_mesa) AS n_mesas
                       FROM votos v LEFT JOIN agrupaciones a ON a.partido_id = v.partido_id
                       WHERE v.codigo_mesa LIKE ?
                       GROUP BY v.partido_id ORDER BY total_votos DESC""",
                    (pat,),
                ).fetchall()

        results = []
        rank = 1
        for row in rows:
            nombre = row["nombre"] or row["partido_id"] or ""
            if exclude_blancos_nulos:
                nom_low = nombre.lower()
                if any(k in nom_low for k in ("blanco", "nulo", "impugnad")):
                    continue
            results.append({
                "rank": rank,
                "partido_id": row["partido_id"],
                "nombre": nombre,
                "votos": int(row["total_votos"] or 0),
                "n_mesas": int(row["n_mesas"] or 0),
            })
            rank += 1
            if rank > top_n:
                break
        return results

    def get_coverage_metrics(
        self,
        *,
        prefix: str | None = None,
        ubigeos: set[str] | None = None,
    ) -> dict[str, Any]:
        """Métricas de cobertura para un segmento.

        Para queries por prefijo de 1-4 dígitos usa mesa_prefix_totals (O(1)).
        Para queries por ubigeo usa mesas_data directamente.
        """
        if not prefix and not ubigeos:
            return {
                "total_mesas": 0, "mesas_con_votos": 0,
                "votos_emitidos": 0, "votos_validos": 0, "coverage_pct": 0.0,
            }
        with self._connect() as conn:
            if prefix:
                lp = self._mesa_prefix_like(prefix)
                # Fast path: use pre-aggregated table if available
                plen = len(lp)
                if 1 <= plen <= 4:
                    row = conn.execute(
                        """SELECT n_mesas, mesas_con_votos, votos_emitidos, votos_validos
                           FROM mesa_prefix_totals WHERE prefix = ?""",
                        (lp,),
                    ).fetchone()
                    if row:
                        total_mesas = int(row["n_mesas"] or 0)
                        cov = int(row["mesas_con_votos"] or 0)
                        votos_emitidos = int(row["votos_emitidos"] or 0)
                        votos_validos = int(row["votos_validos"] or 0)
                        coverage_pct = round(cov / total_mesas * 100, 1) if total_mesas > 0 else 0.0
                        return {
                            "total_mesas": total_mesas,
                            "mesas_con_votos": cov,
                            "votos_emitidos": votos_emitidos,
                            "votos_validos": votos_validos,
                            "coverage_pct": coverage_pct,
                        }
                # Fallback: LIKE scan on mesas_data (still fast via PK index)
                pat = f"{lp}%"
                row2 = conn.execute(
                    """SELECT COUNT(*) AS n, SUM(CASE WHEN votos_emitidos>0 THEN 1 ELSE 0 END) AS cov,
                              COALESCE(SUM(votos_emitidos),0) AS ve, COALESCE(SUM(votos_validos),0) AS vv
                       FROM mesas_data WHERE codigo_mesa LIKE ?""", (pat,)
                ).fetchone()
                total_mesas = int((row2["n"] if row2 else 0) or 0)
                cov = int((row2["cov"] if row2 else 0) or 0)
                votos_emitidos = int((row2["ve"] if row2 else 0) or 0)
                votos_validos = int((row2["vv"] if row2 else 0) or 0)
            else:
                ph = ",".join("?" for _ in ubigeos)  # type: ignore[arg-type]
                args = sorted(ubigeos)  # type: ignore[arg-type]
                row2 = conn.execute(
                    f"""SELECT COUNT(*) AS n,
                               SUM(CASE WHEN votos_emitidos>0 THEN 1 ELSE 0 END) AS cov,
                               COALESCE(SUM(votos_emitidos),0) AS ve,
                               COALESCE(SUM(votos_validos),0) AS vv
                        FROM mesas_data WHERE ubigeo IN ({ph})""", args
                ).fetchone()
                total_mesas = int((row2["n"] if row2 else 0) or 0)
                cov = int((row2["cov"] if row2 else 0) or 0)
                votos_emitidos = int((row2["ve"] if row2 else 0) or 0)
                votos_validos = int((row2["vv"] if row2 else 0) or 0)
        coverage_pct = round(cov / total_mesas * 100, 1) if total_mesas > 0 else 0.0
        return {
            "total_mesas": total_mesas,
            "mesas_con_votos": cov,
            "votos_emitidos": votos_emitidos,
            "votos_validos": votos_validos,
            "coverage_pct": coverage_pct,
        }

    def get_uncovered_mesas(
        self,
        *,
        prefix: str | None = None,
        ubigeos: set[str] | None = None,
        limit: int = 20,
    ) -> list[str]:
        """Retorna códigos de mesas sin datos de votos en el segmento dado."""
        limit = max(1, min(int(limit), 200))
        with self._connect() as conn:
            if prefix:
                lp = self._mesa_prefix_like(prefix)
                rows = conn.execute(
                    """SELECT m.codigo_mesa FROM mesas_data m
                       WHERE m.codigo_mesa LIKE ?
                       AND NOT EXISTS (
                           SELECT 1 FROM votos v WHERE v.codigo_mesa = m.codigo_mesa AND v.votos > 0
                       )
                       ORDER BY m.codigo_mesa LIMIT ?""",
                    (f"{lp}%", limit),
                ).fetchall()
            elif ubigeos:
                ph = ",".join("?" for _ in ubigeos)
                rows = conn.execute(
                    f"""SELECT m.codigo_mesa FROM mesas_data m
                        WHERE m.ubigeo IN ({ph})
                        AND NOT EXISTS (
                            SELECT 1 FROM votos v WHERE v.codigo_mesa = m.codigo_mesa AND v.votos > 0
                        )
                        ORDER BY m.codigo_mesa LIMIT ?""",
                    [*sorted(ubigeos), limit],
                ).fetchall()
            else:
                return []
        return [str(row["codigo_mesa"]) for row in rows]


        prefix = str(mesa_prefix or "").strip()
        if not prefix:
            raise ValueError("mesa_prefix no puede estar vacío")
        like_prefix = self._mesa_prefix_like(prefix)

        sample_size = max(1, min(int(sample_size), 20))
        like_value = f"{like_prefix}%"

        with self._connect() as conn:
            total_row = conn.execute(
                "SELECT COUNT(*) AS c FROM mesas_data WHERE codigo_mesa LIKE ?",
                (like_value,),
            ).fetchone()
            total_mesas = int(total_row["c"] if total_row else 0)

            votos_row = conn.execute(
                """
                SELECT COUNT(DISTINCT v.codigo_mesa) AS c
                FROM votos v
                INNER JOIN mesas_data m ON m.codigo_mesa = v.codigo_mesa
                WHERE m.codigo_mesa LIKE ?
                """,
                (like_value,),
            ).fetchone()
            mesas_con_votos = int(votos_row["c"] if votos_row else 0)

            foreign_row = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM mesas_data m
                INNER JOIN foreign_catalog f ON f.ubigeo = m.ubigeo
                WHERE m.codigo_mesa LIKE ?
                """,
                (like_value,),
            ).fetchone()
            mesas_con_match_foreign_catalog = int(foreign_row["c"] if foreign_row else 0)

            totals_row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(COALESCE(m.votos_emitidos, 0)), 0) AS votos_emitidos,
                    COALESCE(SUM(COALESCE(m.votos_validos, 0)), 0) AS votos_validos
                FROM mesas_data m
                WHERE m.codigo_mesa LIKE ?
                """,
                (like_value,),
            ).fetchone()
            votos_emitidos = int(totals_row["votos_emitidos"] if totals_row else 0)
            votos_validos = int(totals_row["votos_validos"] if totals_row else 0)

            geo_row = conn.execute(
                """
                SELECT
                    COUNT(DISTINCT CASE WHEN COALESCE(f.pais, ul.pais, '') <> '' THEN COALESCE(f.pais, ul.pais) END) AS paises,
                    COUNT(DISTINCT CASE WHEN COALESCE(f.ciudad, ul.ciudad, '') <> '' THEN COALESCE(f.ciudad, ul.ciudad) END) AS ciudades
                FROM mesas_data m
                LEFT JOIN foreign_catalog f ON f.ubigeo = m.ubigeo
                LEFT JOIN ubigeo_location_cache ul ON ul.ubigeo = m.ubigeo
                WHERE m.codigo_mesa LIKE ?
                """,
                (like_value,),
            ).fetchone()
            total_paises = int(geo_row["paises"] if geo_row else 0)
            total_ciudades = int(geo_row["ciudades"] if geo_row else 0)

            top_city_rows = conn.execute(
                """
                SELECT
                    COALESCE(f.pais, ul.pais, '') AS pais,
                    COALESCE(f.ciudad, ul.ciudad, '') AS ciudad,
                    COALESCE(ul.departamento, '') AS departamento,
                    COUNT(*) AS mesas,
                    COALESCE(SUM(COALESCE(m.votos_emitidos, 0)), 0) AS votos_emitidos,
                    COALESCE(SUM(COALESCE(m.votos_validos, 0)), 0) AS votos_validos
                FROM mesas_data m
                LEFT JOIN foreign_catalog f ON f.ubigeo = m.ubigeo
                LEFT JOIN ubigeo_location_cache ul ON ul.ubigeo = m.ubigeo
                WHERE m.codigo_mesa LIKE ?
                GROUP BY COALESCE(f.pais, ul.pais, ''), COALESCE(f.ciudad, ul.ciudad, ''), COALESCE(ul.departamento, '')
                ORDER BY mesas DESC, votos_validos DESC, pais ASC, ciudad ASC
                LIMIT 5
                """,
                (like_value,),
            ).fetchall()

            sample_rows = conn.execute(
                """
                SELECT
                    m.codigo_mesa,
                    COALESCE(m.ubigeo, '') AS ubigeo,
                    COALESCE(m.local_votacion, '') AS local_votacion,
                    COALESCE(m.estado_acta, '') AS estado_acta,
                    CASE WHEN f.ubigeo IS NULL THEN 0 ELSE 1 END AS foreign_catalog_match,
                    COALESCE(f.continente, '') AS continente,
                    COALESCE(f.pais, ul.pais, '') AS pais,
                    COALESCE(f.ciudad, ul.ciudad, '') AS ciudad,
                    COALESCE(ul.departamento, '') AS departamento
                FROM mesas_data m
                LEFT JOIN foreign_catalog f ON f.ubigeo = m.ubigeo
                LEFT JOIN ubigeo_location_cache ul ON ul.ubigeo = m.ubigeo
                WHERE m.codigo_mesa LIKE ?
                ORDER BY m.codigo_mesa ASC
                LIMIT ?
                """,
                (like_value, sample_size),
            ).fetchall()

        sample: list[dict[str, Any]] = []
        for row in sample_rows:
            sample.append(
                {
                    "codigo_mesa": str(row["codigo_mesa"] or ""),
                    "ubigeo": str(row["ubigeo"] or ""),
                    "local_votacion": str(row["local_votacion"] or ""),
                    "estado_acta": str(row["estado_acta"] or ""),
                    "foreign_catalog_match": bool(int(row["foreign_catalog_match"] or 0)),
                    "continente": str(row["continente"] or ""),
                    "pais": str(row["pais"] or ""),
                    "ciudad": str(row["ciudad"] or ""),
                    "departamento": str(row["departamento"] or ""),
                }
            )

        top_ciudades: list[dict[str, Any]] = []
        for row in top_city_rows:
            top_ciudades.append(
                {
                    "pais": str(row["pais"] or ""),
                    "ciudad": str(row["ciudad"] or ""),
                    "departamento": str(row["departamento"] or ""),
                    "mesas": int(row["mesas"] or 0),
                    "votos_emitidos": int(row["votos_emitidos"] or 0),
                    "votos_validos": int(row["votos_validos"] or 0),
                }
            )

        return {
            "mesa_prefix": prefix,
            "total_mesas": total_mesas,
            "mesas_con_votos": mesas_con_votos,
            "votos_emitidos": votos_emitidos,
            "votos_validos": votos_validos,
            "total_paises": total_paises,
            "total_ciudades": total_ciudades,
            "mesas_con_match_foreign_catalog": mesas_con_match_foreign_catalog,
            "mesas_sin_match_foreign_catalog": max(0, total_mesas - mesas_con_match_foreign_catalog),
            "top_ciudades": top_ciudades,
            "sample": sample,
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # ─── SEGUNDA VUELTA METHODS ─────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════════════════

    def get_sv_sync_meta(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM sv_sync_meta WHERE key = ?", (key,)
            ).fetchone()
        return str(row["value"]) if row else None

    def set_sv_sync_meta(self, key: str, value: str) -> None:
        now = self.now_iso()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sv_sync_meta (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, value, now),
            )

    def bootstrap_sv_mesas(self, sv_output_dir: Path) -> int:
        """Load/UPSERT mesas_sv from mesas_data.txt. Returns rows_affected."""
        mesas_file = sv_output_dir / "mesas_data.txt"
        if not mesas_file.exists():
            return 0
        now = self.now_iso()
        count = 0
        with self._connect() as conn:
            with mesas_file.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    cm = str(row.get("codigo_mesa", "")).strip()
                    if not cm:
                        continue
                    conn.execute(
                        """INSERT INTO mesas_sv (
                            codigo_mesa, id_ubigeo, nombre_local, id_ambito,
                            electores_habiles, votos_emitidos, votos_validos,
                            total_asistentes, codigo_estado_acta, fetched_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(codigo_mesa) DO UPDATE SET
                            id_ubigeo=excluded.id_ubigeo,
                            nombre_local=excluded.nombre_local,
                            id_ambito=excluded.id_ambito,
                            electores_habiles=excluded.electores_habiles,
                            votos_emitidos=excluded.votos_emitidos,
                            votos_validos=excluded.votos_validos,
                            total_asistentes=excluded.total_asistentes,
                            codigo_estado_acta=excluded.codigo_estado_acta,
                            fetched_at=excluded.fetched_at""",
                        (
                            cm,
                            str(row.get("id_ubigeo", "")).strip(),
                            str(row.get("nombre_local_votacion", "")).strip(),
                            int(str(row.get("id_ambito_geografico", "1")).strip() or 1),
                            int(str(row.get("electores_habiles", "0")).strip() or 0),
                            int(str(row.get("votos_emitidos", "0")).strip() or 0),
                            int(str(row.get("votos_validos", "0")).strip() or 0),
                            int(str(row.get("total_asistentes", "0")).strip() or 0),
                            str(row.get("codigo_estado_acta", "")).strip(),
                            now,
                        ),
                    )
                    count += 1
        return count

    def bootstrap_sv_votos(self, sv_output_dir: Path) -> int:
        """Load/UPSERT votos_sv from votos.txt. Returns rows_affected."""
        votos_file = sv_output_dir / "votos.txt"
        if not votos_file.exists():
            return 0
        now = self.now_iso()
        count = 0
        with self._connect() as conn:
            with votos_file.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    cm = str(row.get("codigo_mesa", "")).strip()
                    pid = str(row.get("partido_id", "")).strip()
                    votos_raw = str(row.get("votos", "0")).strip()
                    if not cm or not pid or not votos_raw.lstrip("-").isdigit():
                        continue
                    conn.execute(
                        """INSERT INTO votos_sv (codigo_mesa, partido_id, votos, fetched_at)
                        VALUES (?,?,?,?)
                        ON CONFLICT(codigo_mesa, partido_id) DO UPDATE SET
                            votos=excluded.votos, fetched_at=excluded.fetched_at""",
                        (cm, pid, int(votos_raw), now),
                    )
                    count += 1
        return count

    def bootstrap_sv_agrupaciones(self, sv_output_dir: Path) -> int:
        agr_file = sv_output_dir / "agrupaciones.txt"
        if not agr_file.exists():
            return 0
        now = self.now_iso()
        count = 0
        with self._connect() as conn:
            with agr_file.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    pid = str(row.get("partido_id", "")).strip()
                    if not pid:
                        continue
                    conn.execute(
                        """INSERT INTO agrupaciones_sv (partido_id, nombre, fetched_at)
                        VALUES (?,?,?)
                        ON CONFLICT(partido_id) DO UPDATE SET nombre=excluded.nombre, fetched_at=excluded.fetched_at""",
                        (pid, str(row.get("nombre", "")).strip(), now),
                    )
                    count += 1
        return count

    def bootstrap_sv_ubicaciones(self, sv_output_dir: Path) -> int:
        ub_file = sv_output_dir / "ubicaciones.txt"
        if not ub_file.exists():
            return 0
        now = self.now_iso()
        count = 0
        with self._connect() as conn:
            with ub_file.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    ubigeo = str(row.get("ubigeo", "")).strip()
                    if not ubigeo:
                        continue
                    conn.execute(
                        """INSERT INTO ubicaciones_sv (ubigeo, ambito, departamento, provincia, distrito, continente, pais, ciudad, fetched_at)
                        VALUES (?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(ubigeo) DO UPDATE SET
                            ambito=excluded.ambito, departamento=excluded.departamento,
                            provincia=excluded.provincia, distrito=excluded.distrito,
                            continente=excluded.continente, pais=excluded.pais,
                            ciudad=excluded.ciudad, fetched_at=excluded.fetched_at""",
                        (
                            ubigeo,
                            str(row.get("ambito", "")).strip(),
                            str(row.get("departamento", "")).strip(),
                            str(row.get("provincia", "")).strip(),
                            str(row.get("distrito", "")).strip(),
                            str(row.get("continente", "")).strip(),
                            str(row.get("pais", "")).strip(),
                            str(row.get("ciudad", "")).strip(),
                            now,
                        ),
                    )
                    count += 1
        return count

    def bootstrap_sv_reasignados(self, sv_output_dir: Path) -> int:
        reass_file = sv_output_dir / "locales_reasignados_segunda_vuelta_2026.txt"
        if not reass_file.exists():
            return 0
        count = 0
        with self._connect() as conn:
            with reass_file.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    nro_raw = str(row.get("nro", "")).strip()
                    if not nro_raw.isdigit():
                        continue
                    conn.execute(
                        """INSERT INTO locales_reasignados_sv (
                            nro, odpe, dpto, provincia, distrito, ccpp,
                            nombre_local_original, nombre_local_nuevo, motivo, mesas_afectadas, estado_parseo
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(nro) DO UPDATE SET
                            odpe=excluded.odpe, dpto=excluded.dpto, provincia=excluded.provincia,
                            distrito=excluded.distrito, ccpp=excluded.ccpp,
                            nombre_local_original=excluded.nombre_local_original,
                            nombre_local_nuevo=excluded.nombre_local_nuevo,
                            motivo=excluded.motivo, mesas_afectadas=excluded.mesas_afectadas,
                            estado_parseo=excluded.estado_parseo""",
                        (
                            int(nro_raw),
                            str(row.get("odpe", "")).strip(),
                            str(row.get("dpto", "")).strip(),
                            str(row.get("provincia", "")).strip(),
                            str(row.get("distrito", "")).strip(),
                            str(row.get("ccpp", "")).strip(),
                            str(row.get("nombre_local_votacion", "")).strip(),
                            str(row.get("nombre_local_votacion_nuevo", "")).strip(),
                            str(row.get("motivo", "")).strip(),
                            int(str(row.get("mesas_a_reasignar", "0")).strip() or 0),
                            str(row.get("estado_parseo", "")).strip(),
                        ),
                    )
                    count += 1
        return count

    def bootstrap_resumen_sv(self, sv_resumen_dir: Path) -> dict[str, int]:
        """Load all 4 resumen files transactionally. Full replace."""

        def _safe_int(value: Any) -> int:
            raw = str(value or "").strip()
            if not raw:
                return 0
            try:
                return int(float(raw))
            except ValueError:
                return 0

        def _safe_float(value: Any) -> float:
            raw = str(value or "").strip()
            if not raw:
                return 0.0
            try:
                return float(raw)
            except ValueError:
                return 0.0

        def _infer_pid(row: dict[str, Any], fallback_index: int) -> str:
            pid = str(row.get("partido_id", "")).strip()
            if pid:
                return pid
            label = _norm_text(
                str(row.get("nombre_agrupacion_politica", "")).strip()
                or str(row.get("nombre_candidato", "")).strip()
            )
            explicit = {
                "fuerza popular": "8",
                "keiko sofia fujimori higuchi": "8",
                "juntos por el peru": "10",
                "roberto helbert sanchez palomino": "10",
                "votos en blanco": "80",
                "votos nulos": "81",
                "votos impugnados": "82",
            }
            return explicit.get(label, f"sv_nacional_{fallback_index}")

        now = self.now_iso()
        counts: dict[str, int] = {"nacional": 0, "departamentos": 0, "provincias": 0, "cobertura": 0}

        nac_file = sv_resumen_dir / "resumen_nacional.txt"
        nacionales: list[tuple[Any, ...]] = []
        if nac_file.exists():
            with nac_file.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for idx, row in enumerate(reader, start=1):
                    pid = _infer_pid(row, idx)
                    nacionales.append((
                        pid,
                        str(row.get("nombre_candidato", "")).strip(),
                        str(row.get("nombre_agrupacion_politica", "")).strip(),
                        _safe_int(row.get("votos_validos", "0")),
                        _safe_float(row.get("pct_votos_validos", "0")),
                        _safe_float(row.get("pct_votos_emitidos", "0")),
                        _safe_float(row.get("actas_contabilizadas_pct", "0")),
                        _safe_int(row.get("contabilizadas", "0")),
                        _safe_int(row.get("total_actas", "0")),
                        _safe_float(row.get("participacion_ciudadana", "0")),
                        str(row.get("fecha_actualizacion", "")).strip(),
                        str(row.get("fuente", "")).strip(),
                        now,
                    ))

        dept_file = sv_resumen_dir / "resumen_departamentos.txt"
        departamentos: list[tuple[Any, ...]] = []
        if dept_file.exists():
            with dept_file.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    ubigeo = str(row.get("ubigeo", "")).strip()
                    pid = str(row.get("partido_id", "")).strip()
                    if not ubigeo or not pid:
                        continue
                    departamentos.append((
                        ubigeo, pid,
                        str(row.get("nombre_candidato", "")).strip(),
                        str(row.get("nombre_agrupacion_politica", "")).strip(),
                        _safe_int(row.get("votos_validos", "0")),
                        _safe_float(row.get("pct_votos_validos", "0")),
                        _safe_float(row.get("pct_votos_emitidos", "0")),
                        _safe_int(row.get("total_votos_validos_geo", "0")),
                        _safe_int(row.get("total_votos_emitidos_geo", "0")),
                        str(row.get("fuente", "")).strip(),
                        now,
                    ))

        prov_file = sv_resumen_dir / "resumen_provincias.txt"
        provincias: list[tuple[Any, ...]] = []
        if prov_file.exists():
            with prov_file.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    ubigeo = str(row.get("ubigeo", "")).strip()
                    pid = str(row.get("partido_id", "")).strip()
                    if not ubigeo or not pid:
                        continue
                    provincias.append((
                        ubigeo, pid,
                        str(row.get("nombre_candidato", "")).strip(),
                        str(row.get("nombre_agrupacion_politica", "")).strip(),
                        "",
                        _safe_int(row.get("votos_validos", "0")),
                        _safe_float(row.get("pct_votos_validos", "0")),
                        _safe_float(row.get("pct_votos_emitidos", "0")),
                        _safe_int(row.get("total_votos_validos_geo", "0")),
                        _safe_int(row.get("total_votos_emitidos_geo", "0")),
                        str(row.get("fuente", "")).strip(),
                        now,
                    ))

        cob_file = sv_resumen_dir / "resumen_cobertura_departamentos.txt"
        coberturas: list[tuple[Any, ...]] = []
        if cob_file.exists():
            with cob_file.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    ubigeo = str(row.get("ubigeo", "")).strip()
                    if not ubigeo:
                        continue
                    coberturas.append((
                        ubigeo,
                        str(row.get("nombre_departamento", "")).strip(),
                        _safe_int(row.get("actas_contabilizadas", "0")),
                        _safe_float(row.get("pct_actas_contabilizadas", "0")),
                        str(row.get("fuente", "")).strip(),
                        now,
                    ))

        with self._connect() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM sv_resumen_nacional")
                if nacionales:
                    conn.executemany(
                        """INSERT INTO sv_resumen_nacional
                        (partido_id, nombre_candidato, nombre_agrupacion, votos_validos,
                         pct_votos_validos, pct_votos_emitidos, actas_contabilizadas_pct,
                         contabilizadas, total_actas, participacion_ciudadana,
                         fecha_actualizacion, fuente, loaded_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        nacionales,
                    )
                    counts["nacional"] = len(nacionales)

                conn.execute("DELETE FROM sv_resumen_departamentos")
                if departamentos:
                    conn.executemany(
                        """INSERT INTO sv_resumen_departamentos
                        (ubigeo, partido_id, nombre_candidato, nombre_agrupacion,
                         votos_validos, pct_votos_validos, pct_votos_emitidos,
                         total_votos_validos_geo, total_votos_emitidos_geo, fuente, loaded_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        departamentos,
                    )
                    counts["departamentos"] = len(departamentos)

                conn.execute("DELETE FROM sv_resumen_provincias")
                if provincias:
                    conn.executemany(
                        """INSERT INTO sv_resumen_provincias
                        (ubigeo, partido_id, nombre_candidato, nombre_agrupacion, nombre_geo,
                         votos_validos, pct_votos_validos, pct_votos_emitidos,
                         total_votos_validos_geo, total_votos_emitidos_geo, fuente, loaded_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        provincias,
                    )
                    # Populate nombre_geo: ubigeo_reniec/ubicaciones_sv have district-level
                    # ubigeos, while sv_resumen_provincias has province/country ubigeos.
                    # Match on first 4 chars (province prefix) to find a representative row.
                    conn.execute(
                        """UPDATE sv_resumen_provincias
                        SET nombre_geo = COALESCE(
                            NULLIF((
                                SELECT CASE
                                    WHEN substr(sv_resumen_provincias.ubigeo, 1, 1) = '9'
                                        THEN COALESCE(NULLIF(u.pais, ''), NULLIF(u.ciudad, ''), NULLIF(u.continente, ''))
                                    ELSE COALESCE(NULLIF(u.provincia, ''), NULLIF(u.departamento, ''), NULLIF(u.distrito, ''))
                                END
                                FROM ubicaciones_sv u
                                WHERE u.ubigeo LIKE SUBSTR(sv_resumen_provincias.ubigeo, 1, 4) || '%'
                                LIMIT 1
                            ), ''),
                            NULLIF(nombre_geo, '')
                        )
                        WHERE nombre_geo IS NULL OR nombre_geo = ''"""
                    )
                    counts["provincias"] = len(provincias)

                conn.execute("DELETE FROM sv_resumen_cobertura")
                if coberturas:
                    conn.executemany(
                        """INSERT INTO sv_resumen_cobertura
                        (ubigeo, nombre_departamento, actas_contabilizadas,
                         pct_actas_contabilizadas, fuente, loaded_at)
                        VALUES (?,?,?,?,?,?)""",
                        coberturas,
                    )
                    counts["cobertura"] = len(coberturas)
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        return counts

    def populate_sv_nombre_geo(self) -> int:
        """Populate nombre_geo in sv_resumen_provincias for existing rows.

        Uses LIKE on first 4 chars of ubigeo to match district-level rows in
        ubicaciones_sv (which don't have exact province-level ubigeo matches).
        Returns number of rows updated.
        """
        with self._connect() as conn:
            result = conn.execute(
                """UPDATE sv_resumen_provincias
                SET nombre_geo = COALESCE(
                    NULLIF((
                        SELECT CASE
                            WHEN substr(sv_resumen_provincias.ubigeo, 1, 1) = '9'
                                THEN COALESCE(NULLIF(u.pais, ''), NULLIF(u.ciudad, ''), NULLIF(u.continente, ''))
                            ELSE COALESCE(NULLIF(u.provincia, ''), NULLIF(u.departamento, ''), NULLIF(u.distrito, ''))
                        END
                        FROM ubicaciones_sv u
                        WHERE u.ubigeo LIKE SUBSTR(sv_resumen_provincias.ubigeo, 1, 4) || '%'
                        LIMIT 1
                    ), ''),
                    NULLIF(nombre_geo, '')
                )
                WHERE nombre_geo IS NULL OR nombre_geo = ''"""
            )
            return result.rowcount


        """Rebuild sv_agg_distrito and sv_agg_ciudad via CTAS from raw tables."""
        now = self.now_iso()
        with self._connect() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DROP TABLE IF EXISTS _sv_base")
                conn.execute(
                    """
                    CREATE TEMP TABLE _sv_base AS
                    SELECT
                        m.codigo_mesa,
                        m.id_ubigeo AS ubigeo,
                        COALESCE(u.departamento, '') AS departamento,
                        COALESCE(u.provincia, '') AS provincia,
                        COALESCE(u.distrito, '') AS distrito,
                        COALESCE(NULLIF(u.ciudad, ''), NULLIF(u.distrito, ''), NULLIF(u.provincia, ''), '') AS ciudad,
                        m.codigo_estado_acta,
                        v.partido_id,
                        COALESCE(a.nombre, COALESCE(v.partido_id, '')) AS nombre_candidato,
                        COALESCE(v.votos, 0) AS votos
                    FROM mesas_sv m
                    LEFT JOIN ubicaciones_sv u ON u.ubigeo = m.id_ubigeo
                    LEFT JOIN votos_sv v ON v.codigo_mesa = m.codigo_mesa
                    LEFT JOIN agrupaciones_sv a ON a.partido_id = v.partido_id
                    """
                )

                conn.execute("DROP TABLE IF EXISTS sv_agg_distrito_new")
                conn.execute(
                    """CREATE TABLE sv_agg_distrito_new (
                        ubigeo TEXT NOT NULL,
                        partido_id TEXT NOT NULL,
                        nombre_candidato TEXT,
                        votos INTEGER,
                        total_mesas INTEGER,
                        mesas_contabilizadas INTEGER,
                        rebuilt_at TEXT NOT NULL,
                        PRIMARY KEY (ubigeo, partido_id)
                    )"""
                )
                conn.execute(
                    f"""
                    INSERT INTO sv_agg_distrito_new
                    (ubigeo, partido_id, nombre_candidato, votos, total_mesas, mesas_contabilizadas, rebuilt_at)
                    SELECT
                        ubigeo,
                        partido_id,
                        MAX(nombre_candidato) AS nombre_candidato,
                        SUM(votos) AS votos,
                        COUNT(DISTINCT codigo_mesa) AS total_mesas,
                        COUNT(DISTINCT CASE WHEN codigo_estado_acta='C' THEN codigo_mesa END) AS mesas_contabilizadas,
                        '{now}' AS rebuilt_at
                    FROM _sv_base
                    WHERE partido_id IS NOT NULL AND partido_id != '' AND ubigeo != ''
                    GROUP BY ubigeo, partido_id
                    """
                )
                conn.execute("DROP TABLE IF EXISTS sv_agg_distrito")
                conn.execute("ALTER TABLE sv_agg_distrito_new RENAME TO sv_agg_distrito")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sv_agg_distrito_ubigeo ON sv_agg_distrito (ubigeo)")

                conn.execute("DROP TABLE IF EXISTS sv_agg_ciudad_new")
                conn.execute(
                    """CREATE TABLE sv_agg_ciudad_new (
                        ubigeo TEXT NOT NULL,
                        ciudad TEXT NOT NULL,
                        partido_id TEXT NOT NULL,
                        nombre_candidato TEXT,
                        votos INTEGER,
                        total_mesas INTEGER,
                        mesas_contabilizadas INTEGER,
                        rebuilt_at TEXT NOT NULL,
                        PRIMARY KEY (ubigeo, ciudad, partido_id)
                    )"""
                )
                conn.execute(
                    f"""
                    INSERT INTO sv_agg_ciudad_new
                    (ubigeo, ciudad, partido_id, nombre_candidato, votos, total_mesas, mesas_contabilizadas, rebuilt_at)
                    SELECT
                        ubigeo,
                        ciudad,
                        partido_id,
                        MAX(nombre_candidato) AS nombre_candidato,
                        SUM(votos) AS votos,
                        COUNT(DISTINCT codigo_mesa) AS total_mesas,
                        COUNT(DISTINCT CASE WHEN codigo_estado_acta='C' THEN codigo_mesa END) AS mesas_contabilizadas,
                        '{now}' AS rebuilt_at
                    FROM _sv_base
                    WHERE partido_id IS NOT NULL AND partido_id != '' AND ciudad != ''
                    GROUP BY ubigeo, ciudad, partido_id
                    """
                )
                conn.execute("DROP TABLE IF EXISTS sv_agg_ciudad")
                conn.execute("ALTER TABLE sv_agg_ciudad_new RENAME TO sv_agg_ciudad")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sv_agg_ciudad_ubigeo ON sv_agg_ciudad (ubigeo)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sv_agg_ciudad_nombre ON sv_agg_ciudad (ciudad)")

                n_dist = conn.execute("SELECT COUNT(*) AS c FROM sv_agg_distrito").fetchone()["c"]
                n_city = conn.execute("SELECT COUNT(*) AS c FROM sv_agg_ciudad").fetchone()["c"]
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        return {"distrito": int(n_dist), "ciudad": int(n_city)}

    def get_mesa_sv_from_local(self, codigo_mesa: str) -> dict[str, Any] | None:
        """Build SV mesa bundle from local tables."""
        with self._connect() as conn:
            mesa_row = conn.execute(
                "SELECT * FROM mesas_sv WHERE codigo_mesa = ?", (codigo_mesa,)
            ).fetchone()
            if mesa_row is None:
                return None

            votos_rows = conn.execute(
                """SELECT v.partido_id, COALESCE(a.nombre,'') AS nombre_partido, v.votos
                   FROM votos_sv v
                   LEFT JOIN agrupaciones_sv a ON a.partido_id = v.partido_id
                   WHERE v.codigo_mesa = ?
                   ORDER BY v.votos DESC""",
                (codigo_mesa,),
            ).fetchall()

            ub = str(mesa_row["id_ubigeo"] or "")
            loc_row = conn.execute(
                "SELECT departamento, provincia, distrito, ciudad FROM ubicaciones_sv WHERE ubigeo = ?",
                (ub,),
            ).fetchone()

        mesa_data: dict[str, Any] = {
            "codigo_mesa": codigo_mesa,
            "ubigeo": ub,
            "nombre_local": str(mesa_row["nombre_local"] or ""),
            "electores_habiles": int(mesa_row["electores_habiles"] or 0),
            "votos_emitidos": int(mesa_row["votos_emitidos"] or 0),
            "votos_validos": int(mesa_row["votos_validos"] or 0),
            "codigo_estado_acta": str(mesa_row["codigo_estado_acta"] or ""),
            "id_eleccion": 10,
        }
        if loc_row:
            mesa_data.update({
                "departamento": str(loc_row["departamento"] or ""),
                "provincia": str(loc_row["provincia"] or ""),
                "distrito": str(loc_row["distrito"] or ""),
                "ciudad": str(loc_row["ciudad"] or ""),
            })

        votos = [
            {"partido_id": str(r["partido_id"]), "nombre_partido": str(r["nombre_partido"]), "votos": int(r["votos"] or 0)}
            for r in votos_rows
        ]

        return {
            "codigo_mesa": codigo_mesa,
            "found": True,
            "mesa_data": mesa_data,
            "agrupaciones": [{"partido_id": v["partido_id"], "nombre": v["nombre_partido"]} for v in votos],
            "votos": votos,
            "source": "local_db_sv",
            "id_eleccion": 10,
        }

    def query_sv_nacional(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT partido_id, nombre_candidato, nombre_agrupacion, votos_validos,
                   pct_votos_validos, pct_votos_emitidos, actas_contabilizadas_pct,
                   contabilizadas, total_actas, participacion_ciudadana, fecha_actualizacion
                   FROM sv_resumen_nacional
                   ORDER BY votos_validos DESC"""
            ).fetchall()
        return [dict(r) for r in rows]

    def query_sv_geo(self, nivel: str, ubigeo: str | None = None, nombre: str | None = None, top_n: int = 10) -> list[dict[str, Any]]:
        """
        Query SV results by geographic level.
        nivel: 'nacional' | 'continente' | 'pais_exterior' | 'departamento' | 'provincia' | 'distrito' | 'ciudad'
        """
        with self._connect() as conn:
            if nivel == "nacional":
                rows = conn.execute(
                    "SELECT partido_id, nombre_candidato, nombre_agrupacion, votos_validos, pct_votos_validos FROM sv_resumen_nacional ORDER BY votos_validos DESC"
                ).fetchall()
            elif nivel == "continente":
                if ubigeo:
                    rows = conn.execute(
                        "SELECT ubigeo, partido_id, nombre_candidato, nombre_agrupacion, votos_validos, pct_votos_validos FROM sv_resumen_departamentos WHERE ubigeo = ? ORDER BY votos_validos DESC",
                        (ubigeo,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT ubigeo, partido_id, nombre_candidato, nombre_agrupacion, votos_validos, pct_votos_validos FROM sv_resumen_departamentos WHERE CAST(ubigeo AS TEXT) >= '910000' ORDER BY ubigeo, votos_validos DESC"
                    ).fetchall()
            elif nivel == "departamento":
                if ubigeo:
                    rows = conn.execute(
                        "SELECT ubigeo, partido_id, nombre_candidato, nombre_agrupacion, votos_validos, pct_votos_validos, total_votos_validos_geo FROM sv_resumen_departamentos WHERE ubigeo = ? ORDER BY votos_validos DESC",
                        (ubigeo,),
                    ).fetchall()
                else:
                    # Fetch with nombre_departamento for Python-side accent-insensitive filtering
                    all_dept_rows = conn.execute(
                        """SELECT d.ubigeo, d.partido_id, d.nombre_candidato, d.nombre_agrupacion,
                                  d.votos_validos, d.pct_votos_validos,
                                  COALESCE(c.nombre_departamento,'') AS nombre_departamento
                           FROM sv_resumen_departamentos d
                           LEFT JOIN sv_resumen_cobertura c ON c.ubigeo = d.ubigeo
                           WHERE CAST(d.ubigeo AS TEXT) < '910000'
                           ORDER BY d.ubigeo, d.votos_validos DESC
                           LIMIT ?""",
                        (top_n * 30,),
                    ).fetchall()
                    if nombre:
                        norm_n = _norm_text(nombre)
                        rows = [r for r in all_dept_rows if norm_n in _norm_text(str(r["nombre_departamento"] or ""))]
                    else:
                        rows = all_dept_rows
            elif nivel == "provincia":
                if ubigeo:
                    rows = conn.execute(
                        "SELECT ubigeo, partido_id, nombre_candidato, nombre_agrupacion, nombre_geo, votos_validos, pct_votos_validos FROM sv_resumen_provincias WHERE ubigeo = ? ORDER BY votos_validos DESC",
                        (ubigeo,),
                    ).fetchall()
                elif nombre:
                    rows = conn.execute(
                        "SELECT ubigeo, partido_id, nombre_candidato, nombre_agrupacion, nombre_geo, votos_validos, pct_votos_validos FROM sv_resumen_provincias WHERE nombre_geo LIKE ? ORDER BY ubigeo, votos_validos DESC LIMIT ?",
                        (f"%{nombre}%", top_n * 5),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT ubigeo, partido_id, nombre_candidato, nombre_agrupacion, nombre_geo, votos_validos, pct_votos_validos FROM sv_resumen_provincias WHERE CAST(ubigeo AS TEXT) < '910000' ORDER BY ubigeo, votos_validos DESC LIMIT ?",
                        (top_n * 5,),
                    ).fetchall()
            elif nivel == "pais_exterior":
                if nombre:
                    rows = conn.execute(
                        "SELECT ubigeo, partido_id, nombre_candidato, nombre_agrupacion, nombre_geo, votos_validos, pct_votos_validos FROM sv_resumen_provincias WHERE CAST(ubigeo AS TEXT) >= '910000' AND nombre_geo LIKE ? ORDER BY votos_validos DESC",
                        (f"%{nombre}%",),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT ubigeo, partido_id, nombre_candidato, nombre_agrupacion, nombre_geo, votos_validos, pct_votos_validos FROM sv_resumen_provincias WHERE CAST(ubigeo AS TEXT) >= '910000' ORDER BY ubigeo, votos_validos DESC LIMIT ?",
                        (top_n * 5,),
                    ).fetchall()
            elif nivel == "distrito":
                if ubigeo:
                    rows = conn.execute(
                        "SELECT ubigeo, partido_id, nombre_candidato, votos, total_mesas, mesas_contabilizadas FROM sv_agg_distrito WHERE ubigeo = ? ORDER BY votos DESC",
                        (ubigeo,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT ubigeo, partido_id, nombre_candidato, votos, total_mesas FROM sv_agg_distrito ORDER BY votos DESC LIMIT ?",
                        (top_n * 3,),
                    ).fetchall()
            elif nivel == "ciudad":
                if nombre:
                    rows = conn.execute(
                        "SELECT ubigeo, ciudad, partido_id, nombre_candidato, votos, total_mesas FROM sv_agg_ciudad WHERE ciudad LIKE ? ORDER BY votos DESC LIMIT ?",
                        (f"%{nombre}%", top_n * 3),
                    ).fetchall()
                elif ubigeo:
                    rows = conn.execute(
                        "SELECT ubigeo, ciudad, partido_id, nombre_candidato, votos, total_mesas FROM sv_agg_ciudad WHERE ubigeo = ? ORDER BY votos DESC",
                        (ubigeo,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT ubigeo, ciudad, partido_id, nombre_candidato, votos, total_mesas FROM sv_agg_ciudad ORDER BY votos DESC LIMIT ?",
                        (top_n * 3,),
                    ).fetchall()
            else:
                rows = []

        return [dict(r) for r in rows]

    def get_sv_cobertura(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ubigeo, nombre_departamento, actas_contabilizadas, pct_actas_contabilizadas FROM sv_resumen_cobertura ORDER BY ubigeo"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_sv_reasignados(self, dpto: str | None = None, motivo: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if dpto:
                rows = conn.execute(
                    "SELECT * FROM locales_reasignados_sv WHERE UPPER(dpto) LIKE ? ORDER BY nro",
                    (f"%{dpto.upper()}%",),
                ).fetchall()
            elif motivo:
                rows = conn.execute(
                    "SELECT * FROM locales_reasignados_sv WHERE UPPER(motivo) LIKE ? ORDER BY nro",
                    (f"%{motivo.upper()}%",),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM locales_reasignados_sv ORDER BY nro").fetchall()
        return [dict(r) for r in rows]

    def total_mesas_sv_local(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM mesas_sv").fetchone()
        return int((row or {"c": 0})["c"])

    def get_sv_estado_actas(
        self,
        ubigeo_prefix: str | None = None,
        top_geo: int = 10,
    ) -> dict[str, Any]:
        """Resumen de estados de acta SV (C/E/P) y escenario "si JEE acepta todas las E".

        - C = Contabilizada
        - E = Para envío al JEE (observada)
        - P = Pendiente (aún no procesada)

        Args:
            ubigeo_prefix: Filtra por prefijo de ubigeo (2 dígitos = departamento,
                6 dígitos = distrito). None = nacional.
            top_geo: Top departamentos a incluir en `geo_top_jee` (solo cuando no
                se filtra por ubigeo). 0 desactiva el listado.

        Returns dict con:
            - totales: {mesas, contabilizadas_C, para_envio_jee_E, pendientes_P,
                        electores_habiles, votos_emitidos}
            - por_estado: lista [{codigo, descripcion, mesas, electores_habiles,
                                  votos_emitidos, votos_validos}]
            - votos_jee_pendientes: lista [{partido_id, nombre, votos}] (E)
            - escenario_jee_aceptadas: {
                actual: [{partido_id, nombre, votos, pct_validos}],
                con_jee_aceptadas: [{partido_id, nombre, votos, pct_validos}],
                margen_actual: {lider, ventaja, ventaja_pp},
                margen_si_aceptadas: {lider, ventaja, ventaja_pp},
              }
            - geo_top_jee: top departamentos con mesas E (solo si no se filtra)
            - fecha_actualizacion: timestamp ONPE de sv_resumen_nacional
            - filtro: {ubigeo_prefix}
        """
        descripciones_estado = {
            "C": "Contabilizada",
            "E": "Para envío al JEE",
            "P": "Pendiente",
        }

        like = None
        if ubigeo_prefix:
            ubigeo_prefix = str(ubigeo_prefix).strip()
            if ubigeo_prefix:
                like = f"{ubigeo_prefix}%"

        with self._connect() as conn:
            # 1) Conteos por estado
            if like:
                estado_rows = conn.execute(
                    """SELECT codigo_estado_acta, COUNT(*) AS mesas,
                       SUM(electores_habiles) AS electores_habiles,
                       SUM(votos_emitidos) AS votos_emitidos,
                       SUM(votos_validos) AS votos_validos
                       FROM mesas_sv WHERE id_ubigeo LIKE ?
                       GROUP BY codigo_estado_acta""",
                    (like,),
                ).fetchall()
            else:
                estado_rows = conn.execute(
                    """SELECT codigo_estado_acta, COUNT(*) AS mesas,
                       SUM(electores_habiles) AS electores_habiles,
                       SUM(votos_emitidos) AS votos_emitidos,
                       SUM(votos_validos) AS votos_validos
                       FROM mesas_sv
                       GROUP BY codigo_estado_acta"""
                ).fetchall()

            por_estado: list[dict[str, Any]] = []
            por_codigo: dict[str, dict[str, int]] = {}
            for r in estado_rows:
                cod = str(r["codigo_estado_acta"] or "").strip().upper()
                item = {
                    "codigo": cod,
                    "descripcion": descripciones_estado.get(cod, cod),
                    "mesas": int(r["mesas"] or 0),
                    "electores_habiles": int(r["electores_habiles"] or 0),
                    "votos_emitidos": int(r["votos_emitidos"] or 0),
                    "votos_validos": int(r["votos_validos"] or 0),
                }
                por_estado.append(item)
                por_codigo[cod] = item

            totales = {
                "mesas": sum(it["mesas"] for it in por_estado),
                "contabilizadas_C": por_codigo.get("C", {}).get("mesas", 0),
                "para_envio_jee_E": por_codigo.get("E", {}).get("mesas", 0),
                "pendientes_P": por_codigo.get("P", {}).get("mesas", 0),
                "electores_habiles": sum(it["electores_habiles"] for it in por_estado),
                "votos_emitidos": sum(it["votos_emitidos"] for it in por_estado),
            }

            # 2) Votos en mesas E por partido
            if like:
                jee_rows = conn.execute(
                    """SELECT v.partido_id, COALESCE(a.nombre,'') AS nombre,
                       SUM(v.votos) AS total_votos
                       FROM votos_sv v
                       JOIN mesas_sv m ON m.codigo_mesa = v.codigo_mesa
                       LEFT JOIN agrupaciones_sv a ON a.partido_id = v.partido_id
                       WHERE m.codigo_estado_acta = 'E' AND m.id_ubigeo LIKE ?
                       GROUP BY v.partido_id
                       ORDER BY total_votos DESC""",
                    (like,),
                ).fetchall()
            else:
                jee_rows = conn.execute(
                    """SELECT v.partido_id, COALESCE(a.nombre,'') AS nombre,
                       SUM(v.votos) AS total_votos
                       FROM votos_sv v
                       JOIN mesas_sv m ON m.codigo_mesa = v.codigo_mesa
                       LEFT JOIN agrupaciones_sv a ON a.partido_id = v.partido_id
                       WHERE m.codigo_estado_acta = 'E'
                       GROUP BY v.partido_id
                       ORDER BY total_votos DESC"""
                ).fetchall()

            votos_jee_pendientes = [
                {
                    "partido_id": str(r["partido_id"]),
                    "nombre": str(r["nombre"] or ""),
                    "votos": int(r["total_votos"] or 0),
                }
                for r in jee_rows
            ]

            # 3) Escenario actual (C) vs aceptadas (C+E) por partido
            if like:
                escenario_rows = conn.execute(
                    """SELECT v.partido_id, COALESCE(a.nombre,'') AS nombre,
                       SUM(CASE WHEN m.codigo_estado_acta='C' THEN v.votos ELSE 0 END) AS contabilizado,
                       SUM(CASE WHEN m.codigo_estado_acta='E' THEN v.votos ELSE 0 END) AS jee_pendiente
                       FROM votos_sv v
                       JOIN mesas_sv m ON m.codigo_mesa = v.codigo_mesa
                       LEFT JOIN agrupaciones_sv a ON a.partido_id = v.partido_id
                       WHERE m.id_ubigeo LIKE ?
                       GROUP BY v.partido_id""",
                    (like,),
                ).fetchall()
            else:
                escenario_rows = conn.execute(
                    """SELECT v.partido_id, COALESCE(a.nombre,'') AS nombre,
                       SUM(CASE WHEN m.codigo_estado_acta='C' THEN v.votos ELSE 0 END) AS contabilizado,
                       SUM(CASE WHEN m.codigo_estado_acta='E' THEN v.votos ELSE 0 END) AS jee_pendiente
                       FROM votos_sv v
                       JOIN mesas_sv m ON m.codigo_mesa = v.codigo_mesa
                       LEFT JOIN agrupaciones_sv a ON a.partido_id = v.partido_id
                       GROUP BY v.partido_id"""
                ).fetchall()

            # 4) Top departamentos con mesas E (solo nacional)
            geo_top_jee: list[dict[str, Any]] = []
            if not like and top_geo and int(top_geo) > 0:
                # Map de prefijo (2-3 dígitos) → nombre departamento/continente
                dpto_name_map: dict[str, str] = {}
                for r in conn.execute(
                    "SELECT ubigeo, nombre_departamento FROM sv_resumen_cobertura"
                ).fetchall():
                    ub_raw = str(r["ubigeo"] or "")
                    nombre_d = str(r["nombre_departamento"] or "")
                    if not ub_raw:
                        continue
                    # Departamentos peruanos: 6 dígitos, prefijo 2 dígitos. Continentes
                    # exterior (91-95): prefijo 2 dígitos también.
                    dpto_name_map[ub_raw[:2]] = nombre_d

                geo_rows = conn.execute(
                    """SELECT SUBSTR(id_ubigeo,1,2) AS dpto,
                       COUNT(*) AS mesas_E,
                       SUM(electores_habiles) AS electores_E
                       FROM mesas_sv WHERE codigo_estado_acta = 'E'
                       GROUP BY dpto ORDER BY mesas_E DESC LIMIT ?""",
                    (int(top_geo),),
                ).fetchall()

                # Votos E por departamento × partido finalista (8 Keiko, 10 Sánchez)
                votos_dpto_rows = conn.execute(
                    """SELECT SUBSTR(m.id_ubigeo,1,2) AS dpto, v.partido_id,
                       SUM(v.votos) AS votos
                       FROM votos_sv v
                       JOIN mesas_sv m ON m.codigo_mesa = v.codigo_mesa
                       WHERE m.codigo_estado_acta = 'E' AND v.partido_id IN ('8','10')
                       GROUP BY dpto, v.partido_id"""
                ).fetchall()
                votos_dpto: dict[tuple[str, str], int] = {
                    (str(r["dpto"]), str(r["partido_id"])): int(r["votos"] or 0)
                    for r in votos_dpto_rows
                }

                for r in geo_rows:
                    dpto = str(r["dpto"])
                    geo_top_jee.append({
                        "dpto_prefix": dpto,
                        "nombre": dpto_name_map.get(dpto, ""),
                        "mesas_E": int(r["mesas_E"] or 0),
                        "electores_E": int(r["electores_E"] or 0),
                        "votos_E_keiko": votos_dpto.get((dpto, "8"), 0),
                        "votos_E_sanchez": votos_dpto.get((dpto, "10"), 0),
                    })

            # 5) Última fecha de actualización oficial ONPE
            row_fa = conn.execute(
                "SELECT MAX(fecha_actualizacion) AS f FROM sv_resumen_nacional"
            ).fetchone()
            fecha_actualizacion = str((row_fa or {"f": ""})["f"] or "")

        # Construir escenario
        actual: list[dict[str, Any]] = []
        aceptadas: list[dict[str, Any]] = []
        for r in escenario_rows:
            pid = str(r["partido_id"])
            nombre = str(r["nombre"] or "")
            c = int(r["contabilizado"] or 0)
            e = int(r["jee_pendiente"] or 0)
            actual.append({"partido_id": pid, "nombre": nombre, "votos": c})
            aceptadas.append({"partido_id": pid, "nombre": nombre, "votos": c + e})

        # Solo candidatos (partido_id != 80/81/82) cuentan para % válidos
        def _pct_validos(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            total_validos = sum(it["votos"] for it in rows if it["partido_id"] not in ("80", "81", "82"))
            out = []
            for it in rows:
                if it["partido_id"] in ("80", "81", "82"):
                    pct = 0.0
                else:
                    pct = round(it["votos"] / total_validos * 100, 3) if total_validos > 0 else 0.0
                out.append({**it, "pct_validos": pct})
            return sorted(out, key=lambda x: x["votos"], reverse=True)

        actual_pct = _pct_validos(actual)
        aceptadas_pct = _pct_validos(aceptadas)

        def _margen(rows: list[dict[str, Any]]) -> dict[str, Any]:
            candidatos = [r for r in rows if r["partido_id"] not in ("80", "81", "82")]
            if len(candidatos) < 2:
                return {"lider": None, "ventaja": 0, "ventaja_pp": 0.0}
            primero, segundo = candidatos[0], candidatos[1]
            return {
                "lider": primero["partido_id"],
                "lider_nombre": primero["nombre"],
                "ventaja": primero["votos"] - segundo["votos"],
                "ventaja_pp": round(primero["pct_validos"] - segundo["pct_validos"], 3),
            }

        return {
            "filtro": {"ubigeo_prefix": ubigeo_prefix},
            "fecha_actualizacion": fecha_actualizacion,
            "totales": totales,
            "por_estado": por_estado,
            "votos_jee_pendientes": votos_jee_pendientes,
            "escenario_jee_aceptadas": {
                "actual": actual_pct,
                "con_jee_aceptadas": aceptadas_pct,
                "margen_actual": _margen(actual_pct),
                "margen_si_aceptadas": _margen(aceptadas_pct),
            },
            "geo_top_jee": geo_top_jee,
        }

    def get_comparacion_mesa(self, codigo_mesa: str) -> dict[str, Any]:
        """Compare 1V vs 2V results for the same mesa."""
        with self._connect() as conn:
            m1 = conn.execute("SELECT * FROM mesas_data WHERE codigo_mesa = ?", (codigo_mesa,)).fetchone()
            v1 = conn.execute(
                "SELECT v.partido_id, COALESCE(a.nombre,'') AS nombre, v.votos FROM votos v LEFT JOIN agrupaciones a ON a.partido_id = v.partido_id WHERE v.codigo_mesa = ? ORDER BY v.votos DESC",
                (codigo_mesa,),
            ).fetchall()
            m2 = conn.execute("SELECT * FROM mesas_sv WHERE codigo_mesa = ?", (codigo_mesa,)).fetchone()
            v2 = conn.execute(
                "SELECT v.partido_id, COALESCE(a.nombre,'') AS nombre, v.votos FROM votos_sv v LEFT JOIN agrupaciones_sv a ON a.partido_id = v.partido_id WHERE v.codigo_mesa = ? ORDER BY v.votos DESC",
                (codigo_mesa,),
            ).fetchall()

        result: dict[str, Any] = {
            "codigo_mesa": codigo_mesa,
            "primera_vuelta": None,
            "segunda_vuelta": None,
        }
        if m1:
            result["primera_vuelta"] = {
                "electores_habiles": int(m1["electores_habiles"] or 0),
                "votos_emitidos": int(m1["votos_emitidos"] or 0),
                "votos_validos": int(m1["votos_validos"] or 0),
                "estado_acta": str(m1["estado_acta"] or ""),
                "votos": [{"partido_id": str(r["partido_id"]), "nombre": str(r["nombre"]), "votos": int(r["votos"] or 0)} for r in v1],
            }
        if m2:
            result["segunda_vuelta"] = {
                "electores_habiles": int(m2["electores_habiles"] or 0),
                "votos_emitidos": int(m2["votos_emitidos"] or 0),
                "votos_validos": int(m2["votos_validos"] or 0),
                "codigo_estado_acta": str(m2["codigo_estado_acta"] or ""),
                "votos": [{"partido_id": str(r["partido_id"]), "nombre": str(r["nombre"]), "votos": int(r["votos"] or 0)} for r in v2],
            }
        return result

    def get_comparacion_geo(self, ubigeo_prefix: str) -> dict[str, Any]:
        """Compare 1V vs 2V aggregates for a geo prefix.

        Normalizes dept/province-level ubigeo codes so they match district-level
        ubigeos stored in votos_by_ubigeo_partido and sv_agg_distrito:
          '140000' → '14'  (Lima Metropolitana dept)
          '040000' → '04'  (Arequipa dept)
          '150100' → '1501' (Lima province)
          '140110' → '140110' (specific district, unchanged)
        """
        # Normalize: strip trailing zeros for dept/province codes so LIKE
        # matches district-level ubigeos (e.g., '14%' matches '140110')
        raw = str(ubigeo_prefix or "").strip()
        if len(raw) >= 6 and raw[2:] == "0000":       # dept code like '140000'
            normalized = raw[:2]
        elif len(raw) >= 6 and raw[4:] == "00" and raw[2:4] != "00":  # province like '150100'
            normalized = raw[:4]
        else:
            normalized = raw                           # district or short prefix

        # 1V mesas_data/votos_by_ubigeo_partido stores ubigeos with leading zeros stripped
        # (ONPE internal format): '040101' → '40101', '100101' stays '100101'
        # 2V mesas_sv/sv_resumen_provincias uses RENIEC 6-digit format with leading zeros
        normalized_1v = normalized.lstrip("0") or normalized
        with self._connect() as conn:
            v1_rows = conn.execute(
                """SELECT vup.partido_id, COALESCE(a.nombre,'') AS nombre, SUM(vup.total_votos) AS total_votos
                   FROM votos_by_ubigeo_partido vup
                   LEFT JOIN agrupaciones a ON a.partido_id = vup.partido_id
                   WHERE vup.ubigeo LIKE ?
                   GROUP BY vup.partido_id
                   ORDER BY total_votos DESC""",
                (f"{normalized_1v}%",),
            ).fetchall()
            m1_count = conn.execute(
                "SELECT COUNT(*) AS c FROM mesas_data WHERE ubigeo LIKE ?",
                (f"{normalized_1v}%",),
            ).fetchone()["c"]

            v2_rows = conn.execute(
                """SELECT partido_id, COALESCE(nombre_candidato,'') AS nombre, SUM(votos_validos) AS total_votos
                   FROM sv_resumen_provincias
                   WHERE ubigeo LIKE ?
                   GROUP BY partido_id
                   ORDER BY total_votos DESC""",
                (f"{normalized}%",),
            ).fetchall()
            if not v2_rows:
                v2_rows = conn.execute(
                    """SELECT partido_id, nombre_candidato AS nombre, SUM(votos) AS total_votos
                       FROM sv_agg_distrito
                       WHERE ubigeo LIKE ?
                       GROUP BY partido_id
                       ORDER BY total_votos DESC""",
                    (f"{normalized}%",),
                ).fetchall()
            m2_count = conn.execute(
                "SELECT COUNT(*) AS c FROM mesas_sv WHERE id_ubigeo LIKE ?",
                (f"{normalized}%",),
            ).fetchone()["c"]

        return {
            "ubigeo_prefix": ubigeo_prefix,
            "primera_vuelta": {
                "mesas": int(m1_count),
                "votos": [{"partido_id": str(r["partido_id"]), "nombre": str(r["nombre"]), "total_votos": int(r["total_votos"] or 0)} for r in v1_rows],
            },
            "segunda_vuelta": {
                "mesas": int(m2_count),
                "votos": [{"partido_id": str(r["partido_id"]), "nombre": str(r["nombre"]), "total_votos": int(r["total_votos"] or 0)} for r in v2_rows],
            },
        }

    def seed_transfer_map(self) -> int:
        """Seed voto_transfer_map from TRANSFER_MAP in knowledge_base."""
        from onpe_mcp.knowledge_base import TRANSFER_MAP

        now = self.now_iso()
        count = 0
        with self._connect() as conn:
            for nombre_norm, (pk, ps, pb, fuente) in TRANSFER_MAP.items():
                conn.execute(
                    """INSERT INTO voto_transfer_map (partido_nombre_norm, peso_keiko, peso_sanchez, peso_bn, fuente, loaded_at)
                    VALUES (?,?,?,?,?,?)
                    ON CONFLICT(partido_nombre_norm) DO UPDATE SET
                        peso_keiko=excluded.peso_keiko, peso_sanchez=excluded.peso_sanchez,
                        peso_bn=excluded.peso_bn, fuente=excluded.fuente, loaded_at=excluded.loaded_at""",
                    (nombre_norm, pk, ps, pb, fuente, now),
                )
                count += 1
        return count

    def rebuild_proyeccion_sv(self) -> dict[str, Any]:
        """Build proyeccion_sv_by_ubigeo using float accumulation + NNLS weights."""
        from onpe_mcp.knowledge_base import get_transfer

        now = self.now_iso()
        with self._connect() as conn:
            rows_1v = conn.execute(
                """SELECT m.ubigeo, v.partido_id, COALESCE(a.nombre,'') AS nombre_partido, SUM(v.votos) AS votos
                   FROM votos v
                   JOIN mesas_data m ON m.codigo_mesa = v.codigo_mesa
                   LEFT JOIN agrupaciones a ON a.partido_id = v.partido_id
                   WHERE v.partido_id NOT IN ('80','81','82')
                   GROUP BY m.ubigeo, v.partido_id""",
            ).fetchall()

        ubigeo_proj: dict[str, dict[str, float]] = {}
        ubigeo_total: dict[str, int] = {}
        for row in rows_1v:
            ubigeo = str(row["ubigeo"] or "")
            partido = str(row["nombre_partido"] or "")
            votos = int(row["votos"] or 0)
            pk, ps, pb, _ = get_transfer(partido)

            if ubigeo not in ubigeo_proj:
                ubigeo_proj[ubigeo] = {"keiko": 0.0, "sanchez": 0.0, "bn": 0.0, "total": 0.0}
                ubigeo_total[ubigeo] = 0

            ubigeo_proj[ubigeo]["keiko"] += votos * pk
            ubigeo_proj[ubigeo]["sanchez"] += votos * ps
            ubigeo_proj[ubigeo]["bn"] += votos * pb
            ubigeo_proj[ubigeo]["total"] += votos
            ubigeo_total[ubigeo] += votos

        proj_rows = []
        for ubigeo, proj in ubigeo_proj.items():
            total = ubigeo_total[ubigeo]
            pk_int = round(proj["keiko"])
            ps_int = round(proj["sanchez"])
            pb_int = round(proj["bn"])
            abs_int = max(0, total - pk_int - ps_int - pb_int)
            proj_rows.append((ubigeo, total, pk_int, ps_int, pb_int, abs_int, now))

        with self._connect() as conn:
            conn.execute("DELETE FROM proyeccion_sv_by_ubigeo")
            conn.executemany(
                """INSERT INTO proyeccion_sv_by_ubigeo
                (ubigeo, votos_1v_total, votos_proyectados_keiko, votos_proyectados_sanchez,
                 votos_proyectados_bn, votos_abstencion_estimada, rebuilt_at)
                VALUES (?,?,?,?,?,?,?)""",
                proj_rows,
            )

        return {"ubigeos_processed": len(proj_rows)}

    def get_proyeccion_sv(self, ubigeo_prefix: str | None = None) -> list[dict[str, Any]]:
        """Get transfer projection. If ubigeo_prefix given, filter. If None, aggregate nationally."""
        with self._connect() as conn:
            if ubigeo_prefix:
                rows = conn.execute(
                    """SELECT ubigeo, votos_1v_total, votos_proyectados_keiko, votos_proyectados_sanchez,
                       votos_proyectados_bn, votos_abstencion_estimada FROM proyeccion_sv_by_ubigeo
                       WHERE ubigeo LIKE ?""",
                    (f"{ubigeo_prefix}%",),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT 'nacional' AS ubigeo,
                       SUM(votos_1v_total) AS votos_1v_total,
                       SUM(votos_proyectados_keiko) AS votos_proyectados_keiko,
                       SUM(votos_proyectados_sanchez) AS votos_proyectados_sanchez,
                       SUM(votos_proyectados_bn) AS votos_proyectados_bn,
                       SUM(votos_abstencion_estimada) AS votos_abstencion_estimada
                       FROM proyeccion_sv_by_ubigeo"""
                ).fetchall()
        return [dict(r) for r in rows]

    def get_proyeccion_sv_by_mesa_prefix(
        self,
        mesa_prefix: str,
        *,
        top_partidos: int = 15,
    ) -> dict[str, Any]:
        """Calcula proyección 1V→2V para el bloque de mesas cuyo código empieza con `mesa_prefix`.

        Aplica TRANSFER_MAP nacional (NNLS calibrado 86K mesas) a los votos 1V del bloque
        y compara con los votos 2V observados. Útil para preguntas como
        "transferencia en mesas 900K".

        Args:
            mesa_prefix: prefijo del código de mesa (ej: '9', '900', '9001'). Normalizado externamente.
            top_partidos: número de partidos emisores 1V a detallar.

        Returns:
            dict con totales 1V/2V, predicción NNLS, error, breakdown por partido y notas.
        """
        from onpe_mcp.knowledge_base import get_transfer

        prefix = str(mesa_prefix or "").strip()
        if not prefix or not prefix.isdigit():
            raise ValueError(f"mesa_prefix debe ser numérico no vacío, got {mesa_prefix!r}")

        like = f"{prefix}%"

        with self._connect() as conn:
            # Totales 1V por partido en el bloque
            rows_1v = conn.execute(
                """SELECT a.partido_id, COALESCE(a.nombre,'') AS nombre, SUM(v.votos) AS total
                   FROM votos v
                   LEFT JOIN agrupaciones a ON a.partido_id = v.partido_id
                   WHERE v.codigo_mesa LIKE ? AND v.votos IS NOT NULL
                   GROUP BY a.partido_id, a.nombre
                   HAVING total > 0
                   ORDER BY total DESC""",
                (like,),
            ).fetchall()

            # Cobertura del bloque en 1V
            cov_1v = conn.execute(
                """SELECT COUNT(*) AS mesas,
                          COALESCE(SUM(electores_habiles),0) AS electores,
                          COALESCE(SUM(votos_emitidos),0) AS emitidos,
                          COALESCE(SUM(votos_validos),0) AS validos
                   FROM mesas_data WHERE codigo_mesa LIKE ?""",
                (like,),
            ).fetchone()

            # Observación 2V real
            obs_2v = conn.execute(
                """SELECT
                     COALESCE(SUM(CASE WHEN partido_id='8'  THEN votos END),0) AS keiko,
                     COALESCE(SUM(CASE WHEN partido_id='10' THEN votos END),0) AS sanchez,
                     COALESCE(SUM(CASE WHEN partido_id='80' THEN votos END),0) AS blancos,
                     COALESCE(SUM(CASE WHEN partido_id='81' THEN votos END),0) AS nulos
                   FROM votos_sv WHERE codigo_mesa LIKE ?""",
                (like,),
            ).fetchone()

            cov_2v = conn.execute(
                """SELECT COUNT(*) AS mesas,
                          COALESCE(SUM(electores_habiles),0) AS electores,
                          COALESCE(SUM(votos_emitidos),0) AS emitidos
                   FROM mesas_sv WHERE codigo_mesa LIKE ?""",
                (like,),
            ).fetchone()

        # Aplicar TRANSFER_MAP nacional partido por partido
        pred_keiko = 0.0
        pred_sanchez = 0.0
        pred_bn = 0.0
        pred_abs = 0.0
        breakdown: list[dict[str, Any]] = []
        total_1v_pool = 0
        for r in rows_1v:
            nombre = str(r["nombre"] or "").strip()
            votos = int(r["total"] or 0)
            total_1v_pool += votos
            pk, ps, pb, fuente = get_transfer(nombre or "DESCONOCIDO")
            pa = max(0.0, 1.0 - pk - ps - pb)
            vk = votos * pk
            vs = votos * ps
            vb = votos * pb
            va = votos * pa
            pred_keiko += vk
            pred_sanchez += vs
            pred_bn += vb
            pred_abs += va
            breakdown.append(
                {
                    "partido_id": str(r["partido_id"] or ""),
                    "nombre": nombre,
                    "votos_1v": votos,
                    "pct_keiko": round(pk * 100, 1),
                    "pct_sanchez": round(ps * 100, 1),
                    "pct_bn": round(pb * 100, 1),
                    "pct_abstencion": round(pa * 100, 1),
                    "pred_keiko": round(vk),
                    "pred_sanchez": round(vs),
                    "pred_bn": round(vb),
                    "pred_abstencion": round(va),
                    "fuente": fuente,
                }
            )

        keiko_obs = int(obs_2v["keiko"] or 0)
        sanchez_obs = int(obs_2v["sanchez"] or 0)
        blancos_obs = int(obs_2v["blancos"] or 0)
        nulos_obs = int(obs_2v["nulos"] or 0)
        pred_k_int = round(pred_keiko)
        pred_s_int = round(pred_sanchez)

        def _err_pct(pred: int, obs: int) -> float | None:
            if obs == 0:
                return None
            return round((pred - obs) / obs * 100, 2)

        breakdown.sort(key=lambda x: -int(x.get("votos_1v") or 0))

        return {
            "mesa_prefix": prefix,
            "primera_vuelta": {
                "mesas": int(cov_1v["mesas"] or 0),
                "electores_habiles": int(cov_1v["electores"] or 0),
                "votos_emitidos": int(cov_1v["emitidos"] or 0),
                "votos_validos": int(cov_1v["validos"] or 0),
                "pool_total_1v": total_1v_pool,
            },
            "segunda_vuelta_observada": {
                "mesas": int(cov_2v["mesas"] or 0),
                "electores_habiles": int(cov_2v["electores"] or 0),
                "votos_emitidos": int(cov_2v["emitidos"] or 0),
                "keiko": keiko_obs,
                "sanchez": sanchez_obs,
                "blancos": blancos_obs,
                "nulos": nulos_obs,
            },
            "proyeccion_nnls_nacional": {
                "keiko": pred_k_int,
                "sanchez": pred_s_int,
                "bn": round(pred_bn),
                "abstencion": round(pred_abs),
                "modelo": "NNLS calibrado 86,124 mesas (TRANSFER_MAP nacional)",
            },
            "error_modelo": {
                "keiko_abs": pred_k_int - keiko_obs,
                "sanchez_abs": pred_s_int - sanchez_obs,
                "keiko_pct": _err_pct(pred_k_int, keiko_obs),
                "sanchez_pct": _err_pct(pred_s_int, sanchez_obs),
                "interpretacion": (
                    "Error positivo: el modelo nacional sobreestima en este bloque. "
                    "Error negativo: el modelo nacional subestima."
                ),
            },
            "breakdown_partidos_top": breakdown[: max(0, int(top_partidos))],
            "notas": [
                "Las tasas de transferencia provienen del modelo NNLS nacional, no recalibradas para este bloque específico.",
                "Para bloques con perfil rural/urbano distinto al promedio nacional (ej: mesas 900K), el modelo puede tener sesgo sistemático.",
                "Compara `proyeccion_nnls_nacional` vs `segunda_vuelta_observada` para cuantificar el sesgo.",
            ],
        }

    def bootstrap_segunda_vuelta(
        self,
        sv_output_dir: Path,
        sv_resumen_dir: Path,
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        """Master bootstrap: loads all SV data. Idempotent (UPSERT). Returns stats."""
        existing = self.total_mesas_sv_local()
        if existing > 0 and not force:
            return {"skipped": True, "mesas_sv": existing}

        result: dict[str, Any] = {"skipped": False}
        result["mesas_sv"] = self.bootstrap_sv_mesas(sv_output_dir)
        result["votos_sv"] = self.bootstrap_sv_votos(sv_output_dir)
        result["agrupaciones_sv"] = self.bootstrap_sv_agrupaciones(sv_output_dir)
        result["ubicaciones_sv"] = self.bootstrap_sv_ubicaciones(sv_output_dir)
        result["reasignados"] = self.bootstrap_sv_reasignados(sv_output_dir)
        result["resumen"] = self.bootstrap_resumen_sv(sv_resumen_dir)
        result["ctas"] = self.rebuild_sv_ctas_levels()
        result["transfer_map_seeded"] = self.seed_transfer_map()
        return result

    def onpe_sv_refresh_from_scraper(
        self,
        sv_output_dir: Path,
        sv_resumen_dir: Path,
    ) -> dict[str, Any]:
        """Incremental refresh: re-import all SV files (UPSERT). Returns change stats."""
        result: dict[str, Any] = {}
        result["mesas_sv"] = self.bootstrap_sv_mesas(sv_output_dir)
        result["votos_sv"] = self.bootstrap_sv_votos(sv_output_dir)
        result["agrupaciones_sv"] = self.bootstrap_sv_agrupaciones(sv_output_dir)
        result["ubicaciones_sv"] = self.bootstrap_sv_ubicaciones(sv_output_dir)
        result["reasignados"] = self.bootstrap_sv_reasignados(sv_output_dir)
        result["resumen"] = self.bootstrap_resumen_sv(sv_resumen_dir)
        result["ctas"] = self.rebuild_sv_ctas_levels()
        return result
