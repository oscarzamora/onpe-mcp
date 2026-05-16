from __future__ import annotations

import sys
from typing import Any

from .config import Settings


class GatewayError(RuntimeError):
    pass


class OnpeScraperGateway:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._extractor_cls: type | None = None

    def _ensure_import(self) -> type:
        if self._extractor_cls is not None:
            return self._extractor_cls

        scraper_src = self.settings.scraper_root / "src"
        if not scraper_src.exists():
            raise GatewayError(f"No existe ruta de scraper: {scraper_src}")

        if str(scraper_src) not in sys.path:
            sys.path.insert(0, str(scraper_src))

        try:
            from onpe_scraper.scraper import OnpeExtractor  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise GatewayError(f"No se pudo importar onpe_scraper: {exc}") from exc

        self._extractor_cls = OnpeExtractor
        return OnpeExtractor

    def _build_extractor(
        self,
        *,
        base_url: str | None = None,
        id_eleccion: int = 10,
        timeout: int = 30,
        pause_seconds: float = 0.0,
        max_workers: int = 5,
        batch_size: int = 50,
    ) -> Any:
        extractor_cls = self._ensure_import()
        return extractor_cls(
            base_url=base_url or "https://resultadoelectoral.onpe.gob.pe/presentacion-backend",
            id_eleccion=id_eleccion,
            timeout=timeout,
            pause_seconds=pause_seconds,
            max_workers=max_workers,
            batch_size=batch_size,
        )

    def get_mesa(
        self,
        codigo_mesa: str,
        *,
        id_eleccion: int = 10,
        timeout: int = 30,
        base_url: str | None = None,
    ) -> dict[str, Any]:
        extractor = self._build_extractor(
            id_eleccion=id_eleccion,
            timeout=timeout,
            base_url=base_url,
            max_workers=1,
            batch_size=1,
        )
        codigo = extractor.normalize_mesa_code(codigo_mesa)
        payload = extractor.fetch_mesa(codigo)
        acta = extractor.extract_acta(payload)

        if acta is None:
            return {
                "codigo_mesa": codigo,
                "found": False,
                "mesa_data": None,
                "agrupaciones": [],
                "votos": [],
            }

        mesa_data = extractor.build_mesa_data(acta)
        agrupaciones = extractor.build_agrupaciones(acta)
        votos = extractor.build_votos(codigo, acta)

        return {
            "codigo_mesa": codigo,
            "found": True,
            "mesa_data": {
                "codigo_mesa": mesa_data.codigo_mesa,
                "ubigeo": mesa_data.id_ubigeo,
                "local_votacion": mesa_data.local_votacion,
                "electores_habiles": mesa_data.electores_habiles,
                "votos_emitidos": mesa_data.votos_emitidos,
                "votos_validos": mesa_data.votos_validos,
                "blancos": mesa_data.blancos,
                "nulos": mesa_data.nulos,
                "impugnados": mesa_data.impugnados,
                "estado_acta": mesa_data.estado_acta,
            },
            "agrupaciones": [
                {"partido_id": item.partido_id, "nombre": item.nombre}
                for item in agrupaciones
            ],
            "votos": [
                {
                    "codigo_mesa": item.codigo_mesa,
                    "partido_id": item.partido_id,
                    "votos": item.votos,
                }
                for item in votos
            ],
        }

