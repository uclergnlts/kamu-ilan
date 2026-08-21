# Yayın ve GitHub cron kurulumu

## Mimari

GitHub Actions yalnız zamanlayıcıdır. Uygulama Render, Railway, Fly.io veya benzeri sürekli çalışan
bir Docker servisinde barındırılır; kalıcı veriler yönetilen PostgreSQL'de tutulur. GitHub görevi
her gün backend'in gizli anahtarla korunan `POST /api/v1/jobs/daily` adresini çağırır.

## Backend ortam değişkenleri

```text
APP_ENV=production
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE
TIMEZONE=Europe/Istanbul
ADMIN_EMAIL=uclergnlts_0101@hotmail.com
RESEND_API_KEY=...
EMAIL_FROM=IlanDetect <ilan@dogrulanmis-domain.com>
CRON_SECRET=uzun-rastgele-bir-deger
SCHEDULER_ENABLED=false
DAILY_SCAN_LIMIT=50
```

`RESEND_API_KEY`, veritabanı parolası ve `CRON_SECRET` yalnız hosting sağlayıcısının secret/env
alanında saklanmalıdır. `.env` dosyası repoya veya Docker image içine eklenmemelidir.

## GitHub repository secrets

Repository > Settings > Secrets and variables > Actions altında:

- `ILANDETECT_BASE_URL`: Yayındaki servisin HTTPS kök adresi, örneğin `https://ilan.example.com`
- `CRON_SECRET`: Backend'deki `CRON_SECRET` ile birebir aynı değer

`.github/workflows/daily-scan.yml` her gün 04:30 UTC'de, yani Europe/Istanbul için 07:30'da
çalışır. `workflow_dispatch` ile Actions ekranından elle de tetiklenebilir.

## Sağlık ve ilk doğrulama

```bash
curl https://BACKEND-ADRESI/health
curl https://BACKEND-ADRESI/api/v1/sources/status
curl -X POST https://BACKEND-ADRESI/api/v1/jobs/daily \
  -H "Authorization: Bearer CRON_SECRET"
```

İlk yayında PostgreSQL boş olacağı için tablolar uygulama başlangıcında oluşturulur. Üretimde ilk
şema değişikliğinden önce Alembic migration sistemi eklenmelidir.
