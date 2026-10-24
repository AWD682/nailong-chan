import unittest

from aiohttp.test_utils import TestClient, TestServer

import h5_tiles


class H5TilesTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from h5_quiz import make_app
        self.server = TestServer(make_app())
        self.client = TestClient(self.server)
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

    async def test_tiles_pages_are_served(self):
        for path in ("/tiles/", "/tiles/app.css", "/tiles/app.js"):
            with self.subTest(path=path):
                response = await self.client.get(path)
                self.assertEqual(response.status, 200)
                self.assertTrue(await response.read())

    async def test_nailong_images_are_served(self):
        for name in ("nailong-laugh.png", "nailong-arms.jpg"):
            with self.subTest(name=name):
                response = await self.client.get(f"/tiles/img/{name}")
                self.assertEqual(response.status, 200)
                self.assertGreater(len(await response.read()), 1000)

    async def test_unknown_image_is_404(self):
        response = await self.client.get("/tiles/img/evil.png")
        self.assertEqual(response.status, 404)


if __name__ == "__main__":
    unittest.main()
