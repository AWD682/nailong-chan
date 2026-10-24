(() => {
  "use strict";

  const story = window.LOVE_STORY;
  if (!story) return;

  const $ = (id) => document.getElementById(id);
  const SAVE_KEY = "nailong_love_save_v2";
  const TOTAL_CHOICES = story.meta.totalChoices ||
    Object.values(story.scenes).filter((scene) => scene.step).length;
  const FACT_KEYS = Object.keys(story.facts || {});
  const MOODS = ["normal", "smile", "shy", "sad", "surprised"];
  const BACKGROUNDS = [
    "campus", "classroom", "dorm", "restaurant", "walk", "cinema",
    "street", "library", "rain", "track", "ferris", "aquarium",
    "dorm-day-girl", "dorm-night-boy", "dorm-night-girl",
    "dorm-storm-girl", "dorm-radio-night",
  ];
  const NIGHT_BACKGROUNDS = new Set([
    "ferris", "dorm-night-boy", "dorm-night-girl",
    "dorm-storm-girl", "dorm-radio-night",
  ]);
  const SCENE_CAST_BACKGROUNDS = new Set([
    "dorm-day-girl", "dorm-night-boy", "dorm-night-girl",
    "dorm-storm-girl", "dorm-radio-night",
  ]);
  const TYPE_SPEED = 26;

  const BOY_SVG = `
<svg viewBox="0 0 300 520" role="img" aria-label="男生">
  <defs>
    <filter id="boyRough" x="-10%" y="-10%" width="120%" height="120%">
      <feTurbulence type="fractalNoise" baseFrequency="0.028" numOctaves="2" seed="17" result="noise"/>
      <feDisplacementMap in="SourceGraphic" in2="noise" scale="3.8" xChannelSelector="R" yChannelSelector="G"/>
    </filter>
  </defs>
  <g filter="url(#boyRough)" stroke="#4a3d35" stroke-width="3.8" stroke-linecap="round" stroke-linejoin="round">
    <ellipse cx="150" cy="502" rx="62" ry="6" fill="#dfd8cc" stroke="none"/>

    <path d="M118 300 L148 300 L146 466 L124 466 Z" fill="#7d9cc0"/>
    <path d="M152 300 L182 300 L176 466 L154 466 Z" fill="#7d9cc0"/>
    <path d="M120 448 L146 448 M154 448 L178 448" fill="none" stroke="#6a86a8" stroke-width="2.2" opacity=".65"/>

    <path d="M127 464 L148 464 L150 482 C142 490 126 490 120 483 C116 477 121 469 127 464 Z" fill="#8695a9"/>
    <path d="M152 464 L173 464 L180 483 C174 490 158 490 150 482 Z" fill="#8695a9"/>
    <path d="M121 479 C130 486 142 486 149 480 L150 482 C142 490 126 490 120 483 Z" fill="#f7f3ea"/>
    <path d="M151 480 C158 486 170 486 179 480 L180 483 C174 490 158 490 150 482 Z" fill="#f7f3ea"/>
    <path d="M120 484 C129 490 141 490 149 484 M151 484 C160 490 172 490 180 484" fill="none" stroke="#c9c0b1" stroke-width="2"/>
    <path d="M132 469 l10 4 M160 469 l10 4" stroke="#c9c0b1" stroke-width="1.8"/>

    <path d="M140 192 L160 192 L161 214 C155 218 145 218 139 214 Z" fill="#f7ddc4"/>

    <path d="M108 212 C112 204 124 198 136 196 L164 196 C176 198 188 204 192 212 L194 300 C194 308 189 312 183 312 L117 312 C111 312 106 308 106 300 Z" fill="#cfe3ef"/>
    <path d="M110 304 C140 310 160 310 190 304" fill="none" stroke="#a9c4d6" stroke-width="2.2" opacity=".8"/>
    <path d="M126 236 C140 242 160 242 174 236" fill="none" stroke="#b7d4e6" stroke-width="2" opacity=".55"/>

    <path d="M132 194 C134 208 166 208 168 194 C176 198 184 202 189 208 C178 218 164 222 150 222 C136 222 122 218 111 208 C116 202 124 198 132 194 Z" fill="#fdf8ee"/>
    <path d="M168 208 C179 214 186 226 184 240 C183 248 173 248 172 240 C173 228 167 218 160 214 Z" fill="#fdf8ee"/>
    <path d="M125 204 C136 212 164 212 175 204 M170 214 C176 222 180 232 180 240" fill="none" stroke="#d8d0c0" stroke-width="2"/>

    <path d="M108 214 C98 224 94 238 96 252 C106 258 116 252 118 242 L122 218 Z" fill="#cfe3ef"/>
    <path d="M192 214 C202 224 206 238 204 252 C194 258 184 252 182 242 L178 218 Z" fill="#cfe3ef"/>
    <path d="M98 250 C103 254 111 254 116 250 M202 250 C197 254 189 254 184 250" fill="none" stroke="#a9c4d6" stroke-width="2"/>
    <path d="M100 248 C96 270 95 294 96 312 C96 320 105 322 108 315 C110 294 110 268 112 250 Z" fill="#f7ddc4"/>
    <path d="M200 248 C204 270 205 294 204 312 C204 320 195 322 192 315 C190 294 190 268 188 250 Z" fill="#f7ddc4"/>

    <ellipse cx="100" cy="138" rx="7" ry="10" fill="#f7ddc4"/>
    <ellipse cx="200" cy="138" rx="7" ry="10" fill="#f7ddc4"/>

    <path d="M150 78 C116 78 100 102 100 136 C100 168 118 198 150 198 C182 198 200 168 200 136 C200 102 184 78 150 78 Z" fill="#f7ddc4"/>

    <path d="M96 140 C86 106 104 64 150 62 C196 64 214 106 204 140 C198 138 192 136 186 132 C180 138 174 140 168 138 C160 132 154 130 148 134 C142 140 132 140 124 136 C116 131 106 134 96 140 Z" fill="#5b4636"/>
    <path d="M96 136 C92 152 93 166 99 176 C101 160 102 146 106 136 Z" fill="#5b4636"/>
    <path d="M204 136 C208 152 207 166 201 176 C199 160 198 146 194 136 Z" fill="#5b4636"/>
    <path d="M164 62 C158 46 170 40 180 46 C170 50 168 55 171 64 Z" fill="#5b4636"/>
    <path d="M104 118 C120 96 142 90 166 92 M112 104 C128 88 148 84 168 88" fill="none" stroke="#453225" stroke-width="2.2" opacity=".45"/>

    <g class="face face-normal">
      <ellipse cx="132" cy="150" rx="4.2" ry="5" fill="#3b332c" stroke="none"/>
      <ellipse cx="168" cy="150" rx="4.2" ry="5" fill="#3b332c" stroke="none"/>
      <path d="M146 166 q4 3 8 0" fill="none" stroke="#b06f63" stroke-width="2.2"/>
    </g>
    <g class="face face-smile">
      <path d="M125 150 q7 -7 14 0" fill="none" stroke="#3b332c" stroke-width="3"/>
      <path d="M161 150 q7 -7 14 0" fill="none" stroke="#3b332c" stroke-width="3"/>
      <path d="M144 164 q6 8 12 0 Z" fill="#d98b82"/>
    </g>
    <g class="face face-shy">
      <ellipse cx="130.5" cy="152" rx="4" ry="4.8" fill="#3b332c" stroke="none"/>
      <ellipse cx="166.5" cy="152" rx="4" ry="4.8" fill="#3b332c" stroke="none"/>
      <path d="M144 167 q3 -3 6 0 q3 3 6 0" fill="none" stroke="#b06f63" stroke-width="2.2"/>
    </g>
    <g class="face face-sad">
      <ellipse cx="132" cy="152" rx="4.2" ry="5" fill="#3b332c" stroke="none"/>
      <ellipse cx="168" cy="152" rx="4.2" ry="5" fill="#3b332c" stroke="none"/>
      <path d="M125 138 q7 3 13 1 M162 139 q6 2 13 -1" fill="none" stroke="#5b4636" stroke-width="2.4"/>
      <path d="M146 169 q4 -3 8 0" fill="none" stroke="#b06f63" stroke-width="2.2"/>
    </g>
    <g class="face face-surprised">
      <ellipse cx="132" cy="150" rx="5.6" ry="6.4" fill="#3b332c" stroke="none"/>
      <ellipse cx="168" cy="150" rx="5.6" ry="6.4" fill="#3b332c" stroke="none"/>
      <path d="M124 134 q8 -4 14 0 M162 134 q6 -4 14 0" fill="none" stroke="#5b4636" stroke-width="2.4"/>
      <ellipse cx="150" cy="167" rx="3.4" ry="4.4" fill="#d98b82"/>
    </g>

    <ellipse cx="120" cy="162" rx="10" ry="5" fill="#f2a7a0" opacity=".5" stroke="none"/>
    <ellipse cx="180" cy="162" rx="10" ry="5" fill="#f2a7a0" opacity=".5" stroke="none"/>
  </g>
</svg>
`;

  const GIRL_SVG = `
<svg viewBox="0 0 300 520" role="img" aria-label="奶龙酱">
  <defs>
    <filter id="girlRough" x="-10%" y="-10%" width="120%" height="120%">
      <feTurbulence type="fractalNoise" baseFrequency="0.028" numOctaves="2" seed="31" result="noise"/>
      <feDisplacementMap in="SourceGraphic" in2="noise" scale="3.8" xChannelSelector="R" yChannelSelector="G"/>
    </filter>
  </defs>
  <g filter="url(#girlRough)" stroke="#4a3d35" stroke-width="3.8" stroke-linecap="round" stroke-linejoin="round">
    <ellipse cx="150" cy="502" rx="60" ry="6" fill="#dfd8cc" stroke="none"/>

    <path d="M150 64 C118 62 98 88 98 124 C97 154 88 186 88 224 C85 262 86 300 94 326 C96 334 107 334 110 326 C112 292 115 258 122 228 L178 228 C185 258 188 292 190 326 C193 334 204 334 206 326 C214 300 215 262 212 224 C212 186 203 154 202 124 C202 88 182 62 150 64 Z" fill="#e8c07d"/>
    <path d="M99 200 C94 240 92 290 96 326 M201 200 C206 240 208 290 204 326" fill="none" stroke="#cf9f57" stroke-width="2.4" opacity=".5"/>
    <path d="M114 262 C112 292 112 314 113 328 M186 262 C188 292 188 314 187 328" fill="none" stroke="#cf9f57" stroke-width="2" opacity=".4"/>
    <path d="M102 132 C96 172 96 214 102 246 C104 258 116 258 117 246 C112 210 112 172 117 136 Z" fill="#e8c07d"/>
    <path d="M198 132 C204 172 204 214 198 246 C196 258 184 258 183 246 C188 210 188 172 183 136 Z" fill="#e8c07d"/>
    <path d="M103 148 C105 176 105 208 107 234 M197 148 C195 176 195 208 193 234" fill="none" stroke="#cf9f57" stroke-width="1.8" opacity=".4"/>

    <path d="M128 392 L148 392 L146 456 L126 456 Z" fill="#f7ddc4"/>
    <path d="M152 392 L172 392 L174 456 L154 456 Z" fill="#f7ddc4"/>

    <path d="M126 448 L147 448 L146 460 L126 460 Z" fill="#fbf4ea"/>
    <path d="M153 448 L174 448 L174 460 L154 460 Z" fill="#fbf4ea"/>

    <path d="M127 458 L148 458 L150 480 C142 488 126 488 120 481 C116 475 121 467 127 462 Z" fill="#a9785a"/>
    <path d="M152 458 L173 458 L180 481 C174 488 158 488 150 480 Z" fill="#a9785a"/>
    <path d="M120 482 C129 488 141 488 149 482 M151 482 C160 488 172 488 180 482" fill="none" stroke="#8b6149" stroke-width="2"/>
    <path d="M130 467 C138 472 146 471 150 466 M150 466 C158 472 168 471 174 467" fill="none" stroke="#8b6149" stroke-width="1.8" opacity=".8"/>

    <path d="M140 192 L160 192 L161 214 C155 218 145 218 139 214 Z" fill="#f7ddc4"/>

    <path d="M108 212 C112 202 124 196 136 194 L164 194 C176 196 188 202 192 212 L186 300 L114 300 Z" fill="#f4d5da"/>
    <path d="M134 192 C138 206 162 206 166 192 C158 186 142 186 134 192 Z" fill="#fdf8ee"/>
    <path d="M138 196 C142 208 158 208 162 196" fill="none" stroke="#d9bfc4" stroke-width="2.4"/>
    <path d="M120 250 C136 256 164 256 180 250" fill="none" stroke="#d9bfc4" stroke-width="2.2" opacity=".6"/>
    <path d="M114 296 C140 302 160 302 186 296" fill="none" stroke="#d9bfc4" stroke-width="2.2" opacity=".7"/>

    <path d="M114 300 L186 300 L204 392 C180 402 120 402 96 392 Z" fill="#f4d5da"/>
    <path d="M124 304 L132 392 M150 304 L150 396 M176 304 L168 392" fill="none" stroke="#d9bfc4" stroke-width="2.2" opacity=".5"/>
    <path d="M100 392 C124 400 176 400 200 392" fill="none" stroke="#d9bfc4" stroke-width="2.2"/>

    <path d="M108 214 C100 224 96 238 98 252 C108 258 118 252 120 242 L122 218 Z" fill="#f4d5da"/>
    <path d="M192 214 C200 224 204 238 202 252 C192 258 182 252 180 242 L178 218 Z" fill="#f4d5da"/>
    <path d="M100 250 C105 254 113 254 118 250 M200 250 C195 254 187 254 182 250" fill="none" stroke="#d9bfc4" stroke-width="2"/>
    <path d="M102 248 C98 270 97 294 98 312 C98 320 107 322 110 315 C112 294 112 268 114 250 Z" fill="#f7ddc4"/>
    <path d="M198 248 C202 270 203 294 202 312 C202 320 193 322 190 315 C188 294 188 268 186 250 Z" fill="#f7ddc4"/>


    <ellipse cx="100" cy="138" rx="7" ry="10" fill="#f7ddc4"/>
    <ellipse cx="200" cy="138" rx="7" ry="10" fill="#f7ddc4"/>
    <circle cx="100" cy="146" r="2.4" fill="#e88f88" stroke="none"/>
    <circle cx="200" cy="146" r="2.4" fill="#e88f88" stroke="none"/>

    <path d="M150 78 C116 78 100 102 100 136 C100 168 118 198 150 198 C182 198 200 168 200 136 C200 102 184 78 150 78 Z" fill="#f7ddc4"/>

    <path d="M100 136 C94 102 112 70 150 68 C188 70 206 102 200 136 C196 135 192 135 187 133 C181 123 172 113 164 109 C159 106 154 104 150 104 C146 104 141 106 136 109 C128 113 119 123 113 133 C108 135 104 135 100 136 Z" fill="#e8c07d"/>
    <path d="M108 118 C124 98 146 92 168 94 M116 104 C132 90 150 86 168 90" fill="none" stroke="#cf9f57" stroke-width="2.2" opacity=".5"/>
    <path d="M150 68 C148 82 148 94 150 104" fill="none" stroke="#cf9f57" stroke-width="2" opacity=".45"/>

    <g transform="rotate(14 107 88)">
      <path d="M107 88 C119 74 133 81 126 92 C133 103 119 110 107 96 Z" fill="#e8a06f"/>
      <path d="M107 88 C95 74 81 81 88 92 C81 103 95 110 107 96 Z" fill="#e8a06f"/>
      <circle cx="107" cy="92" r="4" fill="#f4c39a"/>
    </g>

    <g class="face face-normal">
      <ellipse cx="132" cy="150" rx="4.2" ry="5" fill="#3b332c" stroke="none"/>
      <ellipse cx="168" cy="150" rx="4.2" ry="5" fill="#3b332c" stroke="none"/>
      <path d="M146 166 q4 3 8 0" fill="none" stroke="#b06f63" stroke-width="2.2"/>
    </g>
    <g class="face face-smile">
      <path d="M125 150 q7 -7 14 0" fill="none" stroke="#3b332c" stroke-width="3"/>
      <path d="M161 150 q7 -7 14 0" fill="none" stroke="#3b332c" stroke-width="3"/>
      <path d="M144 164 q6 8 12 0 Z" fill="#d98b82"/>
    </g>
    <g class="face face-shy">
      <ellipse cx="130.5" cy="152" rx="4" ry="4.8" fill="#3b332c" stroke="none"/>
      <ellipse cx="166.5" cy="152" rx="4" ry="4.8" fill="#3b332c" stroke="none"/>
      <path d="M144 167 q3 -3 6 0 q3 3 6 0" fill="none" stroke="#b06f63" stroke-width="2.2"/>
    </g>
    <g class="face face-sad">
      <ellipse cx="132" cy="152" rx="4.2" ry="5" fill="#3b332c" stroke="none"/>
      <ellipse cx="168" cy="152" rx="4.2" ry="5" fill="#3b332c" stroke="none"/>
      <path d="M125 138 q7 3 13 1 M162 139 q6 2 13 -1" fill="none" stroke="#8a6045" stroke-width="2.4"/>
      <path d="M146 169 q4 -3 8 0" fill="none" stroke="#b06f63" stroke-width="2.2"/>
    </g>
    <g class="face face-surprised">
      <ellipse cx="132" cy="150" rx="5.6" ry="6.4" fill="#3b332c" stroke="none"/>
      <ellipse cx="168" cy="150" rx="5.6" ry="6.4" fill="#3b332c" stroke="none"/>
      <path d="M124 134 q8 -4 14 0 M162 134 q6 -4 14 0" fill="none" stroke="#8a6045" stroke-width="2.4"/>
      <ellipse cx="150" cy="167" rx="3.4" ry="4.4" fill="#d98b82"/>
    </g>

    <ellipse cx="120" cy="162" rx="10" ry="5" fill="#f2a7a0" opacity=".55" stroke="none"/>
    <ellipse cx="180" cy="162" rx="10" ry="5" fill="#f2a7a0" opacity=".55" stroke="none"/>
  </g>
</svg>
`;

  const state = {
    sceneId: story.start,
    score: story.meta.startScore,
    flags: {},
    tagStats: {},
    memories: {},
    factResults: {},
    finalTone: null,
    location: null,
    history: [],
    chapterId: null,
    mode: "dialogue",
    queue: [],
    queueIndex: 0,
    queueKind: "scene",
    pendingNext: null,
    typing: false,
    typeTimer: 0,
    fullText: "",
    optionsShown: false,
    activeOptions: [],
    customOpen: false,
    customEditor: null,
    locked: false,
    paused: false,
    finished: false,
    endingId: null,
    chatTimer: 0,
    currentLine: null,
    chapterTimer: 0,
    chapterSkip: null,
    toastTimer: 0,
  };

  const clampScore = (value) =>
    Math.max(story.meta.minScore, Math.min(story.meta.maxScore, value));

  function show(element) {
    element.classList.remove("hidden");
  }

  function hide(element) {
    element.classList.add("hidden");
  }

  function clearTimers() {
    window.clearTimeout(state.typeTimer);
    window.clearTimeout(state.chatTimer);
    window.clearTimeout(state.chapterTimer);
    window.clearTimeout(state.toastTimer);
    state.typeTimer = 0;
    state.chatTimer = 0;
    state.chapterTimer = 0;
    state.toastTimer = 0;
    state.chapterSkip = null;
    state.typing = false;
  }

  function setPhase(phase) {
    document.body.dataset.phase = phase;
    document.body.dataset.mode = state.mode;
    $("title-screen").classList.toggle("hidden", phase !== "title");
    $("ending-screen").classList.toggle("hidden", phase !== "ending");
    $("egg-screen").classList.toggle("hidden", phase !== "egg");
    $("hud").classList.toggle("hidden", phase !== "playing");
    const playing = phase === "playing";
    $("dialogue-layer").classList.toggle(
      "hidden", !(playing && state.mode !== "chat"));
    $("chat-panel").classList.toggle(
      "hidden", !(playing && state.mode === "chat"));
    if (!playing) hide($("memory-panel"));
  }

  function setMode(mode) {
    state.mode = mode === "chat" ? "chat" : "dialogue";
    document.body.dataset.mode = state.mode;
    const playing = document.body.dataset.phase === "playing";
    $("dialogue-layer").classList.toggle(
      "hidden", !(playing && state.mode !== "chat"));
    $("chat-panel").classList.toggle(
      "hidden", !(playing && state.mode === "chat"));
  }

  function setExpression(mood) {
    const next = MOODS.includes(mood) ? mood : "normal";
    const girl = $("girl");
    if (girl.dataset.expression !== next) {
      girl.dataset.expression = next;
      girl.classList.remove("pop");
      void girl.offsetWidth;
      girl.classList.add("pop");
    }
  }

  function setBackground(name) {
    const scene = $("scene");
    const next = BACKGROUNDS.includes(name) ? name : "campus";
    for (const className of [...scene.classList]) {
      if (className.startsWith("bg-")) scene.classList.remove(className);
    }
    scene.classList.add(`bg-${next}`);
    scene.dataset.bg = next;
    document.body.dataset.dark = NIGHT_BACKGROUNDS.has(next) ? "true" : "false";
    document.body.dataset.cast = SCENE_CAST_BACKGROUNDS.has(next)
      ? "scene" : "standing";
    $("rain-layer").classList.toggle(
      "active", next === "rain" || next === "dorm-storm-girl");
  }

  function injectCharacters() {
    $("boy").innerHTML = BOY_SVG;
    $("girl").innerHTML = GIRL_SVG;
  }

  function renderParticles() {
    const wrap = $("particles");
    wrap.replaceChildren();
    const tints = [
      "rgba(255, 255, 255, .72)",
      "rgba(255, 214, 166, .68)",
      "rgba(255, 170, 185, .5)",
      "rgba(174, 220, 180, .55)",
    ];
    for (let i = 0; i < 18; i += 1) {
      const particle = document.createElement("span");
      particle.className = "particle";
      particle.style.setProperty("--x", `${Math.random() * 100}%`);
      particle.style.setProperty("--size", `${3 + Math.random() * 5}px`);
      particle.style.setProperty("--delay", `${Math.random() * 10}s`);
      particle.style.setProperty("--duration", `${10 + Math.random() * 11}s`);
      particle.style.setProperty("--drift", `${-34 + Math.random() * 68}px`);
      particle.style.setProperty("--tint", tints[i % tints.length]);
      wrap.append(particle);
    }
  }

  function factLabel(key) {
    return story.facts[key] ? story.facts[key].label : key;
  }

  function updateMemoryCount() {
    const learned = FACT_KEYS.filter((key) => state.memories[key]).length;
    $("memory-count").textContent = `${learned} / ${FACT_KEYS.length}`;
  }

  function learnFacts(keys) {
    if (!Array.isArray(keys) || !keys.length) return;
    const newly = [];
    for (const key of keys) {
      if (!story.facts[key] || state.memories[key]) continue;
      state.memories[key] = true;
      newly.push(key);
    }
    if (!newly.length) return;
    updateMemoryCount();
    if (!$("memory-panel").classList.contains("hidden")) renderMemoryPanel();
    $("memory-toast").textContent =
      `已记住 · ${newly.map((key) => factLabel(key)).join(" · ")}`;
    $("memory-toast").classList.add("show");
    window.clearTimeout(state.toastTimer);
    state.toastTimer = window.setTimeout(() => {
      $("memory-toast").classList.remove("show");
    }, 2500);
    saveProgress();
  }

  function renderMemoryPanel() {
    const list = $("memory-list");
    list.replaceChildren();
    for (const key of FACT_KEYS) {
      const fact = story.facts[key];
      const learned = Boolean(state.memories[key]);
      const item = document.createElement("li");
      item.className = `memory-item ${learned ? "known" : "unknown"}`;
      const mark = document.createElement("span");
      mark.className = "memory-mark";
      mark.textContent = learned ? "✦" : "？";
      const body = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = learned ? fact.label : "？？？";
      const hint = document.createElement("p");
      hint.textContent = learned ? fact.hint : "还没听到这个细节。";
      body.append(title, hint);
      item.append(mark, body);
      list.append(item);
    }
  }

  function openMemory() {
    if (document.body.dataset.phase !== "playing") return;
    renderMemoryPanel();
    show($("memory-panel"));
    state.paused = true;
    window.clearTimeout(state.chatTimer);
    state.chatTimer = 0;
  }

  function closeMemory() {
    hide($("memory-panel"));
    state.paused = false;
    if (state.mode === "chat" && !state.locked && !state.optionsShown &&
        state.queueIndex < state.queue.length) {
      scheduleChatAdvance(state.currentLine);
    }
  }

  function saveProgress() {
    const payload = {
      version: 2,
      sceneId: state.sceneId,
      score: state.score,
      flags: state.flags,
      tagStats: state.tagStats,
      memories: state.memories,
      factResults: state.factResults,
      finalTone: state.finalTone,
      location: state.location,
      history: state.history,
      chapterId: state.chapterId,
      finished: state.finished,
      endingId: state.endingId,
    };
    try {
      localStorage.setItem(SAVE_KEY, JSON.stringify(payload));
    } catch (_) {
      /* 本地存储不可用时仍可继续游玩。 */
    }
  }

  function readSave() {
    try {
      const raw = localStorage.getItem(SAVE_KEY);
      if (!raw) return null;
      const data = JSON.parse(raw);
      if (!data || data.version !== 2) return null;
      if (data.finished) {
        return story.endings.some((ending) => ending.id === data.endingId)
          ? data : null;
      }
      if (!story.scenes[data.sceneId]) return null;
      if (typeof data.score !== "number") return null;
      return data;
    } catch (_) {
      return null;
    }
  }

  function clearSave() {
    try {
      localStorage.removeItem(SAVE_KEY);
    } catch (_) {
      /* ignore */
    }
  }

  function resetState() {
    clearTimers();
    Object.assign(state, {
      sceneId: story.start,
      score: story.meta.startScore,
      flags: {},
      tagStats: {},
      memories: {},
      factResults: {},
      finalTone: null,
      location: null,
      history: [],
      chapterId: null,
      mode: "dialogue",
      queue: [],
      queueIndex: 0,
      queueKind: "scene",
      pendingNext: null,
      typing: false,
      fullText: "",
      optionsShown: false,
      activeOptions: [],
      customOpen: false,
      customEditor: null,
      locked: false,
      paused: false,
      finished: false,
      endingId: null,
      currentLine: null,
    });
    $("memory-toast").classList.remove("show");
    document.body.removeAttribute("data-ending");
  }

  function applySave(data) {
    state.sceneId = data.sceneId;
    state.score = clampScore(Number(data.score) || story.meta.startScore);
    state.flags = data.flags && typeof data.flags === "object" ? data.flags : {};
    state.tagStats =
      data.tagStats && typeof data.tagStats === "object" ? data.tagStats : {};
    state.memories =
      data.memories && typeof data.memories === "object" ? data.memories : {};
    state.factResults =
      data.factResults && typeof data.factResults === "object"
        ? data.factResults : {};
    state.finalTone = data.finalTone || null;
    state.location = data.location || null;
    state.history = Array.isArray(data.history) ? data.history : [];
    state.chapterId = data.chapterId || null;
    state.finished = Boolean(data.finished);
    state.endingId = data.endingId || null;
    state.queue = [];
    state.queueIndex = 0;
    state.queueKind = "scene";
    state.pendingNext = null;
    state.typing = false;
    state.optionsShown = false;
    state.activeOptions = [];
    state.customOpen = false;
    state.customEditor = null;
    state.locked = false;
    state.paused = false;
    state.currentLine = null;
    state.mode = "dialogue";
    updateMemoryCount();
  }

  function updateContinueButton() {
    const save = readSave();
    const button = $("continue-button");
    button.classList.toggle("hidden", !save);
    if (save) {
      button.textContent = save.finished ? "查看上次结局" : "继续上次";
    }
  }

  function updateHud(scene) {
    const chapter = story.chapters[scene.chapter];
    $("chapter-chip").textContent = chapter ? chapter.label : "";
    $("step-chip").textContent = scene.step
      ? `第 ${scene.step} / ${TOTAL_CHOICES} 次选择`
      : "剧情推进";
    updateMemoryCount();
  }

  function startGame(fromSave) {
    clearTimers();
    hide($("memory-panel"));
    hide($("chapter-overlay"));
    $("options").replaceChildren();
    $("chat-options").replaceChildren();
    $("chat-messages").replaceChildren();
    if (fromSave) {
      const data = readSave();
      if (data) {
        applySave(data);
        if (data.finished) {
          setPhase("ending");
          showEnding(story.endings.find((ending) => ending.id === data.endingId));
          return;
        }
        setPhase("playing");
        renderScene(data.sceneId);
        return;
      }
    }
    clearSave();
    resetState();
    setPhase("playing");
    setMode("dialogue");
    updateContinueButton();
    renderScene(story.start);
  }

  function restartGame() {
    clearSave();
    resetState();
    hide($("memory-panel"));
    hide($("chapter-overlay"));
    setPhase("playing");
    setMode("dialogue");
    updateContinueButton();
    renderScene(story.start);
  }

  function withChapterOverlay(scene, callback) {
    const chapter = story.chapters[scene.chapter];
    if (!chapter || state.chapterId === scene.chapter) {
      callback();
      return;
    }
    state.chapterId = scene.chapter;
    saveProgress();
    $("chapter-number").textContent = chapter.number;
    $("chapter-title").textContent = chapter.title;
    $("chapter-subtitle").textContent = chapter.subtitle;
    const overlay = $("chapter-overlay");
    overlay.classList.remove("hidden", "show");
    void overlay.offsetWidth;
    overlay.classList.add("show");
    state.locked = true;
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      window.clearTimeout(state.chapterTimer);
      state.chapterTimer = 0;
      overlay.classList.remove("show");
      window.setTimeout(() => overlay.classList.add("hidden"), 520);
      state.locked = false;
      state.chapterSkip = null;
      callback();
    };
    state.chapterSkip = finish;
    overlay.onclick = (event) => {
      event.stopPropagation();
      finish();
    };
    state.chapterTimer = window.setTimeout(finish, 1750);
  }

  function renderScene(sceneId) {
    const scene = story.scenes[sceneId];
    if (!scene) {
      finishGame();
      return;
    }
    state.sceneId = sceneId;
    state.queue = Array.isArray(scene.lines) ? scene.lines.slice() : [];
    state.queueIndex = 0;
    state.queueKind = "scene";
    state.pendingNext = null;
    state.currentLine = null;
    state.typing = false;
    state.optionsShown = false;
    state.activeOptions = [];
    state.customOpen = false;
    state.customEditor = null;
    state.locked = false;
    state.paused = false;
    state.finished = false;
    state.endingId = null;
    state.location = scene.location || state.location;
    setMode(scene.mode || "dialogue");
    setBackground(scene.background);
    setExpression("normal");
    updateHud(scene);
    $("narration").textContent = scene.narration || "";
    $("options").replaceChildren();
    $("chat-options").replaceChildren();
    $("chat-messages").replaceChildren();
    $("chat-status").textContent = scene.narration || "微信 · 在线";
    $("next-hint").textContent = "点击继续";
    $("next-hint").classList.add("hidden");
    $("dialogue-card").dataset.speaker = "narrator";
    $("speaker").textContent = "旁白";
    $("dialogue-text").textContent = "";
    saveProgress();
    withChapterOverlay(scene, playNextLine);
  }

  function playNextLine() {
    if (state.locked || document.body.dataset.phase !== "playing") return;
    window.clearTimeout(state.chatTimer);
    state.chatTimer = 0;
    if (state.queueIndex >= state.queue.length) {
      onLineFinished();
      return;
    }
    const line = state.queue[state.queueIndex];
    state.queueIndex += 1;
    state.currentLine = line;
    applyLine(line);
  }

  function applyLine(line) {
    if (!line) return;
    if (Array.isArray(line.learn)) learnFacts(line.learn);
    if (line.effect === "flash") triggerFlash();
    if (line.speaker === "奶龙酱" && line.mood) setExpression(line.mood);
    if (state.mode === "chat") {
      appendChatLine(line);
      onLineFinished();
      return;
    }
    const speaker = line.speaker || "旁白";
    $("speaker").textContent = speaker;
    $("dialogue-card").dataset.speaker =
      speaker === "奶龙酱" ? "girl" : speaker === "你" ? "you" : "narrator";
    $("next-hint").classList.remove("hidden");
    $("next-hint").textContent = "点击跳过";
    typeText(line.text || "");
  }

  function typeText(text) {
    window.clearTimeout(state.typeTimer);
    state.fullText = text;
    state.typing = true;
    $("dialogue-text").textContent = "";
    if (!text) {
      finishTyping();
      return;
    }
    let index = 0;
    const step = () => {
      if (!state.typing) return;
      index += 1;
      $("dialogue-text").textContent = text.slice(0, index);
      if (index >= text.length) {
        finishTyping();
        return;
      }
      state.typeTimer = window.setTimeout(step, TYPE_SPEED);
    };
    state.typeTimer = window.setTimeout(step, TYPE_SPEED);
  }

  function finishTyping() {
    if (!state.typing) return;
    window.clearTimeout(state.typeTimer);
    state.typeTimer = 0;
    state.typing = false;
    $("dialogue-text").textContent = state.fullText;
    onLineFinished();
  }

  function setContinueHint() {
    $("next-hint").textContent = "点击继续";
    $("next-hint").classList.remove("hidden");
  }

  function onLineFinished() {
    const scene = story.scenes[state.sceneId];
    const atEnd = state.queueIndex >= state.queue.length;
    if (!atEnd) {
      if (state.mode === "chat") {
        scheduleChatAdvance(state.currentLine);
      } else {
        setContinueHint();
      }
      return;
    }
    if (state.queueKind === "reaction") {
      if (state.mode === "chat") {
        state.chatTimer = window.setTimeout(() => {
          if (!state.paused) showChatContinue();
        }, 700);
      } else {
        setContinueHint();
      }
      return;
    }
    if (scene && scene.options && scene.options.length) {
      if (state.mode === "chat") {
        state.chatTimer = window.setTimeout(() => {
          if (!state.paused) showOptions();
        }, 650);
      } else {
        showOptions();
      }
      return;
    }
    if (state.mode === "chat") {
      state.chatTimer = window.setTimeout(() => {
        if (!state.paused) showChatContinue();
      }, 650);
    } else {
      setContinueHint();
    }
  }

  function scheduleChatAdvance(line) {
    if (state.paused) return;
    window.clearTimeout(state.chatTimer);
    const textLength = line && line.text ? line.text.length : 0;
    const delay = line && line.speaker === "时间"
      ? 520
      : Math.min(2800, 950 + textLength * 26);
    state.chatTimer = window.setTimeout(() => {
      state.chatTimer = 0;
      if (!state.paused && state.mode === "chat" && !state.locked) {
        playNextLine();
      }
    }, delay);
  }

  function advance() {
    if (state.locked || state.paused) return;
    if (document.body.dataset.phase !== "playing") return;
    if (!$("memory-panel").classList.contains("hidden")) return;
    if (state.optionsShown) return;
    if (state.typing) {
      finishTyping();
      return;
    }
    if (state.queueIndex < state.queue.length) {
      window.clearTimeout(state.chatTimer);
      state.chatTimer = 0;
      playNextLine();
      return;
    }
    onQueueFinished();
  }

  function onQueueFinished() {
    if (state.locked) return;
    state.locked = true;
    window.clearTimeout(state.chatTimer);
    state.chatTimer = 0;
    hide($("next-hint"));
    const kind = state.queueKind;
    if (kind === "reaction") {
      const next = state.pendingNext;
      state.pendingNext = null;
      state.queueKind = "scene";
      if (next) renderScene(next);
      else finishGame();
      return;
    }
    const scene = story.scenes[state.sceneId];
    if (scene && scene.options && scene.options.length) {
      state.locked = false;
      showOptions();
      return;
    }
    if (scene && scene.next) {
      renderScene(scene.next);
      return;
    }
    finishGame();
  }

  function showOptions() {
    if (state.optionsShown || state.locked) return;
    const scene = story.scenes[state.sceneId];
    if (!scene || !scene.options || !scene.options.length) return;
    state.optionsShown = true;
    state.activeOptions = scene.options;
    state.locked = false;
    window.clearTimeout(state.chatTimer);
    state.chatTimer = 0;
    hide($("next-hint"));
    if (state.mode === "chat") renderChatOptions(scene.options);
    else renderDialogueOptions(scene.options);
  }

  function renderDialogueOptions(options) {
    const scene = story.scenes[state.sceneId];
    const container = $("options");
    container.replaceChildren();
    options.forEach((option, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "option-button";
      button.style.animationDelay = `${index * 80}ms`;
      const badge = document.createElement("span");
      badge.className = "option-index";
      badge.textContent = String(index + 1);
      const text = document.createElement("span");
      text.className = "option-text";
      text.textContent = option.text;
      button.append(badge, text);
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        chooseOption(index);
      });
      container.append(button);
    });
    if (scene && scene.custom) {
      const customButton = document.createElement("button");
      customButton.type = "button";
      customButton.className = "option-button custom-option-button";
      customButton.style.animationDelay = `${options.length * 80}ms`;
      const badge = document.createElement("span");
      badge.className = "option-index";
      badge.textContent = "写";
      const text = document.createElement("span");
      text.className = "option-text";
      text.textContent = "自己说一句……";
      customButton.append(badge, text);
      customButton.addEventListener("click", (event) => {
        event.stopPropagation();
        openCustomEditor("dialogue", customButton);
      });
      container.append(customButton);
    }
  }

  function renderChatOptions(options) {
    const scene = story.scenes[state.sceneId];
    const container = $("chat-options");
    container.replaceChildren();
    const label = document.createElement("p");
    label.className = "chat-choice-label";
    label.textContent = "选择你的回复";
    container.append(label);
    options.forEach((option, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "chat-option";
      button.style.animationDelay = `${index * 70}ms`;
      button.textContent = option.text;
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        chooseOption(index);
      });
      container.append(button);
    });
    if (scene && scene.custom) {
      const customButton = document.createElement("button");
      customButton.type = "button";
      customButton.className = "chat-option custom-chat-option";
      customButton.style.animationDelay = `${options.length * 70}ms`;
      customButton.textContent = "自己写一句回复……";
      customButton.addEventListener("click", (event) => {
        event.stopPropagation();
        openCustomEditor("chat", customButton);
      });
      container.append(customButton);
    }
    scrollChat();
  }

  function normalizeCustomText(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/[\s，。！？、；：,.!?;:'"“”‘’（）()《》<>…—\-_/\\[\]{}·~`|]+/g, "");
  }

  function matchCustomOption(scene, text) {
    const custom = scene && scene.custom;
    const normalized = normalizeCustomText(text);
    if (!custom || !Array.isArray(custom.rules) || !normalized) return 0;
    let bestIndex = -1;
    let bestScore = 0;
    custom.rules.forEach((rule) => {
      const index = Number(rule.option);
      if (!Number.isInteger(index) || index < 0 || index >= scene.options.length) {
        return;
      }
      let score = 0;
      (rule.keys || []).forEach((key) => {
        const normalizedKey = normalizeCustomText(key);
        if (normalizedKey && normalized.includes(normalizedKey)) {
          score += normalizedKey.length + 2;
        }
      });
      if (score > bestScore) {
        bestScore = score;
        bestIndex = index;
      }
    });
    if (bestIndex >= 0) return bestIndex;
    const fallback = Number.isInteger(custom.fallback) ? custom.fallback : 0;
    return fallback >= 0 && fallback < scene.options.length ? fallback : 0;
  }

  function closeCustomEditor() {
    const editor = state.customEditor ||
      document.querySelector(".custom-editor");
    if (editor) editor.remove();
    document
      .querySelectorAll(".option-button[disabled], .chat-option[disabled]")
      .forEach((button) => {
        button.disabled = false;
      });
    state.customOpen = false;
    state.customEditor = null;
    const trigger = document.querySelector(
      ".custom-option-button, .custom-chat-option");
    if (trigger) trigger.focus({ preventScroll: true });
  }

  function openCustomEditor(mode, trigger) {
    if (state.customOpen) {
      closeCustomEditor();
      return;
    }
    const scene = story.scenes[state.sceneId];
    if (!scene || !scene.custom || !scene.options) return;
    const container = mode === "chat" ? $("chat-options") : $("options");
    container
      .querySelectorAll(".option-button, .chat-option")
      .forEach((button) => {
        if (button !== trigger) button.disabled = true;
      });

    const editor = document.createElement("form");
    editor.className = `custom-editor custom-editor-${mode}`;
    const input = document.createElement("textarea");
    input.className = "custom-input";
    input.rows = 2;
    input.maxLength = 40;
    input.placeholder = scene.custom.placeholder || "用你自己的话说……";
    input.setAttribute("aria-label", "自己说一句");

    const foot = document.createElement("div");
    foot.className = "custom-editor-foot";
    const count = document.createElement("span");
    count.className = "custom-count";
    count.textContent = "0 / 40";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "custom-cancel";
    cancel.textContent = "取消";
    const submit = document.createElement("button");
    submit.type = "submit";
    submit.className = "custom-submit";
    submit.textContent = "说出口";
    foot.append(count, cancel, submit);
    editor.append(input, foot);

    let composing = false;
    input.addEventListener("compositionstart", () => {
      composing = true;
    });
    input.addEventListener("compositionend", () => {
      composing = false;
    });
    input.addEventListener("input", () => {
      count.textContent = `${input.value.length} / 40`;
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        closeCustomEditor();
        return;
      }
      if (event.key === "Enter" && !event.shiftKey &&
          !event.isComposing && !composing) {
        event.preventDefault();
        event.stopPropagation();
        editor.requestSubmit();
      }
    });
    cancel.addEventListener("click", (event) => {
      event.stopPropagation();
      closeCustomEditor();
    });
    editor.addEventListener("click", (event) => {
      event.stopPropagation();
    });
    editor.addEventListener("submit", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const text = input.value.trim();
      if (!text) {
        editor.classList.remove("custom-editor-nudge");
        void editor.offsetWidth;
        editor.classList.add("custom-editor-nudge");
        input.focus();
        return;
      }
      const index = matchCustomOption(scene, text);
      closeCustomEditor();
      chooseOption(index, text);
    });

    container.append(editor);
    state.customOpen = true;
    state.customEditor = editor;
    if (mode === "chat") scrollChat();
    window.requestAnimationFrame(() => input.focus());
  }

  function showChatContinue() {
    const container = $("chat-options");
    container.replaceChildren();
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chat-continue";
    button.textContent = "继续 →";
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      onQueueFinished();
    });
    container.append(button);
    scrollChat();
  }

  function chooseOption(index, customText = "") {
    if (state.locked || !state.optionsShown) return;
    const scene = story.scenes[state.sceneId];
    const option = scene && scene.options ? scene.options[index] : null;
    if (!option) return;
    const spokenText = String(customText || "").trim() || option.text;
    const isCustom = Boolean(String(customText || "").trim());
    state.locked = true;
    state.optionsShown = false;
    state.activeOptions = [];
    state.customOpen = false;
    state.customEditor = null;
    $("options").replaceChildren();
    $("chat-options").replaceChildren();
    hide($("next-hint"));

    const delta = Number(option.delta) || 0;
    state.score = clampScore(state.score + delta);
    const stats = state.tagStats[option.tag] ||
      (state.tagStats[option.tag] = { count: 0, good: 0, bad: 0, delta: 0 });
    stats.count += 1;
    stats.delta += delta;
    if (delta > 0) stats.good += 1;
    else if (delta < 0) stats.bad += 1;

    if (option.flag) state.flags[option.flag] = true;
    if (option.finalTone) state.finalTone = option.finalTone;
    if (scene.location) state.location = scene.location;

    const factKey = option.factKey || scene.memoryFact;
    if (factKey && story.facts[factKey]) {
      state.factResults[factKey] = Boolean(option.factHit);
    }

    state.history.push({
      sceneId: state.sceneId,
      sceneLabel: scene.narration || "",
      chapter: scene.chapter,
      text: option.text,
      delta,
      tag: option.tag,
      note: option.note || "",
      factKey: factKey || null,
      factHit: factKey ? Boolean(option.factHit) : null,
      custom: isCustom,
    });

    if (option.mood) setExpression(option.mood);
    const useCold = option.reactionCold && state.score < 60;
    const reaction = useCold ? option.reactionCold : option.reaction;
    const lines = Array.isArray(reaction) ? reaction.slice() : [];
    if (state.mode === "chat") {
      appendChatBubble("你", spokenText);
    } else {
      lines.unshift({ speaker: "你", text: spokenText });
    }

    state.queueKind = "reaction";
    state.queue = lines;
    state.queueIndex = 0;
    state.pendingNext = option.next || "";
    state.locked = false;
    saveProgress();
    updateMemoryCount();
    if (!lines.length) {
      onQueueFinished();
      return;
    }
    if (state.mode === "chat") {
      window.clearTimeout(state.chatTimer);
      state.chatTimer = window.setTimeout(() => {
        if (!state.paused) playNextLine();
      }, 420);
    } else {
      playNextLine();
    }
  }

  function appendChatLine(line) {
    appendChatBubble(line.speaker || "旁白", line.text || "");
  }

  function appendChatBubble(speaker, text) {
    const messages = $("chat-messages");
    if (speaker === "时间") {
      const node = document.createElement("div");
      node.className = "chat-time";
      node.textContent = text;
      messages.append(node);
      scrollChat();
      return;
    }
    if (speaker === "旁白") {
      const node = document.createElement("div");
      node.className = "chat-narration";
      node.textContent = text;
      messages.append(node);
      scrollChat();
      return;
    }
    const row = document.createElement("div");
    row.className = `chat-row ${speaker === "奶龙酱" ? "left" : "right"}`;
    if (speaker === "奶龙酱") {
      const avatar = document.createElement("span");
      avatar.className = "chat-avatar-small";
      avatar.textContent = "奶";
      row.append(avatar);
    }
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${speaker === "奶龙酱" ? "left" : "right"}`;
    bubble.textContent = text;
    row.append(bubble);
    messages.append(row);
    scrollChat();
  }

  function scrollChat() {
    const messages = $("chat-messages");
    window.requestAnimationFrame(() => {
      messages.scrollTop = messages.scrollHeight;
    });
  }

  function triggerFlash() {
    const flash = $("flash-overlay");
    flash.classList.remove("flash");
    void flash.offsetWidth;
    flash.classList.add("flash");
    window.setTimeout(() => flash.classList.remove("flash"), 760);
  }

  function pickEnding() {
    const memoryHits = Object.values(state.factResults)
      .filter((value) => value === true).length;
    const ordered = [...story.endings]
      .sort((a, b) => (a.priority ?? 99) - (b.priority ?? 99));
    return ordered.find((ending) => {
      if (ending.requiresFlag && !state.flags[ending.requiresFlag]) return false;
      if (ending.fallback) return false;
      if (state.score < ending.minScore || state.score > ending.maxScore) {
        return false;
      }
      if (ending.requiresMemory && memoryHits < ending.requiresMemory) {
        return false;
      }
      if (ending.tones && !ending.tones.includes(state.finalTone)) return false;
      return true;
    }) || story.endings.find((ending) => ending.fallback) ||
      story.endings[story.endings.length - 1];
  }

  function topTags(limit) {
    const entries = Object.entries(state.tagStats)
      .map(([key, stats]) => ({
        key,
        label: story.tags[key] || key,
        count: Number(stats.count) || 0,
        delta: Number(stats.delta) || 0,
      }))
      .filter((item) => item.count > 0);
    entries.sort((a, b) => b.count - a.count || b.delta - a.delta);
    return entries.slice(0, limit).map((item) => item.label);
  }

  function renderMemoryReview() {
    const list = $("memory-review");
    list.replaceChildren();
    for (const key of FACT_KEYS) {
      const fact = story.facts[key];
      const learned = Boolean(state.memories[key]);
      const result = state.factResults[key];
      let status = "还没听到这个细节";
      let cls = "unknown";
      let mark = "？";
      if (learned && result === true) {
        status = "这次接住了";
        cls = "hit";
        mark = "✓";
      } else if (learned && result === false) {
        status = "这次没有接住";
        cls = "miss";
        mark = "✕";
      } else if (learned) {
        status = "没来得及验证";
        cls = "untested";
        mark = "○";
      } else if (result === true) {
        status = "接住了，但之前没留意";
        cls = "hit";
        mark = "✓";
      }
      const item = document.createElement("li");
      item.className = `memory-review-item ${cls}`;
      const badge = document.createElement("span");
      badge.className = "memory-review-mark";
      badge.textContent = mark;
      const body = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = learned ? fact.label : "？？？";
      const hint = document.createElement("p");
      hint.textContent = learned ? fact.hint : "这一段可能藏在别的选择里。";
      const stateLabel = document.createElement("small");
      stateLabel.textContent = status;
      body.append(title, hint, stateLabel);
      item.append(badge, body);
      list.append(item);
    }
  }

  function renderChoiceReview() {
    const good = state.history
      .filter((item) => item.delta > 0)
      .sort((a, b) => b.delta - a.delta)
      .slice(0, 3);
    const growth = state.history
      .filter((item) => item.delta < 0)
      .sort((a, b) => a.delta - b.delta)
      .slice(0, 2);
    fillReviewList($("choice-good"), good,
      "这一局还没有明显做得好的瞬间。");
    fillReviewList($("choice-growth"), growth,
      "这一局没有明显的扣分项，继续把倾听和尊重带进现实吧。");
  }

  function fillReviewList(container, items, emptyText) {
    container.replaceChildren();
    if (!items.length) {
      const empty = document.createElement("li");
      empty.className = "review-empty";
      empty.textContent = emptyText;
      container.append(empty);
      return;
    }
    for (const item of items) {
      const li = document.createElement("li");
      const head = document.createElement("div");
      head.className = "review-head";
      const delta = document.createElement("span");
      delta.className =
        `review-delta ${item.delta > 0 ? "good" : "bad"}`;
      delta.textContent = item.delta > 0 ? `+${item.delta}` : String(item.delta);
      const scene = document.createElement("span");
      scene.className = "review-scene";
      scene.textContent = item.sceneLabel || "这一段";
      head.append(delta, scene);
      const text = document.createElement("p");
      text.className = "review-text";
      text.textContent = item.text;
      const note = document.createElement("small");
      note.className = "review-note";
      note.textContent = item.note;
      li.append(head, text, note);
      container.append(li);
    }
  }

  function showEnding(ending) {
    if (!ending) {
      finishGame();
      return;
    }
    clearTimers();
    state.locked = true;
    state.optionsShown = false;
    state.finished = true;
    state.endingId = ending.id;
    document.body.dataset.ending = ending.id;
    setPhase("ending");
    $("ending-title").textContent = ending.title;
    $("ending-subtitle").textContent = ending.subtitle;
    const flavor = ending.flavors && state.location
      ? ending.flavors[state.location] : "";
    $("ending-flavor").textContent = flavor || "";
    $("ending-flavor").classList.toggle("hidden", !flavor);
    $("ending-text").textContent = ending.text;
    $("ending-score").textContent = String(state.score);
    $("score-ring").style.setProperty("--value", String(state.score));
    $("ending-score-fill").style.width = `${state.score}%`;
    const tags = topTags(2);
    $("ending-score-label").textContent =
      `本局心动值 ${state.score} · 你最常给出的回应：` +
      `${tags.length ? tags.join("、") : "还在观察"}`;
    renderMemoryReview();
    renderChoiceReview();
    $("ending-advice").textContent = ending.advice || "";
    $("crush-name").value = "";
    $("egg-to").textContent = "";
    $("egg-to").classList.add("hidden");
    setExpression(ending.mood || "normal");
    $("ending-screen").scrollTop = 0;
    saveProgress();
  }

  function finishGame() {
    state.locked = true;
    state.optionsShown = false;
    clearTimers();
    const ending = pickEnding();
    state.finished = true;
    state.endingId = ending.id;
    saveProgress();
    showEnding(ending);
  }

  function showEgg() {
    const name = $("crush-name").value.trim().slice(0, 16);
    const to = $("egg-to");
    if (name) {
      to.textContent = `致 ${name}`;
      to.classList.remove("hidden");
    } else {
      to.textContent = "";
      to.classList.add("hidden");
    }
    setPhase("egg");
  }

  function returnToTitle() {
    clearTimers();
    hide($("memory-panel"));
    hide($("chapter-overlay"));
    $("crush-name").value = "";
    $("egg-to").textContent = "";
    $("egg-to").classList.add("hidden");
    $("options").replaceChildren();
    $("chat-options").replaceChildren();
    state.locked = false;
    state.paused = false;
    state.mode = "dialogue";
    setMode("dialogue");
    setPhase("title");
    setBackground("campus");
    setExpression("normal");
    updateContinueButton();
  }

  $("start-button").addEventListener("click", () => startGame(false));
  $("continue-button").addEventListener("click", () => startGame(true));
  $("click-catcher").addEventListener("click", advance);
  $("dialogue-card").addEventListener("click", (event) => {
    event.stopPropagation();
    advance();
  });
  $("dialogue-card").addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      advance();
    }
  });
  $("chat-messages").addEventListener("click", (event) => {
    if (event.target.closest("button")) return;
    advance();
  });
  $("memory-button").addEventListener("click", (event) => {
    event.stopPropagation();
    openMemory();
  });
  $("memory-close").addEventListener("click", closeMemory);
  $("memory-panel").addEventListener("click", (event) => {
    if (event.target === $("memory-panel")) closeMemory();
  });
  $("egg-button").addEventListener("click", showEgg);
  $("crush-name").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      showEgg();
    }
  });
  $("egg-back").addEventListener("click", returnToTitle);
  $("again-button").addEventListener("click", restartGame);
  $("title-button").addEventListener("click", returnToTitle);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (state.customOpen) {
        event.preventDefault();
        closeCustomEditor();
        return;
      }
      if (!$("memory-panel").classList.contains("hidden")) closeMemory();
      return;
    }
    if (state.customOpen) return;
    if (!$("chapter-overlay").classList.contains("hidden")) {
      if ((event.key === "Enter" || event.key === " ") && state.chapterSkip) {
        event.preventDefault();
        state.chapterSkip();
      }
      return;
    }
    if (document.body.dataset.phase !== "playing") return;
    if (!$("memory-panel").classList.contains("hidden")) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      advance();
      return;
    }
    if (state.optionsShown && !state.locked) {
      const number = Number(event.key);
      if (number >= 1 && number <= state.activeOptions.length) {
        event.preventDefault();
        chooseOption(number - 1);
      }
    }
  });

  injectCharacters();
  renderParticles();
  setBackground("campus");
  setExpression("normal");
  updateMemoryCount();
  updateContinueButton();
  setMode("dialogue");
  setPhase("title");
})();
