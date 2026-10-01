<<<<<<< HEAD
# MCP-Documents



## Getting started

To make it easy for you to get started with GitLab, here's a list of recommended next steps.

Already a pro? Just edit this README.md and make it your own. Want to make it easy? [Use the template at the bottom](#editing-this-readme)!

## Add your files

* [Create](https://docs.gitlab.com/ee/user/project/repository/web_editor.html#create-a-file) or [upload](https://docs.gitlab.com/ee/user/project/repository/web_editor.html#upload-a-file) files
* [Add files using the command line](https://docs.gitlab.com/topics/git/add_files/#add-files-to-a-git-repository) or push an existing Git repository with the following command:

```
cd existing_repo
git remote add origin http://myrepo.lan.go.id/ai-lan/mcp-documents.git
git branch -M main
git push -uf origin main
```

## Integrate with your tools

* [Set up project integrations](http://myrepo.lan.go.id/ai-lan/mcp-documents/-/settings/integrations)

## Collaborate with your team

* [Invite team members and collaborators](https://docs.gitlab.com/ee/user/project/members/)
* [Create a new merge request](https://docs.gitlab.com/ee/user/project/merge_requests/creating_merge_requests.html)
* [Automatically close issues from merge requests](https://docs.gitlab.com/ee/user/project/issues/managing_issues.html#closing-issues-automatically)
* [Enable merge request approvals](https://docs.gitlab.com/ee/user/project/merge_requests/approvals/)
* [Set auto-merge](https://docs.gitlab.com/user/project/merge_requests/auto_merge/)

## Test and Deploy

Use the built-in continuous integration in GitLab.

* [Get started with GitLab CI/CD](https://docs.gitlab.com/ee/ci/quick_start/)
* [Analyze your code for known vulnerabilities with Static Application Security Testing (SAST)](https://docs.gitlab.com/ee/user/application_security/sast/)
* [Deploy to Kubernetes, Amazon EC2, or Amazon ECS using Auto Deploy](https://docs.gitlab.com/ee/topics/autodevops/requirements.html)
* [Use pull-based deployments for improved Kubernetes management](https://docs.gitlab.com/ee/user/clusters/agent/)
* [Set up protected environments](https://docs.gitlab.com/ee/ci/environments/protected_environments.html)

***

# Editing this README

When you're ready to make this README your own, just edit this file and use the handy template below (or feel free to structure it however you want - this is just a starting point!). Thanks to [makeareadme.com](https://www.makeareadme.com/) for this template.

## Suggestions for a good README

Every project is different, so consider which of these sections apply to yours. The sections used in the template are suggestions for most open source projects. Also keep in mind that while a README can be too long and detailed, too long is better than too short. If you think your README is too long, consider utilizing another form of documentation rather than cutting out information.

## Name
Choose a self-explaining name for your project.

## Description
Let people know what your project can do specifically. Provide context and add a link to any reference visitors might be unfamiliar with. A list of Features or a Background subsection can also be added here. If there are alternatives to your project, this is a good place to list differentiating factors.

## Badges
On some READMEs, you may see small images that convey metadata, such as whether or not all the tests are passing for the project. You can use Shields to add some to your README. Many services also have instructions for adding a badge.

## Visuals
Depending on what you are making, it can be a good idea to include screenshots or even a video (you'll frequently see GIFs rather than actual videos). Tools like ttygif can help, but check out Asciinema for a more sophisticated method.

## Installation
Within a particular ecosystem, there may be a common way of installing things, such as using Yarn, NuGet, or Homebrew. However, consider the possibility that whoever is reading your README is a novice and would like more guidance. Listing specific steps helps remove ambiguity and gets people to using your project as quickly as possible. If it only runs in a specific context like a particular programming language version or operating system or has dependencies that have to be installed manually, also add a Requirements subsection.

## Usage
Use examples liberally, and show the expected output if you can. It's helpful to have inline the smallest example of usage that you can demonstrate, while providing links to more sophisticated examples if they are too long to reasonably include in the README.

## Support
Tell people where they can go to for help. It can be any combination of an issue tracker, a chat room, an email address, etc.

## Roadmap
If you have ideas for releases in the future, it is a good idea to list them in the README.

## Contributing
State if you are open to contributions and what your requirements are for accepting them.

For people who want to make changes to your project, it's helpful to have some documentation on how to get started. Perhaps there is a script that they should run or some environment variables that they need to set. Make these steps explicit. These instructions could also be useful to your future self.

You can also document commands to lint the code or run tests. These steps help to ensure high code quality and reduce the likelihood that the changes inadvertently break something. Having instructions for running tests is especially helpful if it requires external setup, such as starting a Selenium server for testing in a browser.

## Authors and acknowledgment
Show your appreciation to those who have contributed to the project.

## License
For open source projects, say how it is licensed.

## Project status
If you have run out of energy or time for your project, put a note at the top of the README saying that development has slowed down or stopped completely. Someone may choose to fork your project or volunteer to step in as a maintainer or owner, allowing your project to keep going. You can also make an explicit request for maintainers.
=======
# SEIRAMA Document MCP

MCP server terpisah untuk pencarian semantik dan pengambilan isi PDF pada folder `Docs`, menggunakan Qdrant, FastEmbed, Docling, OCR, dan SQLite metadata seperti implementasi lama.

## Menjalankan

```powershell
pip install -e .
python document_server.py
```

Endpoint: `http://127.0.0.1:8001/mcp`

Tools: `document_search`, `document_get`, `document_index`.

Konfigurasi utama: `QDRANT_URL`, `QDRANT_COLLECTION`, `EMBEDDING_MODEL`, `DOCUMENT_PARSER` (`docling` atau `pypdf`), dan `DOCUMENT_OCR`.
<<<<<<< HEAD
>>>>>>> b4f021b (Add initial project structure with configuration, document handling, and server setup)
=======

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

<<<<<<< HEAD
Jika volume dibuat oleh project name Podman yang berbeda, lihat nama volume
dengan `podman volume ls`, lalu sesuaikan nilai `$volume`.
>>>>>>> 336fc17 (Add Podman Compose configuration for Qdrant service and update README)
=======
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
>>>>>>> 1d42bf8 (Enhance document processing features and update configurations)
