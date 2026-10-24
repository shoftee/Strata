"""The Gyro entries of setup's catalog (agentionai/Qwen3.8-Flash-Next-Gyro-GGUF): sizes, pins, the VRAM + RAM memory rule
and never being a default.  Offline."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import setup  # noqa: E402


class GyroCatalog(unittest.TestCase):
    def test_the_two_sizes_and_their_numbers(self):
        self.assertEqual(setup.FAMILIES["gyro"]["file"].format(q="Gyro-S"), "Qwen3.8-Flash-Next-Gyro-S.gguf")
        for model, name, download, memory in (("Gyro-S", "Qwen3.8-Flash-Next-Gyro-S-TQ1_0.gguf", 58.5, 27.6),
                                              ("Gyro-M", "Qwen3.8-Flash-Next-Gyro-M-TQ2_0.gguf", 92.0, 35.0)):
            d = setup.MODELS[model]
            self.assertEqual(setup.model_file(setup.FAMILIES["gyro"], model, 1), name)
            self.assertEqual((d["download_gb"], d["ram_gb"]), (download, memory))
            size, sha = setup.GYRO_FILES[name]
            self.assertAlmostEqual(size / 1e9, download, delta=0.05)
            self.assertEqual(len(sha), 64)
            self.assertEqual(setup.model_shards(setup.FAMILIES["gyro"], model), 1)
            self.assertIs(d.get("vision"), True)
            self.assertTrue(d["mem_total"])
            self.assertEqual(d["families"], ("gyro",))

    def test_pinned_revision_and_license(self):
        repo = "agentionai/Qwen3.8-Flash-Next-Gyro-GGUF"
        self.assertEqual(len(setup.HF_REVISIONS[repo]), 40)
        self.assertIn(setup.HF_REVISIONS[repo], setup.FAMILIES["gyro"]["hf"])
        self.assertIn("Qwen Community License 1.0", setup.FAMILIES["gyro"]["license"])

    def test_never_the_default_family(self):
        self.assertEqual(setup.menu_families(False)[0], "qwen")
        self.assertNotIn("gyro", setup.RECOMMENDED_SIZES)

    def test_memory_is_vram_plus_ram(self):
        self.assertEqual(setup.mem_have("Gyro-S", 16.0, 12.0), 28.0)
        self.assertEqual(setup.mem_have("Q2_0", 16.0, 12.0), 16.0)
        names = ["Gyro-S", "Gyro-M"]
        self.assertEqual(setup.recommended_size("gyro", names, 24.0, 12.0), "Gyro-M")     # 36 GB
        self.assertEqual(setup.recommended_size("gyro", names, 16.0, 12.0), "Gyro-S")     # 28 GB
        self.assertEqual(setup.recommended_size("gyro", names, 8.0, 8.0), "Gyro-S")       # nothing fits: the first


class GyroEngineVersionTest(unittest.TestCase):
    """Gyro's expert files are native_experts.txt v5 (Hadamard-folded). The released 0.1.45 engine reads only up to v4, so the
    minimum is 0.1.45.1, the first engine package built after the v5 reader (APR port, f47b0385f) was merged."""

    def test_gyro_needs_an_engine_that_reads_v5_files(self):
        self.assertEqual(setup.GYRO_ENGINE, (0, 1, 45, 1))
        self.assertGreater(setup.GYRO_ENGINE, (0, 1, 45))            # the released 0.1.45 is not enough
        sizes = [m for m in setup.MODELS.values() if "gyro" in str(m.get("file", "")).lower()]
        self.assertEqual(len(sizes), 2)
        self.assertTrue(all(m["engine"] == (0, 1, 45, 1) for m in sizes))

    def test_every_catalog_agrees(self):
        for m in ("Gyro-S", "Gyro-M"):
            self.assertEqual(setup.MODELS[m]["engine"], setup.GYRO_ENGINE, m)

    def test_the_pack_reader_is_in_the_source_this_minimum_describes(self):
        text = (ROOT / "src" / "kernels" / "cpu" / "expert_layout.cpp").read_text(encoding="utf-8")
        self.assertIn("native_experts.txt v5 declares Hadamard-folded experts", text)


if __name__ == "__main__":
    unittest.main()
