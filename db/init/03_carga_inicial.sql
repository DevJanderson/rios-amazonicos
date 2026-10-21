-- Rios, estações e cotas de referência (levantamento de 20/10/2026, ver docs/dados.md).
-- Roda no banco "rios". Idempotente: reaplicar atualiza os valores.

INSERT INTO dados.rios (id, nome) VALUES
    (1, 'Negro'),
    (2, 'Solimões'),
    (3, 'Madeira'),
    (4, 'Amazonas')
ON CONFLICT (id) DO UPDATE SET nome = EXCLUDED.nome;

INSERT INTO dados.estacoes (codigo_ana, nome, municipio, uf, rio_id, ordem_no_rio) VALUES
    ('14320001', 'São Gabriel da Cachoeira', 'São Gabriel da Cachoeira', 'AM', 1, 1),
    ('14480002', 'Barcelos',                 'Barcelos',                 'AM', 1, 2),
    ('14990000', 'Manaus',                   'Manaus',                   'AM', 1, 3),
    ('10100000', 'Tabatinga',                'Tabatinga',                'AM', 2, 1),
    ('13150000', 'Coari (Itapéua)',          'Coari',                    'AM', 2, 2),
    ('14100000', 'Manacapuru',               'Manacapuru',               'AM', 2, 3),
    ('15400000', 'Porto Velho',              'Porto Velho',              'RO', 3, 1),
    ('15630000', 'Humaitá',                  'Humaitá',                  'AM', 3, 2),
    ('16030000', 'Itacoatiara',              'Itacoatiara',              'AM', 4, 1),
    ('16350002', 'Parintins',                'Parintins',                'AM', 4, 2)
ON CONFLICT (codigo_ana) DO UPDATE SET
    nome = EXCLUDED.nome, municipio = EXCLUDED.municipio, uf = EXCLUDED.uf,
    rio_id = EXCLUDED.rio_id, ordem_no_rio = EXCLUDED.ordem_no_rio;

-- Cotas em centímetros
INSERT INTO dados.cotas_referencia (estacao, tipo, cota_cm, data_evento, fonte, vigente_desde) VALUES
    -- Manaus
    ('14990000', 'alerta',           2700, NULL,         'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    ('14990000', 'inundacao',        2750, NULL,         'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    ('14990000', 'inundacao_severa', 2900, NULL,         'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    ('14990000', 'maxima_historica', 3002, '2021-06-16', 'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    ('14990000', 'minima_historica', 1213, '2024-11-03', 'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    -- Manacapuru
    ('14100000', 'inundacao_severa', 1960, NULL,         'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    ('14100000', 'maxima_historica', 2086, '2021-06-17', 'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    ('14100000', 'minima_historica',  206, '2024-10-12', 'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    -- Itacoatiara
    ('16030000', 'inundacao',        1400, NULL,         'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    ('16030000', 'inundacao_severa', 1420, NULL,         'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    ('16030000', 'maxima_historica', 1520, '2021-05-27', 'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    ('16030000', 'minima_historica',  -18, '2024-11-01', 'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    -- Parintins
    ('16350002', 'inundacao',         843, NULL,         'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    ('16350002', 'inundacao_severa',  930, NULL,         'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    ('16350002', 'maxima_historica',  947, '2021-05-30', 'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    ('16350002', 'minima_historica', -267, '2024-11-07', 'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    -- Porto Velho
    ('15400000', 'atencao',          1400, NULL,         'SGB/CPRM via Portal Amazônia; Boletim Madeira (2018)', '2026-10-20'),
    ('15400000', 'alerta',           1500, NULL,         'SGB/CPRM via Portal Amazônia; Boletim Madeira (2018)', '2026-10-20'),
    ('15400000', 'inundacao',        1700, NULL,         'SGB/CPRM via Portal Amazônia; Boletim Madeira (2018)', '2026-10-20'),
    -- Humaitá
    ('15630000', 'maxima_historica', 2563, '2014-04-11', 'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    ('15630000', 'minima_historica',  802, '2024-10-15', 'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    -- Coari (Itapéua)
    ('13150000', 'maxima_historica', 1801, '2015-06-24', 'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    ('13150000', 'minima_historica',  -29, '2024-10-07', 'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    -- Tabatinga (data da máxima a conferir na série da ANA)
    ('10100000', 'emergencia_seca',   150, NULL,         'SGB, alerta de vazante 2026 (via Portal Amazônia)',  '2026-10-20'),
    ('10100000', 'maxima_historica', 1382, '1999-08-25', 'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    ('10100000', 'minima_historica', -254, '2024-09-26', 'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    -- São Gabriel da Cachoeira
    ('14320001', 'maxima_historica', 1268, '2021-06-11', 'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    ('14320001', 'minima_historica',  330, '1992-02-07', 'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    -- Barcelos
    ('14480002', 'maxima_historica', 1052, '2022-06-22', 'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20'),
    ('14480002', 'minima_historica',   58, '1980-03-18', 'SGB, 24º Boletim Bacia do Amazonas (16/06/2026)', '2026-10-20')
ON CONFLICT (estacao, tipo, vigente_desde) DO UPDATE SET
    cota_cm = EXCLUDED.cota_cm, data_evento = EXCLUDED.data_evento, fonte = EXCLUDED.fonte;
