import json
import unittest
from collections import deque
from types import SimpleNamespace
from unittest.mock import AsyncMock

import bot  # noqa: F401 - 先初始化 NoneBot
import nailong_ai
from nonebot.adapters.qq.event import C2CMessageCreateEvent
from unittest.mock import patch


class MemeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.cards = nailong_ai.load_meme_refs()

    def test_all_cards_load_without_truncation(self):
        self.assertEqual(len(self.cards), 69)
        self.assertEqual(len({card["id"] for card in self.cards}), 69)
        self.assertEqual(len([card for card in self.cards if card.get("topic")]), 63)
        self.assertEqual(len([card for card in self.cards if card.get("casual")]), 5)
        self.assertIn("new_three_kingdoms_x_what", {card["id"] for card in self.cards})

    def test_quote_fragments_and_homophones_find_right_card(self):
        cases = {
            "列位诸公，请听我说": "语文",
            "列位猪公，请听我说": "语文",
            "接着凑乐接着舞": "娱乐",
            "胜兵必骄": "兵法",
            "我好困想睡觉": "睡眠",
        }
        for question, topic in cases.items():
            with self.subTest(question=question):
                found = nailong_ai.rank_meme_candidates(question, self.cards)
                self.assertIn(topic, [card.get("topic") for card in found])
                self.assertLessEqual(len(found), 12)
        self.assertFalse(nailong_ai.rank_meme_candidates("abcdefg", self.cards))

    def test_short_call_completes_only_the_exact_message(self):
        for question in ("龙？", "龙", "@奶龙酱 龙？"):
            self.assertEqual(nailong_ai.exact_meme_completion(question, self.cards),
                             "可是帝王之征啊")
        for question in ("屠龙？", "龙是什么动物？", "龙年快乐"):
            self.assertIsNone(nailong_ai.exact_meme_completion(question, self.cards))
        found = nailong_ai.rank_meme_candidates("龙？", self.cards)
        self.assertEqual(found[0]["topic"], "政治")

    async def test_fictional_missing_fate_forces_quote_with_caveat(self):
        question = "呜呜呜，鸣潮3.3剧情之后达妮娅生死不明了怎么办"
        found = nailong_ai.rank_meme_candidates(question, self.cards)
        self.assertIn("推理", [card.get("topic") for card in found])
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
            create=AsyncMock()
        )))
        selected, slots, opening = await nailong_ai.select_meme(
            client, question, deque(), self.cards
        )
        self.assertEqual(selected["topic"], "推理")
        self.assertEqual(slots, {})
        self.assertIn("生死不明？那就是死了", opening)
        self.assertIn("只是玩梗", opening)
        client.chat.completions.create.assert_not_awaited()
        for serious in ("现实中朋友生死不明了怎么办", "小说剧情让我想起现实中家人失踪"):
            self.assertIsNone(nailong_ai.fictional_meme_opening(serious, self.cards))

    async def test_generated_reply_keeps_fictional_quote_when_model_omits_it(self):
        event = C2CMessageCreateEvent(
            id="fiction-call", content="鸣潮剧情之后达妮娅生死不明了怎么办",
            timestamp="2026-10-17T20:00:00+08:00",
            author={"id": "u", "user_openid": "u"},
        )
        answer = SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content="先别难过喵。")
        )])
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=answer))),
            close=AsyncMock(),
        )
        nailong_ai.history.clear()
        with patch.object(nailong_ai, "AsyncOpenAI", return_value=client), \
             patch.object(nailong_ai, "finish_reply", AsyncMock()) as finish:
            await nailong_ai.handle_chat(SimpleNamespace(), event)
        reply = finish.await_args.args[2]
        self.assertTrue(reply.startswith("“生死不明？那就是死了”"))
        self.assertIn("只是玩梗，剧情还没实锤", reply)
        self.assertIn("先别难过", reply)
        client.chat.completions.create.assert_awaited_once()

    async def test_direct_chat_short_call_replies_without_model(self):
        event = C2CMessageCreateEvent(
            id="short-call", content="龙？", timestamp="2026-10-17T20:00:00+08:00",
            author={"id": "u", "user_openid": "u"},
        )
        nailong_ai.history.clear()
        with patch.object(nailong_ai, "finish_reply", AsyncMock()) as finish, \
             patch.object(nailong_ai, "AsyncOpenAI") as client:
            await nailong_ai.handle_chat(SimpleNamespace(), event)
        finish.assert_awaited_once()
        self.assertEqual(finish.await_args.args[2], "可是帝王之征啊喵！")
        client.assert_not_called()

    async def test_selection_uses_shortlist_and_accepts_compact_card(self):
        target = next(card for card in self.cards if card.get("topic") == "语文")
        answer = SimpleNamespace(message=SimpleNamespace(
            content=json.dumps({"id": target["id"], "slots": {}})
        ))
        create = AsyncMock(return_value=SimpleNamespace(choices=[answer]))
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        selected, slots, opening = await nailong_ai.select_meme(
            client, "列位猪公，我说两句", deque(), self.cards
        )
        self.assertEqual(selected["id"], target["id"])
        self.assertEqual((slots, opening), ({}, ""))
        prompt = create.call_args.kwargs["messages"][0]["content"]
        self.assertIn(target["id"], prompt)
        self.assertNotIn("ntk_zhi_chang", prompt)


if __name__ == "__main__":
    unittest.main()
