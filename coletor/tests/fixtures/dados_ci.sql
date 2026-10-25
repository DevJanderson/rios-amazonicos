-- Minimal readings for CI (empty database). Not for production use.
-- Manaus and Humaitá: hourly readings for the last 8 days, so /nivel, /semana
-- and alerts have recent data. São Gabriel: one old reading only (stale).
INSERT INTO dados.leituras (estacao, instante, fonte, cota_cm, cota_original)
SELECT e.codigo, t, 'ana_telemetria', e.base + 2 * extract(epoch FROM t - now()) / 86400,
       'ci'
FROM (VALUES ('14990000', 2000), ('15630000', 1500)) AS e(codigo, base),
     generate_series(date_trunc('hour', now()) - interval '8 days',
                     date_trunc('hour', now()), interval '1 hour') AS t
ON CONFLICT DO NOTHING;

INSERT INTO dados.leituras (estacao, instante, fonte, cota_cm, cota_original)
VALUES ('14320001', '2023-11-01 12:00-04', 'ana_telemetria', 500, 'ci')
ON CONFLICT DO NOTHING;
