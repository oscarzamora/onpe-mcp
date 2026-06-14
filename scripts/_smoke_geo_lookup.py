"""Smoke test for the 7 new geo/lookup/comparacion methods."""
from __future__ import annotations

import json

from onpe_mcp.config import Settings
from onpe_mcp.storage import DataStore


def main() -> None:
    ds = DataStore(Settings.from_env().data_dir)

    print("=== lookup_ubigeo('La Molina') ===")
    out = ds.lookup_ubigeo("La Molina")
    print(json.dumps(out, ensure_ascii=False, indent=2)[:600])

    print("\n=== listar_mesas_por_geo(distrito='Miraflores', año=2026, vuelta=1, limit=5) ===")
    out = ds.listar_mesas_por_geo(año=2026, vuelta=1, distrito="Miraflores", limit=5)
    print(f"  total={out['total']}, returned={out['returned']}, has_more={out['has_more']}")
    for r in out["rows"][:3]:
        print(f"  mesa {r['codigo_mesa']} local='{r['local_votacion']}' "
              f"elec={r['electores_habiles']}")

    print("\n=== listar_locales_por_geo(distrito='La Molina', año=2026, vuelta=1) ===")
    out = ds.listar_locales_por_geo(año=2026, vuelta=1, distrito="La Molina", limit=10)
    print(f"  total={out['total']}")
    for r in out["rows"][:5]:
        print(f"  '{r['local_votacion']}' n_mesas={r['n_mesas']} "
              f"elec={r['electores_habiles']}")

    print("\n=== listar_locales_por_geo(distrito='La Molina', año=2021, vuelta=1) ===")
    out = ds.listar_locales_por_geo(año=2021, vuelta=1, distrito="La Molina")
    print(f"  available={out['available']}, total={out.get('total')}, "
          f"note={out.get('note', '')[:80]}")

    print("\n=== mesa_geo_lookup('900100', año=2026, vuelta=1) ===")
    print(json.dumps(ds.mesa_geo_lookup("900100", año=2026, vuelta=1),
                     ensure_ascii=False))

    print("\n=== mesa_geo_lookup('900100', año=2021, vuelta=1) ===")
    print(json.dumps(ds.mesa_geo_lookup("900100", año=2021, vuelta=1),
                     ensure_ascii=False))

    print("\n=== comparacion_mesa_2021('900100') ===")
    out = ds.comparacion_mesa_2021("900100")
    print(f"  available_1v={out['available_1v']}, available_2v={out['available_2v']}")
    if out["primera_vuelta"]:
        v1 = out["primera_vuelta"]
        print(f"  1V: {v1['departamento']}/{v1['distrito']} "
              f"emit={v1['votos_emitidos']} val={v1['votos_validos']}")
    if out["segunda_vuelta"]:
        v2 = out["segunda_vuelta"]
        print(f"  2V: emit={v2['votos_emitidos']} val={v2['votos_validos']}")

    print("\n=== comparacion_mesa_cross_year('900100', 2021, 2026, 1V vs 1V) ===")
    out = ds.comparacion_mesa_cross_year("900100", año_a=2021, año_b=2026,
                                          vuelta_a=1, vuelta_b=1)
    a = out["lado_a"]
    b = out["lado_b"]
    print(f"  A 2021: available={a.get('available')} found={a.get('found')}")
    if a.get("top"):
        print(f"    top0: {a['top'][0]}")
    print(f"  B 2026: available={b.get('available')} found={b.get('found')}")
    if b.get("top"):
        print(f"    top0: {b['top'][0]}")

    print("\n=== comparacion_mesa_cross_year('421234', 2016, 2021) — año no disp ===")
    out = ds.comparacion_mesa_cross_year("421234", año_a=2016, año_b=2021)
    print(f"  A 2016: available={out['lado_a'].get('available')}, "
          f"reason={out['lado_a'].get('reason')}")
    print(f"  B 2021: available={out['lado_b'].get('available')}, "
          f"found={out['lado_b'].get('found')}")

    print("\n=== comparacion_geo_cross_year('MIRAFLORES', distrito, 2021 vs 2026, 2V vs 2V) ===")
    out = ds.comparacion_geo_cross_year(
        nivel="distrito", geo_name="MIRAFLORES",
        año_a=2021, año_b=2026, vuelta_a=2, vuelta_b=2,
    )
    print(f"  A 2021 mesas={out['lado_a'].get('mesas')}, validos={out['lado_a'].get('total_validos')}")
    for r in out["lado_a"].get("top", [])[:2]:
        print(f"    {r['candidato']}: {r['votos']:,} ({r['pct']:.2f}%)")
    print(f"  B 2026 mesas={out['lado_b'].get('mesas')}, validos={out['lado_b'].get('total_validos')}")
    for r in out["lado_b"].get("top", [])[:2]:
        print(f"    {r['candidato']}: {r['votos']:,} ({r['pct']:.2f}%)")


if __name__ == "__main__":
    main()
