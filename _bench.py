import sqlite3, time
conn = sqlite3.connect('data/onpe.db')

# Check votos_by_ubigeo_partido
n = conn.execute('SELECT COUNT(*) FROM votos_by_ubigeo_partido').fetchone()[0]
print('votos_by_ubigeo_partido rows:', n)

# Benchmark common queries
queries = {
    'mesa lookup': ('SELECT * FROM mesas_data WHERE codigo_mesa=?', ('900017',)),
    'prefix summary (900K)': ('SELECT COUNT(*), SUM(votos_emitidos) FROM mesas_data WHERE codigo_mesa LIKE ?', ('9%',)),
    'top candidatos 900K': ('''SELECT a.nombre, SUM(v.votos) FROM votos v
        JOIN agrupaciones a ON a.partido_id=v.partido_id
        WHERE v.codigo_mesa LIKE "9%" GROUP BY v.partido_id ORDER BY 2 DESC LIMIT 5''', ()),
    'ubigeo location': ('SELECT ciudad, departamento FROM ubigeo_location_cache WHERE ubigeo=?', ('010101',)),
    'coverage metrics': ('''SELECT COUNT(*) as total, SUM(CASE WHEN votos_emitidos>0 THEN 1 ELSE 0 END)
        FROM mesas_data WHERE codigo_mesa LIKE ?''', ('9%',)),
    'votos_by_ubigeo': ('SELECT * FROM votos_by_ubigeo_partido WHERE ubigeo=? LIMIT 5', ('010101',)),
}

for name, (sql, params) in queries.items():
    t0 = time.perf_counter()
    for _ in range(10):
        conn.execute(sql, params).fetchall()
    ms = (time.perf_counter() - t0) / 10 * 1000
    print(f'{name}: {ms:.1f}ms avg')
conn.close()
