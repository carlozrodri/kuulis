# Contrato de API · Fase 1A (cuentas, motorizados y configuración)

Base: `/api/v1`. Errores con el sobre estándar `{"error": {"code", "message", "details"}}`.
Fechas en ISO 8601. Los ids son UUID. "Staff" = roles `staff` o `admin`.

## Login social

| Método | Ruta | Cuerpo | Respuesta |
| --- | --- | --- | --- |
| POST | `/auth/social/google` | `{"id_token": str}` | `AuthResponse` (igual que `/auth/login`) |
| POST | `/auth/social/apple` | `{"id_token": str, "full_name": str \| null}` | `AuthResponse` |

- Google: el `id_token` se valida con las llaves públicas de Google; `aud` debe estar en
  `GOOGLE_CLIENT_IDS` (lista separada por comas) e `iss` en `accounts.google.com` / `https://accounts.google.com`.
  Se exige `email_verified`.
- Apple: llaves de `https://appleid.apple.com/auth/keys`, `iss` = `https://appleid.apple.com`, `aud` en
  `APPLE_CLIENT_IDS`. Apple solo envía el nombre la primera vez (lo manda la app en `full_name`) y el email
  puede ser un relay privado o no venir en logins siguientes.
- Orden de búsqueda: cuenta social (`provider`, `sub`) → usuario con el mismo email (se vincula) → usuario nuevo
  (`is_verified = true`, sin contraseña).
- Errores: `social_token_invalid` (401), `social_provider_disabled` (400, si la lista de client ids está vacía),
  `user_inactive` (401).

## Configuración

Valores editables desde el admin, con estos valores por defecto:

| Clave | Defecto | Descripción |
| --- | --- | --- |
| `driver_min_age` | `21` | Edad mínima del motorizado |
| `vehicle_min_year` | `{"moto": 2013, "car": 1993}` | Año mínimo por tipo de vehículo |
| `enabled_vehicle_types` | `["moto"]` | Tipos aceptados hoy |
| `driver_required_documents` | `["id_card", "rif", "drivers_license", "medical_certificate", "vehicle_registration", "selfie", "vehicle_photo"]` | Documentos obligatorios |
| `vehicle_photo_min_count` | `2` | Fotos mínimas de la moto |

| Método | Ruta | Quién | Respuesta |
| --- | --- | --- | --- |
| GET | `/config/public` | cualquiera | `AppConfig` (todas las claves de arriba) |
| GET | `/admin/config` | staff | `AppConfig` |
| PATCH | `/admin/config` | admin | cuerpo parcial de `AppConfig` → `AppConfig` |

## Motorizados

Estados del perfil: `draft` → `pending_review` → `approved` | `rejected`; `approved` ↔ `suspended`.
Un perfil `rejected` se puede corregir y reenviar.

Tipos de documento (`kind`): `id_card` (cédula), `rif`, `drivers_license`, `medical_certificate`,
`vehicle_registration` (carnet de circulación), `selfie`, `vehicle_photo` (varias).
Estado de cada documento: `pending`, `approved`, `rejected`.

### `DriverProfile`
```json
{
  "id": "uuid", "user_id": "uuid", "status": "draft",
  "birth_date": "1995-04-12", "national_id": "V12345678", "rif": "V123456789", "phone": "+584121234567",
  "city": "caracas", "rejection_reason": null,
  "submitted_at": null, "reviewed_at": null, "approved_at": null,
  "vehicle": {"id": "uuid", "type": "moto", "brand": "Yamaha", "model": "YBR 125", "year": 2019, "plate": "AB2C34D", "color": "Negra"},
  "documents": [{"id": "uuid", "kind": "id_card", "status": "pending", "content_type": "image/jpeg", "rejection_reason": null, "created_at": "..."}],
  "requirements": {"missing_documents": ["selfie"], "vehicle_photos": 1, "vehicle_photos_required": 2,
                    "age_ok": true, "vehicle_ok": true, "can_submit": false}
}
```

| Método | Ruta | Cuerpo | Notas |
| --- | --- | --- | --- |
| GET | `/drivers/me` | | 404 `driver_not_found` si no existe |
| PUT | `/drivers/me` | `{birth_date, national_id, rif, phone}` | Crea o edita; solo en `draft` o `rejected` |
| PUT | `/drivers/me/vehicle` | `{type, brand, model, year, plate, color}` | Valida tipo habilitado y año mínimo; placa única |
| POST | `/drivers/me/documents/presign` | `{kind, filename, content_type, size}` | Devuelve `{key, upload_url, headers, expires_in}`; jpg, png, webp, heic o pdf |
| POST | `/drivers/me/documents` | `{kind, key}` | Registra el archivo ya subido; reemplaza el anterior del mismo tipo salvo `vehicle_photo` |
| DELETE | `/drivers/me/documents/{id}` | | Solo en `draft` o `rejected` |
| POST | `/drivers/me/submit` | | Pasa a `pending_review` si `can_submit`; si no, 400 `driver_requirements_missing` con el detalle |

### Admin (staff)

| Método | Ruta | Cuerpo | Notas |
| --- | --- | --- | --- |
| GET | `/admin/drivers` | `?status=&q=&page=&size=` | Paginado como `/users`; `q` busca nombre, email, cédula o placa |
| GET | `/admin/drivers/{id}` | | `DriverProfile` + `user` + cada documento con `download_url` firmada |
| POST | `/admin/drivers/{id}/approve` | | `pending_review` → `approved` |
| POST | `/admin/drivers/{id}/reject` | `{reason}` | `pending_review` → `rejected`; `reason` obligatorio |
| POST | `/admin/drivers/{id}/suspend` | `{reason}` | `approved` → `suspended` |
| POST | `/admin/drivers/{id}/reinstate` | | `suspended` → `approved` |
| POST | `/admin/drivers/{id}/documents/{doc_id}/review` | `{status, reason}` | Aprueba o rechaza un documento |

Cada cambio de estado notifica al motorizado (push + bandeja) en su idioma.
