import unittest
from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import TestClient, TestServer

import h5_quiz
import quiz_api
from quiz_bank import CATEGORY_QUIZ_QUESTIONS, QUIZ_CATEGORIES


class H5QuizTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        h5_quiz.sessions.clear()
        h5_quiz.recent_questions.clear()
        # 默认关闭实时出题，走备用题库；出题路径单独 mock 测试。
        self.api_patcher = patch.object(quiz_api, "available", return_value=False)
        self.api_patcher.start()
        self.addCleanup(self.api_patcher.stop)
        self.server = TestServer(h5_quiz.make_app())
        self.client = TestClient(self.server)
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        h5_quiz.sessions.clear()

    async def test_web_page_and_mascot_are_available(self):
        for path in ("/quiz/", "/quiz/app.css", "/quiz/app.js",
                     "/quiz/mascot/wave.png", "/quiz/api/categories"):
            with self.subTest(path=path):
                response = await self.client.get(path)
                self.assertEqual(response.status, 200)
                self.assertTrue(await response.read())
        self.assertEqual((await self.client.get("/quiz/mascot/other.png")).status, 404)
        listed = (await (await self.client.get("/quiz/api/categories")).json())["categories"]
        self.assertEqual([key for key, _ in listed], list(QUIZ_CATEGORIES))

    async def test_ten_rounds_in_chosen_categories_keep_answers_server_side(self):
        bank = {question: answer
                for questions in CATEGORY_QUIZ_QUESTIONS.values()
                for question, answer, _ in questions}
        response = await self.client.post(
            "/quiz/api/start", json={"categories": ["games", "anime"]})
        self.assertEqual(response.status, 200)
        current = await response.json()
        token = current["session_id"]
        self.assertNotIn("answer", current)
        self.assertEqual(current["total"], 10)
        self.assertEqual(current["categories"], ["games", "anime"])
        self.assertEqual(current["category_label"], "游戏、动漫")

        blocked = await self.client.post("/quiz/api/next", json={"session_id": token})
        self.assertEqual(blocked.status, 409)

        seen = set()
        for number in range(1, 11):
            self.assertEqual(current["number"], number)
            self.assertNotIn(current["question"], seen)
            self.assertIn(current["question"], bank)
            seen.add(current["question"])
            response = await self.client.post("/quiz/api/answer", json={
                "session_id": token, "number": number,
                "choice": bank[current["question"]],
            })
            self.assertEqual(response.status, 200)
            result = await response.json()
            self.assertTrue(result["correct"])
            self.assertEqual(result["score"], number)
            self.assertEqual(result["finished"], number == 10)
            duplicate = await self.client.post("/quiz/api/answer", json={
                "session_id": token, "number": number,
                "choice": bank[current["question"]],
            })
            self.assertEqual(duplicate.status, 409)
            if number < 10:
                response = await self.client.post(
                    "/quiz/api/next", json={"session_id": token})
                self.assertEqual(response.status, 200)
                current = await response.json()
                self.assertNotIn("answer", current)

        self.assertEqual(h5_quiz.sessions[token].score, 10)
        self.assertEqual(h5_quiz.sessions[token].categories, ("games", "anime"))
        self.assertEqual((await self.client.post(
            "/quiz/api/next", json={"session_id": token})).status, 409)

    async def test_start_rejects_unknown_or_oversized_categories(self):
        for payload in ({"category": "nope"}, {"categories": ["nope"]},
                        {"categories": []},
                        {"categories": ["games", "anime", "songs", "movies"]}):
            with self.subTest(payload=payload):
                response = await self.client.post("/quiz/api/start", json=payload)
                self.assertEqual(response.status, 400)

    async def test_duplicate_categories_are_collapsed(self):
        response = await self.client.post(
            "/quiz/api/start", json={"categories": ["games", "games"]})
        self.assertEqual(response.status, 200)
        current = await response.json()
        self.assertEqual(current["categories"], ["games"])

    async def test_start_without_category_still_works(self):
        response = await self.client.post("/quiz/api/start", json={})
        self.assertEqual(response.status, 200)
        current = await response.json()
        self.assertEqual(len(current["categories"]), 1)
        self.assertIn(current["categories"][0], QUIZ_CATEGORIES)
        self.assertEqual(current["total"], 10)

    async def test_invalid_choice_cannot_score(self):
        current = await (await self.client.post(
            "/quiz/api/start", json={"categories": ["songs"]})).json()
        token = current["session_id"]
        response = await self.client.post("/quiz/api/answer", json={
            "session_id": token, "number": current["number"], "choice": "true",
        })
        self.assertEqual(response.status, 400)
        self.assertEqual(h5_quiz.sessions[token].score, 0)

    async def test_live_api_questions_are_served_and_remembered(self):
        generated = [("实时出题一。", True, "解释一。"), ("实时出题二。", False, "解释二。")]
        with patch.object(quiz_api, "available", return_value=True), \
             patch.object(h5_quiz.quiz_api, "generate_quiz_batch",
                          AsyncMock(return_value=generated)) as batch:
            response = await self.client.post(
                "/quiz/api/start", json={"categories": ["games", "novels"]})
        self.assertEqual(response.status, 200)
        current = await response.json()
        self.assertEqual(current["question"], generated[0][0])
        batch.assert_awaited_once_with(
            10, ("games", "novels"), h5_quiz.recent_questions)
        token = current["session_id"]
        stored = h5_quiz.sessions[token].questions
        self.assertEqual(stored[:2], tuple(generated))
        self.assertEqual(len(stored), 10)
        # 不足 10 题的部分由备用题库补齐。
        bank = {question for questions in CATEGORY_QUIZ_QUESTIONS.values()
                for question, _, _ in questions}
        self.assertTrue(all(question[0] in bank for question in stored[2:]))
        self.assertEqual(set(h5_quiz.recent_questions), {item[0] for item in stored})

    async def test_live_api_failure_falls_back_to_bank(self):
        with patch.object(quiz_api, "available", return_value=True), \
             patch.object(h5_quiz.quiz_api, "generate_quiz_batch",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            response = await self.client.post(
                "/quiz/api/start", json={"categories": ["games"]})
        self.assertEqual(response.status, 200)
        current = await response.json()
        self.assertEqual(current["total"], 10)
        bank = {question for question, _, _ in CATEGORY_QUIZ_QUESTIONS["games"]}
        self.assertIn(current["question"], bank)


if __name__ == "__main__":
    unittest.main()
