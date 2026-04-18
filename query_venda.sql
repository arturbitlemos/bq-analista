DECLARE data_d1 DATE DEFAULT DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY);
DECLARE data_inicio_mtd DATE;
DECLARE data_fim_mtd DATE;

-- Logica MTD: Se dia 1, pega mes anterior; senao, pega dia 1 ate D-1
SET data_inicio_mtd = CASE 
  WHEN EXTRACT(DAY FROM CURRENT_DATE()) = 1 
  THEN DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH)
  ELSE DATE_TRUNC(CURRENT_DATE(), MONTH)
END;

SET data_fim_mtd = CASE 
  WHEN EXTRACT(DAY FROM CURRENT_DATE()) = 1 
  THEN LAST_DAY(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH))
  ELSE DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
END;

SELECT 
  "BigQuery" as FONTE,
  rede_lojas_mais_vendas,
  MAX(CASE rede_lojas_mais_vendas
        WHEN 1 THEN 'ANIMALE'
        WHEN 2 THEN 'FARM'
        WHEN 5 THEN 'FABULA'
        WHEN 6 THEN 'OFF PREMIUM'
        WHEN 7 THEN 'FOXTON'
        WHEN 9 THEN 'CRIS BARROS'
        WHEN 15 THEN 'MARIA FILO'
        WHEN 16 THEN 'NV'
        WHEN 26 THEN 'FARM ETC'
        WHEN 30 THEN 'CAROL BASSI'
        ELSE 'OUTRAS'
  END) AS MARCA,
  
  SUM(CASE 
    WHEN DATE(data_faturamento) = data_d1 
    THEN valor_pago_produto ELSE 0 
  END) AS VALOR_D1,
  
  SUM(CASE 
    WHEN DATE(data_faturamento) >= data_inicio_mtd 
     AND DATE(data_faturamento) <= data_fim_mtd
    THEN valor_pago_produto ELSE 0 
  END) AS VALOR_MTD

FROM `soma-dl-refined-online.soma_online_refined.refined_captacao` 
WHERE TIMESTAMP_TRUNC(data_evento, DAY) >= TIMESTAMP_TRUNC(TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 60 DAY), DAY)
AND tipo_seller <> "EXTERNO"
AND (tipo_venda<>"FISICO" or programa<>"franquia")
GROUP BY rede_lojas_mais_vendas