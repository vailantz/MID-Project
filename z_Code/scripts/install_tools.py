"""Install pinned portable tools inside .runtime; no administrator required."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
import hashlib
import shutil
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1] / ".runtime"
PACKAGES = [
    (
        "mongodb",
        "https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-8.0.28.zip",
        "sha256",
    ),
    (
        "elasticsearch",
        "https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-8.19.23-windows-x86_64.zip",
        "sha512",
    ),
]


def download_mongodb(url, archive):
    # Independent byte ranges avoid a slow single connection to the large ZIP.
    partial = archive.with_suffix(".part")
    offset = partial.stat().st_size if partial.exists() else 0
    request = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        total = int(response.headers["Content-Range"].split("/")[-1])
    chunks = ROOT / "mongodb-download"
    chunks.mkdir(exist_ok=True)
    ranges = [
        (start, min(start + 8 * 1024 * 1024, total) - 1)
        for start in range(offset, total, 8 * 1024 * 1024)
    ]

    def fetch(bounds):
        start, end = bounds
        part = chunks / str(start)
        if not part.exists() or part.stat().st_size != end - start + 1:
            request = urllib.request.Request(
                url, headers={"Range": f"bytes={start}-{end}"}
            )
            with urllib.request.urlopen(request, timeout=120) as response, part.open(
                "wb"
            ) as output:
                if (
                    response.headers.get("Content-Range")
                    != f"bytes {start}-{end}/{total}"
                ):
                    raise RuntimeError("Unexpected MongoDB byte range")
                shutil.copyfileobj(response, output)
            if part.stat().st_size != end - start + 1:
                raise RuntimeError("Incomplete MongoDB download range")
        return part

    with ThreadPoolExecutor(max_workers=12) as pool:
        parts = list(pool.map(fetch, ranges))
    with archive.open("wb") as output:
        if partial.exists():
            with partial.open("rb") as source:
                shutil.copyfileobj(source, output)
        for part in parts:
            with part.open("rb") as source:
                shutil.copyfileobj(source, output)


def install(package):
    name, url, algorithm = package
    target = ROOT / name
    marker = target / ".installed"
    if marker.exists():
        print(name + ": already installed", flush=True)
        return
    ROOT.mkdir(parents=True, exist_ok=True)
    archive = ROOT / (name + ".zip")
    if not archive.exists():
        print(name + ": downloading", flush=True)
        if name == "mongodb":
            download_mongodb(url, archive)
        else:
            with urllib.request.urlopen(
                url, timeout=120
            ) as response, archive.with_suffix(".part").open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            archive.with_suffix(".part").replace(archive)
    if algorithm:
        with urllib.request.urlopen(url + "." + algorithm, timeout=60) as response:
            expected = response.read().decode().split()[0].lower()
        digest = hashlib.new(algorithm)
        with archive.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise RuntimeError(name + ": archive checksum mismatch")
        print(name + ": checksum verified", flush=True)
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        # Debug symbols are not needed to execute the database server.
        members = [m for m in source.infolist() if not m.filename.endswith(".pdb")]
        for member in members:
            if (
                not (target / member.filename)
                .resolve()
                .is_relative_to(target.resolve())
            ):
                raise RuntimeError("Unsafe archive path")
        source.extractall(target, members=members)
    marker.write_text(url + "\n", encoding="utf-8")
    print(name + ": installed", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-running", action="store_true")
    args = parser.parse_args()
    if args.check_running:
        from support import es, mongo

        elastic = es("GET", "")["version"]["number"]
        with mongo() as client:
            mongodb = client.server_info()["version"]
        if not elastic.startswith("8.19.") or not mongodb.startswith("8."):
            raise RuntimeError(
                "Use Elasticsearch 8.19.x and MongoDB 8.x, or run setup without -UseExisting."
            )
        print(f"Using MongoDB {mongodb} and Elasticsearch {elastic}.")
    else:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(install, PACKAGES))
