"""Request inspection through HTTP; no native model or GPU is required."""
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from serve.frontend import ChatTemplate
from serve.server import ByteTokenizer, EngineDied, MockEngine, Service, serve


class ReloadableEngine(MockEngine):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running, self.unloaded = True, False

    def alive(self):
        return self.running

    def unload(self):
        self.running, self.unloaded = False, True

    def restart(self):
        self.running, self.unloaded = True, False


class MonitorOff(unittest.TestCase):
    """#332 is opt-in: by default no prompt or answer is kept, and the monitor's endpoints do not exist."""

    def test_off_by_default(self):
        tok = ByteTokenizer()
        svc = Service(MockEngine(tok, "Hello.", max_context=4096), tok,
                      ChatTemplate(Path(__file__).parent / "chat_template.jinja"))
        httpd = serve(svc, port=0)
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        try:
            req = urllib.request.Request(base + "/v1/chat/completions", headers={"Content-Type": "application/json"},
                                         data=json.dumps({"messages": [{"role": "user", "content": "secret"}]}).encode())
            with urllib.request.urlopen(req, timeout=10) as r:
                self.assertEqual(r.status, 200)
            self.assertEqual(len(svc.api_requests), 0)
            for path in ("/api/requests", "/api-monitor"):
                with self.assertRaises(urllib.error.HTTPError) as e:
                    urllib.request.urlopen(base + path, timeout=10)
                self.assertEqual(e.exception.code, 404, path)
                e.exception.close()
        finally:
            httpd.shutdown()
            httpd.server_close()


class Monitor(unittest.TestCase):
    def setUp(self):
        self.tok = ByteTokenizer()
        self.engine = ReloadableEngine(self.tok, "Thought.</think>\nHello <script>alert(1)</script>.", max_context=16384)
        self.svc = Service(self.engine, self.tok, ChatTemplate(Path(__file__).parent / "chat_template.jinja"))
        self.svc.api_monitor = True                       # opt-in ("api_monitor": true / --api-monitor)
        self.httpd = serve(self.svc, port=0)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def request(self, path, body=None, headers=None):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json", **(headers or {})})
        try:
            response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read().decode()
            return response.status, json.loads(raw) if "application/json" in response.headers.get("Content-Type", "") else raw

    def chat(self, api="openai", **kwargs):
        # Anthropic thinks only when asked (#278): "thinking" there, reasoning_effort for OpenAI
        think = {"thinking": {"type": "enabled", "budget_tokens": 1024}} if api == "anthropic" else             {"reasoning_effort": "low"}
        return self.request("/v1/messages" if api == "anthropic" else "/v1/chat/completions",
                            {"messages": [{"role": "user", "content": "Say hello."}],
                             "max_tokens": 256, **think, **kwargs})

    def latest(self):
        summary = self.request("/api/requests")[1]["requests"][0]
        return self.request("/api/requests?id=" + summary["id"])[1]

    def test_output_and_reasoning_for_both_dialects_and_stream_modes(self):
        for api in ("openai", "anthropic"):
            for stream in (False, True):
                with self.subTest(api=api, stream=stream):
                    code, reply = self.chat(api, stream=stream)
                    self.assertEqual(code, 200)
                    record = self.latest()
                    self.assertEqual(record["state"], "completed")
                    self.assertEqual(record["http_status"], 200)
                    self.assertIn("Say hello.", record["input"])
                    self.assertIn("<script>alert(1)</script>", record["output"])
                    self.assertIn("Thought.", record["reasoning"])
                    self.assertGreater(record["usage"].get("completion_tokens", record["usage"].get("output_tokens", 0)), 0)
                    self.assertGreaterEqual(record["wallclock_s"], record["first_token_s"])
                    self.assertNotIn("_clock", record)
                    if not stream:
                        self.assertEqual(json.loads(record["response"]), reply)
                    else:
                        self.assertNotIn("response", record)

    def test_error_and_engine_death_are_not_successes(self):
        self.assertEqual(self.chat(max_tokens=20000)[0], 400)
        self.assertEqual(self.latest()["state"], "error")
        for api in ("openai", "anthropic"):
            for stream in (False, True):
                with self.subTest(api=api, stream=stream), mock.patch.object(self.engine, "generate", side_effect=EngineDied("stopped")):
                    self.chat(api, stream=stream)
                    record = self.latest()
                    self.assertEqual(record["state"], "error")
                    self.assertIn("stopped", record["error"]["message"])
                    self.assertEqual(record["output"], "")
                    self.assertNotIn("timings", record)

    def test_history_is_authorized_and_does_not_capture_headers(self):
        self.svc.api_key = "secret"
        auth = {"Authorization": "Bearer secret"}
        self.assertEqual(self.request("/api/requests")[0], 401)
        self.assertEqual(self.request("/api/requests?id=missing")[0], 401)
        self.assertEqual(len(self.svc.api_requests), 0)
        self.assertEqual(self.request("/v1/chat/completions", {"messages": [{"role": "user", "content": "hi"}]}, auth)[0], 200)
        summary = self.request("/api/requests", headers=auth)[1]["requests"][0]
        self.assertNotIn("input", summary)
        self.assertNotIn("output", summary)
        self.assertEqual(self.request("/api/requests?id=" + summary["id"])[0], 401)
        detail = self.request("/api/requests?id=" + summary["id"], headers=auth)[1]
        self.assertNotIn("secret", json.dumps(detail))

    def test_capture_is_bounded_and_eviction_returns_404(self):
        huge = "x" * 262200
        first = self.svc.begin_request("/v1/chat/completions", {"messages": [{"content": huge}]})
        self.assertEqual(len(first["input"]), 262144)
        self.assertTrue(first["input_truncated"])
        for _ in range(100):
            self.svc.begin_request("/v1/chat/completions", {"messages": []})
        self.assertEqual(len(self.request("/api/requests")[1]["requests"]), 100)
        self.assertEqual(self.request("/api/requests?id=" + first["id"])[0], 404)
        # Exercise output capture without making a mock engine emit 262K tokens.
        handler = object.__new__(self.httpd.RequestHandlerClass)
        handler.record = self.svc.api_requests[-1]
        chunk = {"choices": [{"delta": {"content": huge, "reasoning_content": huge}}]}
        list(handler._capture((item for item in [chunk]), "openai"))
        for field in ("output", "reasoning"):
            self.assertEqual(len(handler.record[field]), 262144)
            self.assertTrue(handler.record[field + "_truncated"])

    def test_queue_wait_and_loading_are_attributed_separately(self):
        self.engine.unload()
        entered, release = threading.Event(), threading.Event()
        original = self.engine.restart
        def restart():
            entered.set()
            self.assertTrue(release.wait(5))
            original()
        with mock.patch.object(self.engine, "restart", side_effect=restart), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.chat)
            self.assertTrue(entered.wait(5))
            second = pool.submit(self.chat)
            deadline = time.monotonic() + 5
            while len(self.svc.api_requests) < 2 and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(len(self.svc.api_requests), 2)
            history = self.request("/api/requests")[1]
            self.assertEqual({r["state"] for r in history["requests"]}, {"queued", "loading"})
            self.assertFalse(history["loaded"])
            self.assertTrue(history["auto_load"])
            time.sleep(0.03)
            release.set()
            self.assertEqual(first.result()[0], 200)
            self.assertEqual(second.result()[0], 200)
        records = list(self.svc.api_requests)
        self.assertGreater(records[0]["load_s"], 0.02)
        self.assertGreater(records[1]["queue_s"], 0.02)
        self.assertLess(records[1]["load_s"], records[0]["load_s"])
        self.assertTrue(all(r["state"] == "completed" for r in records))

    def test_page_and_relative_assets_are_served(self):
        code, html = self.request("/api-monitor")
        self.assertEqual(code, 200)
        self.assertIn('src="/web/monitor.js"', html)
        code, script = self.request("/web/monitor.js")
        self.assertEqual(code, 200)
        self.assertIn("textContent", script)
        self.assertNotIn("innerHTML", script)
        self.assertEqual(self.request("/web/../server.py")[0], 404)


class ConversationCacheCard(unittest.TestCase):
    """#596: /metrics' "conversation_cache": the parked conversations from the engine's log lines, the budget and
    slots from its INFO line, and how much of the prompts the cache gave back."""

    PARK = ("strata serve: conversation cache: parked 5000 tokens in 12.0 ms; parked=1 bytes=104857600 evictions=0 "
            "snapshot_bytes=104857600 reused_kv_bytes=0\n")
    RESTORE = "strata serve: conversation cache: restored 4000 tokens (exact) in 30.0 ms; parked=2 bytes=209715200\n"

    def test_the_log(self):
        from serve.server import ConvCacheLog
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "strata.log"
            log.write_text("an earlier run\n" + self.PARK, encoding="utf-8")
            start = log.stat().st_size                 # this run starts here: the earlier run's park is not counted
            c = ConvCacheLog()
            self.assertEqual(c.poll(str(log), start)["parked"], 0)
            with open(log, "a", encoding="utf-8") as f:
                f.write("strata serve: something else\n" + self.PARK + self.RESTORE + "strata serve: conversation ca")
            st = c.poll(str(log), start)
            self.assertEqual((st["parked"], st["bytes"], st["parks"], st["restores"]), (2, 209715200, 1, 1))
            self.assertEqual((st["last_event"], st["last_tokens"]), ("restored", 4000))
            with open(log, "a", encoding="utf-8") as f:   # the cut line is read once it is whole
                f.write("che: dropped 1 superseded copy of this conversation; parked=1\n")
            self.assertEqual(c.poll(str(log), start)["parked"], 1)
            self.assertEqual(c.poll(str(log), log.stat().st_size)["parked"], 0)   # the engine started again
            self.assertEqual(c.poll(None, None)["parked"], 0)

    def test_metrics(self):
        tok = ByteTokenizer()
        engine = MockEngine(tok, "Thought.</think>\nHello.", max_context=4096)
        engine.info = {"conversation_cache_mib": 8192, "conversation_cache_slots": 4}
        svc = Service(engine, tok, ChatTemplate(Path(__file__).parent / "chat_template.jinja"))
        httpd = serve(svc, port=0)
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        try:
            with urllib.request.urlopen(base + "/metrics", timeout=10) as r:
                c = json.loads(r.read())["conversation_cache"]
            self.assertEqual((c["enabled"], c["budget_mib"], c["slots"], c["parked"], c["requests"]),
                             (True, 8192, 4, 0, 0))
            req = urllib.request.Request(base + "/v1/chat/completions", headers={"Content-Type": "application/json"},
                                         data=json.dumps({"messages": [{"role": "user", "content": "hi"}]}).encode())
            with urllib.request.urlopen(req, timeout=10) as r:
                r.read()
            with urllib.request.urlopen(base + "/metrics", timeout=10) as r:
                c = json.loads(r.read())["conversation_cache"]
            self.assertEqual(c["requests"], 1)
            self.assertGreater(c["last_prompt"], 0)
            engine.info = {}
            with urllib.request.urlopen(base + "/metrics", timeout=10) as r:
                self.assertFalse(json.loads(r.read())["conversation_cache"]["enabled"])   # off: the reuse lines only
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_the_card_is_on_the_page(self):
        web = Path(__file__).parent / "web"
        html, js = (web / "index.html").read_text(encoding="utf-8"), (web / "app.js").read_text(encoding="utf-8")
        for el in ("cc-card", "cc-slots-text", "cc-mem-text", "cc-facts", "cc-note"):
            self.assertIn(f'id="{el}"', html)
            self.assertIn(f'"{el}"', js)


class MemoryBreakdown(unittest.TestCase):
    """The Monitor's RAM / VRAM breakdown: /metrics' "memory" carries measured (process RSS) and engine-reported
    figures; the web app splits each bar into one coloured segment per type, with a per-item tooltip."""

    HW = {"ram_total": 128 * 2**30, "ram_used": 100 * 2**30, "gpu_mem_used": 20 * 2**30, "gpu_mem_total": 24 * 2**30}
    PARKED = {"parked": 3, "bytes": 5 * 2**30, "snapshot_bytes": 1024 * 2**20, "snapshot_tokens": 4096}   # 262144 B/token

    def service(self):
        tok = ByteTokenizer()
        engine = MockEngine(tok, "ok", max_context=4096)
        engine.info = {"arena_mib": 40960, "expert_cache_mib": 20480, "vram_free_mib": 4096, "conversation_cache_mib": 8192}
        return Service(engine, tok, ChatTemplate(Path(__file__).parent / "chat_template.jinja"))

    def test_the_figures(self):
        svc = self.service()
        m = svc._memory(self.HW, self.PARKED)
        self.assertEqual(m["arena_bytes"], 40960 * 2**20)
        self.assertEqual(m["expert_cache_bytes"], 20480 * 2**20)
        self.assertEqual(m["conv_bytes"], 5 * 2**30)

    def test_the_unified_flag_comes_from_the_engine(self):
        svc = self.service()
        self.assertFalse(svc._memory(self.HW, self.PARKED)["unified"])
        svc.engine.info["unified"] = 1
        self.assertTrue(svc._memory(self.HW, self.PARKED)["unified"])
        svc.engine.info["unified"] = 0
        self.assertFalse(svc._memory({**self.HW, "gpu_mem_total": 512 * 2**20}, self.PARKED)["unified"])

    def test_slots_report_their_tokens(self):
        svc = self.service()
        svc.engine.slots_view = lambda: [{"slot": 0, "state": "idle", "held_tokens": 1000},
                                         {"slot": 1, "state": "decoding", "prompt_tokens": 500, "generated": 20}]
        slots = svc._memory(self.HW, self.PARKED)["slots"]
        self.assertEqual([(s["tokens"], s["kv_bytes"]) for s in slots], [(1000, None), (520, None)])

    def test_slot_kv_is_exact_when_the_engine_gives_the_per_token_size(self):
        svc = self.service()
        svc.engine.info["kv_bytes_per_token"] = 12672
        svc.engine.slots_view = lambda: [{"slot": 0, "state": "idle", "context_tokens": 1000},
                                         {"slot": 1, "state": "decoding", "prompt_tokens": 500, "generated": 20}]
        slots = svc._memory(self.HW, self.PARKED)["slots"]
        self.assertEqual([(s["tokens"], s["kv_bytes"]) for s in slots], [(1000, 12672000), (520, 6589440)])

    def test_batch_slots_reserve_their_pinned_kv(self):
        """KV streaming: every session - the main one and each batch slot - pins a full-context K/V copy in RAM at
        load (session_init -> qsa_state_init) that never returns until the engine exits; the Monitor's RAM bar gets
        the slots' share as its own segment, not inside the engine's other RSS."""
        svc = self.service()
        svc.engine.info = {"kv_bytes_per_token": 12672, "context": 262144, "batch_slots": 2, "kv_resident": 32768}
        m = svc._memory(self.HW, self.PARKED)
        self.assertEqual(m["kv_session_bytes"], 12672 * 262144)
        self.assertEqual(m["kv_slot_reserve_bytes"], 2 * 12672 * 262144)

    def test_no_reserve_without_kv_streaming_or_slots(self):
        """Without `--kv-resident` the K/V lives in the VRAM pools, so there is nothing pinned per session to show."""
        svc = self.service()
        svc.engine.info = {"kv_bytes_per_token": 12672, "context": 262144, "batch_slots": 2}
        m = svc._memory(self.HW, self.PARKED)
        self.assertIsNone(m["kv_session_bytes"])
        self.assertIsNone(m["kv_slot_reserve_bytes"])
        svc.engine.info = {"kv_bytes_per_token": 12672, "context": 262144, "kv_resident": 32768}
        m = svc._memory(self.HW, self.PARKED)
        self.assertIsNone(m["kv_slot_reserve_bytes"])

    def test_the_slots_device_carveouts_come_from_the_engine_log(self):
        from serve.server import SlotCarveLog
        import tempfile
        SESSION = "strata generate: --batch: 2 slot sessions on CUDA0 (0.95 GiB each); 101.77 GiB free\n"
        DRAFTER = "strata generate: --batch-mtp: 2 slot drafters on CUDA0 (15 MiB of private K/V state and buffers each, sharing the solo drafter's weights); 100.95 GiB free there\n"
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "strata.log"
            log.write_text("an earlier run with --batch: 4 slot sessions on CUDA0 (0.50 GiB each);\n", encoding="utf-8")
            start = log.stat().st_size                 # this run starts here: the earlier run's carves are not counted
            c = SlotCarveLog()
            self.assertIsNone(c.poll(str(log), start)["sessions"] or None)
            with open(log, "a", encoding="utf-8") as f:
                f.write(SESSION)
            st = c.poll(str(log), start)
            self.assertEqual(st["sessions"], 2)
            self.assertEqual(st["per_slot_bytes"], round(0.95 * (1 << 30)))
            with open(log, "a", encoding="utf-8") as f:
                f.write(DRAFTER)
            st = c.poll(str(log), start)
            self.assertEqual(st["drafter_bytes"], 15 * 1048576)
            self.assertIsNone(SlotCarveLog().poll(None, None)["sessions"] or None)   # no log seen: nothing to show

    def test_memory_carries_the_slot_carveouts(self):
        from serve.server import SlotCarveLog
        import tempfile
        svc = self.service()
        svc.engine.info = {"kv_bytes_per_token": 12672, "context": 262144, "batch_slots": 2, "kv_resident": 32768}
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "strata.log"
            log.write_text("strata generate: --batch: 2 slot sessions on CUDA0 (0.95 GiB each); 101.77 GiB free\n"
                           "strata generate: --batch-mtp: 2 slot drafters on CUDA0 (15 MiB of private K/V state and "
                           "buffers each, sharing the solo drafter's weights); 100.95 GiB free there\n", encoding="utf-8")
            svc.engine.log_path = str(log)
            svc.engine.log_start = 0
            m = svc._memory(self.HW, self.PARKED)
        self.assertEqual(m["slot_carve_per_slot"], round(0.95 * (1 << 30)) + 15 * 1048576)
        self.assertEqual(m["slot_carve_bytes"], m["slot_carve_per_slot"] * 2)
        fresh = self.service()                       # a service that never saw the engine print its carves
        fresh.engine.info = svc.engine.info
        self.assertIsNone(fresh._memory(self.HW, self.PARKED)["slot_carve_bytes"])

    def test_the_ram_bar_shows_the_slot_reserve_as_its_own_segment(self):
        web = Path(__file__).parent / "web"
        js = (web / "app.js").read_text(encoding="utf-8")
        self.assertIn('kind: "slotres", label: "Batch slot reserve"', js)
        self.assertIn("engineRss - arena - conv - kvReserve", js)
        self.assertIn('slotres: "slotres"', js)

    def test_the_vram_bar_shows_the_carveouts_and_drops_the_spilled_kv(self):
        """With KV streaming the K/V's authoritative copy is pinned in RAM, so the card's bar names the slots' device
        carveouts instead; without streaming the used-KV segment stays as before."""
        web = Path(__file__).parent / "web"
        js = (web / "app.js").read_text(encoding="utf-8")
        self.assertIn('label: "Batch slots"', js)
        self.assertIn("function slotCarveTip", js)
        self.assertIn("kvStream ? carve : kvTotal", js)
        self.assertIn('if (!kvStream && kvTotal) vsegs.push({kind: "slots"', js)
        self.assertIn('if (kvStream && carve) grows.push(["Slot carveouts"', js)

    def test_metrics_carries_memory(self):
        svc = self.service()
        httpd = serve(svc, port=0)
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        try:
            with urllib.request.urlopen(base + "/metrics", timeout=10) as r:
                mem = json.loads(r.read())["memory"]
            self.assertEqual(mem["arena_bytes"], 40960 * 2**20)
            self.assertIn("slots", mem)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_the_sparkline_follows_the_same_figure_as_the_tile(self):
        """The tile reads the measured figure, so its sparkline has to be the history of that same figure: the
        sampler's own gpu_mem_used series is the driver's whole-card reading, which is a different memory on a card
        that shares memory with the CPU."""
        from serve import telemetry
        svc = self.service()
        svc.engine.proc = SimpleNamespace(pid=4242)
        with mock.patch.object(telemetry, "drm_memory_bytes",
                               lambda pid: {"gtt": 40 << 30, "total": 40 << 30} if pid == 4242 else {}):
            first = svc._memory(self.HW, self.PARKED)["gpu_mem_used"]
            hist = svc._memory(self.HW, self.PARKED)["gpu_used_hist"]
        self.assertEqual(first, 40 << 30)
        self.assertEqual(hist, [first, first])
        web = Path(__file__).parent / "web"
        js = (web / "app.js").read_text(encoding="utf-8")
        self.assertIn('spark("sp-vram", mem && mem.gpu_used_hist', js)

    def test_the_vram_bar_uses_the_system_ram_colours_for_the_encoder_and_the_rest(self):
        """The VRAM bar's two measured parts keep the colours the System RAM bar uses for the same things: the encoder
        red (it is a row of "Strata (other)" there), the remainder grey (as "System & other apps")."""
        web = Path(__file__).parent / "web"
        js = (web / "app.js").read_text(encoding="utf-8")
        self.assertIn('visiongpu: "engine"', js)
        self.assertIn('othergpu: "system"', js)
        self.assertIn('kind: "visiongpu", label: "Vision encoder"', js)
        self.assertIn('kind: "othergpu", label: "Other"', js)

    def test_the_vram_label_reads_the_total_not_the_expert_cache(self):
        """The bar is drawn against everything Strata holds on the card, so the figure beside its title says the same:
        it used to show eng.expert_cache_mib, which is one segment of it, next to a bar drawn to a different total."""
        js = (Path(__file__).parent / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn('mem && mem.gpu_mem_used != null ? `${gb(mem.gpu_mem_used)} GB`', js)

    def test_the_vram_total_is_what_strata_holds_not_the_startup_pool(self):
        """The bar's total used to be max(gpu_mem_total, expert_cache + vram_free_bytes): the driver's dedicated VRAM
        (a 512 MiB carve-out on a card sharing memory with the CPU) or, failing that, the pool the engine sized its
        cache against at startup - a figure frozen at that moment. It is now the sum of what the engine and the image
        encoder hold on the card, measured per process, so it follows the allocations."""
        from serve import telemetry
        svc = self.service()
        with mock.patch.object(telemetry, "drm_memory_bytes", lambda pid: {} if pid != 4242 else {"vram": 8 << 30, "gtt": 32 << 30, "total": 40 << 30}):
            svc.engine.proc = SimpleNamespace(pid=4242)
            m = svc._memory(self.HW, self.PARKED)
        self.assertEqual(m["gpu_mem_used"], 40 << 30)          # not 20 << 30 (the driver), not 53 GiB (the pool)
        self.assertEqual(m["gpu_mem_used_hw"], 20 << 30)      # the driver's own reading, kept beside it
        self.assertEqual(m["gpu_bytes"]["engine"], {"vram": 8 << 30, "gtt": 32 << 30, "total": 40 << 30})
        self.assertIsNone(m["gpu_bytes"]["vision"])

    def test_both_processes_are_counted_apart(self):
        from serve import telemetry
        svc = self.service()
        one, two = 4242, 4343
        svc.engine.proc = SimpleNamespace(pid=one)
        svc.vision = SimpleNamespace(proc=SimpleNamespace(pid=two))
        with mock.patch.object(telemetry, "drm_memory_bytes",
                               lambda pid: {one: {"gtt": 39 << 30, "total": 39 << 30},
                                            two: {"gtt": 1460 << 20, "total": 1460 << 20}}.get(pid, {})):
            m = svc._memory(self.HW, self.PARKED)
        self.assertEqual(m["gpu_mem_used"], (39 << 30) + (1460 << 20))
        self.assertEqual(m["gpu_bytes"]["vision"]["gtt"], 1460 << 20)

    def test_the_reader_splits_the_kernel_figures_and_counts_a_client_once(self):
        """drm-memory-vram is dedicated VRAM, -gtt system RAM the GPU is using, -cpu host RAM mapped for it: one split
        for both kinds of card. A DRM client reachable through several fds is counted once, and a process with no DRM
        fd at all gives {} - never a zero, which would read as "holds nothing"."""
        from serve import telemetry
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "4242" / "fdinfo"
            root.mkdir(parents=True)
            one = "drm-driver:\tamdgpu\ndrm-client-id:\t16\ndrm-memory-vram:\t36312 KiB\ndrm-memory-gtt:\t40982532 KiB\n"
            (root / "7").write_text(one)
            (root / "9").write_text(one)                       # the same client under a second fd
            (root / "3").write_text("pos:\t0\nflags:\t02000002\n")   # not a DRM client
            with mock.patch.object(telemetry.os, "listdir", lambda p: ["3", "7", "9"]), \
                 mock.patch("builtins.open", side_effect=lambda p, **k: (root / Path(p).name).open() if "fdinfo" in p
                            else open(p, **k)):
                got = telemetry.drm_memory_bytes(4242)
        self.assertEqual(got["vram"], 36312 * 1024)
        self.assertEqual(got["gtt"], 40982532 * 1024)
        self.assertEqual(got["total"], (36312 + 40982532) * 1024)
        self.assertEqual(telemetry.drm_memory_bytes(None), {})
        self.assertEqual(telemetry.drm_memory_bytes(999999), {})      # no such process

    def test_no_kernel_reporting_leaves_the_tile_empty_rather_than_zero(self):
        from serve import telemetry
        svc = self.service()
        svc.engine.proc = SimpleNamespace(pid=4242)
        with mock.patch.object(telemetry, "drm_memory_bytes", lambda pid: {}):
            m = svc._memory(self.HW, self.PARKED)
        self.assertIsNone(m["gpu_mem_used"])                   # a dash, not a false "nothing on the card"

    def test_the_bars_are_on_the_page(self):
        web = Path(__file__).parent / "web"
        html, js = (web / "index.html").read_text(encoding="utf-8"), (web / "app.js").read_text(encoding="utf-8")
        for el in ("ram-bar", "ram-legend", "vram-bar", "vram-legend", "ctx-slots", "state-slots", "tip"):
            self.assertIn(f'id="{el}"', html)
            self.assertIn(f'"{el}"', js)
        self.assertIn("renderMemory", js)                          # the JS builds the stacked bars from "memory"


if __name__ == "__main__":
    unittest.main()
