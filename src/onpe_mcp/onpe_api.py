from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from curl_cffi import requests as curl_requests
except Exception:  # pragma: no cover
    curl_requests = None  # type: ignore[assignment]


BASE_URL = "https://resultadoelectoral.onpe.gob.pe/presentacion-backend"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://resultadoelectoral.onpe.gob.pe/main/presidenciales",
    "Origin": "https://resultadoelectoral.onpe.gob.pe",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


@dataclass(frozen=True)
class UbigeoItem:
    ubigeo: str
    nombre: str


@dataclass(frozen=True)
class DistrictItem:
    id_distrito_electoral: int
    nombre: str


class OnpeApiError(RuntimeError):
    pass


class OnpeApiClient:
    def __init__(self, base_url: str = BASE_URL, retries: int = 3, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.retries = max(1, retries)
        self.timeout = max(1, timeout)
        self._session = curl_requests.Session() if curl_requests is not None else None
        self._foreign_catalog_by_ubigeo: dict[str, dict[str, str]] | None = None
        self._domestic_departments: dict[str, str] | None = None
        self._domestic_districts_by_province: dict[str, dict[str, str]] = {}

    @staticmethod
    def _norm(text: str) -> str:
        return " ".join(str(text or "").casefold().strip().split())

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        query = urlencode(params or {})
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"

        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                if self._session is not None:
                    response = self._session.get(
                        url,
                        headers=DEFAULT_HEADERS,
                        timeout=self.timeout,
                        impersonate="chrome124",
                    )
                    if int(response.status_code) >= 400:
                        raise OnpeApiError(f"HTTP {response.status_code}")
                    body = str(response.text or "").strip()
                else:
                    request = Request(url, headers=DEFAULT_HEADERS)
                    with urlopen(request, timeout=self.timeout) as response:
                        body = response.read().decode("utf-8", errors="replace").strip()

                lowered = body[:120].lower()
                if lowered.startswith("<!doctype html") or lowered.startswith("<html"):
                    raise OnpeApiError("ONPE devolvió HTML en lugar de JSON")

                payload = json.loads(body)
                if payload.get("success") is False:
                    raise OnpeApiError(str(payload.get("message", "sin detalle")))
                return payload
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OnpeApiError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(1.2 * attempt)
                    continue
                raise OnpeApiError(f"No se pudo consultar {url}: {exc}") from exc

        raise OnpeApiError(f"No se pudo consultar {url}: {last_error}")

    def _pick_mesa_acta(self, items: Any, id_eleccion: int) -> dict[str, Any] | None:
        if not isinstance(items, list):
            return None

        actas: list[dict[str, Any]] = []
        items_raw: list[Any] = cast(list[Any], items)
        for item in items_raw:
            if isinstance(item, dict):
                actas.append(cast(dict[str, Any], item))
        if not actas:
            return None

        def is_contabilizada(acta: dict[str, Any]) -> bool:
            return self._norm(str(acta.get("descripcionEstadoActa") or "")) == "contabilizada"

        matching = [acta for acta in actas if self._to_int(acta.get("idEleccion"), default=-1) == id_eleccion]
        contabilizadas_matching = [acta for acta in matching if is_contabilizada(acta)]
        if contabilizadas_matching:
            return contabilizadas_matching[0]

        contabilizadas = [acta for acta in actas if is_contabilizada(acta)]
        if contabilizadas:
            return contabilizadas[0]

        if matching:
            return matching[0]

        return actas[0]

    def _build_mesa_bundle(self, codigo_mesa: str, acta: dict[str, Any]) -> dict[str, Any]:
        detalle_raw: list[Any] = cast(list[Any], acta.get("detalle") or [])
        detalle: list[dict[str, Any]] = []
        for item in detalle_raw:
            if isinstance(item, dict):
                detalle.append(cast(dict[str, Any], item))

        detalle_by_code: dict[str, dict[str, Any]] = {}
        for item in detalle:
            code = str(item.get("adCodigo") or "").strip()
            if code and code not in detalle_by_code:
                detalle_by_code[code] = item

        def detalle_votos(code: str) -> int:
            return self._to_int(detalle_by_code.get(code, {}).get("adVotos"), default=0)

        agrupaciones: list[dict[str, Any]] = []
        votos: list[dict[str, Any]] = []
        seen_partidos: set[str] = set()
        for item in detalle:
            partido_id = str(item.get("adAgrupacionPolitica") or "").strip()
            if not partido_id or partido_id in seen_partidos:
                continue
            seen_partidos.add(partido_id)
            nombre = str(item.get("adDescripcion") or "").strip()
            agrupaciones.append({"partido_id": partido_id, "nombre": nombre})
            votos.append(
                {
                    "codigo_mesa": codigo_mesa,
                    "partido_id": partido_id,
                    "votos": self._to_int(item.get("adVotos"), default=0),
                }
            )

        return {
            "codigo_mesa": str(acta.get("codigoMesa") or codigo_mesa),
            "found": True,
            "mesa_data": {
                "codigo_mesa": str(acta.get("codigoMesa") or codigo_mesa),
                "ubigeo": acta.get("idUbigeo"),
                "local_votacion": acta.get("nombreLocalVotacion"),
                "electores_habiles": self._to_int(acta.get("totalElectoresHabiles"), default=0),
                "votos_emitidos": self._to_int(acta.get("totalVotosEmitidos"), default=0),
                "votos_validos": self._to_int(acta.get("totalVotosValidos"), default=0),
                "blancos": detalle_votos("80"),
                "nulos": detalle_votos("81"),
                "impugnados": detalle_votos("82"),
                "estado_acta": acta.get("descripcionEstadoActa"),
            },
            "agrupaciones": agrupaciones,
            "votos": votos,
        }

    def get_active_election_id(self) -> int:
        payload = self._get_json("/proceso/proceso-electoral-activo")
        data_raw = payload.get("data")
        if not isinstance(data_raw, dict):
            raise OnpeApiError("No se encontró bloque data en proceso activo")
        data: dict[str, Any] = cast(dict[str, Any], data_raw)
        election_id = data.get("idEleccionPrincipal")
        if not isinstance(election_id, int):
            raise OnpeApiError("No se encontró idEleccionPrincipal")
        return election_id

    def get_mesa(
        self,
        codigo_mesa: str,
        *,
        id_eleccion: int = 10,
        timeout: int | None = None,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        client = self if base_url is None or base_url.rstrip("/") == self.base_url else OnpeApiClient(
            base_url=base_url,
            retries=self.retries,
            timeout=timeout or self.timeout,
        )
        if timeout is not None and timeout > 0 and timeout != client.timeout:
            client = OnpeApiClient(base_url=client.base_url, retries=client.retries, timeout=timeout)

        payload = client._get_json("/actas/buscar/mesa", {"codigoMesa": codigo_mesa})
        acta = client._pick_mesa_acta(payload.get("data"), max(1, int(id_eleccion)))
        if acta is None:
            return {
                "codigo_mesa": codigo_mesa,
                "found": False,
                "mesa_data": None,
                "agrupaciones": [],
                "votos": [],
            }
        return client._build_mesa_bundle(codigo_mesa, acta)

    def list_level1_foreign(self, election_id: int) -> list[UbigeoItem]:
        payload = self._get_json(
            "/ubigeos/departamentos",
            {"idEleccion": election_id, "idAmbitoGeografico": 2},
        )
        data_raw: list[Any] = cast(list[Any], payload.get("data") or [])
        data: list[dict[str, Any]] = []
        for item in data_raw:
            if isinstance(item, dict):
                data.append(cast(dict[str, Any], item))
        return [UbigeoItem(str(item["ubigeo"]), str(item["nombre"])) for item in data]

    def list_level1_domestic(self, election_id: int) -> list[UbigeoItem]:
        payload = self._get_json(
            "/ubigeos/departamentos",
            {"idEleccion": election_id, "idAmbitoGeografico": 1},
        )
        data_raw: list[Any] = cast(list[Any], payload.get("data") or [])
        data: list[dict[str, Any]] = []
        for item in data_raw:
            if isinstance(item, dict):
                data.append(cast(dict[str, Any], item))
        return [UbigeoItem(str(item["ubigeo"]), str(item["nombre"])) for item in data]

    def list_countries(self, election_id: int, continent_code: str) -> list[UbigeoItem]:
        payload = self._get_json(
            "/ubigeos/provincias",
            {
                "idEleccion": election_id,
                "idAmbitoGeografico": 2,
                "idUbigeoDepartamento": continent_code,
            },
        )
        data_raw: list[Any] = cast(list[Any], payload.get("data") or [])
        data: list[dict[str, Any]] = []
        for item in data_raw:
            if isinstance(item, dict):
                data.append(cast(dict[str, Any], item))
        return [UbigeoItem(str(item["ubigeo"]), str(item["nombre"])) for item in data]

    def list_provinces(self, election_id: int, department_code: str, *, ambito: int = 1) -> list[UbigeoItem]:
        payload = self._get_json(
            "/ubigeos/provincias",
            {
                "idEleccion": election_id,
                "idAmbitoGeografico": int(ambito),
                "idUbigeoDepartamento": department_code,
            },
        )
        data_raw: list[Any] = cast(list[Any], payload.get("data") or [])
        data: list[dict[str, Any]] = []
        for item in data_raw:
            if isinstance(item, dict):
                data.append(cast(dict[str, Any], item))
        return [UbigeoItem(str(item["ubigeo"]), str(item["nombre"])) for item in data]

    def list_cities(self, election_id: int, country_code: str) -> list[UbigeoItem]:
        payload = self._get_json(
            "/ubigeos/distritos",
            {
                "idEleccion": election_id,
                "idAmbitoGeografico": 2,
                "idUbigeoProvincia": country_code,
            },
        )
        data_raw: list[Any] = cast(list[Any], payload.get("data") or [])
        data: list[dict[str, Any]] = []
        for item in data_raw:
            if isinstance(item, dict):
                data.append(cast(dict[str, Any], item))
        return [UbigeoItem(str(item["ubigeo"]), str(item["nombre"])) for item in data]

    def list_ubigeo_districts(self, election_id: int, province_code: str, *, ambito: int = 1) -> list[UbigeoItem]:
        payload = self._get_json(
            "/ubigeos/distritos",
            {
                "idEleccion": election_id,
                "idAmbitoGeografico": int(ambito),
                "idUbigeoProvincia": province_code,
            },
        )
        data_raw: list[Any] = cast(list[Any], payload.get("data") or [])
        data: list[dict[str, Any]] = []
        for item in data_raw:
            if isinstance(item, dict):
                data.append(cast(dict[str, Any], item))
        return [UbigeoItem(str(item["ubigeo"]), str(item["nombre"])) for item in data]

    def build_foreign_catalog(self, election_id: int | None = None) -> tuple[int, list[dict[str, str]]]:
        current_election = election_id or self.get_active_election_id()
        rows: list[dict[str, str]] = []

        continents = self.list_level1_foreign(current_election)
        for continent in continents:
            countries = self.list_countries(current_election, continent.ubigeo)
            for country in countries:
                cities = self.list_cities(current_election, country.ubigeo)
                for city in cities:
                    rows.append(
                        {
                            "ubigeo": city.ubigeo,
                            "Continente": continent.nombre,
                            "pais": country.nombre,
                            "ciudad": city.nombre,
                        }
                    )

        rows.sort(key=lambda item: (item["Continente"], item["pais"], item["ciudad"]))
        return current_election, rows

    def build_domestic_catalog(self, election_id: int | None = None) -> tuple[int, list[dict[str, str]]]:
        """Construye el catálogo completo de ubigeos domésticos desde la API ONPE.
        Retorna (id_eleccion, lista de dicts con ubigeo/departamento/provincia/distrito).
        Itera: departamentos → provincias → distritos."""
        current_election = election_id or self.get_active_election_id()
        rows: list[dict[str, str]] = []

        departments = self.list_level1_domestic(current_election)
        for dept in departments:
            dept_nombre = str(dept.nombre).strip()
            provinces = self.list_provinces(current_election, dept.ubigeo, ambito=1)
            for prov in provinces:
                prov_nombre = str(prov.nombre).strip()
                districts = self.list_ubigeo_districts(current_election, prov.ubigeo, ambito=1)
                for dist in districts:
                    rows.append(
                        {
                            "ubigeo": str(dist.ubigeo).strip(),
                            "departamento": dept_nombre,
                            "provincia": prov_nombre,
                            "distrito": str(dist.nombre).strip(),
                        }
                    )

        rows.sort(key=lambda item: item["ubigeo"])
        return current_election, rows

    def resolve_location_by_ubigeo(
        self,
        ubigeo: str,
        *,
        id_eleccion: int | None = None,
    ) -> dict[str, str] | None:
        code = str(ubigeo or "").strip()
        if len(code) < 6 or not code.isdigit():
            return None

        election_id = id_eleccion or self.get_active_election_id()

        if code.startswith("9"):
            if self._foreign_catalog_by_ubigeo is None:
                _, rows = self.build_foreign_catalog(election_id)
                self._foreign_catalog_by_ubigeo = {str(row.get("ubigeo") or ""): row for row in rows}

            row = (self._foreign_catalog_by_ubigeo or {}).get(code)
            if row is None:
                return None
            return {
                "ubigeo": code,
                "ambito": "extranjero",
                "departamento": str(row.get("Continente") or "").strip(),
                "ciudad": str(row.get("ciudad") or "").strip(),
                "pais": str(row.get("pais") or "").strip(),
            }

        dept_code = code[:2]
        prov_code = code[:4]
        if self._domestic_departments is None:
            departments = self.list_level1_domestic(election_id)
            self._domestic_departments = {
                str(item.ubigeo): str(item.nombre).strip()
                for item in departments
                if str(item.ubigeo).strip()
            }

        departamento = (self._domestic_departments or {}).get(dept_code, "")

        if prov_code not in self._domestic_districts_by_province:
            districts_map: dict[str, str] = {}
            districts = self.list_ubigeo_districts(election_id, prov_code, ambito=1)
            for item in districts:
                code_k = str(item.ubigeo).strip()
                if code_k:
                    districts_map[code_k] = str(item.nombre).strip()
            self._domestic_districts_by_province[prov_code] = districts_map

        ciudad = self._domestic_districts_by_province.get(prov_code, {}).get(code, "")
        if not departamento and not ciudad:
            return None

        return {
            "ubigeo": code,
            "ambito": "peru",
            "departamento": departamento,
            "ciudad": ciudad,
            "pais": "",
        }

    def list_districts(self) -> list[DistrictItem]:
        payload = self._get_json("/distrito-electoral/distritos")
        data_raw: list[Any] = cast(list[Any], payload.get("data") or [])
        data: list[dict[str, Any]] = []
        for item in data_raw:
            if isinstance(item, dict):
                data.append(cast(dict[str, Any], item))
        items: list[DistrictItem] = []

        for raw in data:
            raw_id = raw.get("idDistritoElectoral")
            if raw_id is None:
                raw_id = raw.get("id")
            if raw_id is None:
                raw_id = raw.get("codigo")

            raw_nombre = raw.get("nombre")
            if raw_nombre is None:
                raw_nombre = raw.get("nombreDistritoElectoral")
            if raw_id is None or raw_nombre is None:
                continue
            try:
                district_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            nombre = str(raw_nombre).strip()
            if not nombre:
                continue
            items.append(DistrictItem(id_distrito_electoral=district_id, nombre=nombre))

        return items

    def resolve_district(self, query: str) -> DistrictItem | None:
        q = self._norm(query)
        if not q:
            return None

        districts = self.list_districts()
        exact = [d for d in districts if self._norm(d.nombre) == q]
        if exact:
            return exact[0]

        contains = [d for d in districts if q in self._norm(d.nombre)]
        if contains:
            return contains[0]

        return None

    def get_candidates_by_district(
        self,
        *,
        endpoint_path: str,
        id_eleccion: int,
        id_distrito_electoral: int,
        page_size: int = 200,
    ) -> list[dict[str, Any]]:
        payload = self._get_json(
            f"/{endpoint_path.lstrip('/')}",
            {
                "pagina": 0,
                "tamanio": max(10, min(int(page_size), 1000)),
                "idEleccion": int(id_eleccion),
                "tipoFiltro": "distrito_electoral",
                "idDistritoElectoral": int(id_distrito_electoral),
            },
        )
        data_raw: list[Any] = cast(list[Any], payload.get("data") or [])
        data: list[dict[str, Any]] = []
        for item in data_raw:
            if isinstance(item, dict):
                data.append(cast(dict[str, Any], item))

        rows: list[dict[str, Any]] = []
        for raw in data:
            nombre_candidato = str(raw.get("nombreCandidato") or "").strip()
            if not nombre_candidato:
                continue
            codigo_agrupacion = str(raw.get("codigoAgrupacionPolitica") or "").strip()
            try:
                votos = int(raw.get("totalVotosValidos") or 0)
            except (TypeError, ValueError):
                votos = 0
            rows.append(
                {
                    "nombre_candidato": nombre_candidato,
                    "nombre_agrupacion": str(raw.get("nombreAgrupacionPolitica") or "").strip(),
                    "codigo_agrupacion": codigo_agrupacion,
                    "votos_validos": votos,
                    "lista": raw.get("lista"),
                }
            )

        rows.sort(key=lambda item: int(item.get("votos_validos") or 0), reverse=True)
        return rows
