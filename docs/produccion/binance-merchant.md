# Plan: pasar a Binance Pay Merchant

Hoy las recargas llegan a una **cuenta personal de Binance** y se concilian leyendo su historial de Binance Pay
con una clave de solo lectura (`api/apps/wallet/binance.py`). Funciona, pero tiene riesgos: la cuenta está a
nombre de una persona, Binance puede limitarla por volumen comercial, y el motorizado tiene que escribir la
referencia o registrar su Pay ID para que sepamos de quién es cada pago.

Binance Pay Merchant exige una empresa registrada (KYB). Este es el plan para cuando exista.

## Qué cambia
| | Hoy (cuenta personal) | Merchant |
| --- | --- | --- |
| Cómo paga el motorizado | Envía USDT al Pay ID de Kuulis | La app crea una orden y abre el checkout de Binance |
| Cómo sabemos quién pagó | Pay ID verificado o referencia escrita | La orden lleva nuestro `merchantTradeNo` |
| Confirmación | Leemos el historial cada minuto | Binance llama a nuestro webhook (firmado) |
| Monto | Lo que el motorizado envíe | Fijo en la orden |
| Recibo | No fiscal | Puede ser fiscal (con RIF de la empresa) |

## Pasos
1. **Empresa y KYB**: registrar la empresa, abrir la cuenta Merchant y pasar la verificación de Binance.
2. **Claves**: crear la API key del merchant (certificado y clave secreta) y guardarlas en Coolify como
   variables de entorno nuevas, sin tocar las de solo lectura actuales.
3. **API**:
   - `POST /wallet/me/top-ups` crea la orden en Binance (`/binancepay/openapi/v3/order`) con
     `merchantTradeNo` = id de la recarga y guarda el `prepayId`; devuelve el enlace o el QR del checkout.
   - `POST /webhooks/binance-pay`: verifica la firma, busca la recarga por `merchantTradeNo` y llama a la
     misma función que hoy acredita (`services._complete`), así que recibos, cobro de cuotas e invariantes no
     cambian. Idempotente por id de transacción (ya hay índice único).
   - Mantener la conciliación por historial como red de seguridad: si un webhook se pierde, la pasada de cada
     minuto lo encuentra y la consulta `queryOrder` lo confirma.
4. **App**: el botón "Recargar" abre el checkout de Binance (deep link) en vez de mostrar el Pay ID. Sale como
   OTA si no hace falta código nativo nuevo.
5. **Convivencia**: durante un mes aceptar las dos formas. Los Pay ID verificados siguen acreditándose solos.
6. **Recibos fiscales**: con empresa, agregar RIF y razón social al recibo y decidir si se emite factura
   (consultar al contador).
7. **Apagar lo viejo**: cuando nadie use la cuenta personal en 30 días, quitar su Pay ID de Ajustes y dejar la
   clave de lectura solo para el cierre mensual.

## Riesgos
- Binance Merchant cobra comisión por orden (revisar la tarifa vigente); hoy la recarga no tiene costo.
- El webhook necesita una URL pública estable de la API (ya existe detrás de NPM y Traefik).
- Si Binance cambia su API, la conciliación por historial sigue funcionando como respaldo.
