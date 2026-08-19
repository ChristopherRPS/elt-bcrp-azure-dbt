variable "resource_group_name" {
  description = "Nombre del resource group para el proyecto"
  type        = string
  default     = "rg-bcrp-elt-portfolio"
}

variable "location" {
  description = "Región de Azure"
  type        = string
  default     = "eastus2" # o "brazilsouth" si buscas menor latencia desde Perú
}

variable "storage_account_name" {
  description = "Nombre de la cuenta de almacenamiento (debe ser único global, minúsculas, sin guiones, 3-24 caracteres)"
  type        = string
  default     = "stbcrpeltcp2026" # cámbialo si sale "ya existe", debe ser único a nivel Azure
}

variable "key_vault_name" {
  description = "Nombre del Key Vault (debe ser único global)"
  type        = string
  default     = "kv-bcrp-elt-cp2026"
}

variable "pg_location" {
  description = "Región para el PostgreSQL Flexible Server. Separada de `location` por si esta región también tuviera restricciones de aprovisionamiento en la cuenta trial (ver error 'ProvisioningDisabled' que ya salió con Azure SQL en eastus2)."
  type        = string
  default     = "brazilsouth" # cambia a "eastus" si esta también falla
}

variable "pg_server_name" {
  description = "Nombre del servidor de PostgreSQL Flexible Server (debe ser único global)"
  type        = string
  default     = "pg-bcrp-elt-cp2026"
}

variable "pg_admin_username" {
  description = "Usuario administrador del servidor PostgreSQL"
  type        = string
  default     = "bcrpadmin"
}

variable "pg_admin_password" {
  description = "Password del administrador de PostgreSQL. Debe cumplir la política de Azure (mayúscula, minúscula, número, símbolo, 8+ caracteres). Pásalo con -var, nunca lo dejes hardcodeado ni lo subas a git."
  type        = string
  sensitive   = true
}

variable "my_ip_address" {
  description = "Tu IP pública actual, para poder conectarte a la base de datos desde tu máquina. Obtenla con: curl -s ifconfig.me"
  type        = string
}
