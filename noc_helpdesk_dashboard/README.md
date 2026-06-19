# Network Helpdesk Dashboard — Odoo 16

Dashboard de monitoramento de chamados de falha de link de rede para Odoo 16.

## Funcionalidades

- **KPIs em tempo real**: Total, Em Aberto, Resolvidos, TMA, SLA Cumprido/Violado
- **Gráficos interativos** (Chart.js):
  - Chamados Abertos × Resolvidos por Mês
  - Distribuição por Tag (Indisponibilidade, Alta Latência, Descarte, Oscilação)
  - Chamados por Equipamento (Switch, Roteador, Access Point)
  - Chamados por Tag × Mês (stacked)
  - Tempo Médio de Atendimento por categoria
  - Tendência das últimas 8 semanas
- **Tabela Top Redes** com mais incidentes
- **Tabela de Chamados em Aberto** com status SLA (OK / VIOLADO)
- **Filtro de período**: 7D, 30D, 90D, 1A
- **Auto-refresh** a cada 5 minutos

## Instalação

### 1. Copiar o módulo

```bash
cp -r network_helpdesk_dashboard /opt/odoo/addons/
# ou no caminho dos seus addons customizados:
cp -r network_helpdesk_dashboard /opt/odoo/custom_addons/
```

### 2. Atualizar lista de módulos no Odoo

- Vá em **Configurações → Técnico → Atualizar Lista de Apps**
- Ou reinicie o servidor com: `./odoo-bin -u network_helpdesk_dashboard`

### 3. Instalar o módulo

- Vá em **Apps**
- Pesquise por `Network Helpdesk Dashboard`
- Clique em **Instalar**

### 4. Acessar o Dashboard

- No menu principal acesse **NetOps Dashboard → Dashboard de Chamados**

## Dependências Odoo

- `base`
- `web`
- `helpdesk` (módulo oficial Odoo Helpdesk)

## Configuração das Tags

Para que os gráficos reflitam corretamente os incidentes, configure as tags nos seus
chamados do Helpdesk com os seguintes termos:

| Tipo de Incidente       | Tag sugerida          |
| ----------------------- | --------------------- |
| Indisponibilidade total | `Indisponibilidade`   |
| Alta latência           | `Alta Latência`       |
| Descarte de pacotes     | `Descarte de Pacotes` |
| Oscilação de link       | `Oscilação`           |
| Switch                  | `Switch`              |
| Roteador                | `Roteador`            |
| Access Point            | `Access Point`        |

## Estrutura do Módulo

```
network_helpdesk_dashboard/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── main.py              ← Endpoints JSON com dados reais do Odoo
├── views/
│   └── dashboard_menu.xml   ← Menu + Client Action
├── static/src/
│   ├── css/
│   │   └── dashboard.css    ← Estilos completos
│   └── js/
│       └── dashboard.js     ← Componente OWL + Chart.js
└── security/
    └── ir.model.access.csv
```

## Versão

- **Odoo**: 16.0
- **Dashboard**: 1.0.0
