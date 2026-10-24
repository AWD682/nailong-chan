from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from nonebot.adapters.qq.event import (
    GroupAtMessageCreateEvent,
    GroupMessageCreateEvent,
    InteractionCreateEvent,
)

import bot  # noqa: F401 - 初始化 NoneBot 并加载插件
import mini_games
import quiz_api
from quiz_bank import FALLBACK_QUIZ_QUESTIONS, QUIZ_CATEGORIES


def group_message(text: str, *, mentioned: bool = True):
    event_type = GroupAtMessageCreateEvent if mentioned else GroupMessageCreateEvent
    return event_type(
        id="message-1", content=text, timestamp="2026-09-26T14:00:00+08:00",
        group_id="g", group_openid="group-1",
        author={"id": "u", "bot": False,
                "member_openid": "owner-1", "member_role": "member"},
    )


def click(token: str, action: str, *, player: str = "owner-1",
          group: str = "group-1") -> InteractionCreateEvent:
    return InteractionCreateEvent(
        id=f"interaction-{token}-{action}", type=11, version=1,
        timestamp="2026-09-26T14:00:00+08:00", scene="group", chat_type=1,
        group_openid=group, group_member_openid=player, application_id="bot",
        event_id="event-1",
        data={"resolved": {"button_data": f"nlgame:{token}:{action}"}},
    )


def buttons(message):
    return [button for row in message["keyboard"][0].data["keyboard"].content.rows
            for button in row.buttons]


def card_text(message):
    return message["markdown"][0].data["markdown"].content


def labels(message):
    return [b.render_data.label for b in buttons(message)]


def first_token(message):
    return buttons(message)[0].action.data.split(":")[1]


class MiniGameTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        mini_games.sessions.clear()
        mini_games.recent_questions.clear()
        # 默认关闭实时出题；实时路径单独 mock 测试。
        self.api_patcher = patch.object(quiz_api, "available", return_value=False)
        self.api_patcher.start()
        self.addCleanup(self.api_patcher.stop)
        self.qq_bot = SimpleNamespace(send=AsyncMock(), put_interaction=AsyncMock())

    def test_generated_quiz_requires_a_boolean_answer(self):
        self.assertEqual(mini_games.parse_generated_quiz(
            '{"question":"章鱼有三颗心。","answer":true,'
            '"explanation":"章鱼确实有三颗心。"}'
        ), ("章鱼有三颗心。", True, "章鱼确实有三颗心。"))
        self.assertIsNone(mini_games.parse_generated_quiz(
            '{"question":"章鱼有三颗心。","answer":"true",'
            '"explanation":"章鱼确实有三颗心。"}'
        ))

    async def test_model_creates_new_quiz_and_remembers_it(self):
        result = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content='{"question":"章鱼有三颗心。","answer":true,'
                    '"explanation":"它的循环系统有三颗心脏。"}'
        ))])
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.chat.completions.create.return_value = result
        config = SimpleNamespace(ai_api_key="test-key", ai_model="test-model",
                                 ai_base_url="https://example.com/v1")
        with patch.object(mini_games, "ai_config", config), \
             patch.object(mini_games, "AsyncOpenAI", return_value=client):
            quiz = await mini_games.generate_quiz("group-1", ("biology",))
            duplicate = await mini_games.generate_quiz("group-1", ("biology",))
        self.assertEqual(quiz[1], True)
        self.assertEqual(list(mini_games.recent_questions["group-1"]), [quiz[0]])
        self.assertIsNone(duplicate)
        self.assertEqual(client.chat.completions.create.await_count, 2)
        # 分类与难度要求要写进命题提示词。
        prompt = client.chat.completions.create.await_args.kwargs["messages"][0]["content"]
        self.assertIn("生物", prompt)
        self.assertIn("难度", prompt)

    def test_only_explicit_group_at_game_command_opens_menu(self):
        self.assertTrue(mini_games.is_game_command(group_message("游戏")))
        self.assertTrue(mini_games.is_game_command(group_message("小游戏")))
        self.assertFalse(mini_games.is_game_command(group_message("你好")))
        self.assertFalse(mini_games.is_game_command(group_message("游戏", mentioned=False)))

    async def test_game_menu_offers_quiz_and_web_links(self):
        await mini_games.open_game_menu(self.qq_bot, group_message("游戏"))
        menu = self.qq_bot.send.await_args.args[1]
        self.assertEqual([segment.type for segment in menu], ["markdown", "keyboard"])
        menu_buttons = buttons(menu)
        # 猜拳已下线：菜单是喵话真假按钮 + 五个网页入口（每行 2 个）。
        self.assertEqual([b.render_data.label for b in menu_buttons],
                         ["喵话真假", "奶龙快跑", "你画我猜", "喵话真假 H5", "别猜奶块",
                          "心动选修课"])
        self.assertEqual([b.action.type for b in menu_buttons], [1, 0, 0, 0, 0, 0])
        self.assertEqual(menu_buttons[1].action.data, "http://127.0.0.1:8765/run/")
        self.assertEqual(menu_buttons[2].action.data, "http://127.0.0.1:8765/draw/")
        self.assertEqual(menu_buttons[3].action.data, "http://127.0.0.1:8765/quiz/")
        self.assertEqual(menu_buttons[4].action.data, "http://127.0.0.1:8765/tiles/")
        self.assertEqual(menu_buttons[5].action.data, "http://127.0.0.1:8765/love/")
        self.assertIn("http://127.0.0.1:8765/run/", card_text(menu))
        _, menu_token, _ = menu_buttons[0].action.data.split(":")
        await mini_games.handle_game_click(self.qq_bot, click(menu_token, "quiz"))
        self.qq_bot.put_interaction.assert_awaited_with(
            interaction_id=f"interaction-{menu_token}-quiz", code=0
        )

    async def test_game_menu_adds_web_links_when_public_url_is_configured(self):
        with patch.object(mini_games, "web_config",
                          SimpleNamespace(h5_public_url="https://games.example.com")):
            await mini_games.open_game_menu(self.qq_bot, group_message("游戏"))
        menu = self.qq_bot.send.await_args.args[1]
        menu_buttons = buttons(menu)
        self.assertEqual(menu_buttons[1].action.data,
                         "https://games.example.com/run/")
        self.assertEqual(menu_buttons[2].action.data,
                         "https://games.example.com/draw/")
        self.assertEqual(menu_buttons[3].action.data,
                         "https://games.example.com/quiz/")
        self.assertEqual(menu_buttons[4].action.data,
                         "https://games.example.com/tiles/")
        self.assertEqual(menu_buttons[5].action.data,
                         "https://games.example.com/love/")
        # 菜单文字里也带链接，群友可以直接点进去。
        self.assertIn("https://games.example.com/run/", card_text(menu))

    async def test_live_quiz_api_is_preferred_over_chat_model(self):
        generated = [("实时出题。", True, "解释。")]
        chat_model = AsyncMock()
        with patch.object(quiz_api, "available", return_value=True), \
             patch.object(mini_games.quiz_api, "generate_quiz_batch",
                          AsyncMock(return_value=generated)) as batch, \
             patch.object(mini_games, "AsyncOpenAI", chat_model):
            quiz = await mini_games.generate_quiz("group-1", ("games", "novels"))
        self.assertEqual(quiz, generated[0])
        batch.assert_awaited_once_with(1, ("games", "novels"), [])
        self.assertEqual(list(mini_games.recent_questions["group-1"]),
                         ["实时出题。"])
        # 实时接口成功时不再调用聊天模型。
        self.assertEqual(chat_model.await_count, 0)

    async def test_quiz_menu_asks_for_category_then_first_question(self):
        menu_token = mini_games.new_session("menu", "group-1")
        generated = ("企鹅会飞。", False, "企鹅只能游泳，不能飞。")
        with patch.object(mini_games, "generate_quiz",
                          AsyncMock(return_value=generated)) as generate:
            await mini_games.handle_game_click(self.qq_bot, click(menu_token, "quiz"))
            category_card = self.qq_bot.send.await_args.args[1]
            self.assertEqual(labels(category_card),
                             list(QUIZ_CATEGORIES.values()) + ["开始答题"])
            self.assertIn("选分类", card_text(category_card))
            self.assertEqual(self.qq_bot.send.await_count, 1)

            # 还没选分类就点开始：提示先选分类，不出题。
            _, category_token, _ = buttons(category_card)[-1].action.data.split(":")
            await mini_games.handle_game_click(
                self.qq_bot, click(category_token, "start_quiz"))
            self.assertIn("先点亮至少 1 个",
                          self.qq_bot.send.await_args.args[1])
            self.assertEqual(generate.await_count, 0)

            # 选一个分类，出题会话带上它。
            _, category_token, action = buttons(category_card)[2].action.data.split(":")
            await mini_games.handle_game_click(
                self.qq_bot, click(category_token, action)
            )
            self.assertIn("已选分类：数理化", self.qq_bot.send.await_args.args[1])
            await mini_games.handle_game_click(
                self.qq_bot, click(category_token, "start_quiz"))
            generate.assert_awaited_once_with("group-1", ("science",))
            card = self.qq_bot.send.await_args.args[1]
            self.assertIn("企鹅会飞", card_text(card))
            self.assertIn("数理化", card_text(card))
            self.assertIn("第 1/10 题", card_text(card))
            self.assertEqual(labels(card), ["真的", "假的"])
            # 答题会话记住分类，后面收官时会用到。
            quiz_token = first_token(card)
            self.assertEqual(mini_games.sessions[quiz_token].categories,
                             ("science",))

    async def test_quiz_category_multiselect_toggle_and_cap(self):
        category_token = mini_games.new_session(
            "quiz_category", "group-1", "owner-1")
        await mini_games.handle_game_click(
            self.qq_bot, click(category_token, "cat_games"))
        self.assertEqual(mini_games.sessions[category_token].categories, ("games",))
        await mini_games.handle_game_click(
            self.qq_bot, click(category_token, "cat_anime"))
        self.assertEqual(mini_games.sessions[category_token].categories,
                         ("games", "anime"))
        # 再点一次是取消。
        await mini_games.handle_game_click(
            self.qq_bot, click(category_token, "cat_games"))
        self.assertEqual(mini_games.sessions[category_token].categories, ("anime",))
        for action in ("cat_science", "cat_movies", "cat_biology"):
            await mini_games.handle_game_click(
                self.qq_bot, click(category_token, action))
        self.assertEqual(mini_games.sessions[category_token].categories,
                         ("anime", "science", "movies"))
        # 第 4 个分类被拒绝。
        await mini_games.handle_game_click(
            self.qq_bot, click(category_token, "cat_biology"))
        self.assertIn("最多选 3 个分类", self.qq_bot.send.await_args.args[1])
        self.assertEqual(mini_games.sessions[category_token].categories,
                         ("anime", "science", "movies"))

    async def test_quiz_answer_is_bound_to_player_and_group(self):
        true_question = FALLBACK_QUIZ_QUESTIONS[0]
        false_question = FALLBACK_QUIZ_QUESTIONS[1]
        token = mini_games.new_session("quiz", "group-1", "owner-1", true_question)
        await mini_games.handle_game_click(
            self.qq_bot, click(token, "true", player="other")
        )
        self.assertIn(token, mini_games.sessions)
        self.assertEqual(self.qq_bot.put_interaction.await_args.kwargs["code"], 4)
        await mini_games.handle_game_click(
            self.qq_bot, click(token, "true", group="other-group")
        )
        self.assertIn(token, mini_games.sessions)
        self.assertEqual(self.qq_bot.put_interaction.await_args.kwargs["code"], 4)

        await mini_games.handle_game_click(self.qq_bot, click(token, "true"))
        self.assertNotIn(token, mini_games.sessions)
        result = self.qq_bot.send.await_args.args[1]
        self.assertIn("答对啦", card_text(result))
        self.assertIn(true_question[0], card_text(result))
        self.assertEqual(labels(result), ["下一题", "结束游戏"])

        false_token = mini_games.new_session(
            "quiz", "group-1", "owner-1", false_question
        )
        await mini_games.handle_game_click(self.qq_bot, click(false_token, "true"))
        self.assertIn("答错啦", card_text(self.qq_bot.send.await_args.args[1]))
        self.assertIn("答案：假的", card_text(self.qq_bot.send.await_args.args[1]))

    async def test_quiz_can_continue_then_end_with_score(self):
        first = ("章鱼有三颗心。", True, "章鱼确实有三颗心脏。")
        second = ("企鹅会飞。", False, "企鹅只能游泳，不能飞。")
        category_token = mini_games.new_session("quiz_category", "group-1")
        with patch.object(mini_games, "generate_quiz",
                          AsyncMock(side_effect=[first, second])) as generate, \
             patch.object(mini_games, "QUIZ_ROUNDS", 2):
            await mini_games.handle_game_click(
                self.qq_bot, click(category_token, "cat_games"))
            await mini_games.handle_game_click(
                self.qq_bot, click(category_token, "start_quiz"))
            first_button = buttons(self.qq_bot.send.await_args.args[1])[0]
            first_token = first_button.action.data.split(":")[1]
            await mini_games.handle_game_click(self.qq_bot, click(first_token, "true"))

            result = self.qq_bot.send.await_args.args[1]
            self.assertIn("目前答对 1/1 题", card_text(result))
            # 答对一题会先发一条氦气大笑语音，再发结果按钮卡。
            audio_segment = self.qq_bot.send.call_args_list[-2].args[1]
            self.assertEqual(getattr(audio_segment, "type", ""), "file_audio")
            result_token = buttons(result)[0].action.data.split(":")[1]
            await mini_games.handle_game_click(
                self.qq_bot, click(result_token, "next", player="other")
            )
            self.assertIn(result_token, mini_games.sessions)
            self.assertEqual(generate.await_count, 1)

            await mini_games.handle_game_click(self.qq_bot, click(result_token, "next"))
            question = self.qq_bot.send.await_args.args[1]
            self.assertIn("第 2/2 题", card_text(question))
            self.assertIn(second[0], card_text(question))
            self.assertEqual(generate.await_count, 2)
            second_token = buttons(question)[0].action.data.split(":")[1]
            await mini_games.handle_game_click(self.qq_bot, click(second_token, "true"))
            # 第 2 题是最后一题：直接收官，不再发按钮。
            self.assertEqual(
                self.qq_bot.send.await_args.args[1],
                "喵话真假·游戏收官！2 题答对 1/2 题喵。成绩不错，换个分类再战一轮？")
            # 分类卡 + 题目1 + 音效 + 结果卡 + 题目2 + 音效 + 收官 = 7 条。
            self.assertEqual(self.qq_bot.send.await_count, 7)
            # 猜错也一样先放氦气大笑，再发收官文字。
            wrong_audio = self.qq_bot.send.call_args_list[-2].args[1]
            self.assertEqual(getattr(wrong_audio, "type", ""), "file_audio")

    async def test_quiz_uses_category_backup_when_model_fails(self):
        from quiz_bank import CATEGORY_QUIZ_QUESTIONS
        category_token = mini_games.new_session("quiz_category", "group-1")
        with patch.object(mini_games, "generate_quiz", AsyncMock(return_value=None)):
            await mini_games.handle_game_click(
                self.qq_bot, click(category_token, "cat_anime"))
            await mini_games.handle_game_click(
                self.qq_bot, click(category_token, "start_quiz"))
        card = self.qq_bot.send.await_args.args[1]
        _, round_token, _ = buttons(card)[0].action.data.split(":")
        self.assertIn(mini_games.sessions[round_token].question,
                      CATEGORY_QUIZ_QUESTIONS["anime"])
        self.assertEqual(mini_games.sessions[round_token].categories, ("anime",))


if __name__ == "__main__":
    unittest.main()
