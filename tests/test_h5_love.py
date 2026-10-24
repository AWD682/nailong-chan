import json
from pathlib import Path
import unittest

from aiohttp.test_utils import TestClient, TestServer

import h5_quiz


ROOT = Path(__file__).resolve().parent.parent
STORY_PATH = ROOT / "web" / "love" / "story.js"

BACKGROUNDS = {
    "campus", "classroom", "dorm", "restaurant", "walk", "cinema",
    "street", "library", "rain", "track", "ferris", "aquarium",
    "dorm-day-girl", "dorm-night-boy", "dorm-night-girl",
    "dorm-storm-girl", "dorm-radio-night",
}
MOODS = {"normal", "smile", "shy", "sad", "surprised"}
TONE_VALUES = {"respectful", "pushy", "withdraw", "repair"}
SPEAKERS = {"旁白", "奶龙酱", "你", "时间"}


def load_story() -> dict:
    text = STORY_PATH.read_text(encoding="utf-8")
    prefix = "window.LOVE_STORY ="
    if not text.startswith(prefix):
        raise AssertionError("story.js 缺少 window.LOVE_STORY 声明")
    payload = text[len(prefix):].strip()
    if payload.endswith(";"):
        payload = payload[:-1].rstrip()
    return json.loads(payload)


def pick_ending(story: dict, score: int, memory_hits: int,
                tone: str | None, flags: set[str]):
    ordered = sorted(story["endings"], key=lambda item: item["priority"])
    for ending in ordered:
        if ending.get("requiresFlag") and ending["requiresFlag"] not in flags:
            continue
        if score < ending.get("minScore", 0) or score > ending.get("maxScore", 100):
            continue
        if ending.get("requiresMemory") and memory_hits < ending["requiresMemory"]:
            continue
        tones = ending.get("tones")
        if tones and tone not in tones:
            continue
        return ending
    return None


class LoveStoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.story = load_story()
        cls.scenes = cls.story["scenes"]

    def walk(self, choose):
        """Play one route; choose receives (scene, options) and returns an option."""
        scene_id = self.story["start"]
        score = self.story["meta"]["startScore"]
        memories = {}
        flags = set()
        tone = None
        choices = 0
        visited = []
        while scene_id:
            scene = self.scenes[scene_id]
            visited.append(scene_id)
            options = scene.get("options") or []
            if not options:
                scene_id = scene.get("next")
                continue
            option = choose(scene_id, options)
            choices += 1
            score = max(0, min(100, score + option["delta"]))
            fact_key = option.get("factKey") or scene.get("memoryFact")
            if fact_key:
                memories[fact_key] = bool(option.get("factHit"))
            if option.get("flag"):
                flags.add(option["flag"])
            if option.get("finalTone"):
                tone = option["finalTone"]
            scene_id = option.get("next") or None
        return {
            "score": score,
            "memory_hits": sum(memories.values()),
            "tone": tone,
            "flags": flags,
            "choices": choices,
            "visited": visited,
        }

    def test_story_has_expected_scale(self):
        self.assertEqual(len(self.scenes), 21)
        self.assertEqual(len(self.story["chapters"]), 5)
        self.assertEqual(len(self.story["facts"]), 9)
        self.assertEqual(len(self.story["endings"]), 5)
        self.assertEqual(self.story["meta"]["totalChoices"], 16)
        self.assertEqual(self.story["meta"]["startScore"], 50)
        self.assertNotIn("林晚", STORY_PATH.read_text(encoding="utf-8"))

    def test_graph_is_reachable_and_well_formed(self):
        seen = set()
        stack = [self.story["start"]]
        while stack:
            scene_id = stack.pop()
            if scene_id in seen:
                continue
            self.assertIn(scene_id, self.scenes)
            seen.add(scene_id)
            scene = self.scenes[scene_id]

            self.assertIn(scene["chapter"], self.story["chapters"])
            self.assertIn(scene["background"], BACKGROUNDS)
            self.assertTrue(scene["narration"].strip())
            self.assertIn(scene.get("mode", "dialogue"), {"dialogue", "chat"})

            for line in scene["lines"]:
                self.assertIn(line["speaker"], SPEAKERS)
                self.assertTrue(line["text"].strip())
                if "mood" in line:
                    self.assertIn(line["mood"], MOODS)
                if "effect" in line:
                    self.assertEqual(line["effect"], "flash")
                for fact_key in line.get("learn", []):
                    self.assertIn(fact_key, self.story["facts"])

            if scene.get("memoryFact"):
                self.assertIn(scene["memoryFact"], self.story["facts"])

            options = scene["options"]
            if not options:
                self.assertIsNone(scene.get("step"))
                self.assertTrue(scene.get("next"))
                self.assertIn(scene["next"], self.scenes)
                stack.append(scene["next"])
                continue

            self.assertIsInstance(scene["step"], int)
            self.assertEqual(len(options), 3)
            for option in options:
                self.assertTrue(option["text"].strip())
                self.assertIn(option["tag"], self.story["tags"])
                self.assertIsInstance(option["delta"], int)
                self.assertGreaterEqual(option["delta"], -10)
                self.assertLessEqual(option["delta"], 10)
                self.assertIn(option["mood"], MOODS)
                self.assertTrue(option["note"].strip())
                self.assertTrue(option["reaction"])
                for reaction in option["reaction"] + option.get("reactionCold", []):
                    self.assertIn(reaction["speaker"], SPEAKERS)
                    self.assertTrue(reaction["text"].strip())
                    if "mood" in reaction:
                        self.assertIn(reaction["mood"], MOODS)
                if "factHit" in option:
                    self.assertIsInstance(option["factHit"], bool)
                if option.get("factKey"):
                    self.assertIn(option["factKey"], self.story["facts"])
                if option.get("finalTone"):
                    self.assertIn(option["finalTone"], TONE_VALUES)
                if option.get("next"):
                    self.assertIn(option["next"], self.scenes)
                    stack.append(option["next"])

        self.assertEqual(seen, set(self.scenes))

    def test_custom_answers_cover_every_choice(self):
        choice_count = 0
        for scene_id, scene in self.scenes.items():
            if not scene.get("options"):
                continue
            choice_count += 1
            with self.subTest(scene=scene_id):
                custom = scene.get("custom")
                self.assertIsInstance(custom, dict)
                self.assertTrue(custom.get("placeholder", "").strip())
                self.assertIn(custom.get("fallback"), range(3))
                rules = custom.get("rules")
                self.assertIsInstance(rules, list)
                covered = set()
                for rule in rules:
                    self.assertIn(rule.get("option"), range(3))
                    covered.add(rule["option"])
                    keys = rule.get("keys")
                    self.assertTrue(keys)
                    for key in keys:
                        self.assertGreaterEqual(len(key.strip()), 2)
                self.assertEqual(covered, set(range(3)))
        self.assertEqual(choice_count, 20)

    def test_every_step_1_to_16_is_used(self):
        steps = sorted({scene["step"] for scene in self.scenes.values()
                        if scene["options"]})
        self.assertEqual(steps, list(range(1, 17)))

    def test_all_facts_can_be_tested_and_cold_reactions_exist(self):
        testable = set()
        cold_count = 0
        for scene in self.scenes.values():
            if scene.get("memoryFact"):
                testable.add(scene["memoryFact"])
            for option in scene["options"]:
                if option.get("factKey"):
                    testable.add(option["factKey"])
                if option.get("reactionCold"):
                    cold_count += 1
        self.assertEqual(testable, set(self.story["facts"]))
        self.assertGreaterEqual(cold_count, 3)

    def test_all_nine_branch_combinations_can_reach_best_ending(self):
        activities = [scene_id for scene_id in ("c3_movie", "c3_shopping", "c3_library")]
        locations = [scene_id for scene_id in ("c4_track", "c4_ferris", "c4_aquarium")]
        for activity in activities:
            for location in locations:
                with self.subTest(activity=activity, location=location):
                    def choose(scene_id, options):
                        pool = options
                        if scene_id == "c3_weekend":
                            pool = [item for item in options
                                    if item.get("next") == activity]
                        elif scene_id == "c4_place":
                            pool = [item for item in options
                                    if item.get("next") == location]
                        return max(
                            pool,
                            key=lambda item: (
                                item["delta"]
                                + (2 if item.get("factHit") else 0)
                                + (1 if item.get("finalTone") == "respectful" else 0)
                            ),
                        )

                    result = self.walk(choose)
                    self.assertEqual(result["choices"], 16)
                    self.assertGreaterEqual(result["score"], 80)
                    self.assertGreaterEqual(result["memory_hits"], 5)
                    ending = pick_ending(
                        self.story, result["score"], result["memory_hits"],
                        result["tone"], result["flags"],
                    )
                    self.assertIsNotNone(ending)
                    self.assertEqual(ending["id"], "best")

    def test_weak_route_falls_back_to_miss_ending(self):
        def choose(scene_id, options):
            if scene_id == "c3_weekend":
                options = [item for item in options
                           if item.get("next") == "c3_movie"]
            elif scene_id == "c4_place":
                options = [item for item in options
                           if item.get("next") == "c4_track"]
            return min(
                (item for item in options if not item.get("flag")),
                key=lambda item: item["delta"],
            )

        result = self.walk(choose)
        self.assertEqual(result["choices"], 16)
        ending = pick_ending(
            self.story, result["score"], result["memory_hits"],
            result["tone"], result["flags"],
        )
        self.assertIsNotNone(ending)
        self.assertEqual(ending["id"], "miss")

    def test_overstep_flag_overrides_score_and_ending_priority(self):
        def choose(scene_id, options):
            if scene_id == "c3_weekend":
                options = [item for item in options
                           if item.get("next") == "c3_library"]
            if scene_id == "c4_place":
                return next(item for item in options
                            if item.get("next") == "c4_ferris")
            if scene_id == "c4_ferris":
                return next(item for item in options if item.get("flag") == "overstep")
            return max(options, key=lambda item: item["delta"])

        result = self.walk(choose)
        self.assertIn("overstep", result["flags"])
        ending = pick_ending(self.story, 100, 9, "pushy", result["flags"])
        self.assertEqual(ending["id"], "overstep")
        self.assertEqual(ending["priority"], 0)

    def test_endings_have_branch_flavors_and_a_fallback(self):
        ids = {ending["id"] for ending in self.story["endings"]}
        self.assertEqual(ids, {"overstep", "best", "almost", "slow", "miss"})
        self.assertEqual(
            len({ending["priority"] for ending in self.story["endings"]}),
            len(self.story["endings"]),
        )
        fallback = next(item for item in self.story["endings"]
                        if item["id"] == "miss")
        self.assertFalse(fallback.get("requiresFlag"))
        self.assertFalse(fallback.get("requiresMemory"))
        self.assertFalse(fallback.get("tones"))
        for ending in self.story["endings"]:
            self.assertTrue(ending["text"].strip())
            self.assertTrue(ending["advice"].strip())
            self.assertEqual(set(ending["flavors"]),
                             {"track", "ferris", "aquarium"})
            for flavor in ending["flavors"].values():
                self.assertTrue(flavor.strip())

    def test_overstep_flag_is_reachable(self):
        flag = next(item for item in self.story["endings"]
                    if item["id"] == "overstep")["requiresFlag"]
        self.assertTrue(any(
            option.get("flag") == flag
            for scene in self.scenes.values()
            for option in scene["options"]
        ))


class LovePageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = TestServer(h5_quiz.make_app())
        self.client = TestClient(self.server)
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

    async def test_love_page_and_assets_are_served(self):
        for path in ("/love/", "/love/index.html", "/love/style.css",
                     "/love/story.js", "/love/game.js",
                     "/love/favicon.svg"):
            with self.subTest(path=path):
                response = await self.client.get(path)
                self.assertEqual(response.status, 200)
                self.assertTrue(await response.read())

    async def test_every_scene_background_is_served(self):
        for name in sorted(BACKGROUNDS):
            with self.subTest(background=name):
                response = await self.client.get(f"/love/backgrounds/{name}.svg")
                self.assertEqual(response.status, 200)
                self.assertIn("svg", response.headers.get("Content-Type", ""))
                self.assertTrue(await response.read())

    async def test_love_path_redirects_to_directory(self):
        response = await self.client.get("/love", allow_redirects=False)
        self.assertIn(response.status, (301, 302, 308))
        self.assertEqual(response.headers["Location"], "/love/")


if __name__ == "__main__":
    unittest.main()
