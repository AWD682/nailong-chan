/* 别猜奶块:奶龙版别踩白块。每行 3 块纯白块 + 1 块奶龙块(两张奶龙图轮换),
   只能点奶龙块;点白块或漏掉奶龙块就结束,播放氦气大笑。判定全部在本地。 */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const board = $("board");
  const tilesLayer = $("tiles");
  const COLUMNS = 4;
  const VISIBLE_ROWS = 4;
  // 两张奶龙图按行轮换:大笑奶龙和抱臂奶龙轮流当「黑块」。
  const TARGET_IMAGES = [
    "/tiles/img/nailong-laugh.png",
    "/tiles/img/nailong-arms.jpg",
  ];
  const CLIP_TAP = "jump";     // 安迪:点中奶龙块
  const CLIP_OVER = "helium";  // 氦气大笑:点白块或漏块,游戏结束
  const START_ROWS_PER_SEC = 0.5;
  const MAX_ROWS_PER_SEC = 1.6;
  const SPEEDUP_PER_TAP = 0.03;
  const BEST_KEY = "nailong-tiles-best";

  const state = {
    running: false,
    rows: [],
    nextImageIndex: 0,
    score: 0,
    best: Number(localStorage.getItem(BEST_KEY) || 0),
    speed: START_ROWS_PER_SEC,
    rowHeight: 0,
    lastFrame: 0,
    rafId: 0,
    overTimer: 0,
  };

  function playClip(name) {
    new Audio(`/audio/${name}.m4a`).play().catch(() => {});
  }

  function refreshHud() {
    $("score-chip").textContent = `${state.score} 分`;
    $("best-chip").textContent = `最佳 ${state.best}`;
  }

  function makeRow(y) {
    const row = document.createElement("div");
    row.className = "row";
    // 行高必须显式设置:块里只有绝对定位的图,没有内容撑高度。
    row.style.height = `${state.rowHeight}px`;
    row.style.transform = `translateY(${y}px)`;
    const targetCol = Math.floor(Math.random() * COLUMNS);
    const info = { el: row, col: targetCol, done: false, y, target: null };
    for (let col = 0; col < COLUMNS; col += 1) {
      const tile = document.createElement("div");
      tile.className = "tile";
      const isTarget = col === targetCol;
      if (isTarget) {
        tile.classList.add("target");
        const image = document.createElement("img");
        image.src = TARGET_IMAGES[state.nextImageIndex % TARGET_IMAGES.length];
        image.alt = "奶龙块";
        state.nextImageIndex += 1;
        tile.appendChild(image);
        info.target = tile;
      } else {
        tile.classList.add("white");
      }
      tile.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        handleTap(info, tile, isTarget);
      });
      row.appendChild(tile);
    }
    tilesLayer.appendChild(row);
    return info;
  }

  function handleTap(row, tile, isTarget) {
    if (!state.running || row.done) return;
    if (isTarget) {
      row.done = true;
      tile.classList.add("tapped");
      playClip(CLIP_TAP);
      state.score += 1;
      state.speed = Math.min(MAX_ROWS_PER_SEC,
        state.speed + SPEEDUP_PER_TAP);
      refreshHud();
    } else {
      gameOver("wrong", tile, null);
    }
  }

  function layoutMetrics() {
    state.rowHeight = board.clientHeight / VISIBLE_ROWS;
  }

  function spawnIfNeeded() {
    const topmost = state.rows[0];
    if (topmost === undefined || topmost.y >= 0) {
      state.rows.unshift(makeRow((topmost ? topmost.y : 0) - state.rowHeight));
    }
  }

  function updateFrame(timestamp) {
    if (!state.running) return;
    const delta = Math.min((timestamp - state.lastFrame) / 1000, 0.05);
    state.lastFrame = timestamp;
    const shift = state.speed * state.rowHeight * delta;
    for (const row of state.rows) {
      row.y += shift;
      row.el.style.transform = `translateY(${row.y}px)`;
    }
    // 底部整行滑出还没点奶龙块 = 漏块,直接结束。
    while (state.rows.length
           && state.rows[state.rows.length - 1].y >= board.clientHeight) {
      const missed = state.rows.pop();
      if (!missed.done) {
        gameOver("missed", null, missed.target);
        return;
      }
      missed.el.remove();
    }
    spawnIfNeeded();
    state.rafId = requestAnimationFrame(updateFrame);
  }

  function startGame() {
    clearTimeout(state.overTimer);
    tilesLayer.replaceChildren();
    layoutMetrics();
    state.running = true;
    state.rows = [];
    state.nextImageIndex = 0;
    state.score = 0;
    state.speed = START_ROWS_PER_SEC;
    // 铺满棋盘并在顶部多留一行正在进入的：-1 .. VISIBLE_ROWS-1。
    for (let index = VISIBLE_ROWS - 1; index >= -1; index -= 1) {
      state.rows.unshift(makeRow(index * state.rowHeight));
    }
    refreshHud();
    $("start-view").classList.add("hidden");
    $("over-view").classList.add("hidden");
    state.lastFrame = performance.now();
    state.rafId = requestAnimationFrame(updateFrame);
  }

  function gameOver(reason, bustedTile, missedTarget) {
    state.running = false;
    cancelAnimationFrame(state.rafId);
    playClip(CLIP_OVER);
    if (bustedTile) {
      bustedTile.classList.add("busted");
    }
    if (missedTarget) {
      missedTarget.classList.add("busted");
    }
    const isRecord = state.score > state.best;
    if (isRecord) {
      state.best = state.score;
      localStorage.setItem(BEST_KEY, String(state.best));
    }
    const reasonText = reason === "wrong"
      ? "点到白块啦，大笑奶龙笑得停不下来喵！"
      : "漏掉了一块奶龙块，被大笑奶龙嘲笑了喵！";
    $("over-title").textContent = isRecord ? "新纪录喵！🎉" : "游戏结束喵！";
    $("over-detail").textContent = `${reasonText}这局点了 ${state.score} 块奶龙块。`;
    $("over-best").textContent = `最佳纪录 ${state.best} 块`;
    refreshHud();
    // 稍等一下让玩家看清是哪块出的问题,再弹结算。
    state.overTimer = setTimeout(() => {
      $("over-view").classList.remove("hidden");
    }, 700);
  }

  $("start-button").addEventListener("click", startGame);
  $("retry-button").addEventListener("click", startGame);

  // 结算画面打开时才跟着窗口变化重新量尺寸;进行中不重排,避免打断手速。
  window.addEventListener("resize", () => {
    if (!state.running) layoutMetrics();
  });

  TARGET_IMAGES.forEach((src) => { new Image().src = src; });
  refreshHud();
})();
