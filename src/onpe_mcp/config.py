from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    scraper_root: Path
    scraper_repo_url: str
    source_dir: Path
    output_dir: Path
    data_dir: Path
    log_level: str
    max_batch_size: int
    cache_ttl_seconds: int
    geo_query_cache_ttl_seconds: int
    auto_sync_foreign_catalog_on_demand: bool
    local_only: bool
    bootstrap_on_startup: bool
    bootstrap_include_votes: bool
    auto_hydrate_on_demand: bool
    auto_hydrate_max_mesas: int
    atu_manera_bootstrap: bool
    atu_manera_csv_path: str
    sv_scraper_root: Path
    sv_output_dir: Path
    sv_resumen_dir: Path
    voto2021_root: Path

    @staticmethod
    def from_env() -> "Settings":
        workspace_default = Path(__file__).resolve().parents[2]  # repo root: onpe-mcp/
        scraper_root = Path(
            os.getenv(
                "ONPE_SCRAPER_ROOT",
                str((workspace_default / ".." / "onpescraper").resolve()),
            )
        ).resolve()
        scraper_repo_url = (
            os.getenv("ONPE_SCRAPER_REPO_URL", "https://github.com/oscarzamora/onpeescraper")
            .strip()
            or "https://github.com/oscarzamora/onpeescraper"
        )

        source_dir = Path(
            os.getenv("ONPE_SOURCE_DIR", str((scraper_root / "source_data").resolve()))
        ).resolve()
        output_dir = Path(
            os.getenv("ONPE_OUTPUT_DIR", str((scraper_root / "output").resolve()))
        ).resolve()
        data_dir = Path(
            os.getenv("ONPE_DATA_DIR", str((workspace_default / "data").resolve()))
        ).resolve()

        raw_level = os.getenv("ONPE_LOG_LEVEL", "INFO").strip().upper() or "INFO"
        raw_batch = os.getenv("ONPE_MAX_BATCH_SIZE", "200").strip()
        raw_ttl = os.getenv("ONPE_CACHE_TTL_SECONDS", "900").strip()
        raw_geo_ttl = os.getenv("ONPE_GEO_QUERY_CACHE_TTL_SECONDS", "300").strip()
        raw_auto_sync_catalog = os.getenv("ONPE_AUTO_SYNC_FOREIGN_CATALOG_ON_DEMAND", "true").strip().lower()
        raw_local_only = os.getenv("ONPE_LOCAL_ONLY", "true").strip().lower()
        raw_bootstrap_on_startup = os.getenv("ONPE_BOOTSTRAP_ON_STARTUP", "true").strip().lower()
        raw_bootstrap_include_votes = os.getenv("ONPE_BOOTSTRAP_INCLUDE_VOTES", "true").strip().lower()
        raw_auto_hydrate = os.getenv("ONPE_AUTO_HYDRATE_ON_DEMAND", "true").strip().lower()
        raw_auto_hydrate_max = os.getenv("ONPE_AUTO_HYDRATE_MAX_MESAS", "5").strip()
        raw_atu_manera_bootstrap = os.getenv("ONPE_ATU_MANERA_BOOTSTRAP", "false").strip().lower()
        atu_manera_csv_path = os.getenv("ONPE_ATU_MANERA_CSV_PATH", "").strip()
        sv_scraper_root = Path(
            os.getenv(
                "ONPE_SV_SCRAPER_ROOT",
                str((workspace_default / ".." / "onpe-scraper-2026-2").resolve()),
            )
        ).resolve()
        sv_output_dir = Path(
            os.getenv("ONPE_SV_OUTPUT_DIR", str((sv_scraper_root / "output").resolve()))
        ).resolve()
        sv_resumen_dir = Path(
            os.getenv("ONPE_SV_RESUMEN_DIR", str((sv_scraper_root / "resumen").resolve()))
        ).resolve()
        voto2021_root = Path(
            os.getenv(
                "ONPE_VOTO2021_ROOT",
                str((workspace_default / ".." / "peruvoto2021").resolve()),
            )
        ).resolve()

        try:
            max_batch_size = int(raw_batch)
        except ValueError:
            max_batch_size = 200

        try:
            cache_ttl_seconds = int(raw_ttl)
        except ValueError:
            cache_ttl_seconds = 900

        try:
            geo_query_cache_ttl_seconds = int(raw_geo_ttl)
        except ValueError:
            geo_query_cache_ttl_seconds = 300

        max_batch_size = max(1, min(max_batch_size, 2000))
        cache_ttl_seconds = max(30, min(cache_ttl_seconds, 86400))
        geo_query_cache_ttl_seconds = max(10, min(geo_query_cache_ttl_seconds, 3600))
        auto_sync_foreign_catalog_on_demand = raw_auto_sync_catalog in {"1", "true", "yes", "y", "on"}
        local_only = raw_local_only in {"1", "true", "yes", "y", "on"}
        bootstrap_on_startup = raw_bootstrap_on_startup in {"1", "true", "yes", "y", "on"}
        bootstrap_include_votes = raw_bootstrap_include_votes in {"1", "true", "yes", "y", "on"}

        auto_hydrate_on_demand = raw_auto_hydrate in {"1", "true", "yes", "y", "on"}
        try:
            auto_hydrate_max_mesas = max(1, min(int(raw_auto_hydrate_max), 100))
        except ValueError:
            auto_hydrate_max_mesas = 20
        atu_manera_bootstrap = raw_atu_manera_bootstrap in {"1", "true", "yes", "y", "on"}

        return Settings(
            scraper_root=scraper_root,
            scraper_repo_url=scraper_repo_url,
            source_dir=source_dir,
            output_dir=output_dir,
            data_dir=data_dir,
            log_level=raw_level,
            max_batch_size=max_batch_size,
            cache_ttl_seconds=cache_ttl_seconds,
            geo_query_cache_ttl_seconds=geo_query_cache_ttl_seconds,
            auto_sync_foreign_catalog_on_demand=auto_sync_foreign_catalog_on_demand,
            local_only=local_only,
            bootstrap_on_startup=bootstrap_on_startup,
            bootstrap_include_votes=bootstrap_include_votes,
            auto_hydrate_on_demand=auto_hydrate_on_demand,
            auto_hydrate_max_mesas=auto_hydrate_max_mesas,
            atu_manera_bootstrap=atu_manera_bootstrap,
            atu_manera_csv_path=atu_manera_csv_path,
            sv_scraper_root=sv_scraper_root,
            sv_output_dir=sv_output_dir,
            sv_resumen_dir=sv_resumen_dir,
            voto2021_root=voto2021_root,
        )
