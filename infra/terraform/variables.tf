variable "cloudflare_account_id" {
  description = "Cuenta de Cloudflare de Carlos (no es secreto: aparece en las URLs del panel)."
  type        = string
  default     = "1e6a34cfe895e17e830e8d7824b429b2"
}

variable "manage_shared_dns" {
  description = <<-EOT
    Registros de top8.uk que Kuulis usa pero que comparte con otros proyectos del homelab (el comodín
    *.top8.uk). Por defecto se documentan y no se adoptan, para que un error aquí no tumbe NDS ni el resto.
  EOT
  type        = bool
  default     = false
}

variable "manage_r2_lifecycle" {
  description = <<-EOT
    Gestionar las reglas de retención del bucket kuulis-backups. El proveedor no puede importarlas, así que el
    primer apply las reescribe (con las mismas reglas de cloudflare.tf). Revisarlas antes de activarlo.
  EOT
  type        = bool
  default     = false
}
