import io
import os
import time
import zipfile

import pytest
from fastapi import HTTPException
from PIL import Image as PILImage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.opening_archive import SiteOpeningArchive
from app.models.site import Site
from app.models.user import User
from app.services import archive_batch_export as batch


def _photo(path, size=(3000, 2000)):
    PILImage.effect_noise(size, 80).convert("RGB").save(path, "JPEG", quality=95)
    return path


def _content(photo_paths):
    return {
        "check_categories": [
            {
                "category_id": "c1",
                "category_name": "安装",
                "items": [
                    {
                        "item_id": "i1",
                        "item_name": "设备照片",
                        "fields": [{"field_id": "sn", "label": "SN", "type": "text"}],
                        "values": {"sn": "SN-001"},
                        "photos": [{"file_path": p} for p in photo_paths],
                    }
                ],
            }
        ]
    }


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "EXPORT_ROOT", str(tmp_path / "exports"))
    batch._jobs.clear()
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    db = factory()
    photos = [_photo(str(tmp_path / f"p{i}.jpg")) for i in range(3)]
    db.add_all(
        [
            User(id=1, username="admin", email="a@example.com", hashed_password="x", full_name="Admin"),
            User(id=2, username="tom", email="t@example.com", hashed_password="x", full_name="Tom"),
            Site(id=10, site_code="KA4874-TDD", site_name="Kabira-TDD"),
            Site(id=11, site_code="KA4874-FDD", site_name="Kabira-FDD"),
            SiteOpeningArchive(id="a1", site_id=10, work_order_id="w1", inspection_id="n1", template_id="t1",
                               current_version=1, content=_content(photos)),
            SiteOpeningArchive(id="a2", site_id=11, work_order_id="w2", inspection_id="n2", template_id="t1",
                               current_version=2, content=_content(photos[:1])),
        ]
    )
    db.commit()
    yield {"factory": factory, "db": db, "photos": photos, "tmp": tmp_path}
    db.close()
    batch._jobs.clear()


def _wait(job_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = batch.get_job(job_id)
        if job["status"] not in batch.ACTIVE_STATUSES:
            return job
        time.sleep(0.1)
    raise AssertionError("batch export did not finish")


def test_photo_resizer_shrinks_large_photo_and_keeps_small_jpeg(tmp_path):
    big = _photo(str(tmp_path / "big.jpg"))
    small = _photo(str(tmp_path / "small.jpg"), size=(800, 600))
    resize = batch.make_photo_resizer(str(tmp_path / "cache"))

    out = resize(big)
    assert out != big
    with PILImage.open(out) as im:
        assert max(im.size) == batch.PHOTO_MAX_PX
    assert os.path.getsize(out) < os.path.getsize(big) / 3
    assert resize(small) == small


def test_batch_job_packs_pdfs_and_reports_missing(env):
    job = batch.create_job(
        archive_type="opening", ids=["a1", "a2", "missing", "a1"], locale="en-US",
        user_id=1, session_factory=env["factory"],
    )
    assert job["total"] == 3  # 去重
    done = _wait(job["job_id"])

    assert done["status"] == "done"
    assert done["success_count"] == 2
    assert done["errors"] == [{"id": "missing", "name": "missing", "message": "档案不存在"}]
    assert done["file_name"].startswith("Site Installation Archive_Batch_Export_")

    with zipfile.ZipFile(done["file_path"]) as zf:
        names = zf.namelist()
        pdfs = [n for n in names if n.endswith(".pdf")]
        assert len(pdfs) == 2
        assert any("KA4874-TDD_Kabira-TDD_v1" in n for n in pdfs)
        assert zf.read("export_failures.txt").decode() == "missing: Archive not found\n"
        assert all(zf.read(n).startswith(b"%PDF") for n in pdfs)
        batch_pdf_size = max(zf.getinfo(n).file_size for n in pdfs)

    # 照片已压缩：批量 PDF 明显小于原图版单个导出
    from app.api.opening_archives import _load_archive_for_export, _render_archive_pdf

    original, _, _ = _render_archive_pdf(_load_archive_for_export(env["db"], "a1"), locale_code="en-US")
    assert batch_pdf_size < len(original.getvalue()) / 3
    # 压缩缓存随档案清理，只留下 zip
    assert os.listdir(os.path.dirname(done["file_path"])) == ["export.zip"]


def test_all_failed_job_is_marked_failed(env):
    job = batch.create_job(archive_type="ssv", ids=["nope"], locale="zh-CN", user_id=1, session_factory=env["factory"])
    done = _wait(job["job_id"])
    assert done["status"] == "failed"
    assert done["message"] == "所选档案均导出失败"
    assert done["file_path"] is None


def test_low_disk_space_stops_job(env, monkeypatch):
    monkeypatch.setattr(batch, "MIN_FREE_BYTES", 1 << 62)
    job = batch.create_job(archive_type="opening", ids=["a1"], locale="zh-CN", user_id=1, session_factory=env["factory"])
    done = _wait(job["job_id"])
    assert done["status"] == "failed"
    assert done["message"] == "服务器磁盘空间不足，已停止导出"
    assert not os.path.exists(os.path.join(batch.EXPORT_ROOT, job["job_id"]))


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"archive_type": "bad", "ids": ["a1"]}, "不支持的档案类型"),
        ({"archive_type": "opening", "ids": []}, "请选择要导出的档案"),
        ({"archive_type": "opening", "ids": [str(i) for i in range(31)]}, "单次最多导出 30 个档案"),
    ],
)
def test_create_job_validation(env, kwargs, message):
    with pytest.raises(ValueError, match=message):
        batch.create_job(locale="zh-CN", user_id=1, session_factory=env["factory"], **kwargs)


def test_one_active_job_per_user(env):
    batch._jobs["busy"] = {"id": "busy", "user_id": 1, "status": "running"}
    with pytest.raises(ValueError, match="已有批量导出任务进行中"):
        batch.create_job(archive_type="opening", ids=["a1"], locale="zh-CN", user_id=1, session_factory=env["factory"])
    batch._jobs.pop("busy")


def test_endpoints_guard_owner_and_unfinished_download(env):
    from app.api.archive_exports import download_batch_export, get_batch_export

    from types import SimpleNamespace

    admin = SimpleNamespace(id=1, is_admin=True)
    tom = SimpleNamespace(id=2, is_admin=False)
    job = batch.create_job(archive_type="opening", ids=["a2"], locale="zh-CN", user_id=1, session_factory=env["factory"])
    with pytest.raises(HTTPException) as exc:
        get_batch_export(job["job_id"], current_user=tom)
    assert exc.value.status_code == 404

    done = _wait(job["job_id"])
    assert get_batch_export(job["job_id"], current_user=admin)["status"] == "done"
    resp = download_batch_export(job["job_id"])
    assert resp.path == done["file_path"]

    with pytest.raises(HTTPException) as exc:
        download_batch_export("unknown")
    assert exc.value.status_code == 404


def test_expired_jobs_are_swept(env):
    job = batch.create_job(archive_type="opening", ids=["a2"], locale="zh-CN", user_id=1, session_factory=env["factory"])
    done = _wait(job["job_id"])
    batch.sweep_expired_jobs(now=done["finished_ts"] + batch.JOB_TTL_SECONDS + 1)
    assert batch.get_job(job["job_id"]) is None
    assert not os.path.exists(os.path.dirname(done["file_path"]))


def test_single_pdf_export_still_streams_original_quality(env):
    import asyncio

    from app.api.opening_archives import export_archive_pdf

    resp = export_archive_pdf("a1", with_thumbs=True, locale="zh-CN", db=env["db"], current_user=None)

    async def read():
        return b"".join([c async for c in resp.body_iterator])

    data = asyncio.run(read())
    assert data.startswith(b"%PDF")
    assert "KA4874-TDD" in resp.headers["content-disposition"]
    assert len(data) > sum(os.path.getsize(p) for p in env["photos"]) * 0.9


def test_batch_export_messages_are_localized():
    from app.i18n.error_localization import localize_text

    assert localize_text("单次最多导出 30 个档案", "en-US") == "Up to 30 archives per export"
    assert localize_text("服务器磁盘空间不足，已停止导出", "id-ID") == "Ruang disk server tidak cukup; ekspor dihentikan"
