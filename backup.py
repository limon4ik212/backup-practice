"""ПР1. Резервное копирование с ротацией и проверкой целостности.
Вариант 6: KEEP_LAST = 3.

Запуск:
    python backup.py                 — создать копию, ротация, проверка восстановления
    python backup.py verify          — проверить последнюю копию
    python backup.py restore         — восстановить данные из последней копии
"""
import hashlib
import json
import shutil
import sys
import tarfile
import time
from datetime import datetime
from pathlib import Path

SOURCE = Path("company_data")   # что копируем
BACKUP_DIR = Path("backups")    # куда складываем архивы
KEEP_LAST = 3                   # сколько последних копий хранить (вариант 6)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def make_manifest(folder):
    """Контрольная сумма каждого файла: {относительный_путь: sha256}."""
    return {str(p.relative_to(folder).as_posix()): sha256(p)
            for p in sorted(folder.rglob("*")) if p.is_file()}


def safe_extract(archive, dest):
    """Распаковка архива. filter="data" (защита от опасных путей в архиве)
    есть только в новых версиях Python, в старых распаковываем без него."""
    with tarfile.open(archive) as tar:
        try:
            tar.extractall(dest, filter="data")
        except TypeError:
            tar.extractall(dest)


def manifest_path(archive):
    """backup_X.tar.gz -> backup_X.json"""
    return archive.with_suffix("").with_suffix(".json")


def create_backup():
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = BACKUP_DIR / f"backup_{stamp}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(SOURCE, arcname=SOURCE.name)
    manifest = {"created": stamp, "archive_sha256": sha256(archive),
                "files": make_manifest(SOURCE)}
    manifest_path(archive).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] Создан {archive.name}, файлов: {len(manifest['files'])}, "
          f"размер: {archive.stat().st_size / 1024:.1f} КБ")
    return archive


def rotate():
    archives = sorted(BACKUP_DIR.glob("backup_*.tar.gz"))
    for old in archives[:-KEEP_LAST]:
        old.unlink()
        manifest_path(old).unlink(missing_ok=True)
        print(f"[ROTATE] Удалена старая копия {old.name}")


def verify_restore(archive):
    """Восстанавливает архив во временную папку и сравнивает контрольные суммы."""
    manifest = json.loads(manifest_path(archive).read_text(encoding="utf-8"))
    if sha256(archive) != manifest["archive_sha256"]:
        print("[FAIL] Архив повреждён: контрольная сумма не совпадает")
        return False

    tmp = Path("restore_test")
    shutil.rmtree(tmp, ignore_errors=True)
    safe_extract(archive, tmp)
    restored = make_manifest(tmp / SOURCE.name)
    shutil.rmtree(tmp)

    if restored == manifest["files"]:
        print(f"[OK] Восстановление проверено: {len(restored)} файлов совпадают")
        return True

    # Задание 3: подробный отчёт о различиях
    expected = manifest["files"]
    missing = sorted(set(expected) - set(restored))   # есть в манифесте, нет в архиве
    extra = sorted(set(restored) - set(expected))     # есть в архиве, нет в манифесте
    changed = sorted(f for f in set(expected) & set(restored)
                     if expected[f] != restored[f])   # хеши не совпадают

    print("[FAIL] Восстановленные данные не совпадают с оригиналом")
    for f in missing:
        print(f"   [ОТСУТСТВУЕТ] {f}")
    for f in extra:
        print(f"   [ЛИШНИЙ]      {f}")
    for f in changed:
        print(f"   [ИЗМЕНЁН]     {f}")
    print(f"   Итого: отсутствует {len(missing)}, лишних {len(extra)}, изменено {len(changed)}")
    return False


def restore(archive):
    """Задание 4: восстанавливает company_data из выбранного архива."""
    start = time.perf_counter()
    manifest = json.loads(manifest_path(archive).read_text(encoding="utf-8"))
    if sha256(archive) != manifest["archive_sha256"]:
        print("[FAIL] Архив повреждён, восстановление отменено")
        return False

    shutil.rmtree(SOURCE, ignore_errors=True)        # удаляем повреждённую папку
    safe_extract(archive, SOURCE.parent)             # распаковываем в текущую папку

    ok = make_manifest(SOURCE) == manifest["files"]
    elapsed = time.perf_counter() - start
    status = "[OK]" if ok else "[FAIL]"
    print(f"{status} Данные восстановлены из {archive.name}, "
          f"файлов: {len(manifest['files'])}")
    print(f"Время восстановления: {elapsed:.3f} с")
    return ok


def latest_archive():
    archives = sorted(BACKUP_DIR.glob("backup_*.tar.gz"))
    if not archives:
        sys.exit("Нет ни одной резервной копии в папке backups/")
    return archives[-1]


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "backup"
    if cmd == "verify":
        verify_restore(latest_archive())
    elif cmd == "restore":
        restore(latest_archive())
    else:
        archive = create_backup()
        rotate()
        verify_restore(archive)
