import unittest

from aiohttp.test_utils import TestClient, TestServer

import h5_run


class H5RunTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from h5_quiz import make_app
        self.server = TestServer(make_app())
        self.client = TestClient(self.server)
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

    async def test_run_pages_are_served(self):
        for path in ("/run/", "/run/app.css", "/run/app.js"):
            with self.subTest(path=path):
                response = await self.client.get(path)
                self.assertEqual(response.status, 200)
                self.assertTrue(await response.read())

    async def test_three_js_is_served(self):
        response = await self.client.get("/run/three.min.js")
        self.assertEqual(response.status, 200)
        body = await response.read()
        # UMD 版 Three.js 开头带有版权注释，确认不是空文件或 404 页面。
        self.assertGreater(len(body), 100_000)
        self.assertIn(b"Three.js", body[:200])

    async def test_textured_model_and_loader_are_served(self):
        for path in (
            "/run/boot.js",
            "/run/three.module.js",
            "/run/loaders/GLTFLoader.js",
            "/run/utils/BufferGeometryUtils.js",
        ):
            with self.subTest(path=path):
                response = await self.client.get(path)
                self.assertEqual(response.status, 200)
                self.assertTrue(await response.read())
        response = await self.client.get("/run/nailong.glb")
        self.assertEqual(response.status, 200)
        self.assertEqual((await response.read())[:4], b"glTF")
        response = await self.client.get("/run/gameover-laugh.png")
        self.assertEqual(response.status, 200)
        self.assertEqual((await response.read())[:8], b"\x89PNG\r\n\x1a\n")
        for name in ("crossed-arms", "belly-laugh", "side-view"):
            with self.subTest(standee=name):
                response = await self.client.get(f"/run/standees/{name}.png")
                self.assertEqual(response.status, 200)
                self.assertEqual((await response.read())[:8], b"\x89PNG\r\n\x1a\n")

    async def test_run_sound_clips_are_served(self):
        for name in ("jump", "hurt", "heal", "helium"):
            with self.subTest(sound=name):
                response = await self.client.get(f"/audio/{name}.m4a")
                self.assertEqual(response.status, 200)
                body = await response.read()
                self.assertGreater(len(body), 1_000)
                self.assertEqual(body[4:8], b"ftyp")


if __name__ == "__main__":
    unittest.main()
