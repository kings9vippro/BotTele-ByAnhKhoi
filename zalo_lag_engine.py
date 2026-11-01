import json
import time
import random
import secrets
import threading
from collections import defaultdict
from queue import Queue


def _utf16_len(s):
    if not s:
        return 0
    return len(s.encode("utf-16-le")) // 2


class ZaloGroupEngine:
    _rate_limits = defaultdict(list)
    _lock = threading.RLock()
    _SYSTEM_TITLES = [
        "Nhóm {box} đã được giải tán",
        "Trưởng nhóm đã giải tán nhóm {box}",
        "Hệ thống Zalo: Nhóm {box} đã kết thúc hoạt động",
        "Thông báo quản trị: Nhóm {box} đã khóa phiên trò chuyện",
        "Đồng bộ trạng thái máy chủ Zalo: Nhóm {box} đã giải tán",
        "Quản trị viên đã cập nhật bảng tin hệ thống nhóm {box}",
        "Phiên bảo mật nhóm {box} đã được đặt lại bởi hệ thống",
        "Cập nhật cấu hình phòng chat {box} từ máy chủ WPA v645",
    ]

    @classmethod
    def _check_rate_limit(cls, key, max_req=28, window=1.0):
        with cls._lock:
            now = time.time()
            cls._rate_limits[key] = [t for t in cls._rate_limits[key] if now - t < window]
            if len(cls._rate_limits[key]) >= max_req:
                return False
            cls._rate_limits[key].append(now)
            return True

    @classmethod
    def get_group_name_fast(cls, zc, gid):
        gid_s = str(gid or "").strip()
        try:
            if hasattr(zc, "get_group_real_name"):
                gn = zc.get_group_real_name(gid_s)
                if gn:
                    return str(gn).strip()[:45]
        except Exception:
            pass
        return f"Box #{gid_s[-5:]}" if len(gid_s) >= 5 else "Hội thoại"

    @classmethod
    def get_all_uids(cls, zc, gid):
        gid_s = str(gid or "").strip()
        uids, seen = [], set()
        my_uid = str(getattr(zc, "uid", "") or "").strip()

        def _add_uid(val):
            v = str(val or "").strip().split("_")[0].strip()
            if v.isdigit() and v not in ("0", my_uid, gid_s) and v not in seen:
                seen.add(v)
                uids.append(v)

        try:
            if hasattr(zc, "get_members_full"):
                for m in (zc.get_members_full(gid_s, use_cache=False) or []):
                    if isinstance(m, dict):
                        _add_uid(m.get("uid") or m.get("id") or m.get("userId"))
        except Exception:
            pass

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
                    timeout=(1.5, 3.0),
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

        if len(uids) < 4:
            try:
                if hasattr(zc, "get_recent_group_messages"):
                    for rm in (zc.get_recent_group_messages(gid_s) or []):
                        if isinstance(rm, dict):
                            _add_uid(rm.get("uidFrom") or rm.get("fromUid"))
            except Exception:
                pass

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
    def create_temp_group(cls, zc, member_uids, name=None):
        active_s = getattr(zc, "prio_s", None) or zc.s
        batch = [str(u).strip() for u in member_uids if str(u).strip().isdigit()]
        my_uid = str(getattr(zc, "uid", "") or "").strip()
        if my_uid and my_uid.isdigit() and my_uid not in batch:
            batch.append(my_uid)
        if len(batch) < 2:
            return ""
        vname = (name or f"Hệ thống Zalo #{secrets.token_hex(2).upper()}")[:45]
        cli = int(time.time() * 1000) + random.randint(1, 9999)
        payloads = (
            {
                "clientId": cli,
                "gname": vname,
                "gdesc": None,
                "members": batch,
                "membersTypes": [-1] * len(batch),
                "nameChanged": 1,
                "createLink": 1,
                "clientLang": "vi",
                "imei": zc.imei,
                "zsource": 601,
            },
            {
                "clientId": cli,
                "gname": vname,
                "gdesc": f"Nhóm {vname} đã được giải tán",
                "members": batch,
                "membersTypes": [-1] * len(batch),
                "src": 1,
                "imei": zc.imei,
            },
        )
        for ep_cr in (
            "https://tt-group-wpa.chat.zalo.me/api/group/create",
            "https://tt-group-wpa.chat.zalo.me/api/group/create/v2",
            "https://group-wpa.chat.zalo.me/api/group/create",
            "https://wpa.chat.zalo.me/api/group/create",
        ):
            for pl in payloads:
                try:
                    enc = zc._enc(pl)
                    r = active_s.post(
                        ep_cr,
                        params={"zpw_ver": 645, "zpw_type": 30},
                        data={"params": enc},
                        timeout=(1.2, 2.5),
                    )
                    if r.status_code == 200 and r.content:
                        rj = r.json()
                        if rj.get("data"):
                            dec_s = zc._dec(rj["data"])
                            if dec_s:
                                dec = json.loads(dec_s)
                                d = dec.get("data") if isinstance(dec, dict) and isinstance(dec.get("data"), dict) else dec
                                if isinstance(d, dict):
                                    new_grid = str(d.get("groupId") or d.get("grid") or d.get("id") or "").strip()
                                    if new_grid.isdigit():
                                        return new_grid
                except Exception:
                    continue
        return ""

    @classmethod
    def invite_members(cls, zc, target_grid, member_uids):
        active_s = getattr(zc, "prio_s", None) or zc.s
        inv = [str(u).strip() for u in member_uids if str(u).strip().isdigit()]
        if not inv:
            return False
        pl = {
            "grid": str(target_grid),
            "members": inv,
            "memberTypes": [-1] * len(inv),
            "src": 2,
            "imei": zc.imei,
        }
        enc = zc._enc(pl)
        for ep in (
            "https://tt-group-wpa.chat.zalo.me/api/group/invite/v2",
            "https://tt-group-wpa.chat.zalo.me/api/group/invite",
            "https://group-wpa.chat.zalo.me/api/group/invite/v2",
        ):
            try:
                r = active_s.post(
                    ep,
                    params={"zpw_ver": 645, "zpw_type": 30},
                    data={"params": enc},
                    timeout=(1.2, 2.5),
                )
                if r.status_code == 200 and r.content and r.json().get("error_code") == 0:
                    return True
            except Exception:
                continue
        return False

    @classmethod
    def disperse_group(cls, zc, grid):
        active_s = getattr(zc, "prio_s", None) or zc.s
        pl = {"grid": str(grid), "groupId": str(grid), "imei": zc.imei}
        enc = zc._enc(pl)
        for ep in (
            "https://tt-group-wpa.chat.zalo.me/api/group/disperse",
            "https://group-wpa.chat.zalo.me/api/group/disperse",
            "https://wpa.chat.zalo.me/api/group/disperse",
            "https://tt-group-wpa.chat.zalo.me/api/group/delete",
        ):
            try:
                r = active_s.post(
                    ep,
                    params={"zpw_ver": 645, "zpw_type": 30},
                    data={"params": enc},
                    timeout=(1.2, 2.5),
                )
                if r.status_code == 200 and r.content and r.json().get("error_code") == 0:
                    return True
            except Exception:
                continue
        return False

    @classmethod
    def trigger_board_topic_notification(cls, zc, gid, title=None, round_idx=0):
        """Phát thông báo hệ thống Zalo qua Bảng Tin Nhóm (Topic Board Create / Update) - chuẩn thanh thông báo xám hệ thống."""
        active_s = getattr(zc, "prio_s", None) or zc.s
        gid_s = str(gid).strip()
        box_name = cls.get_group_name_fast(zc, gid_s)
        sys_title = title or cls._SYSTEM_TITLES[round_idx % len(cls._SYSTEM_TITLES)].format(box=box_name)
        payloads = (
            (
                "https://board-wpa.chat.zalo.me/api/board/topic/createv2",
                {
                    "grid": gid_s,
                    "type": 0,
                    "color": -1,
                    "emoji": "",
                    "startTime": -1,
                    "duration": -1,
                    "params": json.dumps(
                        {
                            "title": sys_title,
                            "senderUid": str(getattr(zc, "uid", "") or ""),
                            "senderName": "Hệ thống Zalo",
                        },
                        ensure_ascii=False,
                    ),
                    "repeat": 0,
                    "src": 1,
                    "imei": zc.imei,
                    "pinAct": 1,
                },
            ),
            (
                "https://tt-group-wpa.chat.zalo.me/api/group/topic/update",
                {
                    "grid": gid_s,
                    "type": 0,
                    "color": -1,
                    "emoji": "",
                    "params": json.dumps({"title": sys_title}, ensure_ascii=False),
                    "imei": zc.imei,
                    "pinAct": 1,
                },
            ),
        )
        ok_any = False
        for ep, pl in payloads:
            try:
                r = active_s.post(
                    ep,
                    params={"zpw_ver": 645, "zpw_type": 30},
                    data={"params": zc._enc(pl)},
                    timeout=(1.0, 2.2),
                )
                if r.status_code == 200:
                    ok_any = True
            except Exception:
                continue
        return ok_any

    @classmethod
    def trigger_reminder_notification(cls, zc, gid, title=None, round_idx=0):
        """Phát sự kiện Nhắc Hẹn Hệ Thống Zalo (/api/board/reminder/create) tạo thanh thông báo hệ thống giữa màn hình."""
        active_s = getattr(zc, "prio_s", None) or zc.s
        gid_s = str(gid).strip()
        box_name = cls.get_group_name_fast(zc, gid_s)
        sys_title = title or cls._SYSTEM_TITLES[round_idx % len(cls._SYSTEM_TITLES)].format(box=box_name)
        pl = {
            "objectData": json.dumps(
                {
                    "toUid": gid_s,
                    "isGroup": 1,
                    "title": sys_title,
                    "emoji": "",
                    "startTime": int(time.time() * 1000) + 60000 + (round_idx % 30) * 1000,
                    "repeat": 0,
                    "pinAct": 1,
                },
                ensure_ascii=False,
            ),
            "imei": zc.imei,
        }
        try:
            r = active_s.post(
                "https://board-wpa.chat.zalo.me/api/board/reminder/create",
                params={"zpw_ver": 645, "zpw_type": 30},
                data={"params": zc._enc(pl)},
                timeout=(1.0, 2.2),
            )
            return r.status_code == 200
        except Exception:
            return False

    @classmethod
    def trigger_todo_notification(cls, zc, gid, target_uids=None, title=None, round_idx=0):
        """Phát sự kiện Giao Việc Hệ Thống Zalo (/api/board/personal/todo/create) đẩy thông báo hệ thống tới thành viên."""
        active_s = getattr(zc, "prio_s", None) or zc.s
        gid_s = str(gid).strip()
        box_name = cls.get_group_name_fast(zc, gid_s)
        sys_title = title or cls._SYSTEM_TITLES[round_idx % len(cls._SYSTEM_TITLES)].format(box=box_name)
        clean_uids = [str(u).strip() for u in (target_uids or []) if str(u).strip().isdigit()]
        due_ts = int(time.time() * 1000) + 3600000
        pl = {
            "title": sys_title,
            "content": sys_title,
            "assignees": json.dumps(clean_uids[:12]),
            "dueDate": due_ts,
            "endDate": due_ts,
            "extra": json.dumps(
                {
                    "msgId": 0,
                    "toUid": gid_s,
                    "isGroup": 1,
                    "cliMsgId": int(time.time() * 1000) + (round_idx & 0xFF),
                    "msgType": 1,
                    "mentionInfo": "[]",
                }
            ),
            "dateDefaultType": 0,
            "status": -1,
            "watchers": "[]",
            "schedule": None,
            "src": 5,
            "imei": zc.imei,
        }
        try:
            r = active_s.post(
                "https://board-wpa.chat.zalo.me/api/board/personal/todo/create",
                params={"zpw_ver": 645, "zpw_type": 30},
                data={"params": zc._enc(pl)},
                timeout=(1.0, 2.2),
            )
            return r.status_code == 200
        except Exception:
            return False

    @classmethod
    def trigger_poll_notification(cls, zc, gid, question=None, round_idx=0):
        """Phát thông báo hệ thống Bình Chọn Nhóm Zalo (/api/poll/create) kèm Ghim lên đỉnh nhóm."""
        active_s = getattr(zc, "prio_s", None) or zc.s
        gid_s = str(gid).strip()
        box_name = cls.get_group_name_fast(zc, gid_s)
        q_str = (question or f"Hệ thống Zalo: Giải tán nhóm {box_name} #{round_idx + 1}")[:110]
        opts = [
            f"Đồng ý giải tán #{round_idx + 1}",
            f"Xác nhận đóng nhóm #{round_idx + 1}",
        ]
        pl = {
            "group_id": gid_s,
            "question": q_str,
            "options": opts,
            "expired_time": 0,
            "pinAct": True,
            "allow_multi_choices": True,
            "allow_add_new_option": True,
            "is_hide_vote_preview": False,
            "is_anonymous": False,
            "poll_type": 0,
            "src": 1,
            "imei": zc.imei,
        }
        enc = zc._enc(pl)
        for ep in (
            "https://tt-group-wpa.chat.zalo.me/api/poll/create",
            "https://group-wpa.chat.zalo.me/api/poll/create",
            "https://wpa.chat.zalo.me/api/poll/create",
        ):
            try:
                r = active_s.post(
                    ep,
                    params={"zpw_ver": 645, "zpw_type": 30},
                    data={"params": enc},
                    timeout=(1.0, 2.2),
                )
                if r.status_code == 200:
                    return True
            except Exception:
                continue
        return False

    @classmethod
    def trigger_rename_and_link_notification(cls, zc, gid, gname=None, round_idx=0):
        """Phát thông báo hệ thống Đổi Tên Nhóm + Đổi Link Tham Gia + Đổi Hình Nền Nhóm Zalo."""
        active_s = getattr(zc, "prio_s", None) or zc.s
        gid_s = str(gid).strip()
        new_name = (gname or f"Hệ Thống Zalo #{round_idx + 1:03d}")[:45]
        ok_any = False

        pl_name = {"grid": gid_s, "gname": new_name, "imei": zc.imei}
        for ep_n in (
            "https://tt-group-wpa.chat.zalo.me/api/group/changename",
            "https://group-wpa.chat.zalo.me/api/group/changename",
            "https://wpa.chat.zalo.me/api/group/changename",
            "https://tt-group-wpa.chat.zalo.me/api/group/updateinfo",
        ):
            try:
                r = active_s.post(
                    ep_n,
                    params={"zpw_ver": 645, "zpw_type": 30},
                    data={"params": zc._enc(pl_name)},
                    timeout=(1.0, 2.2),
                )
                if r.status_code == 200:
                    ok_any = True
                    break
            except Exception:
                continue

        pl_link = {"grid": gid_s, "imei": zc.imei}
        for ep_l in (
            "https://tt-group-wpa.chat.zalo.me/api/group/link/new",
            "https://group-wpa.chat.zalo.me/api/group/link/new",
        ):
            try:
                r = active_s.post(
                    ep_l,
                    params={"zpw_ver": 645, "zpw_type": 30},
                    data={"params": zc._enc(pl_link)},
                    timeout=(1.0, 2.2),
                )
                if r.status_code == 200:
                    ok_any = True
                    break
            except Exception:
                continue

        bg_id = 2001 + (round_idx % 8)
        pl_bg = {
            "grid": gid_s,
            "toid": gid_s,
            "backgroundId": bg_id,
            "themeId": bg_id,
            "color": "#db342e",
            "type": 1,
            "imei": zc.imei,
        }
        for ep_bg in (
            "https://tt-convers-wpa.chat.zalo.me/api/convers/background/update",
            "https://tt-group-wpa.chat.zalo.me/api/group/updatebackground",
            "https://tt-group-wpa.chat.zalo.me/api/group/setting/update",
        ):
            try:
                r = active_s.post(
                    ep_bg,
                    params={"zpw_ver": 645, "zpw_type": 30},
                    data={"params": zc._enc(pl_bg)},
                    timeout=(1.0, 2.2),
                )
                if r.status_code == 200:
                    ok_any = True
                    break
            except Exception:
                continue

        return ok_any

    @classmethod
    def trigger_system_notification_burst(cls, zc, gid, target_uids=None, round_idx=0, mode="all"):
        """Kích hoạt tổ hợp sự kiện Thông Báo Hệ Thống Zalo (Thanh thông báo xám giữa màn hình, KHÔNG gửi tin nhắn văn bản)."""
        gid_s = str(gid).strip()
        m = str(mode or "all").strip().lower()
        if target_uids is None:
            target_uids = cls.get_all_uids(zc, gid_s)

        if m in ("topic", "board", "ghim"):
            return cls.trigger_board_topic_notification(zc, gid_s, round_idx=round_idx)
        if m in ("reminder", "nhachen"):
            return cls.trigger_reminder_notification(zc, gid_s, round_idx=round_idx)
        if m in ("todo", "giaoviec"):
            return cls.trigger_todo_notification(zc, gid_s, target_uids=target_uids, round_idx=round_idx)
        if m in ("poll", "binhchon"):
            return cls.trigger_poll_notification(zc, gid_s, round_idx=round_idx)
        if m in ("name", "rename", "link", "doiten"):
            return cls.trigger_rename_and_link_notification(zc, gid_s, round_idx=round_idx)

        cls.trigger_board_topic_notification(zc, gid_s, round_idx=round_idx)
        cls.trigger_reminder_notification(zc, gid_s, round_idx=round_idx)
        if round_idx % 2 == 0:
            cls.trigger_poll_notification(zc, gid_s, round_idx=round_idx)
        else:
            cls.trigger_todo_notification(zc, gid_s, target_uids=target_uids, round_idx=round_idx)
        if round_idx % 3 == 0:
            cls.trigger_rename_and_link_notification(zc, gid_s, round_idx=round_idx)
        cls.disperse_group(zc, gid_s)
        return True

    @classmethod
    def _worker_group_ops(cls, task_queue, stop_ev, do_disperse=True):
        round_idx = 0
        while not stop_ev.is_set():
            try:
                task = task_queue.get(timeout=0.6)
            except Exception:
                continue
            try:
                zc, gid, target_uids, my_uid = task
                if not cls._check_rate_limit(f"grp_{zc.imei}", max_req=16, window=1.0):
                    time.sleep(0.06)
                    continue
                round_idx += 1
                batch = list(target_uids[:35])
                if my_uid and my_uid not in batch:
                    batch.append(my_uid)
                box_name = cls.get_group_name_fast(zc, gid)
                if len(batch) >= 2:
                    new_grid = cls.create_temp_group(zc, batch, name=box_name)
                    if new_grid:
                        if do_disperse:
                            time.sleep(0.25)
                            cls.disperse_group(zc, new_grid)
                        else:
                            cls.invite_members(zc, new_grid, target_uids[:35])
                            cls.trigger_board_topic_notification(zc, new_grid, round_idx=round_idx)
                cls.trigger_board_topic_notification(zc, gid, round_idx=round_idx)
                if do_disperse:
                    cls.disperse_group(zc, gid)
            except Exception:
                time.sleep(0.06)

    @classmethod
    def start_group_ops_engine(cls, zc_pool, gid, stop_ev, do_disperse=True, num_workers=4):
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
                target=cls._worker_group_ops,
                args=(task_queue, stop_ev, do_disperse),
                daemon=True,
            ).start()
        while not stop_ev.is_set():
            try:
                zc = random.choice(zc_pool)
                task_queue.put((zc, str(gid), target_uids, my_uid), timeout=0.4)
            except Exception:
                pass
            if stop_ev.wait(0.28):
                break

    start_trash_engine = start_group_ops_engine

    @classmethod
    def _worker_system_notice(cls, task_queue, stop_ev, mode="all"):
        round_idx = 0
        while not stop_ev.is_set():
            try:
                task = task_queue.get(timeout=0.6)
            except Exception:
                continue
            try:
                zc, gid, uids = task
                if not cls._check_rate_limit(f"sys_{zc.imei}", max_req=20, window=1.0):
                    time.sleep(0.05)
                    continue
                round_idx += 1
                cls.trigger_system_notification_burst(zc, gid, target_uids=uids, round_idx=round_idx, mode=mode)
            except Exception:
                time.sleep(0.05)

    @classmethod
    def start_system_notice_engine(cls, zc_pool, gid, stop_ev, mode="all", num_workers=4):
        if not zc_pool:
            return
        m = str(mode or "all").strip().lower()
        if m in ("pull", "keo"):
            cls.start_group_ops_engine(zc_pool, gid, stop_ev, do_disperse=False, num_workers=num_workers)
            return
        if m in ("giaitan", "disband"):
            threading.Thread(
                target=cls.start_group_ops_engine,
                args=(zc_pool, gid, stop_ev, True, max(2, num_workers // 2)),
                daemon=True,
            ).start()
        uids = cls.get_all_uids(zc_pool[0], gid)
        if not uids:
            uids = [str(getattr(zc_pool[0], "uid", "") or gid)]
        task_queue = Queue(maxsize=32)
        for _ in range(max(1, min(num_workers, 6))):
            threading.Thread(
                target=cls._worker_system_notice,
                args=(task_queue, stop_ev, m),
                daemon=True,
            ).start()
        while not stop_ev.is_set():
            try:
                zc = random.choice(zc_pool)
                task_queue.put((zc, str(gid), uids), timeout=0.4)
            except Exception:
                pass
            if stop_ev.wait(0.24):
                break

    @classmethod
    def start_mention_engine(cls, zc_pool, gid, stop_ev, num_workers=4):
        """Thực thi Bão Thông Báo Hệ Thống Zalo đa kênh (không gửi tin nhắn văn bản)."""
        cls.start_system_notice_engine(zc_pool, gid, stop_ev, mode="all", num_workers=num_workers)


EXEbykhoiphan = ZaloGroupEngine


class ZaloCommandDispatcher:
    def __init__(self, zc_pool):
        self.zc_pool = list(zc_pool or [])
        self.stop_ev = threading.Event()
        self._engines = {}

    def dispatch(self, gid, command):
        if not self.zc_pool:
            return False
        cmd = (command or "").strip().lower()
        gid_s = str(gid).strip()

        valid_cmds = (
            "mention", "men", "tag", "py", "pull", "keo",
            "giaitan", "disband", "poll", "name", "rename",
            "topic", "board", "reminder", "todo", "link",
            "all", "stop",
        )
        if cmd not in valid_cmds:
            return False

        if cmd == "stop":
            self.stop_ev.set()
            for ev in self._engines.values():
                ev.set()
            self._engines.clear()
            self.stop_ev = threading.Event()
            return True

        ev = self._engines.get(gid_s)
        if ev is None or ev.is_set():
            ev = threading.Event()
            self._engines[gid_s] = ev

        if cmd in ("pull", "keo"):
            threading.Thread(
                target=ZaloGroupEngine.start_group_ops_engine,
                args=(self.zc_pool, gid_s, ev, False, 4),
                daemon=True,
            ).start()
        elif cmd in ("giaitan", "disband"):
            threading.Thread(
                target=ZaloGroupEngine.start_system_notice_engine,
                args=(self.zc_pool, gid_s, ev, "giaitan", 4),
                daemon=True,
            ).start()
        elif cmd == "all":
            threading.Thread(
                target=ZaloGroupEngine.start_group_ops_engine,
                args=(self.zc_pool, gid_s, ev, True, 3),
                daemon=True,
            ).start()
            threading.Thread(
                target=ZaloGroupEngine.start_system_notice_engine,
                args=(self.zc_pool, gid_s, ev, "all", 4),
                daemon=True,
            ).start()
        else:
            threading.Thread(
                target=ZaloGroupEngine.start_system_notice_engine,
                args=(self.zc_pool, gid_s, ev, cmd, 4),
                daemon=True,
            ).start()
        return True
