# Las credenciales llegan por variables de entorno (README → «Credenciales»), nunca escritas aquí:
#   COOLIFY_ENDPOINT, COOLIFY_TOKEN  → proveedor coolify
#   CLOUDFLARE_API_TOKEN            → proveedor cloudflare
provider "coolify" {}

provider "cloudflare" {}
