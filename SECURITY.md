# Política de seguridad

## Reporte

No publiques vulnerabilidades ni credenciales en una issue. Usa el canal privado
**Security → Report a vulnerability** del repositorio cuando esté habilitado. Si
aún no existe remoto, contacta al propietario por un canal privado verificable.
Incluye impacto, reproducción mínima y versión afectada.

## Datos sensibles

Son sensibles `LLM_API_KEY`, `SMTP_USERNAME`, `SMTP_APP_PASSWORD`,
`GITHUB_TOKEN`, cualquier PAT, headers de autorización, cuerpo SMTP y direcciones
personales adicionales. Deben vivir sólo en `.env` ignorado o GitHub Secrets.

## Prácticas

- rota inmediatamente cualquier secreto expuesto;
- usa contraseña de aplicación de Gmail, no la contraseña principal;
- limita permisos de Actions a `contents: write` e `issues: write`;
- configura rulesets cuando quieras limitar efectivamente la rama de estado;
- revisa artifacts y logs antes de compartirlos;
- no incluyas datos reales en fixtures.

## Alcance

Este proyecto reduce riesgos de entrada RSS, logs y duplicación operativa. No
garantiza entrega, aislamiento multiusuario ni seguridad de proveedores externos.
Las dependencias se revisan semanalmente con Dependabot.
