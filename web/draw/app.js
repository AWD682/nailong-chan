/* 你画我猜:本地画板 + 让奶龙酱看图猜。答案判定全部在服务端完成。 */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const canvas = $("draw-canvas");
  const ctx = canvas.getContext("2d");
  const CANVAS_W = canvas.width;
  const CANVAS_H = canvas.height;
  const SEND_WIDTH = 640;

  const PALETTE = ["#3f3540", "#e05b5b", "#f2994a", "#f7d154", "#6fcf97",
    "#56b4c8", "#5678e8", "#9b6dd6", "#f49ac1", "#a9714b"];
  const SIZES = [
    { label: 5, value: 5 },
    { label: 10, value: 10 },
    { label: 20, value: 20 },
  ];
  const ERASER_SCALE = 3;

  const state = {
    color: PALETTE[0],
    size: 10,
    eraser: false,
    strokes: [],
    current: null,
    word: null,
    busy: false,
  };

  const GUESS_LABEL = "让奶龙酱猜";
  const GUESS_BUSY = "奶龙酱眯着眼看…";

  function playClip() {
    new Audio("/audio/helium.m4a").play().catch(() => {});
  }

  function redraw() {
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);
    for (const stroke of state.strokes) drawStroke(stroke);
  }

  function drawStroke(stroke) {
    ctx.strokeStyle = stroke.color;
    ctx.fillStyle = stroke.color;
    ctx.lineWidth = stroke.size;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    const points = stroke.points;
    if (points.length === 1) {
      ctx.beginPath();
      ctx.arc(points[0].x, points[0].y, stroke.size / 2, 0, Math.PI * 2);
      ctx.fill();
      return;
    }
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) ctx.lineTo(points[i].x, points[i].y);
    ctx.stroke();
  }

  function canvasPoint(event) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left) * (CANVAS_W / rect.width),
      y: (event.clientY - rect.top) * (CANVAS_H / rect.height),
    };
  }

  function refreshToolbar() {
    const dirty = state.strokes.length > 0;
    $("undo-button").disabled = !dirty || state.busy;
    $("clear-button").disabled = !dirty || state.busy;
    $("guess-button").disabled = !dirty || state.busy;
    $("guess-button").innerHTML = (state.busy ? GUESS_BUSY : GUESS_LABEL)
      + ' <span aria-hidden="true">👀</span>';
    $("canvas-empty").classList.toggle("hidden", dirty);
    document.querySelectorAll(".swatch").forEach((el) => {
      el.classList.toggle("selected", !state.eraser && el.dataset.color === state.color);
    });
    $("eraser-button").classList.toggle("selected", state.eraser);
    $("eraser-button").setAttribute("aria-pressed", String(state.eraser));
    document.querySelectorAll(".size-button").forEach((el) => {
      el.classList.toggle("selected", !state.eraser && Number(el.dataset.size) === state.size);
    });
  }

  function startStroke(event) {
    if (state.busy || event.button > 0) return;
    event.preventDefault();
    canvas.setPointerCapture(event.pointerId);
    const erasing = state.eraser;
    state.current = {
      color: erasing ? "#ffffff" : state.color,
      size: erasing ? state.size * ERASER_SCALE : state.size,
      points: [canvasPoint(event)],
    };
    state.strokes.push(state.current);
    drawStroke(state.current);
    refreshToolbar();
  }

  function moveStroke(event) {
    if (!state.current) return;
    event.preventDefault();
    state.current.points.push(canvasPoint(event));
    drawStroke(state.current);
  }

  function endStroke() {
    state.current = null;
  }

  function undo() {
    state.strokes.pop();
    redraw();
    refreshToolbar();
  }

  function clearCanvas() {
    state.strokes = [];
    redraw();
    refreshToolbar();
  }

  function showError(text) {
    const box = $("error-message");
    box.textContent = text;
    box.classList.remove("hidden");
  }

  function hideError() {
    $("error-message").classList.add("hidden");
  }

  async function getWord() {
    if (state.busy) return;
    hideError();
    const button = $("word-button");
    button.disabled = true;
    try {
      const response = await fetch("/draw/api/word", { method: "POST" });
      if (!response.ok) throw new Error("bad status");
      const data = await response.json();
      setWord(data.word, data.category);
    } catch {
      showError("题目没抽出来，再点一次试试喵。");
    } finally {
      button.disabled = false;
    }
  }

  function setWord(word, source) {
    state.word = word;
    const chip = $("word-chip");
    chip.textContent = `题目：「${word}」 · ${source}`;
    chip.classList.remove("idle");
    $("mascot-speech").textContent = `就画「${word}」喵！别让奶龙酱一眼看穿~`;
  }

  function setCustomWord() {
    if (state.busy) return;
    hideError();
    const input = $("custom-word-input");
    const word = input.value.trim().replace(/\s+/g, " ");
    if (!word) {
      showError("先在框里写一个词喵，比如「奶茶」。");
      input.focus();
      return;
    }
    setWord(word, "自定义");
    $("result-view").classList.add("hidden");
  }

  async function submitGuess() {
    if (state.busy || state.strokes.length === 0) return;
    hideError();
    state.busy = true;
    refreshToolbar();
    try {
      const image = downscaledDataUrl();
      const response = await fetch("/draw/api/guess", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image, word: state.word }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        showError(data.error || "奶龙酱走神了，再让它猜一次喵。");
        return;
      }
      showResult(data);
    } catch {
      showError("网络不太顺畅，再试一次喵。");
    } finally {
      state.busy = false;
      refreshToolbar();
    }
  }

  function downscaledDataUrl() {
    const scale = Math.min(1, SEND_WIDTH / CANVAS_W);
    const out = document.createElement("canvas");
    out.width = Math.round(CANVAS_W * scale);
    out.height = Math.round(CANVAS_H * scale);
    const context = out.getContext("2d");
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, out.width, out.height);
    context.drawImage(canvas, 0, 0, out.width, out.height);
    return out.toDataURL("image/png");
  }

  function showResult(data) {
    const chip = $("verdict-chip");
    chip.classList.remove("wrong");
    if (data.hit === true) {
      chip.textContent = "猜中啦！🎉";
      playClip();
    } else if (data.hit === false) {
      chip.textContent = "没猜中喵…";
      chip.classList.add("wrong");
    } else {
      chip.textContent = "奶龙酱的答案";
    }
    $("guess-text").textContent = data.guess;
    const alternatives = $("alternatives-row");
    alternatives.textContent = "";
    if (state.word) {
      const span = document.createElement("span");
      span.textContent = `题目：${state.word}`;
      alternatives.appendChild(span);
    }
    for (const item of data.alternatives || []) {
      const span = document.createElement("span");
      span.textContent = `也可能是：${item}`;
      alternatives.appendChild(span);
    }
    $("comment-text").textContent = data.comment || "这幅画充满了抽象派的魅力喵。";
    const mascot = $("mascot-image");
    mascot.src = data.hit === true ? "/draw/mascot/happy.png"
      : data.hit === false ? "/draw/mascot/sad.png" : "/draw/mascot/wave.png";
    $("mascot-speech").textContent = data.comment || "嗯……让奶龙酱再想想喵。";
    $("result-view").classList.remove("hidden");
    $("result-view").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function resetCanvas() {
    clearCanvas();
    $("result-view").classList.add("hidden");
    $("mascot-image").src = "/draw/mascot/wave.png";
    hideError();
  }

  function buildToolbar() {
    const colorRow = $("color-row");
    for (const color of PALETTE) {
      const swatch = document.createElement("button");
      swatch.type = "button";
      swatch.className = "swatch";
      swatch.dataset.color = color;
      swatch.style.background = color;
      swatch.setAttribute("aria-label", `颜色 ${color}`);
      swatch.addEventListener("click", () => {
        state.color = color;
        state.eraser = false;
        refreshToolbar();
      });
      colorRow.appendChild(swatch);
    }
    const sizeRow = $("size-row");
    for (const size of SIZES) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "tool-button size-button";
      button.dataset.size = String(size.value);
      button.setAttribute("aria-label", `粗细 ${size.label}`);
      const dot = document.createElement("span");
      dot.className = "size-dot";
      dot.style.width = `${Math.min(size.label, 18)}px`;
      dot.style.height = `${Math.min(size.label, 18)}px`;
      button.appendChild(dot);
      button.addEventListener("click", () => {
        state.size = size.value;
        state.eraser = false;
        refreshToolbar();
      });
      sizeRow.appendChild(button);
    }
  }

  buildToolbar();
  redraw();
  refreshToolbar();

  canvas.addEventListener("pointerdown", startStroke);
  canvas.addEventListener("pointermove", moveStroke);
  canvas.addEventListener("pointerup", endStroke);
  canvas.addEventListener("pointercancel", endStroke);
  $("eraser-button").addEventListener("click", () => {
    state.eraser = !state.eraser;
    refreshToolbar();
  });
  $("undo-button").addEventListener("click", undo);
  $("clear-button").addEventListener("click", clearCanvas);
  $("word-button").addEventListener("click", getWord);
  $("custom-word-button").addEventListener("click", setCustomWord);
  $("custom-word-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      setCustomWord();
    }
  });
  $("guess-button").addEventListener("click", submitGuess);
  $("reset-button").addEventListener("click", resetCanvas);
})();
