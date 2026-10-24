(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const views = ["start-view", "question-view", "reveal-view", "final-view"];
  const state = { sessionId: "", number: 0, total: 10, score: 0, busy: false,
                  categories: [], categoryLabel: "", picked: [] };
  const CATEGORY_ICONS = {
    games: "🎮", anime: "🌸", science: "🧪", movies: "🎬",
    biology: "🐾", computers: "💻", songs: "🎵", novels: "📖",
  };

  function show(view) {
    for (const id of views) $(id).classList.toggle("hidden", id !== view);
    document.body.dataset.quizView = view;
    $("error-message").classList.add("hidden");
    if (window.matchMedia("(max-width: 600px)").matches) {
      document.querySelector(".game-panel").scrollIntoView({ block: "start" });
    }
  }

  function refreshCategoryUi() {
    const count = state.picked.length;
    const buttons = $("category-grid").querySelectorAll(".category-button");
    buttons.forEach((button) => {
      button.classList.toggle("selected", state.picked.includes(button.dataset.key));
    });
    $("start-button").disabled = state.busy || count < 1;
    $("category-hint").textContent = count === 0 ? "先点亮至少 1 个分类，最多选 3 个喵。"
      : count < 3 ? `已选 ${count} 个，还可以再选 ${3 - count} 个，或直接开始喵。`
      : "已选满 3 个分类，点开始挑战喵！";
  }

  async function loadCategories() {
    try {
      const data = await fetch("/quiz/api/categories", { cache: "no-store" })
        .then((response) => {
          if (!response.ok) throw new Error("bad status");
          return response.json();
        });
      const grid = $("category-grid");
      grid.replaceChildren();
      for (const [key, label] of data.categories) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "category-button";
        button.dataset.key = key;
        button.innerHTML = `<span class="category-icon" aria-hidden="true">${CATEGORY_ICONS[key] || "✦"}</span><span>${label}</span>`;
        button.addEventListener("click", () => toggleCategory(key));
        grid.append(button);
      }
      refreshCategoryUi();
    } catch (_) {
      $("category-grid").replaceChildren();
      error("分类暂时加载不出来，刷新页面试试喵。");
    }
  }

  function toggleCategory(key) {
    if (state.busy) return;
    const index = state.picked.indexOf(key);
    if (index >= 0) state.picked.splice(index, 1);
    else if (state.picked.length >= 3) return;
    else state.picked.push(key);
    refreshCategoryUi();
  }

  function say(message, face = "wave") {
    $("mascot-speech").textContent = message;
    $("mascot-image").src = `/quiz/mascot/${face}.png`;
  }

  function playClip() {
    new Audio("/audio/helium.m4a").play().catch(() => {});
  }

  function error(message) {
    $("error-message").textContent = message;
    $("error-message").classList.remove("hidden");
  }

  async function api(path, body) {
    const response = await fetch(`/quiz/api/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(response.status === 404 ? "这局已经过期啦，刷新页面再来一局喵。" :
        response.status === 409 ? "操作太快啦，请刷新页面重新开局喵。" :
        `暂时连不上游戏服务喵（${response.status}）。${detail.slice(0, 60)}`);
    }
    return response.json();
  }

  function renderQuestion(data) {
    state.number = data.number;
    state.total = data.total;
    state.score = data.score;
    state.categories = data.categories || state.categories;
    state.categoryLabel = data.category_label || state.categoryLabel;
    $("question-counter").textContent = `第 ${data.number} / ${data.total} 题`;
    $("category-chip").textContent = state.categoryLabel ? `分类：${state.categoryLabel}` : "";
    $("score-counter").textContent = `答对 ${data.score} 题`;
    $("question-text").textContent = data.question;
    const dots = $("progress-dots");
    dots.replaceChildren();
    for (let i = 1; i <= data.total; i += 1) {
      const dot = document.createElement("span");
      if (i < data.number) dot.className = "done";
      else if (i === data.number) dot.className = "current";
      dots.append(dot);
    }
    $("answer-true").disabled = false;
    $("answer-false").disabled = false;
    say(data.number === 1 ? "第一题来啦，别被我唬住喵！" : "下一题，继续保持手感喵！");
    show("question-view");
  }

  async function startGame() {
    if (state.busy || state.picked.length < 1) return;
    state.busy = true;
    const startButton = $("start-button");
    const originalLabel = startButton.innerHTML;
    startButton.disabled = true;
    startButton.textContent = "奶龙酱出题中喵…";
    $("again-button").disabled = true;
    try {
      const data = await api("start", { categories: state.picked });
      state.sessionId = data.session_id;
      state.categories = data.categories;
      state.categoryLabel = data.category_label;
      renderQuestion(data);
    } catch (exc) {
      error(exc.message || "这局没开成，请稍后重试喵。");
    } finally {
      state.busy = false;
      startButton.innerHTML = originalLabel;
      refreshCategoryUi();
      $("again-button").disabled = false;
    }
  }

  async function choose(choice) {
    if (state.busy || !state.sessionId) return;
    state.busy = true;
    $("answer-true").disabled = true;
    $("answer-false").disabled = true;
    try {
      const data = await api("answer", {
        session_id: state.sessionId, number: state.number, choice,
      });
      state.score = data.score;
      $("verdict-chip").textContent = data.correct ? "答对啦 ✦" : "差一点点";
      $("verdict-chip").classList.toggle("wrong", !data.correct);
      $("verdict-title").textContent = data.correct ? "这题被你看穿啦！" : "被这题骗到啦！";
      $("verdict-question").textContent = data.question;
      $("correct-answer").textContent = `正确答案：${data.answer ? "真的" : "假的"}`;
      $("explanation-text").textContent = data.explanation;
      $("reveal-score").textContent = `目前答对 ${data.score} / ${data.total} 题`;
      $("streak-text").textContent = data.streak > 1 ? `连对 ${data.streak} 题 ✦` : "继续加油喵";
      $("next-button").textContent = data.finished ? "查看成绩 →" : "下一题 →";
      $("next-button").dataset.finished = String(data.finished);
      say(data.correct ? "懂你意思，这题拿下啦喵！" : "没关系，知识点这不就记住了喵！", data.correct ? "happy" : "sad");
      playClip();
      show("reveal-view");
    } catch (exc) {
      $("answer-true").disabled = false;
      $("answer-false").disabled = false;
      error(exc.message || "提交失败，请再试一次喵。");
    } finally {
      state.busy = false;
    }
  }

  function finishGame() {
    $("final-score").textContent = String(state.score);
    const message = state.score === state.total ? `全对！${state.categoryLabel || "这个分类"}已经被你看穿了喵！` :
      state.score >= 6 ? "成绩不错喵！换个分类再来，看看能不能把我难住？" :
      "被几题绕晕也没关系，换个擅长的分类再战喵！";
    $("final-message").textContent = message;
    say(state.score === state.total ? "!?强强?! 十题全对也太厉害了喵！" : "玩得开心吗？奶龙酱还想再陪你来一局喵！", "happy");
    show("final-view");
  }

  async function nextQuestion() {
    if (state.busy) return;
    if ($("next-button").dataset.finished === "true") {
      finishGame();
      return;
    }
    state.busy = true;
    $("next-button").disabled = true;
    try {
      const data = await api("next", { session_id: state.sessionId });
      renderQuestion(data);
    } catch (exc) {
      error(exc.message || "下一题暂时打不开，请稍后重试喵。");
    } finally {
      state.busy = false;
      $("next-button").disabled = false;
    }
  }

  async function copyResult() {
    const text = `我在奶龙酱的「喵话真假·${state.categoryLabel || "混合"}」答对 ${state.score}/${state.total} 题！`;
    try {
      await navigator.clipboard.writeText(text);
      $("copy-button").textContent = "已复制 ✓";
      setTimeout(() => { $("copy-button").textContent = "复制成绩"; }, 1800);
    } catch (_) {
      error(`复制没有成功，可以手动分享：${text}`);
    }
  }

  $("start-button").addEventListener("click", startGame);
  $("again-button").addEventListener("click", () => {
    // 回到分类选择：保留上次的选择，方便直接再来一局。
    show("start-view");
    refreshCategoryUi();
  });
  $("answer-true").addEventListener("click", () => choose(true));
  $("answer-false").addEventListener("click", () => choose(false));
  $("next-button").addEventListener("click", nextQuestion);
  $("copy-button").addEventListener("click", copyResult);

  loadCategories();
})();
