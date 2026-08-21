# IlanDetect

`ilan.gov.tr`, Kariyer Kapısı, İŞKUR, ÖSYM, Resmî Gazete ve YÖK kaynaklarındaki kamu personeli
ilanlarını tek kullanıcı filtresine göre izlemek için FastAPI tabanlı MVP iskeleti.

Şu anda çalışan bölüm; yapılandırma, SQLite/PostgreSQL uyumlu veri modeli, kaynak bağdaştırıcı
sınırları, sağlık uçları, Docker kurulumu ve temel testlerdir. Gerçek ilan toplama, kaynak kullanım
izni ve örnek veri sözleşmeleri doğrulandıktan sonra etkinleştirilecektir. Bu bilinçli sınır,
belgelenmemiş özel API'lere üretim bağımlılığı kurulmasını önler.

## Yerel çalıştırma

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

Kontrol:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/sources/status
curl 'http://localhost:8000/api/v1/listings/sample?limit=5'
curl -X POST 'http://localhost:8000/api/v1/scans/kariyer-kapisi?limit=10'
curl 'http://localhost:8000/api/v1/listings?limit=20'
curl -X PUT 'http://localhost:8000/api/v1/user-filter' \
  -H 'Content-Type: application/json' \
  -d '{"email":"kullanici@example.com","cities":["Ankara"],"include_keywords":["mühendis"],"kpss_required":true}'
curl 'http://localhost:8000/api/v1/listings/matches'
curl 'http://localhost:8000/api/v1/digest/preview'
curl -X POST 'http://localhost:8000/api/v1/digest/send'
pytest
ruff check .
```

Docker ile:

```bash
docker compose up --build
```

API belgeleri: `http://localhost:8000/docs`

Kaynak keşif notları: [docs/source-analysis.md](docs/source-analysis.md).
Yayın ve GitHub cron kurulumu: [docs/deployment.md](docs/deployment.md).

## Sonraki geliştirme sırası

1. Kaynak kullanım iznini teyit et ve kalan sitemap/veri örneklerini fixture olarak ekle.
2. Yönetim ekranından filtre, tarama ve test e-postası yönetimini ekle.
3. ilan.gov.tr sitemap + detay bağdaştırıcısını hız limitiyle ekle.
4. İŞKUR kamu işçi ve ÖSYM tercih bağdaştırıcılarını ekle.
5. Resmî Gazete ve YÖK ayrıştırıcılarını ekle.
6. Upsert, içerik parmak izi ve değişiklik kaydı iş akışını bağla.
7. Filtre motoru, Resend özeti ve günlük zamanlanmış görevi ekle.
8. Tek kullanıcılı yönetim ekranını ekle.
