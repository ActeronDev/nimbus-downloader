# Nimbus Downloader — plan (v1)

**by ActeronDev** — pencere başlığı, About penceresi ve exe sürüm bilgisinde.

## Stack
Python 3.13 + PySide6 arayüz, çekirdek `yt-dlp` kütüphanesi (aynı süreç, ilerleme hook'ları),
birleştirme/dönüşüm `ffmpeg` (pakete gömülü). PyInstaller `--onedir`.

## Tek pencere
- **Üst:** link kutusu · Video / Ses seçimi · kalite listesi · klasör seç · **İndir** butonu
- **Alt:** indirilenler tablosu — ad, durum, %/ilerleme, hız, kalan süre, boyut
- Her satırda: **Durdur / Devam / İptal / Klasörü aç**
- Alt sağ: toplam hız, "yt-dlp güncelle" butonu, "by ActeronDev"

## Kalite seçenekleri
- Video: En iyi · 2160p · 1440p · 1080p · 720p · 480p (en iyi görüntü + en iyi ses, `copy` ile birleşim)
- Ses: **m4a/opus (kopya, kayıpsız)** · mp3 320 · mp3 192

## Kuyruk
- Eşzamanlı indirme: 2 (ayarlardan 1-4). Fazlası ağ/diski tıkar.
- Kuyruk ve geçmiş `%APPDATA%\Nimbus\queue.json` içinde; program kapanıp açılınca durum korunur.
- İndirilenler: Video → `Videolar\Nimbus`, Ses → `Müzik\Nimbus` (değiştirilebilir).

## Durdur / devam nasıl çalışır
yt-dlp'de gerçek "duraklat" yok. Durdur = indirme sürecini kes, `.part` dosyası kalır.
Devam = `--continue` ile aynı yerden sürer. Parça parça (DASH) indirmede bu güvenilir;
tek parça akışlarda baştan başlayabilir — satırda bunu belirtiriz.

## v1'de YOK
Playlist/toplu indirme, tarayıcı eklentisi, altyazı, zamanlayıcı, tema seçenekleri, otomatik güncelleme sunucusu.

## Kabul kriterleri
1. Link + Video + 1080p → dosya klasörde, oynuyor, ses düzgün.
2. Aynı anda 3 indirme kuyruğa girip 2'si paralel yürüyor.
3. Durdur → devam aynı dosyayı bozmadan bitiriyor.
4. İptal → yarım dosya temizleniyor.
5. Program kapanıp açılınca kuyruk duruyor.
6. `by ActeronDev` görünür.
7. Zip klasör başka x64 Windows makinede Python'suz çalışıyor.
