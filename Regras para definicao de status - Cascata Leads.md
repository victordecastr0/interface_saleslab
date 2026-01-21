# Regras para definicao de status - Cascata Leads



## 1. Cascata

1. **Leads** 

   1. **Filtro AddSales**

      1. Sem viabilidade
      2. Improdutivo
      3. Score biométrico baixo

   2. **Filtro auditoria**

      1. Confirmacao do endereco
      2. Confirmacao CNH
      3. Cliente V.Tal
      4. Análise escavador
      5. Serasa
      6. CNPj

   3. **Qualificados**

      1. Negociacao
      2. Nao venda
      3. Venda bruta
         1. Em aberto
         2. Quebra de vendas
         3. **Venda liquida**

      

      ## 2. Cálculo dos campos

      1.1 - availabilitydescription == sem viabilidade

      1.2 - desistencia do lead == sim

      1.3 - biometrics_score < 500

      2.1 - hzn_address_info_result == reprovado

      2.2 - hzn_consumer_doc_result == reprovado

      2.3 - hzn_vtal_client_result == reprovado

      2.4 - hzn_cour_case_result == reprovado

      2.5 - hzn_serarasa_result or hzn_serpro_result == reprovado

      2.6 - hzn_corp_doc_result === reprovado

      3.1- chegou ate aqui e nao desistiu

      3.2 - chegou ate aqui e installation_date == Null e desistiu

      3.3.1 -  subscriberID sem data de instalacao

      **3.3.2 - deixou de ser cliente em 7 dias**

      3.3.3 - subID com data de instalacao





ifelse(

 {barreira_auditoria_endereco}=1, 'Endereço Inválido',

 ifelse(

  {barreira_auditoria_identidade}=1, 'Identidade Inválida',

  ifelse(

   {barreira_auditoria_juridico}=1, 'Pendências Jurídicas',

   ifelse(

​    {barreira_auditoria_serasa}=1, 'Filtro SERASA',

​    ifelse(

​      {barreira_auditoria_cnpj}=1, 'CNPJ Inválido',

​      NULL

​    )

   )

  )

 )

)