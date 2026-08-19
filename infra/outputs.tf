output "storage_account_name" {
  value = azurerm_storage_account.datalake.name
}

output "storage_account_key" {
  description = "Para AZURE_STORAGE_ACCOUNT_KEY en tu .env (extract_bcrp.py sube el bronze a ADLS Gen2 con esto)"
  value       = azurerm_storage_account.datalake.primary_access_key
  sensitive   = true
}

output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "key_vault_uri" {
  value = azurerm_key_vault.this.vault_uri
}

output "pg_server_fqdn" {
  description = "Host para DBT_PG_HOST en tu .env"
  value       = azurerm_postgresql_flexible_server.this.fqdn
}

output "pg_database_name" {
  description = "Nombre para DBT_PG_DATABASE en tu .env"
  value       = azurerm_postgresql_flexible_server_database.gold.name
}
