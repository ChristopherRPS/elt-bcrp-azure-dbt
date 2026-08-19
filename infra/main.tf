# Infraestructura como código para el proyecto ELT BCRP en Azure.
#
# Provisiona: Resource Group, cuenta de almacenamiento con jerarquía
# habilitada (ADLS Gen2) con contenedores bronze/silver/gold, un Key Vault
# para credenciales, y un Azure Database for PostgreSQL Flexible Server
# (tier Burstable B1ms, el más económico) que funciona como warehouse de
# la capa gold para dbt.
#
# DECISIÓN: se evaluó primero Azure SQL Database + dbt-sqlserver, pero ese
# adaptador (via su dependencia dbt-fabric) tiene incompatibilidades
# internas no resueltas entre versiones (falla tanto en el código Python
# como en las macros SQL). Se migró a PostgreSQL porque usa dbt-postgres
# -- el adaptador más maduro y estable del ecosistema dbt, sin dependencia
# de drivers ODBC ni compiladores en Windows -- y porque es el mismo motor
# que ya se usa en el resto del portafolio. Ver docs/architecture.md.
#
# Uso (recomendado: Azure Cloud Shell, ya autenticado, sin instalar nada):
#   cd infra
#   terraform init
#   terraform plan -var="pg_admin_password=TuPasswordFuerte123!" -var="my_ip_address=$(curl -s ifconfig.me)"
#   terraform apply -var="pg_admin_password=TuPasswordFuerte123!" -var="my_ip_address=$(curl -s ifconfig.me)"
#   # ... tomar capturas de pantalla / probar el pipeline ...
#   terraform destroy   # <- importante para no generar costo recurrente

terraform {
  required_version = ">= 1.7"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.90"
    }
  }
}

provider "azurerm" {
  features {}
}

# Toma el tenant_id automaticamente de la sesion ya autenticada
# (az login / Cloud Shell), sin necesidad de pedirlo como variable.
data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "this" {
  name     = var.resource_group_name
  location = var.location
}

resource "azurerm_storage_account" "datalake" {
  name                     = var.storage_account_name
  resource_group_name      = azurerm_resource_group.this.name
  location                 = azurerm_resource_group.this.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  is_hns_enabled           = true # habilita namespace jerárquico = ADLS Gen2

  tags = {
    project = "bcrp-elt-portfolio"
  }
}

resource "azurerm_storage_data_lake_gen2_filesystem" "bronze" {
  name               = "bronze"
  storage_account_id = azurerm_storage_account.datalake.id
}

resource "azurerm_storage_data_lake_gen2_filesystem" "silver" {
  name               = "silver"
  storage_account_id = azurerm_storage_account.datalake.id
}

resource "azurerm_storage_data_lake_gen2_filesystem" "gold" {
  name               = "gold"
  storage_account_id = azurerm_storage_account.datalake.id
}

resource "azurerm_key_vault" "this" {
  name                = var.key_vault_name
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"
}

# --- Warehouse para la capa gold (dbt corre aquí en target=azure) ---

resource "azurerm_postgresql_flexible_server" "this" {
  name                = var.pg_server_name
  resource_group_name = azurerm_resource_group.this.name
  # Igual que con el intento anterior de SQL Server: se deja en una variable
  # separada por si esta región también tuviera restricciones de aprovisionamiento
  # en la cuenta trial.
  location   = var.pg_location
  version    = "16"
  sku_name   = "B_Standard_B1ms" # tier Burstable, el más económico (~$12-15 USD/mes)
  storage_mb = 32768             # 32 GB, el mínimo permitido

  administrator_login    = var.pg_admin_username
  administrator_password = var.pg_admin_password

  zone                   = "1"
  backup_retention_days  = 7

  tags = {
    project = "bcrp-elt-portfolio"
  }
}

resource "azurerm_postgresql_flexible_server_database" "gold" {
  name      = "bcrp_gold"
  server_id = azurerm_postgresql_flexible_server.this.id
  collation = "en_US.utf8"
  charset   = "utf8"
}

# Permite que otros servicios de Azure se conecten (ej. si luego se agrega
# Azure Data Factory como orquestador).
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.this.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

# Permite conectarte desde tu propia IP (para correr `dbt run --target azure`
# desde tu maquina). Actualiza var.my_ip_address si tu IP cambia -- común si
# tu proveedor de internet no te da una IP fija.
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_my_ip" {
  name             = "AllowMyIP"
  server_id        = azurerm_postgresql_flexible_server.this.id
  start_ip_address = var.my_ip_address
  end_ip_address   = var.my_ip_address
}

# TODO: azurerm_data_factory + linked services hacia ADLS y el servidor
# de PostgreSQL, si decides usar ADF como orquestador en vez de Airflow
# (ver README sección 5).
