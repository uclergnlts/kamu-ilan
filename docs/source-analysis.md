# Kaynak analizi — 20 Ağustos 2026

Bu belge ilk teknik keşfin nokta-zaman sonucudur. Özel/veri uçları resmî ve kararlı bir
entegrasyon sözleşmesi sayılmamalıdır; üretim kullanımı öncesinde kaynak sahiplerinden yazılı
izin veya açık API/RSS kullanım koşulu doğrulanmalıdır.

## ilan.gov.tr

- Resmî personel listesi: `https://www.ilan.gov.tr/ilan/tum-ilanlar/personel-alimi`
- Liste sayfası Angular/JavaScript kabuğudur. İlk HTML yanıtında ilanlar güvenilir biçimde yer
  almıyor; yalnız HTML ayrıştırmak yeterli değil.
- `robots.txt` 20 Ağustos 2026 tarihinde erişilebilir ve `daily-ads.xml` dahil ilan sitemap'leri
  yayımlıyor. Dosyadaki `Disallow: Disallow: /*tebligat` satırı biçimsel olarak hatalı görünüyor;
  bu durum otomatik tarama izni olarak yorumlanmamalı.
- Sitede RSS bağlantısı keşfedilmedi. Sitemap yeni URL keşfi için kullanılabilir, ancak kategori,
  detay alanları ve güncelleme davranışı örneklerle doğrulanmalı.
- Alt bilgi, içeriklerin izinsiz kullanılamayacağını belirtiyor. Bu nedenle üretim tarayıcısı
  devreye alınmadan önce Basın İlan Kurumu ile kullanım amacı ve istek sıklığı netleştirilmeli.
- Olası güvenli strateji: günde bir sitemap kontrolü, yalnız personel kategorisindeki yeni resmî
  URL'lerin düşük hızla alınması, kaynak metnin yeniden yayımlanmaması ve e-postada kısa alanlar
  ile doğrudan resmî bağlantının gösterilmesi.

## Kariyer Kapısı

- Güncel resmî adres: `https://kariyerkapisi.gov.tr/isealim`.
- Plandaki `https://isealimkariyerkapisi.cbiko.gov.tr` alan adı keşif sırasında DNS'te
  çözülmedi; kodda kullanılmamalı.
- Kamuya açık sayfa giriş yapmadan yükleniyor ve sunucu taraflı HTML ile JavaScript kullanıyor.
- Sayfanın kendisi `https://kariyerkapisi.gov.tr/RSS/RssLinkiAl` adresine görünür bir RSS
  bağlantısı veriyor. MVP için ilk tercih bu uç olmalı; RSS alanlarının kapsamı ve kalıcılığı
  gerçek örneklerle sözleşme testine alınmalı.
- Tarayıcı kodunda kamu sayfasının `https://api.kariyerkapisi.gov.tr/api` altında ilan arama
  çağrıları yaptığı görülüyor. Bu, belgelenmiş herkese açık API kanıtı değildir; izin ve sürüm
  garantisi olmadan doğrudan bağımlılık kurulmayacak.
- e-Devlet girişi ve başvuru işlemleri kapsam dışıdır. Sistem yalnız kamuya açık ilan bilgisini
  işler ve kullanıcıyı resmî başvuru adresine yönlendirir.

## Açık kararlar / sonraki doğrulama

1. Her iki kurumdan otomatik, düşük frekanslı kişisel bildirim kullanımı için yazılı onay veya
   açık lisans/koşul teyidi alınmalı.
2. Kariyer Kapısı RSS'sinden en az 20 ilan örneği arşivlenmeden alan eşleme kodu sabitlenmemeli.
3. ilan.gov.tr sitemap URL'lerinden personel kategorisi ayırma ve detay sayfası alanları için
   sözleşme testleri yazılmalı.
4. İstekler tanımlı User-Agent, zaman aşımı, geri çekilme ve kaynak başına hız sınırıyla yapılmalı.
5. Ham ilan metinleri e-postada yeniden yayımlanmamalı; yalnız filtreleme için gereken veriler ve
   resmî bağlantılar saklanmalı/gösterilmeli.

## Eklenen sonraki kaynaklar

- **İŞKUR:** Kamu kurumlarının sürekli/geçici işçi ilanları için Açık İş Haritası ve e-Şube araması.
- **ÖSYM:** KPSS genel, kurumsal ve EKPSS merkezi tercih duyuruları ile kadro tabloları.
- **Resmî Gazete:** Günlük gazetenin ilan bölümü; HTML/PDF ayrıştırması gerektirir.
- **YÖK/üniversiteler:** Akademik kadrolar ve düzeltme/iptal duyuruları; ilan.gov.tr ile güçlü
  mükerrerlik kontrolü gerekir.
- **Kurum duyuruları:** Bakanlık, belediye ve üniversite sayfaları `INSTITUTION_SOURCES` JSON ortam
  değişkeniyle kaynak listesine eklenebilir. Her farklı sayfa için veri toplamadan önce kuruma özel
  ayrıştırıcı ve sözleşme testi gerekir.
