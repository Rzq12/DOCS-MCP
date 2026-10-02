# SEIRAMA Document MCP

MCP server terpisah untuk pencarian semantik dan pengambilan isi PDF pada folder `Docs`, menggunakan Qdrant, FastEmbed, Docling, OCR, dan SQLite metadata.

## Menjalankan

```powershell
pip install -e .
python document_server.py
```

Endpoint: `http://127.0.0.1:8001/mcp`

Tools: `document_search`, `document_get`, `document_index`.

Konfigurasi utama: `QDRANT_URL`, `QDRANT_COLLECTION`, `EMBEDDING_MODEL`, `DOCUMENT_PARSER` (`docling` atau `pypdf`), dan `DOCUMENT_OCR`.

## Menjalankan MCP dan Qdrant di VPS dengan Podman

Siapkan folder PDF di `Docs/`, lalu buat file `.env` dari `.env.example`. Jalankan:

```bash
podman compose -f podman-compose.yml up -d --build
podman compose -f podman-compose.yml ps
```

Endpoint MCP tersedia di `http://SERVER_IP:8001/mcp`. Port `6333` hanya diperlukan
untuk administrasi Qdrant; untuk VPS production, batasi aksesnya dengan firewall.

Untuk melihat log:

```bash
podman compose -f podman-compose.yml logs -f mcp
podman compose -f podman-compose.yml logs -f qdrant
```

## Menjalankan Qdrant dengan Podman

```powershell
podman compose -f podman-compose.yml up -d
podman compose -f podman-compose.yml ps
```

Qdrant tersedia di `http://localhost:6333`. Untuk menghentikan layanan:

```powershell
podman compose -f podman-compose.yml down
```

### Restore data Qdrant ke Podman

Restore dilakukan ke volume yang dipakai container Qdrant pada project ini.
Jalankan dari direktori `DOCS-MCP`. Contoh berikut mencari arsip terbaru dari
`~/mcp/backup/backups` dan menggunakan volume `docs-mcp_qdrant_data`.

```bash
cd ~/mcp/DOCS-MCP

backup_dir="$HOME/mcp/backup/backups"
archive_path="$(find "$backup_dir" -maxdepth 1 -type f -name 'qdrant_data_old_*.tar.gz' -printf '%T@ %p\n' \
	| sort -nr | head -n 1 | cut -d' ' -f2-)"
volume="docs-mcp_qdrant_data"

if [ -z "$archive_path" ]; then
	echo "Arsip Qdrant tidak ditemukan di $backup_dir" >&2
	exit 1
fi

echo "Archive: $archive_path"
echo "Volume : $volume"
podman volume inspect "$volume" >/dev/null || podman volume create "$volume"

# Hentikan hanya Qdrant agar MCP tidak ikut diubah.
podman compose -f podman-compose.yml stop qdrant

# Backup volume target sebelum ditimpa.
podman run --rm \
	-v "${volume}:/source:ro" \
	-v "$(pwd):/backup" \
	docker.io/alpine:3.20 \
	sh -c 'tar -czf /backup/qdrant_data_before_restore.tar.gz -C /source .'

# Restore isi arsip ke root volume Qdrant.
podman run --rm \
	-v "${volume}:/target" \
	-v "$(dirname "$archive_path"):/backup:ro" \
	docker.io/alpine:3.20 \
	sh -c "rm -rf /target/* /target/.[!.]* /target/..?* 2>/dev/null || true; tar -xzf /backup/$(basename "$archive_path") -C /target"

podman compose -f podman-compose.yml up -d qdrant
```

Verifikasi restore:

```bash
curl -s http://localhost:6333/collections | jq
curl -s http://localhost:6333/collections/seirama_documents | jq \
	'{status: .result.status, points_count: .result.points_count, indexed_vectors_count: .result.indexed_vectors_count}'
```

Restore berhasil jika koleksi `seirama_documents` muncul, `points_count` berisi
jumlah point yang diharapkan, dan status akhirnya `green`. Status `grey` dengan
`points_count` yang benar berarti Qdrant masih membangun index; tunggu lalu cek
kembali. Jika nama volume berbeda, cek dengan `podman inspect seirama-qdrant`
dan gunakan volume yang terpasang pada `/qdrant/storage`.
