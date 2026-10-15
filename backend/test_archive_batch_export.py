import asyncio
import io
import os
import time
import zipfile
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from PIL import Image as PILImage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.opening_archive import SiteOpeningArchive
from app.models.site import Site
from app.services import archive_batch_export as batch
from app.services import archive_pdf_cache as cache


def _photo(path, size=(3000, 2000)):
    PILImage.effect_noise(size, 80).convert("RGB").save(path, "JPEG", quality=95)
    return path


def _content(photo_paths, sn="SN-001"):
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
                        "values": {"sn": sn},
                        "photos": [{"file_path": p} for p in photo_paths],
                    }
                ],
            }
        ]
    }


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_ROOT", str(tmp_path / "cache"))
    monkeypatch.setattr(batch, "EXPORT_ROOT", str(tmp_path / "cache" / "_exports"))
    batch._jobs.clear()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    db = factory()
    photos = [_photo(str(tmp_path / f"p{i}.jpg")) for i in range(3)]
    db.add_all(
        [
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


def _download(job_id, part=1):
    from app.api.archive_exports import download_batch_export

    resp = download_batch_export(job_id, part=part)

    async def read():
        return b"".join([c async for c in resp.body_iterator])

    return resp, asyncio.run(read())


def _archive(env, archive_id="a1"):
    return cache.load_archive(env["db"], "opening", archive_id)


def test_photo_resizer_shrinks_large_photo_and_keeps_small_jpeg(tmp_path):
    big = _photo(str(tmp_path / "big.jpg"))
    small = _photo(str(tmp_path / "small.jpg"), size=(800, 600))
    resize = cache.make_photo_resizer(str(tmp_path / "img"))

    out = resize(big)
    with PILImage.open(out) as im:
        assert max(im.size) == cache.PHOTO_MAX_PX
    assert os.path.getsize(out) < os.path.getsize(big) / 3
    assert resize(small) == small


def test_cache_reuses_unchanged_archive_and_regenerates_on_change(env):
    db = env["db"]
    first = cache.get_or_render("opening", _archive(env), "en-US")
    assert first["from_cache"] is False
    again = cache.get_or_render("opening", _archive(env), "en-US")
    assert again["from_cache"] is True and again["path"] == first["path"]

    # 照片已压缩：缓存 PDF 明显小于原图
    assert first["size"] < sum(os.path.getsize(p) for p in env["photos"]) / 3

    # 档案内容变化 -> 重新生成，旧缓存删除
    a = _archive(env)
    a.content = _content(env["photos"], sn="SN-002")
    db.commit()
    changed = cache.get_or_render("opening", _archive(env), "en-US")
    assert changed["from_cache"] is False and changed["path"] != first["path"]
    assert not os.path.exists(first["path"])

    # 照片文件被替换（大小变化）也会重新生成
    _photo(env["photos"][0], size=(2000, 1500))
    os.utime(env["photos"][0], (time.time() + 5, time.time() + 5))
    assert cache.get_or_render("opening", _archive(env), "en-US")["from_cache"] is False

    # 不同语言各自缓存
    zh = cache.get_or_render("opening", _archive(env), "zh-CN")
    assert zh["from_cache"] is False and zh["human_base"].startswith("开站档案_")
    assert len([n for n in os.listdir(os.path.dirname(zh["path"])) if n.endswith(".pdf")]) == 2


def test_preview_reports_cached_size_parts_and_missing(env):
    db = env["db"]
    before = batch.preview(db, archive_type="opening", ids=["a1", "a2", "missing"], locale="en-US")
    assert before["total"] == 3
    assert before["missing_count"] == 1
    assert before["render_count"] == 2 and before["cached_count"] == 0
    assert before["estimated_bytes"] == 2 * cache.EST_BYTES_BASE + 4 * cache.EST_BYTES_PER_PHOTO
    assert before["estimated_seconds"] > 0
    assert before["parts"] == 1

    entry = cache.get_or_render("opening", _archive(env), "en-US")
    after = batch.preview(db, archive_type="opening", ids=["a1", "a2"], locale="en-US")
    assert after["cached_count"] == 1 and after["render_count"] == 1
    assert after["estimated_bytes"] == entry["size"] + cache.EST_BYTES_BASE + cache.EST_BYTES_PER_PHOTO
    # 预估不生成任何文件
    assert batch.preview(db, archive_type="opening", ids=["a2"], locale="en-US")["cached_count"] == 0


def test_filters_select_all_matching_archives(env):
    db = env["db"]
    assert batch.resolve_ids(db, "opening", filters={"keyword": "TDD"}) == ["a1"]
    assert sorted(batch.resolve_ids(db, "opening", filters={})) == ["a1", "a2"]
    for filters in ({"keyword": "NOPE"}, {"date_from": "2999-01-01T00:00:00.000Z"}):
        with pytest.raises(ValueError, match="没有可导出的档案"):
            batch.resolve_ids(db, "opening", filters=filters)


def test_batch_job_streams_zip_reuses_cache_and_reports_missing(env):
    cache.get_or_render("opening", _archive(env), "en-US")
    job = batch.create_job(env["db"], archive_type="opening", ids=["a1", "a2", "missing", "a1"], locale="en-US",
                           user_id=1, session_factory=env["factory"])
    assert job["total"] == 3  # 去重
    done = batch.public_job(_wait(job["job_id"]))

    assert done["status"] == "done"
    assert done["success_count"] == 2 and done["cached_count"] == 1
    assert done["errors"] == [{"id": "missing", "name": "missing", "message": "档案不存在"}]
    assert len(done["parts"]) == 1

    resp, data = _download(job["job_id"])
    assert "Site%20Installation%20Archive_Batch_Export_" in resp.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert zf.testzip() is None
        pdfs = [n for n in zf.namelist() if n.endswith(".pdf")]
        assert len(pdfs) == 2
        assert any("KA4874-TDD_Kabira-TDD_v1" in n for n in pdfs)
        assert all(zf.read(n).startswith(b"%PDF") for n in pdfs)
        assert zf.read("export_failures.txt").decode() == "missing: Archive not found\n"


def test_large_export_is_split_into_volumes(env, monkeypatch):
    monkeypatch.setattr(batch, "VOLUME_BYTES", 1)
    job = batch.create_job(env["db"], archive_type="opening", filters={}, locale="zh-CN",
                           user_id=1, session_factory=env["factory"])
    done = batch.public_job(_wait(job["job_id"]))
    assert [p["count"] for p in done["parts"]] == [1, 1]
    names = []
    for part in (1, 2):
        resp, data = _download(job["job_id"], part)
        assert f"part{part}of2" in resp.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            assert zf.testzip() is None
            names += zf.namelist()
    assert len(names) == 2 and len(set(names)) == 2
    with pytest.raises(HTTPException) as exc:
        _download(job["job_id"], 3)
    assert exc.value.status_code == 404


def test_low_disk_space_stops_job(env, monkeypatch):
    monkeypatch.setattr(cache, "MIN_FREE_BYTES", 1 << 62)
    job = batch.create_job(env["db"], archive_type="opening", ids=["a1"], locale="zh-CN", user_id=1,
                           session_factory=env["factory"])
    done = _wait(job["job_id"])
    assert done["status"] == "failed"
    assert done["message"] == "服务器磁盘空间不足，已停止导出"


def test_low_disk_space_evicts_least_recently_used_cache(env, monkeypatch):
    old = cache.get_or_render("opening", _archive(env, "a2"), "en-US")
    os.utime(old["path"], (1, 1))
    free = iter([0, cache.min_free_bytes()])
    monkeypatch.setattr(cache, "_free_bytes", lambda: next(free))
    cache.ensure_free_space(allow_evict=True)
    assert not os.path.exists(old["path"])

    monkeypatch.setattr(cache, "_free_bytes", lambda: 0)
    with pytest.raises(cache.DiskSpaceError):
        cache.ensure_free_space(allow_evict=False)


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"archive_type": "bad", "ids": ["a1"]}, "不支持的档案类型"),
        ({"archive_type": "opening", "ids": []}, "没有可导出的档案"),
        ({"archive_type": "opening", "ids": ["1", "2", "3"]}, "单次最多导出 2 个档案"),
        ({"archive_type": "opening", "filters": {"date_from": "not-a-date"}}, "日期格式不正确"),
    ],
)
def test_create_job_validation(env, monkeypatch, kwargs, message):
    monkeypatch.setattr(batch, "MAX_ARCHIVES", 2)
    with pytest.raises(ValueError, match=message):
        batch.create_job(env["db"], locale="zh-CN", user_id=1, session_factory=env["factory"], **kwargs)


def test_one_active_job_per_user(env):
    batch._jobs["busy"] = {"id": "busy", "user_id": 1, "status": "running"}
    with pytest.raises(ValueError, match="已有批量导出任务进行中"):
        batch.create_job(env["db"], archive_type="opening", ids=["a1"], locale="zh-CN", user_id=1,
                         session_factory=env["factory"])
    batch._jobs.pop("busy")


def test_endpoints_guard_owner_and_unfinished_download(env):
    from app.api.archive_exports import download_batch_export, get_batch_export

    admin = SimpleNamespace(id=1, is_admin=True)
    tom = SimpleNamespace(id=2, is_admin=False)
    job = batch.create_job(env["db"], archive_type="opening", ids=["a2"], locale="zh-CN", user_id=1,
                           session_factory=env["factory"])
    with pytest.raises(HTTPException) as exc:
        get_batch_export(job["job_id"], current_user=tom)
    assert exc.value.status_code == 404
    _wait(job["job_id"])
    assert get_batch_export(job["job_id"], current_user=admin)["status"] == "done"
    with pytest.raises(HTTPException) as exc:
        download_batch_export("unknown", part=1)
    assert exc.value.status_code == 404


def test_expired_jobs_are_swept(env):
    job = batch.create_job(env["db"], archive_type="opening", ids=["a2"], locale="zh-CN", user_id=1,
                           session_factory=env["factory"])
    done = _wait(job["job_id"])
    batch.sweep_expired_jobs(now=done["finished_ts"] + batch.JOB_TTL_SECONDS + 1)
    assert batch.get_job(job["job_id"]) is None
    assert not os.path.exists(batch._job_dir(job["job_id"]))


def test_single_pdf_export_shares_cache(env):
    from app.api.opening_archives import export_archive_pdf

    first = export_archive_pdf("a1", with_thumbs=True, locale="en-US", db=env["db"], current_user=None)
    entry = cache.lookup("opening", _archive(env), "en-US")
    assert first.path == entry["path"]
    assert "KA4874-TDD" in first.headers["content-disposition"]
    # 批量导出直接复用同一份
    assert batch.preview(env["db"], archive_type="opening", ids=["a1"], locale="en-US")["cached_count"] == 1

    no_thumbs = export_archive_pdf("a1", with_thumbs=False, locale="en-US", db=env["db"], current_user=None)
    assert not hasattr(no_thumbs, "path")


def test_prewarm_generates_english_and_removes_orphans(env):
    orphan = os.path.join(cache.CACHE_ROOT, "opening", "deleted-archive")
    os.makedirs(orphan)
    assert batch.start_prewarm(env["factory"]) is True
    deadline = time.time() + 60
    while batch._prewarm["running"] and time.time() < deadline:
        time.sleep(0.1)
    assert batch._prewarm["rendered"] == 2
    assert cache.lookup("opening", _archive(env, "a1"), "en-US")
    assert cache.lookup("opening", _archive(env, "a2"), "en-US")
    assert not os.path.exists(orphan)

    # 再跑一轮：档案未变化，全部跳过
    batch.start_prewarm(env["factory"])
    while batch._prewarm["running"] and time.time() < deadline:
        time.sleep(0.1)
    assert batch._prewarm["rendered"] == 0 and batch._prewarm["skipped"] == 2


def test_free_space_floor_reserves_room_for_database_backup(monkeypatch):
    monkeypatch.setattr(cache, "_database_bytes", lambda: 3 * 1024 ** 3)
    assert cache.min_free_bytes() == cache.MIN_FREE_BYTES + 3 * 1024 ** 3
    monkeypatch.setattr(cache, "_free_bytes", lambda: cache.MIN_FREE_BYTES + 1024 ** 3)
    with pytest.raises(cache.DiskSpaceError):
        cache.ensure_free_space(allow_evict=False)


def test_batch_export_messages_are_localized():
    from app.i18n.error_localization import localize_text

    assert localize_text("单次最多导出 30 个档案", "en-US") == "Up to 30 archives per export"
    assert localize_text("没有可导出的档案", "id-ID") == "Tidak ada arsip untuk diekspor"
    assert localize_text("服务器磁盘空间不足，已停止导出", "id-ID") == "Ruang disk server tidak cukup; ekspor dihentikan"
