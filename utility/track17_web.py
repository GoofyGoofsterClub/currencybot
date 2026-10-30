import base64
import json
import os
import re
import struct
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import requests

from utility.parcels import (
    build_parcel_summary,
    describe_event,
    make_parcel,
    normalize_parcel_number,
    parse_time,
)

API_BASE = "https://t.17track.net"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Origin": API_BASE,
    "Referer": f"{API_BASE}/",
    "Content-Type": "application/json",
}
TIMEZONE_OFFSET_MINUTES = -480  # eg.DEFAULT_TIMEZONE_OFFSET / simulated browser TZ
WASM_PATH = Path(__file__).parent / "track17" / "fingerprint.wasm"

# Simulated browser environment. The WASM fingerprint module resolves the global
# scope through `self`/`window`/`globalThis`/`global` and requires the winner to
# pass `instanceof Window`; every other browser API is then read off that object.
CANVAS_DATA_URL = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

# Browser environment for the JS feature-probe IIFEs the WASM `eval`s. Built in
# JS so arbitrary probes run against a faithful DOM; values must match the
# reference environment exactly (they feed the fingerprint hash).
_JS_ENVIRONMENT = """
(function(){
  var DATAURL = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==";
  var navigator = {
    userAgent: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    language: "en-US",
    languages: ["en-US"],
    platform: "Linux x86_64",
    hardwareConcurrency: 8,
    maxTouchPoints: 0
  };
  var screen = { width: 1920, height: 1080, colorDepth: 24 };
  var ctx2d = {
    fillRect: function(){}, fillText: function(){}, beginPath: function(){},
    arc: function(){}, fill: function(){}, stroke: function(){},
    moveTo: function(){}, lineTo: function(){},
    textBaseline: "", font: "", fillStyle: "", strokeStyle: "", lineWidth: 0
  };
  var document = {
    createElement: function(t) {
      if (String(t).toLowerCase() === "canvas") {
        return {
          width: 0, height: 0,
          getContext: function(k) { return k === "2d" ? ctx2d : null; },
          toDataURL: function() { return DATAURL; }
        };
      }
      return {};
    }
  };
  var crypto = {
    getRandomValues: function(a) {
      for (var i = 0; i < a.length; i++) a[i] = (i * 37) & 0xff;
      return a;
    }
  };
  var win = {
    navigator: navigator, screen: screen, document: document,
    crypto: crypto, devicePixelRatio: 1
  };
  win.window = win; win.self = win; win.global = win; win.globalThis = win;
  var g = this;
  g.window = win; g.self = win; g.global = win; g.globalThis = win;
  g.document = document; g.navigator = navigator; g.screen = screen;
  g.crypto = crypto; g.devicePixelRatio = 1;
  g.performance = { now: function() { return 100; } };
  g.requestAnimationFrame = function() { return 0; };
  g.__fns = {};
})();
"""


class _Undefined:
    """JS `undefined` sentinel (distinct from JS `null` = Python None)."""

    __slots__ = ()

    def __repr__(self):
        return "undefined"


UNDEFINED = _Undefined()


class Window:
    pass


class HTMLCanvasElement:
    def __init__(self, bare=False):
        self.width = 0
        self.height = 0
        self._ctx = None
        self._bare = bare

    def getContext(self, kind):
        if self._bare or kind != "2d":
            return None
        if self._ctx is None:
            self._ctx = CanvasRenderingContext2D()
        return self._ctx

    def toDataURL(self):
        return CANVAS_DATA_URL


class CanvasRenderingContext2D:
    def __init__(self):
        self.font = ""
        self.textBaseline = ""
        self.fillStyle = ""
        self.strokeStyle = ""
        self.lineWidth = 0

    def fillRect(self, *a):
        pass

    def fillText(self, *a):
        pass

    def beginPath(self):
        pass

    def arc(self, *a):
        pass

    def fill(self):
        pass

    def stroke(self):
        pass

    def moveTo(self, *a):
        pass

    def lineTo(self, *a):
        pass


class BrowserDate:
    """`new Date` as the WASM sees it: toISOString + getTimezoneOffset."""

    def __init__(self, ts=None):
        self._dt = datetime.fromtimestamp(ts if ts is not None else time.time(), tz=timezone.utc)

    def toISOString(self):
        ms = self._dt.microsecond // 1000
        return (
            f"{self._dt:%Y-%m-%dT%H:%M:%S}.{ms:03d}Z"
        )

    def getTimezoneOffset(self):
        # Like the native Date method: minutes WEST of UTC (positive west).
        local = datetime.now().astimezone()
        return -int(local.utcoffset().total_seconds() // 60)

    def now(self):
        return int(self._dt.timestamp() * 1000)


class _BrowserGlobal(Window):
    """The resolved global object the WASM fingerprint reads from. Must be a
    `Window` instance: the WASM checks `instanceof Window` on the resolved
    global and unwraps (traps) if it fails."""

    def __init__(self):
        self.window = self
        self.self = self
        self.globalThis = self
        setattr(self, "global", self)
        self.navigator = {
            "userAgent": USER_AGENT,
            "language": "en-US",
            "languages": ["en-US"],
            "platform": "Linux x86_64",
            "hardwareConcurrency": 8,
            "maxTouchPoints": 0,
        }
        self.screen = {"width": 1920, "height": 1080, "colorDepth": 24}
        self.devicePixelRatio = 1
        self.document = {"createElement": self._create_element}
        self.crypto = {"getRandomValues": _DeterministicRandomValues()}
        self.msCrypto = None

    def _create_element(self, tag):
        if str(tag).lower() == "canvas":
            return HTMLCanvasElement()
        return HTMLCanvasElement(bare=True)


class _DeterministicRandomValues:
    """crypto.getRandomValues stand-in (deterministic per process)."""

    def __call__(self, buf):
        for i in range(len(buf)):
            buf[i] = (i * 37) & 0xFF
        return buf


class WasmFingerprint:
    """Runs the site's WASM fingerprint module (wasm-bindgen glue, Python port)."""

    def __init__(self):
        import wasmtime

        engine = wasmtime.Engine()
        module = wasmtime.Module(engine, WASM_PATH.read_bytes())
        self.store = wasmtime.Store(engine)
        self.engine = engine
        self.module = module

        global_obj = _BrowserGlobal()
        # Same layout as the JS glue heap: slots 0-32 undefined, 33 null,
        # 34 true, 35 false; the WASM may address these constants directly.
        self.heap = [UNDEFINED] * 33 + [None, True, False]
        self.heap_next = 36
        self.wasm_global = global_obj
        self.undefined = UNDEFINED
        self.window_cls = Window
        self.canvas_cls = HTMLCanvasElement
        self.ctx_cls = CanvasRenderingContext2D

        # quickjs runs the JS feature-probe IIFEs the WASM `eval`s (WebGL,
        # doNotTrack, plugins, FPS, ...); results feed the fingerprint hash.
        self._js = None
        self._fn_counter = 0
        try:
            import quickjs
        except ImportError:
            pass
        else:
            self._js = quickjs.Context()
            self._js.eval(_JS_ENVIRONMENT)

        linker = wasmtime.Linker(engine)
        import_types = {
            imp.name: imp.type
            for imp in self.module.imports
            if imp.module == "wbg"
        }
        defined = {}
        for name, fn in self._imports().items():
            ty = import_types.get(name)
            if ty is None:
                continue
            # wasmtime needs the exact result type back: coerce our Python
            # values to the wasm type (JS glue coerces the same way).
            if ty.results:
                rtype = str(ty.results[0])
                if rtype in ("f64", "f32"):
                    fn = lambda *args, f=fn: float(f(*args))
                elif rtype in ("i32", "i64"):
                    fn = lambda *args, f=fn: int(f(*args))
            linker.define_func("wbg", name, ty, fn)
            defined[name] = True
        missing = set(import_types) - set(defined)
        if missing:
            raise RuntimeError(f"unhandled wasm imports: {sorted(missing)}")
        self.instance = linker.instantiate(self.store, module)
        export_map = self.instance.exports(self.store)
        self._exports = {imp.name: export_map[imp.name] for imp in self.module.exports}
        self.memory = self._exports["memory"]

    # ---- heap / memory helpers (mirroring the JS glue) ----

    def add_heap(self, obj):
        if self.heap_next == len(self.heap):
            self.heap.append(len(self.heap) + 1)
        idx = self.heap_next
        self.heap_next = self.heap[idx]
        self.heap[idx] = obj
        return idx

    def get_heap(self, idx):
        return self.heap[idx]

    def drop(self, idx):
        if idx >= 36:
            self.heap[idx] = self.heap_next
            self.heap_next = idx

    @staticmethod
    def _js_to_py(value):
        """Bridge a quickjs result into the heap's Python object model."""
        if value is None or isinstance(value, (str, bool, int, float, dict, list)):
            return value
        to_py = getattr(value, "to_py", None)
        if callable(to_py):
            try:
                return to_py()
            except Exception:
                pass
        try:
            return dict(value)
        except Exception:
            return UNDEFINED

    def take(self, idx):
        obj = self.heap[idx]
        self.drop(idx)
        return obj

    def malloc(self, size):
        return self._exports["__wbindgen_export_0"](self.store, size)

    def read_string(self, ptr, length):
        if length == 0:
            return ""
        raw = self.memory.read(self.store, ptr, ptr + length)
        return raw.decode("utf-8")

    def write_string(self, out_ptr, value):
        """Write a JS string into wasm memory; (ptr, len) at out_ptr/4, /4+1."""
        import os
        if os.environ.get("T17DBG"):
            print(f"[DBG write_string] {value!r}", flush=True)
        if value is None or value is UNDEFINED or not isinstance(value, str):
            length = 0
            ptr = 0
        else:
            encoded = value.encode("utf-8")
            ptr = self.malloc(max(len(encoded), 1))
            self.memory.write(self.store, encoded, ptr)
            length = len(encoded)
        self._i32_store(out_ptr + 4, length)
        self._i32_store(out_ptr, ptr)

    def _i32_store(self, addr, value):
        self.memory.write(self.store, struct.pack("<i", value), addr)

    def _f64_store(self, addr, value):
        self.memory.write(self.store, struct.pack("<d", value), addr)

    # ---- the 75 wbg imports ----

    def _imports(self):
        H = self
        imp = {}

        def imp_fn(name):
            def deco(fn):
                imp[name] = fn
                return fn

            return deco

        @imp_fn("__wbg_instanceof_HtmlCanvasElement_a6157e470d06b638")
        def _(a):
            return isinstance(H.get_heap(a), HTMLCanvasElement)

        @imp_fn("__wbg_instanceof_CanvasRenderingContext2d_e8b3a478a1b32d55")
        def _(a):
            return isinstance(H.get_heap(a), CanvasRenderingContext2D)

        @imp_fn("__wbindgen_string_get")
        def _(a, i):
            import os
            if os.environ.get("T17DBG"):
                v = H.get_heap(i)
                import struct
                print(f"[DBG str_get] heap={v!r} ->", end=" ", flush=True)
                H.write_string(a, v)
                raw = H.memory.read(H.store, a, a + 8)
                ptr, ln = struct.unpack("<ii", raw)
                back = H.memory.read(H.store, ptr, ptr + ln).decode("utf-8", "replace") if ln else "<empty>"
                print(f"mem[{ptr}:{ln}]={back[:60]!r}", flush=True)
            else:
                H.write_string(a, H.get_heap(i))

        @imp_fn("__wbindgen_object_drop_ref")
        def _(a):
            H.take(a)

        @imp_fn("__wbg_navigator_0e0588c949560476")
        def _(a):
            return H.add_heap(getattr(H.get_heap(a), "navigator", UNDEFINED))

        @imp_fn("__wbg_setwidth_362e8db8cbadbe96")
        def _(a, i):
            setattr(H.get_heap(a), "width", i & 0xFFFFFFFF)

        @imp_fn("__wbg_setheight_28f53831182cc410")
        def _(a, i):
            setattr(H.get_heap(a), "height", i & 0xFFFFFFFF)

        @imp_fn("__wbg_settextBaseline_3454329d6d099dd4")
        def _(a, i, g):
            setattr(H.get_heap(a), "textBaseline", H.read_string(i, g))

        @imp_fn("__wbg_setfont_c663e63d7b867055")
        def _(a, i, g):
            setattr(H.get_heap(a), "font", H.read_string(i, g))

        @imp_fn("__wbindgen_string_new")
        def _(a, i):
            import os
            if os.environ.get("T17DBG"):
                s = H.read_string(a, i)
                print(f"[DBG str_new] ptr={a} len={i} : {s[:80]!r}", flush=True)
            return H.add_heap(H.read_string(a, i))

        @imp_fn("__wbg_setfillStyle_680401a47926faa5")
        def _(a, i):
            setattr(H.get_heap(a), "fillStyle", H.get_heap(i))

        @imp_fn("__wbg_fillRect_7ad775936c1881ce")
        def _(a, i, g, b, q):
            H.get_heap(a).fillRect(i, g, b, q)

        @imp_fn("__wbg_fillText_baf70e9d9b7affdd")
        def _(a, i, g, b, q):
            H.get_heap(a).fillText(H.read_string(i, g), b, q)

        @imp_fn("__wbg_parse_e3e7e590474b89d2")
        def _(a, i):
            import os
            if os.environ.get("T17DBG"):
                s = H.read_string(a, i)
                print(f"[DBG parse] ptr={a} len={i} : {s[:100]!r}", flush=True)
            return H.add_heap(json.loads(H.read_string(a, i)))

        @imp_fn("__wbg_instanceof_WebGlRenderingContext_2be4c068bf5f8362")
        def _(a):
            return False

        @imp_fn("__wbg_beginPath_5a6fcb370b5b8eb3")
        def _(a):
            H.get_heap(a).beginPath()

        @imp_fn("__wbg_arc_b3cb1027882c81bb")
        def _(a, i, g, b, q, c):
            H.get_heap(a).arc(i, g, b, q, c)

        @imp_fn("__wbg_fill_0ced47ff22561640")
        def _(a):
            H.get_heap(a).fill()

        @imp_fn("__wbg_setstrokeStyle_4c9ff9ea0c0c4092")
        def _(a, i):
            setattr(H.get_heap(a), "strokeStyle", H.get_heap(i))

        @imp_fn("__wbg_setlineWidth_4819b1bc5c54719b")
        def _(a, i):
            setattr(H.get_heap(a), "lineWidth", i)

        @imp_fn("__wbg_moveTo_8e1f630823114343")
        def _(a, i, g):
            H.get_heap(a).moveTo(i, g)

        @imp_fn("__wbg_lineTo_bf1ae7e03c425ceb")
        def _(a, i, g):
            H.get_heap(a).lineTo(i, g)

        @imp_fn("__wbg_stroke_46c6315e5e1f35db")
        def _(a):
            H.get_heap(a).stroke()

        @imp_fn("__wbg_language_d5a044eb7759a1d3")
        def _(a, i):
            H.write_string(a, H.get_heap(i).get("language"))

        @imp_fn("__wbg_userAgent_3f63af8b4fe2331c")
        def _(a, i):
            H.write_string(a, H.get_heap(i).get("userAgent"))

        @imp_fn("__wbg_platform_9e9e9ea362adda8b")
        def _(a, i):
            H.write_string(a, H.get_heap(i).get("platform"))

        @imp_fn("__wbg_screen_c4aebd91bf58e679")
        def _(a):
            return H.add_heap(getattr(H.get_heap(a), "screen", UNDEFINED))

        def _num(obj, key):
            v = obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)
            if isinstance(v, bool):
                return 0
            return v if isinstance(v, (int, float)) else 0

        @imp_fn("__wbg_width_8bb5aa0cc4a6ad90")
        def _(a):
            return _num(H.get_heap(a), "width")

        @imp_fn("__wbg_height_d46e3acdc77e24bd")
        def _(a):
            return _num(H.get_heap(a), "height")

        @imp_fn("__wbg_colorDepth_b0c25df8e8470f24")
        def _(a):
            return _num(H.get_heap(a), "colorDepth")

        @imp_fn("__wbg_devicePixelRatio_9632545370d525ae")
        def _(a):
            return _num(H.get_heap(a), "devicePixelRatio")

        @imp_fn("__wbg_hardwareConcurrency_ef5d4a8db82266b5")
        def _(a):
            return _num(H.get_heap(a), "hardwareConcurrency")

        @imp_fn("__wbg_maxTouchPoints_8037c89c9d8db7a6")
        def _(a):
            return _num(H.get_heap(a), "maxTouchPoints")

        @imp_fn("__wbindgen_number_get")
        def _(a, i):
            obj = H.get_heap(i)
            ok = isinstance(obj, (int, float)) and not isinstance(obj, bool)
            H._f64_store(a + 8, 0.0 if not ok else float(obj))
            H._i32_store(a, int(ok))

        @imp_fn("__wbg_new0_57a6a2c2aaed3fc5")
        def _():
            return H.add_heap(BrowserDate())

        @imp_fn("__wbg_toISOString_63ce670ffcc88ab8")
        def _(a):
            return H.add_heap(H.get_heap(a).toISOString())

        @imp_fn("__wbg_getTimezoneOffset_41211a984662508b")
        def _(a):
            return H.get_heap(a).getTimezoneOffset()

        @imp_fn("__wbg_randomFillSync_91e2b39becca6147")
        def _(a, i, g):
            # crypto.randomFillSync(subarray of wasm memory): fill in place.
            for k in range(g & 0xFFFFFFFF):
                H.memory.write(
                    H.store, bytes([(k * 37) & 0xFF]), (i & 0xFFFFFFFF) + k
                )

        @imp_fn("__wbg_subarray_a68f835ca2af506f")
        def _(a, i, g):
            return H.add_heap(H.get_heap(a).subarray(i & 0xFFFFFFFF, g & 0xFFFFFFFF))

        @imp_fn("__wbg_getRandomValues_b14734aa289bc356")
        def _(a, i):
            obj = H.get_heap(a)
            meth = obj.get("getRandomValues") if isinstance(obj, dict) else getattr(obj, "getRandomValues", None)
            if meth is not None:
                meth(H.get_heap(i))

        @imp_fn("__wbg_length_30803400a8f15c59")
        def _(a):
            return len(H.get_heap(a))

        @imp_fn("__wbindgen_memory")
        def _():
            return H.add_heap(H.memory)

        @imp_fn("__wbg_buffer_5e74a88a1424a2e0")
        def _(a):
            obj = H.get_heap(a)
            if isinstance(obj, _WasmU8):
                return H.add_heap(obj.buffer)
            # a raw wasmtime Memory -> whole-memory buffer view
            return H.add_heap(_WasmBuffer(H))

        @imp_fn("__wbg_new_e3b800e570795b3c")
        def _(a):
            obj = H.get_heap(a)
            if isinstance(obj, _WasmBuffer):
                # `new Uint8Array(memory.buffer)`: alias the live memory.
                return H.add_heap(_WasmU8(host=H, offset=obj._offset, length=obj.byte_length))
            return H.add_heap(_WasmU8(_bytes=_u8_bytes(obj)))

        @imp_fn("__wbg_set_5b8081e9d002f0df")
        def _(a, i, g):
            H.get_heap(a).set(H.get_heap(i), g)

        @imp_fn("__wbg_log_a131a23859cf7d94")
        def _(a, i):
            pass

        @imp_fn("__wbindgen_is_null")
        def _(a):
            return H.get_heap(a) is None

        @imp_fn("__wbindgen_is_undefined")
        def _(a):
            return H.get_heap(a) is H.undefined

        @imp_fn("__wbg_stringify_f8bfc9e2d1e8b6a0")
        def _(a):
            return H.add_heap(json.dumps(H.get_heap(a)))

        @imp_fn("__wbindgen_is_object")
        def _(a):
            obj = H.get_heap(a)
            return obj is not None and obj is not H.undefined and not isinstance(obj, (str, int, float, bool))

        @imp_fn("__wbg_static_accessor_NODE_MODULE_26b231378c1be7dd")
        def _():
            return H.add_heap(H.undefined)  # non-Node: module is undefined

        @imp_fn("__wbg_process_e56fd54cf6319b6c")
        def _(a):
            return H.add_heap(getattr(H.get_heap(a), "process", UNDEFINED))

        @imp_fn("__wbg_versions_77e21455908dad33")
        def _(a):
            return H.add_heap(getattr(H.get_heap(a), "versions", UNDEFINED))

        @imp_fn("__wbg_node_0dd25d832e4785d5")
        def _(a):
            return H.add_heap(getattr(H.get_heap(a), "node", UNDEFINED))

        @imp_fn("__wbindgen_is_string")
        def _(a):
            return isinstance(H.get_heap(a), str)

        @imp_fn("__wbg_require_0db1598d9ccecb30")
        def _(a, i, g):
            return H.add_heap(getattr(H.get_heap(a), "require", lambda _m: H.undefined)(H.read_string(i, g)))

        @imp_fn("__wbg_crypto_b95d7173266618a9")
        def _(a):
            obj = H.get_heap(a)
            value = obj.get("crypto") if isinstance(obj, dict) else getattr(obj, "crypto", UNDEFINED)
            return H.add_heap(value)

        @imp_fn("__wbg_msCrypto_5a86d77a66230f81")
        def _(a):
            obj = H.get_heap(a)
            value = obj.get("msCrypto") if isinstance(obj, dict) else getattr(obj, "msCrypto", UNDEFINED)
            return H.add_heap(value)

        @imp_fn("__wbg_newwithlength_5f4ce114a24dfe1e")
        def _(a):
            return H.add_heap(_WasmU8(a & 0xFFFFFFFF))

        @imp_fn("__wbg_get_8bbb82393651dd9c")
        def _(a, i):
            # Reflect.get semantics: missing property -> undefined (not null);
            # the glue always pushes the result onto the heap.
            key = H.get_heap(i)
            obj = H.get_heap(a)
            if isinstance(obj, dict):
                value = obj.get(key, UNDEFINED)
            elif isinstance(obj, (list, tuple)):
                try:
                    value = obj[int(key)]
                except Exception:
                    value = UNDEFINED
            else:
                value = getattr(obj, key, UNDEFINED)
            return H.add_heap(value)

        @imp_fn("__wbindgen_object_clone_ref")
        def _(a):
            return H.add_heap(H.get_heap(a))

        @imp_fn("__wbg_self_e23d74ae45fb17d1")
        def _():
            return H.add_heap(H.wasm_global.self)

        @imp_fn("__wbg_window_b4be7f48b24ac56e")
        def _():
            return H.add_heap(H.wasm_global.window)

        @imp_fn("__wbg_globalThis_d61b1f48a57191ae")
        def _():
            return H.add_heap(H.wasm_global.globalThis)

        @imp_fn("__wbg_global_e7669da72fd7f239")
        def _():
            return H.add_heap(getattr(H.wasm_global, "global"))

        @imp_fn("__wbg_newnoargs_f579424187aa1717")
        def _(a, i):
            if H._js is None:
                return 0
            name = f"__f{H._fn_counter}"
            H._fn_counter += 1
            H._js.eval(f"this.__fns['{name}'] = new Function({json.dumps(H.read_string(a, i))});")
            return H.add_heap(name)

        @imp_fn("__wbg_call_89558c3e96703ca1")
        def _(a, i):
            name = H.get_heap(a)
            if H._js is None or not isinstance(name, str):
                return 0
            this_js = "this.window" if H.get_heap(i) is H.wasm_global else "undefined"
            try:
                result = H._js.eval(f"(this.__fns['{name}'] || function() {{}}).call({this_js})")
            except Exception:
                err = H.add_heap(H._js_to_py(H._js.eval("new Error('call error')")))
                H._exports["__wbindgen_export_3"](H.store, err)
                return 0
            return H.add_heap(H._js_to_py(result))

        @imp_fn("__wbg_eval_af3ed6ac70747c99")
        def _(a, i):
            if H._js is None:
                return 0
            try:
                result = H._js.eval(H.read_string(a, i))
            except Exception:
                # glue handleError: on throw, wasm.__wbindgen_export_3(addHeapObject(Error));
                # the Rust handler only sets a flag the caller checks right after.
                err = H.add_heap(H._js_to_py(H._js.eval("new Error('eval error')")))
                H._exports["__wbindgen_export_3"](H.store, err)
                return 0
            return H.add_heap(H._js_to_py(result))

        @imp_fn("__wbindgen_debug_string")
        def _(a, i):
            H.write_string(a, repr(H.get_heap(i)))

        @imp_fn("__wbindgen_throw")
        def _(a, i):
            raise RuntimeError(H.read_string(a, i))

        @imp_fn("__wbg_instanceof_Window_434ce1849eb4e0fc")
        def _(a):
            return isinstance(H.get_heap(a), Window)

        @imp_fn("__wbg_createElement_d017b8d2af99bab9")
        def _(a, i, g):
            doc = H.get_heap(a)
            make = doc.get("createElement") if isinstance(doc, dict) else getattr(doc, "createElement", None)
            el = make(H.read_string(i, g)) if make is not None else None
            return H.add_heap(el) if el is not None else 0

        @imp_fn("__wbg_getContext_bd4e9445094eda84")
        def _(a, i, g):
            ctx = H.get_heap(a).getContext(H.read_string(i, g))
            return H.add_heap(ctx) if ctx is not None else 0

        @imp_fn("__wbg_toDataURL_3b7bad211c47427e")
        def _(a, i):
            H.write_string(a, H.get_heap(i).toDataURL())

        @imp_fn("__wbg_document_5edd43643d1060d9")
        def _(a):
            doc = getattr(H.get_heap(a), "document", None)
            return H.add_heap(doc) if doc is not None else 0

        return imp

    def get_fingerprint(self):
        """`get_fingerprint(points)` with an empty mouse-point list — the exact
        call the tracking page makes (fingerprinter configured with maxMovePoints=0)."""
        exp = self._exports
        stack = exp["__wbindgen_add_to_stack_pointer"](self.store, -16)
        exp["get_fingerprint"](self.store, stack, self.add_heap([]))
        result = struct.unpack("<ii", self.memory.read(self.store, stack, stack + 8))
        ptr, length = result
        value = self.read_string(ptr, length)
        exp["__wbindgen_add_to_stack_pointer"](self.store, 16)
        exp["__wbindgen_export_2"](self.store, ptr, length)
        return value


class _WasmU8:
    """Uint8Array: standalone (own bytes, `new Uint8Array(n)`) or a view over
    the WASM's live linear memory (`new Uint8Array(memory.buffer)`), so that
    `.set`/index writes reach the module's memory exactly like in JS."""

    def __init__(self, length=None, host=None, offset=0, _bytes=None):
        self._host = host
        self._offset = offset
        if _bytes is not None:
            self._buf = bytearray(_bytes)
            self._length = len(self._buf)
        elif host is not None:
            self._buf = None
            self._length = (
                length
                if length is not None
                else host.memory.size(host.store)
            )
        else:
            self._buf = bytearray(length or 0)
            self._length = len(self._buf)

    @property
    def length(self):
        return self._length

    def __len__(self):
        return self._length

    def __getitem__(self, i):
        if self._buf is not None:
            return self._buf[i]
        return self._host.memory.read(
            self._host.store, self._offset + i, self._offset + i + 1
        )[0]

    def __setitem__(self, i, value):
        if self._buf is not None:
            self._buf[i] = value
        else:
            self._host.memory.write(
                self._host.store, bytes([value & 0xFF]), self._offset + i
            )

    @property
    def buffer(self):
        if self._host is not None:
            return _WasmBuffer(self._host, self._offset, self._length)
        return _WasmBufferBytes(self._buf)

    def subarray(self, start, end=None):
        if end is None:
            end = self._length
        return _WasmU8Slice(self, start, min(end, self._length))

    def set(self, other, offset=0):
        for i, b in enumerate(_u8_bytes(other)):
            self[offset + i] = b

    def to_bytes(self):
        if self._buf is not None:
            return bytes(self._buf)
        return self._host.memory.read(
            self._host.store, self._offset, self._offset + self._length
        )


def _u8_bytes(obj):
    if isinstance(obj, (bytes, bytearray)):
        return obj
    to_bytes = getattr(obj, "to_bytes", None)
    if callable(to_bytes):
        try:
            return to_bytes()
        except Exception:
            pass
    if hasattr(obj, "__len__") and hasattr(obj, "__getitem__"):
        return bytes(obj[i] for i in range(len(obj)))
    return bytes(obj)


class _WasmU8Slice:
    def __init__(self, parent, start, end):
        self._parent = parent
        self._start = start
        self._end = end

    def __len__(self):
        return self._end - self._start

    def __getitem__(self, idx):
        return self._parent[self._start + idx]

    def __setitem__(self, idx, value):
        self._parent[self._start + idx] = value

    def to_bytes(self):
        return bytes(self._parent[self._start + i] for i in range(len(self)))


class _WasmBuffer:
    """ArrayBuffer over the WASM's live linear memory (`.buffer` of memory)."""

    def __init__(self, host, offset=0, length=None):
        self._host = host
        self._offset = offset
        self._length = length

    @property
    def byte_length(self):
        if self._length is not None:
            return self._length
        return self._host.memory.size(self._host.store)

    def to_bytes(self):
        size = self.byte_length
        return self._host.memory.read(
            self._host.store, self._offset, self._offset + size
        )


class _WasmBufferBytes:
    def __init__(self, buf):
        self._buf = bytes(buf)

    @property
    def byte_length(self):
        return len(self._buf)

    def to_bytes(self):
        return self._buf


# ================= 17TRACK public web API (no account) =================
#
# Flow (mirrors what t.17track.net's own tracking page does in a browser):
#   1. GET /track/{number}            - prime the session
#   2. POST /track/restapi            - the tracking lookup, `sign` is the WASM
#                                       fingerprint above
#   3. if meta.code == -14:           - the IP is captcha-gated
#        POST /captcha/generate       - image captcha (prompt + 9 options)
#        POST /captcha/verify/17track - answer it (code 200 = accepted)
#   4. POST /track/restapi again      - succeeds for the rest of the session
#
# Nothing is stored in (or required from) a 17TRACK account: the session is
# plain cookies plus the per-IP captcha verification.

CAPTCHA_META_CODE = -14
CAPTCHA_VERIFY_OK = 200
RESTAPI_OK = 200
SIGN_TTL_SECONDS = 60 * 60  # regenerate the fingerprint about hourly

_session = None
_fingerprint = None


def _get_session():
    global _session
    if _session is None:
        session = requests.Session()
        session.headers.update(HEADERS)
        _session = session
    return _session


def _get_sign():
    global _fingerprint
    if _fingerprint is None:
        _fingerprint = WasmFingerprint()
    return _fingerprint.get_fingerprint()


def _prime(number):
    """Same first hit the tracking page makes; establishes the session."""
    _get_session().get(f"{API_BASE}/track/{number}", timeout=30)


def _restapi(number):
    payload = {
        "data": [{"num": number, "fc": 0, "sc": 0}],
        "guid": "",
        "timeZoneOffset": TIMEZONE_OFFSET_MINUTES,
        "sign": _get_sign(),
    }
    response = _get_session().post(
        f"{API_BASE}/track/restapi", json=payload, timeout=30
    )
    response.raise_for_status()
    return response.json()


def _provider_name(provider):
    info = provider.get("provider") or {}
    if isinstance(info, dict):
        return info.get("name") or info.get("alias")
    return str(info) if info else None


def _map_shipment(shipment):
    inner = shipment.get("shipment") or {}
    latest_status = inner.get("latest_status") or {}
    status = latest_status.get("status") or "Unknown"
    delivered = status == "Delivered"
    events = []
    for provider in (inner.get("tracking") or {}).get("providers") or []:
        for event in provider.get("events") or []:
            events.append({
                "time": parse_time(event.get("time_utc") or event.get("time_iso")),
                "description": event.get("description") or "",
                "location": event.get("location") or "",
            })
    return make_parcel("17track", status, delivered, events)


def _shipments_or_error(data):
    """(parcel, None) on success; (None, message) otherwise."""
    meta = data.get("meta") or {}
    code = meta.get("code")
    if code == CAPTCHA_META_CODE:
        return None, "captcha"
    if code != RESTAPI_OK:
        return None, f"17TRACK said: {meta.get('message') or code} (code {code})"
    shipments = data.get("shipments") or []
    if not shipments:
        return None, "17TRACK returned no tracking data for that number."
    return _map_shipment(shipments[0]), None


def _decode_b64(value):
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, str) and value:
        return base64.b64decode(value)
    return b""


def captcha_generate():
    """Fetch a fresh image captcha. None if the endpoint misbehaves."""
    try:
        response = _get_session().post(
            f"{API_BASE}/captcha/generate", data=b"", timeout=30
        )
        response.raise_for_status()
        payload = (response.json() or {}).get("data") or {}
    except (requests.RequestException, ValueError):
        return None
    options = []
    for index, option in enumerate(payload.get("options") or []):
        image = _decode_b64(option.get("content"))
        if image:
            options.append({"key": option.get("key"), "index": index, "image": image})
    if not payload.get("captcha_id") or not options:
        return None
    return {
        "captcha_id": payload["captcha_id"],
        "prompt": _decode_b64(payload.get("prompt")),
        "options": options,
        "created_at": time.time(),
    }


def captcha_verify(captcha_id, selected_keys):
    """Answer a captcha. True when the server accepted it."""
    try:
        response = _get_session().post(
            f"{API_BASE}/captcha/verify/17track",
            json={
                "captcha_id": captcha_id,
                "selected": selected_keys,
                "sign": _get_sign(),
            },
            timeout=30,
        )
        response.raise_for_status()
        body = response.json() or {}
    except (requests.RequestException, ValueError):
        return False
    return body.get("code") == CAPTCHA_VERIFY_OK


def track_parcel(number):
    """One-shot, account-free 17TRACK lookup.

    Returns one of:
      ("ok", parcel)          - parcel in utility.parcels.make_parcel shape
      ("captcha", challenge)  - challenge from captcha_generate()
      ("error", message)
    """
    number = normalize_parcel_number(number)
    if not number:
        return "error", "That doesn't look like a tracking number."
    try:
        _prime(number)
        data = _restapi(number)
    except requests.RequestException as e:
        return "error", f"Couldn't reach 17TRACK ({e})."
    parcel, problem = _shipments_or_error(data)
    if parcel:
        return "ok", parcel
    if problem == "captcha":
        challenge = captcha_generate()
        if challenge:
            return "captcha", challenge
        return "error", "17TRACK is asking for a captcha but wouldn't send one — try again in a few minutes."
    return "error", problem


def track_parcel_after_captcha(number, captcha_id, selected_keys):
    """Verify the captcha answer, then retry the lookup. Same shapes as track_parcel."""
    number = normalize_parcel_number(number)
    if not number:
        return "error", "That doesn't look like a tracking number."
    try:
        if not captcha_verify(captcha_id, selected_keys):
            return "error", "The captcha wasn't accepted — I'll send a fresh one."
        _prime(number)
        data = _restapi(number)
    except requests.RequestException as e:
        return "error", f"Couldn't reach 17TRACK ({e})."
    parcel, problem = _shipments_or_error(data)
    if parcel:
        return "ok", parcel
    if problem == "captcha":
        challenge = captcha_generate()
        if challenge:
            return "captcha", challenge
        return "error", "Captcha solved but 17TRACK still wants one — try again in a few minutes."
    return "error", problem
