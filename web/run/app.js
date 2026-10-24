/* 奶龙快跑:Three.js 三车道 3D 跑酷。
   世界向 +z 移动(障碍从远处扑来),奶龙固定在 z=0,只做换道/跳/滑铲。 */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const errorBox = $("run-error");
  if (typeof THREE === "undefined") {
    errorBox.textContent = "3D 引擎没加载出来，刷新一下再试喵。";
    errorBox.classList.remove("hidden");
    return;
  }

  const LANES = [-2.3, 0, 2.3];
  const SPAWN_Z = -95;
  const DESPAWN_Z = 14;
  const GRAVITY = -26;
  const JUMP_VY = 10.6;
  const SLIDE_SECONDS = 0.65;
  const START_SPEED = 11;
  const MAX_SPEED = 30;
  const ACCEL = 0.26;
  const PLAYER_SCALE = 1.32;
  const BEST_KEY = "nailong-run-best";

  const soundUrls = {
    jump: "/audio/jump.m4a",
    hurt: "/audio/hurt.m4a",
    heal: "/audio/heal.m4a",
    helium: "/audio/helium.m4a",
  };
  const soundBytes = Object.fromEntries(Object.entries(soundUrls).map(([name, url]) => [
    name,
    fetch(url).then((response) => {
      if (!response.ok) throw new Error(`${name}: HTTP ${response.status}`);
      return response.arrayBuffer();
    }).catch((error) => {
      console.warn("奶龙快跑音效加载失败", error);
      return null;
    }),
  ]));
  const soundReady = {};
  let soundContext = null;
  let currentSound = null;

  function activateAudio() {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;
    if (!soundContext) {
      soundContext = new AudioContextClass();
      for (const [name, bytesPromise] of Object.entries(soundBytes)) {
        soundReady[name] = bytesPromise.then((bytes) => bytes && soundContext.decodeAudioData(bytes))
          .catch((error) => {
            console.warn("奶龙快跑音效解码失败", name, error);
            return null;
          });
      }
    }
    void soundContext.resume().catch(() => {});
  }

  function playSound(name) {
    if (!soundContext || !soundReady[name]) return;
    const requestedAt = performance.now();
    void soundReady[name].then((buffer) => {
      // 音频还没加载完时不补播过期动作，避免跳跃声晚几秒才响。
      if (!buffer || performance.now() - requestedAt > 450) return;
      if (currentSound) {
        try { currentSound.stop(); } catch { /* 前一段已经播完 */ }
      }
      const source = soundContext.createBufferSource();
      const gain = soundContext.createGain();
      source.buffer = buffer;
      gain.gain.value = 0.8;
      source.connect(gain).connect(soundContext.destination);
      source.onended = () => {
        if (currentSound === source) currentSound = null;
        source.disconnect();
        gain.disconnect();
      };
      currentSound = source;
      source.start();
    });
  }

  const canvas = $("run-canvas");
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  } catch {
    errorBox.textContent = "这台设备开不了 3D 画面，换台电脑试试喵。";
    errorBox.classList.remove("hidden");
    return;
  }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputEncoding = THREE.sRGBEncoding;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x8fd3ff);
  scene.fog = new THREE.Fog(0x8fd3ff, 42, 92);

  const camera = new THREE.PerspectiveCamera(62, 1, 0.1, 220);
  camera.position.set(0, 4.6, 7.6);
  camera.lookAt(0, 1.4, -6);

  scene.add(new THREE.HemisphereLight(0xffffff, 0xf2d4b8, 0.85));
  const sun = new THREE.DirectionalLight(0xfff3df, 0.78);
  sun.position.set(6, 12, 4);
  scene.add(sun);

  /* ---------- 地面与路 ---------- */
  function makeGroundTexture() {
    const c = document.createElement("canvas");
    c.width = 256;
    c.height = 256;
    const g = c.getContext("2d");
    g.fillStyle = "#7cc571";
    g.fillRect(0, 0, 256, 256);
    for (let i = 0; i < 60; i++) {
      g.fillStyle = i % 2 ? "#86cf7b" : "#72b968";
      g.fillRect(Math.random() * 256, Math.random() * 256, 7, 7);
    }
    g.fillStyle = "#d9c49a";
    g.fillRect(64, 0, 128, 256);
    g.fillStyle = "#bda276";
    g.fillRect(64, 0, 5, 256);
    g.fillRect(187, 0, 5, 256);
    g.fillStyle = "#fffdf7";
    for (let y = 0; y < 256; y += 34) {
      g.fillRect(114, y, 4, 19);
      g.fillRect(138, y, 4, 19);
    }
    const texture = new THREE.CanvasTexture(c);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(1, 24);
    return texture;
  }

  const GROUND_LENGTH = 300;
  const GROUND_TILE = GROUND_LENGTH / 24;
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(26, GROUND_LENGTH),
    new THREE.MeshLambertMaterial({ map: makeGroundTexture() }),
  );
  ground.rotation.x = -Math.PI / 2;
  ground.position.z = -GROUND_LENGTH / 2 + 12;
  scene.add(ground);

  /* ---------- 奶龙酱 ---------- */
  const INK = new THREE.MeshLambertMaterial({ color: 0x4b3d42 });
  function buildNailong() {
    /* 按现有 Q 版立绘制作的实时 3D 角色：大脑袋、金色长发、绿眼、
       头顶奶龙眼睛发饰、黄色宽松连帽衫。所有可见部件都是立体网格。 */
    const group = new THREE.Group();
    const sphere = new THREE.SphereGeometry(1, 24, 16);
    const matte = (color) => new THREE.MeshStandardMaterial({ color, roughness: 0.84 });
    const glossy = (color) => new THREE.MeshStandardMaterial({ color, roughness: 0.28 });
    const skin = matte(0xffdcc8);
    const hair = matte(0xf4bd50);
    const hairLight = matte(0xffd578);
    const hairShadow = matte(0xd99b37);
    const hoodie = matte(0xf8c455);
    const hoodieShade = matte(0xdca540);
    const cream = matte(0xfff5e9);
    const iris = glossy(0x9cc27b);
    const irisDark = glossy(0x54805c);
    const ink = glossy(0x302d31);
    const white = matte(0xfffdf7);
    const blush = matte(0xf5a8a0);
    const mouthColor = matte(0xa66b61);
    const frogGreen = matte(0xc3d9a1);
    const shoe = matte(0xe2a753);

    function oval(parent, material, x, y, z, sx, sy, sz, rz = 0) {
      const mesh = new THREE.Mesh(sphere, material);
      mesh.position.set(x, y, z);
      mesh.scale.set(sx, sy, sz);
      mesh.rotation.z = rz;
      parent.add(mesh);
      return mesh;
    }

    // 带收尖的立体发束，背后跑动时也有清晰的长发轮廓。
    function strand(parent, points, width, material) {
      const curve = new THREE.CatmullRomCurve3(points.map((p) => new THREE.Vector3(...p)));
      const positions = [];
      const indices = [];
      const rings = 12;
      const sides = 8;
      for (let i = 0; i <= rings; i++) {
        const t = i / rings;
        const center = curve.getPoint(t);
        const tangent = curve.getTangent(t).normalize();
        const side = new THREE.Vector3(0, 0, 1).cross(tangent).normalize();
        const depth = tangent.clone().cross(side).normalize();
        const radius = width * (0.95 - 0.86 * t);
        for (let j = 0; j < sides; j++) {
          const angle = 2 * Math.PI * j / sides;
          const point = center.clone().addScaledVector(side, Math.cos(angle) * radius)
            .addScaledVector(depth, Math.sin(angle) * radius);
          positions.push(point.x, point.y, point.z);
          if (i < rings) {
            const a = i * sides + j;
            const b = i * sides + (j + 1) % sides;
            indices.push(a, b, a + sides, b, b + sides, a + sides);
          }
        }
      }
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
      geometry.setIndex(indices);
      geometry.computeVertexNormals();
      const mesh = new THREE.Mesh(geometry, material);
      parent.add(mesh);
      return mesh;
    }

    // 先放后发和兜帽，再放脸，让脸始终处在最前方。
    oval(group, hoodieShade, 0, 1.1, -0.25, 0.56, 0.49, 0.33);
    oval(group, hairShadow, 0, 1.32, -0.32, 0.72, 0.77, 0.43);
    oval(group, hair, 0, 0.91, -0.34, 0.54, 0.72, 0.35);
    const hairTails = [];
    for (const side of [-1, 1]) {
      const tail = new THREE.Group();
      tail.position.set(side * 0.5, 1.57, -0.16);
      strand(tail, [[0, 0, 0], [side * 0.15, -0.37, -0.04],
        [side * 0.26, -0.83, -0.02], [side * 0.35, -1.23, 0.1]], 0.24, hair);
      strand(tail, [[side * 0.08, -0.12, -0.13], [side * 0.25, -0.55, -0.15],
        [side * 0.28, -0.96, -0.09], [side * 0.42, -1.33, 0.05]], 0.14, hairLight);
      group.add(tail);
      hairTails.push(tail);
    }

    // 宽松连帽衫、奶白肚皮和抽绳。
    oval(group, hoodie, 0, 0.58, 0, 0.45, 0.51, 0.36);
    oval(group, cream, 0, 0.56, 0.315, 0.32, 0.36, 0.095);
    oval(group, hoodieShade, 0, 0.98, -0.1, 0.4, 0.18, 0.35);
    for (const side of [-1, 1]) {
      strand(group, [[side * 0.12, 0.93, 0.35], [side * 0.13, 0.71, 0.4],
        [side * 0.12, 0.49, 0.41]], 0.025, hoodieShade);
      oval(group, hoodieShade, side * 0.12, 0.48, 0.41, 0.045, 0.06, 0.04);
    }

    const limbs = { arms: [], legs: [] };
    for (const side of [-1, 1]) {
      const arm = new THREE.Group();
      arm.position.set(side * 0.4, 0.89, 0.04);
      oval(arm, hoodie, side * 0.09, -0.2, 0.05, 0.19, 0.29, 0.2, side * -0.24);
      oval(arm, hoodieShade, side * 0.15, -0.39, 0.08, 0.18, 0.1, 0.18);
      oval(arm, skin, side * 0.18, -0.45, 0.13, 0.115, 0.11, 0.11);
      group.add(arm);
      limbs.arms.push(arm);

      const leg = new THREE.Group();
      leg.position.set(side * 0.19, 0.31, 0.02);
      oval(leg, hoodieShade, 0, -0.12, 0.02, 0.145, 0.22, 0.16);
      oval(leg, shoe, 0, -0.24, 0.12, 0.17, 0.105, 0.23);
      group.add(leg);
      limbs.legs.push(leg);
    }

    // 大头、腮红和亮晶晶的绿眼睛。
    oval(group, skin, 0, 1.52, 0.12, 0.58, 0.59, 0.52);
    for (const side of [-1, 1]) {
      oval(group, skin, side * 0.55, 1.49, 0.1, 0.12, 0.16, 0.09);
      oval(group, white, side * 0.235, 1.55, 0.578, 0.165, 0.205, 0.075);
      oval(group, irisDark, side * 0.223, 1.54, 0.647, 0.117, 0.157, 0.054);
      oval(group, iris, side * 0.223, 1.51, 0.685, 0.086, 0.11, 0.035);
      oval(group, ink, side * 0.215, 1.56, 0.716, 0.064, 0.092, 0.029);
      oval(group, white, side * 0.19 - 0.026, 1.61, 0.742, 0.031, 0.04, 0.014);
      oval(group, blush, side * 0.405, 1.33, 0.535, 0.12, 0.058, 0.025);
      strand(group, [[side * 0.115, 1.78, 0.554], [side * 0.22, 1.79, 0.601],
        [side * 0.34, 1.76, 0.573]], 0.022, hairShadow);
    }
    oval(group, skin, 0, 1.4, 0.633, 0.045, 0.035, 0.026);
    strand(group, [[-0.075, 1.265, 0.574], [0, 1.245, 0.59],
      [0.075, 1.265, 0.574]], 0.018, mouthColor);

    // 刘海只盖住额头，不再像旧版整块横在眼睛前面。
    oval(group, hair, 0, 1.91, 0.055, 0.625, 0.36, 0.54);
    strand(group, [[-0.35, 2.1, 0.36], [-0.22, 1.94, 0.54],
      [-0.18, 1.69, 0.59]], 0.18, hairLight);
    strand(group, [[0, 2.15, 0.39], [-0.05, 1.92, 0.58],
      [0.02, 1.67, 0.59]], 0.2, hair);
    strand(group, [[0.31, 2.08, 0.38], [0.2, 1.9, 0.56],
      [0.18, 1.72, 0.58]], 0.17, hairLight);
    for (const side of [-1, 1]) {
      strand(group, [[side * 0.5, 1.95, 0.25], [side * 0.56, 1.56, 0.39],
        [side * 0.62, 1.08, 0.33], [side * 0.7, 0.8, 0.4]], 0.155, hair);
      strand(group, [[side * 0.58, 1.58, 0.16], [side * 0.7, 1.25, 0.25],
        [side * 0.75, 0.84, 0.33]], 0.11, hairLight);
    }
    strand(group, [[0.02, 2.19, -0.04], [0.06, 2.36, 0.02],
      [0.2, 2.44, 0.04], [0.28, 2.35, 0.08]], 0.065, hair);

    // 奶龙形象最醒目的两只「小眼睛」做成立体发饰。
    for (const side of [-1, 1]) {
      oval(group, frogGreen, side * 0.49, 2.14, 0.06, 0.19, 0.2, 0.135,
        side * -0.18);
      oval(group, ink, side * 0.49, 2.14, 0.178, 0.115, 0.14, 0.042);
      oval(group, white, side * 0.46, 2.205, 0.213, 0.036, 0.043, 0.015);
    }

    const shadow = new THREE.Mesh(
      new THREE.CircleGeometry(0.75, 20),
      new THREE.MeshBasicMaterial({ color: 0x3f3540, transparent: true, opacity: 0.22 }),
    );
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = 0.02;
    group.add(shadow);
    group.userData.limbs = limbs;
    group.userData.hairTails = hairTails;
    group.userData.shadow = shadow;
    return group;
  }

  const player = buildNailong();
  player.scale.setScalar(PLAYER_SCALE);
  scene.add(player);
  let playerMixer = null;

  function addBackRunArms() {
    const sphere = new THREE.SphereGeometry(1, 20, 14);
    const sleeveMaterial = new THREE.MeshStandardMaterial({
      color: 0xe9ad4b, roughness: 0.48, transparent: true, opacity: 0,
    });
    const handMaterial = new THREE.MeshStandardMaterial({
      color: 0xf6c2a6, roughness: 0.74, transparent: true, opacity: 0,
    });
    const arms = [];
    for (const side of [-1, 1]) {
      const arm = new THREE.Group();
      arm.position.set(side * 0.67, 1.10, -0.24);
      const sleeve = new THREE.Mesh(sphere, sleeveMaterial);
      sleeve.position.set(side * 0.075, -0.15, 0);
      sleeve.scale.set(0.125, 0.185, 0.12);
      arm.add(sleeve);
      const hand = new THREE.Mesh(sphere, handMaterial);
      hand.position.set(side * 0.125, -0.31, 0);
      hand.scale.set(0.065, 0.075, 0.065);
      arm.add(hand);
      player.add(arm);
      arms.push(arm);
    }
    return { arms, sleeveMaterial, handMaterial };
  }

  function addRunMorphs(model) {
    const animatedMeshes = [];
    model.traverse((mesh) => {
      if (!mesh.isMesh || !mesh.geometry?.attributes.position) return;
      const geometry = mesh.geometry.clone();
      const position = geometry.attributes.position;
      const poseA = new Float32Array(position.array.length);
      const poseB = new Float32Array(position.array.length);
      for (let i = 0; i < position.count; i++) {
        const x = position.getX(i);
        const y = position.getY(i);
        const z = position.getZ(i);
        const side = x < 0 ? -1 : 1;
        const absX = Math.abs(x);
        // 模型没有骨骼。只让身体两侧靠前的袖子和手、下方的腿参与动作。
        const armWeight = THREE.MathUtils.smoothstep(absX, 0.32, 0.56)
          * THREE.MathUtils.smoothstep(y, -0.40, -0.22)
          * (1 - THREE.MathUtils.smoothstep(y, -0.02, 0.10))
          * THREE.MathUtils.smoothstep(z, 0.10, 0.30);
        const legWeight = THREE.MathUtils.smoothstep(-y, 0.55, 0.82)
          * THREE.MathUtils.smoothstep(absX, 0.05, 0.14)
          * (1 - THREE.MathUtils.smoothstep(absX, 0.38, 0.50));
        for (const [target, phase] of [[poseA, 1], [poseB, -1]]) {
          const armAngle = phase * side * 0.95;
          const armDy = y - 0.02;
          const armDz = z - 0.06;
          const armY = 0.02 + Math.cos(armAngle) * armDy - Math.sin(armAngle) * armDz;
          const armZ = 0.06 + Math.sin(armAngle) * armDy + Math.cos(armAngle) * armDz;
          const legAngle = -phase * side * 0.40;
          const legDy = y + 0.52;
          const legDz = z;
          const legY = -0.52 + Math.cos(legAngle) * legDy - Math.sin(legAngle) * legDz;
          const legZ = Math.sin(legAngle) * legDy + Math.cos(legAngle) * legDz;
          const offset = i * 3;
          target[offset] = x;
          target[offset + 1] = y + armWeight * (armY - y) + legWeight * (legY - y);
          target[offset + 2] = z + armWeight * (armZ - z) + legWeight * (legZ - z);
        }
      }
      geometry.morphAttributes.position = [
        new THREE.Float32BufferAttribute(poseA, 3),
        new THREE.Float32BufferAttribute(poseB, 3),
      ];
      mesh.geometry = geometry;
      mesh.updateMorphTargets();
      animatedMeshes.push(mesh);
    });
    return animatedMeshes;
  }

  // 优先使用独立的贴图模型。下载或解析失败时保留原角色，游戏仍能启动。
  if (typeof GLTFLoader === "function") {
    const modelLoader = new GLTFLoader();
    modelLoader.load("/run/nailong.glb", (gltf) => {
    const model = gltf.scene;
    const box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3());
    if (!Number.isFinite(size.y) || size.y <= 0) return;
    model.scale.setScalar(2.45 / size.y);
    const fitted = new THREE.Box3().setFromObject(model);
    const center = fitted.getCenter(new THREE.Vector3());
    model.position.set(-center.x, -fitted.min.y, -center.z);
    for (const child of [...player.children]) {
      if (child !== player.userData.shadow) player.remove(child);
    }
    player.add(model);
    player.userData.limbs = null;
    player.userData.hairTails = null;
    player.userData.model = model;
    if (gltf.animations.length) {
      const runClip = gltf.animations.find((clip) => /run|跑/i.test(clip.name)) || gltf.animations[0];
      playerMixer = new THREE.AnimationMixer(model);
      playerMixer.clipAction(runClip).play();
    } else {
      player.userData.runMorphs = addRunMorphs(model);
      player.userData.backRunArms = addBackRunArms();
    }
    }, undefined, (error) => {
      console.error("奶龙酱 3D 模型加载失败", error);
    });
  }

  /* ---------- 障碍与点心 ---------- */
  const obstacleGeo = {
    barrier: new THREE.BoxGeometry(1.7, 0.9, 0.45),
    barrierStripe: new THREE.BoxGeometry(1.74, 0.28, 0.47),
    bar: new THREE.BoxGeometry(1.7, 0.5, 0.45),
    post: new THREE.BoxGeometry(0.14, 1.85, 0.14),
  };
  const obstacleMat = {
    barrier: new THREE.MeshLambertMaterial({ color: 0xe05b5b }),
    stripe: new THREE.MeshLambertMaterial({ color: 0xfffdf7 }),
    bar: new THREE.MeshLambertMaterial({ color: 0x9b6dd6 }),
    post: INK,
  };
  const standeeLoader = new THREE.TextureLoader();
  const standees = [
    { file: "crossed-arms.png", width: 1.73 },
    { file: "belly-laugh.png", width: 1.73 },
    { file: "side-view.png", width: 1.38 },
  ].map(({ file, width }) => {
    const texture = standeeLoader.load(`/run/standees/${file}`);
    texture.encoding = THREE.sRGBEncoding;
    return {
      geometry: new THREE.PlaneGeometry(width, 2.6),
      material: new THREE.MeshBasicMaterial({
        map: texture, transparent: true, alphaTest: 0.15,
        side: THREE.DoubleSide, depthWrite: true,
      }),
    };
  });
  let nextStandee = 0;
  const coinGeo = new THREE.CylinderGeometry(0.32, 0.32, 0.09, 18);
  coinGeo.rotateX(Math.PI / 2);
  const coinMat = new THREE.MeshLambertMaterial({ color: 0xf7b32b });
  const heartShape = new THREE.Shape();
  heartShape.moveTo(0, 0.32);
  heartShape.bezierCurveTo(-0.15, 0.55, -0.48, 0.40, -0.46, 0.13);
  heartShape.bezierCurveTo(-0.44, -0.12, -0.17, -0.34, 0, -0.50);
  heartShape.bezierCurveTo(0.17, -0.34, 0.44, -0.12, 0.46, 0.13);
  heartShape.bezierCurveTo(0.48, 0.40, 0.15, 0.55, 0, 0.32);
  const heartGeo = new THREE.ExtrudeGeometry(heartShape, {
    depth: 0.12, bevelEnabled: true, bevelThickness: 0.04,
    bevelSize: 0.04, bevelSegments: 2, curveSegments: 12,
  });
  const heartMat = new THREE.MeshStandardMaterial({
    color: 0xff4f85, emissive: 0x7f1238, emissiveIntensity: 0.28,
    roughness: 0.32, metalness: 0.08,
  });
  const treeTopGeo = new THREE.ConeGeometry(0.9, 2.1, 8);
  const treeTrunkGeo = new THREE.CylinderGeometry(0.16, 0.2, 0.9, 8);
  const treeTopMat = new THREE.MeshLambertMaterial({ color: 0x4d9e57 });
  const treeTrunkMat = new THREE.MeshLambertMaterial({ color: 0x8a6242 });

  function buildObstacle(type, standeeIndex = 0) {
    const group = new THREE.Group();
    if (type === "barrier") {
      const main = new THREE.Mesh(obstacleGeo.barrier, obstacleMat.barrier);
      main.position.y = 0.45;
      group.add(main);
      const stripe = new THREE.Mesh(obstacleGeo.barrierStripe, obstacleMat.stripe);
      stripe.position.y = 0.62;
      group.add(stripe);
    } else if (type === "bar") {
      const bar = new THREE.Mesh(obstacleGeo.bar, obstacleMat.bar);
      bar.position.y = 1.55;
      group.add(bar);
      for (const side of [-1, 1]) {
        const post = new THREE.Mesh(obstacleGeo.post, obstacleMat.post);
        post.position.set(0.8 * side, 0.92, 0);
        group.add(post);
      }
    } else {
      const { geometry, material } = standees[standeeIndex];
      const cutout = new THREE.Mesh(geometry, material);
      cutout.position.y = 1.3;
      group.add(cutout);
    }
    return group;
  }

  const obstacles = [];
  const coins = [];
  const heartPickups = [];

  function spawnObstacle(type, lane, z) {
    const standeeIndex = type === "wall" ? nextStandee++ % standees.length : 0;
    const mesh = buildObstacle(type, standeeIndex);
    mesh.position.set(LANES[lane], 0, z);
    scene.add(mesh);
    obstacles.push({ type, lane, z, mesh });
  }

  function spawnCoinLine(lane, z) {
    for (let i = 0; i < 5; i++) {
      const mesh = new THREE.Mesh(coinGeo, coinMat);
      mesh.position.set(LANES[lane], 0.95, z - i * 1.7);
      scene.add(mesh);
      coins.push({ z: mesh.position.z, lane, y: 0.95, mesh });
    }
  }

  function spawnHeart(lane, z) {
    const mesh = new THREE.Mesh(heartGeo, heartMat);
    mesh.position.set(LANES[lane], 1.18, z);
    scene.add(mesh);
    heartPickups.push({ lane, z, mesh });
  }

  const trees = [];
  for (let i = 0; i < 16; i++) {
    const tree = new THREE.Group();
    const trunk = new THREE.Mesh(treeTrunkGeo, treeTrunkMat);
    trunk.position.y = 0.45;
    tree.add(trunk);
    const top = new THREE.Mesh(treeTopGeo, treeTopMat);
    top.position.y = 1.9;
    tree.add(top);
    const side = i % 2 ? 1 : -1;
    tree.position.set(side * (6 + Math.random() * 5), 0,
      -Math.random() * 110 + 10);
    scene.add(tree);
    trees.push(tree);
  }

  /* ---------- 游戏状态 ---------- */
  const state = {
    mode: "menu",           // menu | playing | crash | over
    lane: 1,
    playerY: 0,
    vy: 0,
    sliding: 0,
    speed: START_SPEED,
    score: 0,
    coins: 0,
    distanceToSpawn: 0,
    crashTimer: 0,
    best: 0,
    runTime: 0,
    turnElapsed: 0,
    hearts: 3,
    heartCooldown: 0,
    invincible: 0,
  };
  try {
    state.best = Number(localStorage.getItem(BEST_KEY)) || 0;
  } catch { /* 隐私模式拿不到就算了 */ }
  $("hud-best").textContent = `最佳 ${Math.floor(state.best)}`;

  function updateHearts() {
    const hearts = Math.max(0, state.hearts);
    $("hud-hearts").textContent = "❤️".repeat(hearts) + "🖤".repeat(3 - hearts);
  }
  updateHearts();

  function resetGame() {
    activateAudio();
    if (currentSound) {
      try { currentSound.stop(); } catch { /* 已经播完 */ }
      currentSound = null;
    }
    for (const item of obstacles) scene.remove(item.mesh);
    obstacles.length = 0;
    for (const coin of coins) scene.remove(coin.mesh);
    coins.length = 0;
    for (const heart of heartPickups) scene.remove(heart.mesh);
    heartPickups.length = 0;
    Object.assign(state, {
      mode: "playing", lane: 1, playerY: 0, vy: 0, sliding: 0,
      speed: START_SPEED, score: 0, coins: 0, distanceToSpawn: 8,
      crashTimer: 0, runTime: 0, turnElapsed: 0, hearts: 3,
      heartCooldown: 0, invincible: 0,
    });
    nextStandee = 0;
    player.rotation.set(0, 0, 0);
    player.position.set(0, 0, 0);
    player.scale.setScalar(PLAYER_SCALE);
    player.visible = true;
    if (player.userData.backRunArms) {
      player.userData.backRunArms.sleeveMaterial.opacity = 0;
      player.userData.backRunArms.handMaterial.opacity = 0;
    }
    updateHearts();
    $("hud-hearts").classList.remove("restored");
    $("hud-coins").textContent = "🐟 0";
    $("start-view").classList.add("hidden");
    $("gameover-view").classList.add("hidden");
    $("hud").classList.remove("hidden");
  }

  function spawnEvent() {
    const laneOrder = [0, 1, 2].sort(() => Math.random() - 0.5);
    const double = Math.random() < Math.min(0.62, 0.12 + state.speed / 42);
    const used = double ? [laneOrder[0], laneOrder[1]] : [laneOrder[0]];
    const types = ["wall", "barrier", "bar"];
    for (const lane of used) {
      spawnObstacle(types[Math.floor(Math.random() * types.length)],
        lane, SPAWN_Z);
    }
    // 点心永远落在这次没有障碍的跑道上。
    const free = [0, 1, 2].filter((lane) => !used.includes(lane));
    if (free.length) {
      const lane = free[Math.floor(Math.random() * free.length)];
      if (state.hearts < 3 && heartPickups.length === 0
          && state.heartCooldown <= 0 && Math.random() < 0.15) {
        spawnHeart(lane, SPAWN_Z - 3);
        state.heartCooldown = 12;
      } else if (Math.random() < 0.72) {
        spawnCoinLine(lane, SPAWN_Z - 3);
      }
    }
  }

  function crash() {
    state.mode = "crash";
    state.crashTimer = 0;
  }

  function finishGame() {
    state.mode = "over";
    playSound("helium");
    const score = Math.floor(state.score);
    const isBest = score > state.best;
    if (isBest) {
      state.best = score;
      try { localStorage.setItem(BEST_KEY, String(score)); } catch { /* 无所谓 */ }
    }
    $("final-score").textContent = score;
    $("final-detail").textContent =
      `捞到 ${state.coins} 块点心，${isBest ? "刷新最佳纪录喵！" : `距离最佳还差 ${Math.ceil(state.best - score)} 分`}`;
    $("over-badge").textContent = isBest ? "新纪录!" : "被抓到啦!";
    $("hud-best").textContent = `最佳 ${Math.floor(state.best)}`;
    $("gameover-view").classList.remove("hidden");
  }

  function loseHeart() {
    state.hearts -= 1;
    playSound("hurt");
    state.invincible = 1;
    updateHearts();
    if (state.hearts <= 0) crash();
  }

  function handleCollisions() {
    for (let i = obstacles.length - 1; i >= 0; i--) {
      const item = obstacles[i];
      if (Math.abs(item.z) > 0.75 || item.lane !== state.lane) continue;
      if (state.invincible > 0) continue;
      let hit;
      if (item.type === "barrier") hit = state.playerY < 0.8;
      else if (item.type === "bar") hit = state.sliding <= 0;
      else hit = true;
      if (!hit) continue;
      // 撞碎障碍扣一颗爱心，并给 1 秒无敌穿过的时间。
      scene.remove(item.mesh);
      obstacles.splice(i, 1);
      loseHeart();
      return;
    }
    for (let i = coins.length - 1; i >= 0; i--) {
      const coin = coins[i];
      if (Math.abs(coin.z) > 0.85 || coin.lane !== state.lane) continue;
      if (Math.abs(coin.y - (state.playerY + 0.9)) > 1.1) continue;
      scene.remove(coin.mesh);
      coins.splice(i, 1);
      state.coins += 1;
      state.score += 15;
      $("hud-coins").textContent = `🐟 ${state.coins}`;
    }
    for (let i = heartPickups.length - 1; i >= 0; i--) {
      const heart = heartPickups[i];
      if (Math.abs(heart.z) > 0.85 || heart.lane !== state.lane) continue;
      if (Math.abs(heart.mesh.position.y - (state.playerY + 0.9)) > 1.25) continue;
      scene.remove(heart.mesh);
      heartPickups.splice(i, 1);
      state.hearts = Math.min(3, state.hearts + 1);
      updateHearts();
      playSound("heal");
      const display = $("hud-hearts");
      display.classList.remove("restored");
      void display.offsetWidth;
      display.classList.add("restored");
    }
  }

  function updatePlayer(dt) {
    // 起跑时从面向镜头转为面向跑道；换道时朝移动方向偏转，再回正。
    const targetX = LANES[state.lane];
    const dx = targetX - player.position.x;
    player.position.x += dx * Math.min(1, 14 * dt);
    state.turnElapsed += dt;
    const turn = THREE.MathUtils.clamp(state.turnElapsed / 0.68, 0, 1);
    const baseYaw = Math.PI * turn * turn * (3 - 2 * turn);
    const laneYaw = THREE.MathUtils.clamp(dx * 0.42, -0.5, 0.5);
    player.rotation.y += (baseYaw - laneYaw - player.rotation.y) * Math.min(1, 15 * dt);
    player.rotation.z = THREE.MathUtils.clamp(-dx * 0.07, -0.13, 0.13);
    // 跳跃
    if (state.playerY > 0 || state.vy !== 0) {
      state.vy += GRAVITY * dt;
      state.playerY += state.vy * dt;
      if (state.playerY <= 0) {
        state.playerY = 0;
        state.vy = 0;
      }
    }
    // 滑铲
    if (state.sliding > 0) {
      state.sliding -= dt;
      player.scale.y = PLAYER_SCALE * 0.48;
    } else {
      player.scale.y = PLAYER_SCALE;
    }
    const running = state.mode === "playing";
    state.runTime += dt;
    const bob = running && state.playerY === 0 && state.sliding <= 0
      ? Math.abs(Math.sin(state.runTime * state.speed * 0.9)) * 0.09 : 0;
    player.position.y = state.playerY + bob;
    // Q 版小短腿和小手跟着跑步节奏划动。
    const limbs = player.userData.limbs;
    const swingAmp = running && state.playerY === 0 && state.sliding <= 0 ? 1 : 0.12;
    const swing = Math.sin(state.runTime * state.speed * 0.9) * 0.5 * swingAmp;
    if (limbs) {
      limbs.legs[0].rotation.x = swing;
      limbs.legs[1].rotation.x = -swing;
      limbs.arms[0].rotation.x = -swing * 0.8;
      limbs.arms[1].rotation.x = swing * 0.8;
    }
    if (player.userData.hairTails) {
      player.userData.hairTails[0].rotation.z = 0.035 * Math.sin(state.runTime * 8);
      player.userData.hairTails[1].rotation.z = -0.035 * Math.sin(state.runTime * 8);
    }
    if (player.userData.model) {
      player.userData.model.rotation.z = running ? 0.025 * Math.sin(state.runTime * state.speed * 0.9) : 0;
    }
    if (player.userData.runMorphs) {
      const runAmount = running && state.playerY === 0 && state.sliding <= 0
        ? THREE.MathUtils.clamp(state.turnElapsed / 0.45, 0, 1) : 0;
      const pose = Math.sin(state.runTime * state.speed * 0.9) * runAmount;
      for (const mesh of player.userData.runMorphs) {
        mesh.morphTargetInfluences[0] = Math.max(0, pose);
        mesh.morphTargetInfluences[1] = Math.max(0, -pose);
      }
    }
    if (player.userData.backRunArms) {
      const { arms, sleeveMaterial, handMaterial } = player.userData.backRunArms;
      const fade = THREE.MathUtils.smoothstep(state.turnElapsed, 0.34, 0.76);
      sleeveMaterial.opacity = fade;
      handMaterial.opacity = fade;
      for (const [index, arm] of arms.entries()) {
        const stride = Math.sin(state.runTime * state.speed * 0.9) * swingAmp;
        const side = index === 0 ? -1 : 1;
        arm.position.y = 1.10 + side * stride * 0.13;
        arm.rotation.x = side * stride * 0.88;
        arm.rotation.z = side * 0.10 + stride * 0.22;
      }
    }
    if (playerMixer && running) playerMixer.update(dt);
    // 无敌帧：一闪一闪表示暂时撞不坏。
    if (state.invincible > 0) {
      state.invincible -= dt;
      player.visible = Math.floor(state.invincible * 12) % 2 === 0;
      if (state.invincible <= 0) player.visible = true;
    }
    player.userData.shadow.position.y = 0.02 - state.playerY;
    const shadowScale = Math.max(0.45, 1 - state.playerY * 0.28);
    player.userData.shadow.scale.set(shadowScale, shadowScale, 1);
  }

  function updateWorld(dt) {
    const move = state.speed * dt;
    state.heartCooldown = Math.max(0, state.heartCooldown - dt);
    ground.material.map.offset.y += move / GROUND_TILE;
    for (const item of obstacles) {
      item.z += move;
      item.mesh.position.z = item.z;
    }
    for (const coin of coins) {
      coin.z += move;
      coin.mesh.position.z = coin.z;
      coin.mesh.rotation.y += dt * 3.4;
    }
    for (const heart of heartPickups) {
      heart.z += move;
      heart.mesh.position.z = heart.z;
      heart.mesh.position.y = 1.18 + Math.sin(state.runTime * 4 + heart.z * 0.1) * 0.12;
      heart.mesh.rotation.y += dt * 1.6;
    }
    for (const tree of trees) {
      tree.position.z += move;
      if (tree.position.z > 16) {
        tree.position.z -= 118;
        tree.position.x = (Math.random() < 0.5 ? -1 : 1) * (6 + Math.random() * 5);
      }
    }
    // 清理跑过的障碍
    for (let i = obstacles.length - 1; i >= 0; i--) {
      if (obstacles[i].z > DESPAWN_Z) {
        scene.remove(obstacles[i].mesh);
        obstacles.splice(i, 1);
      }
    }
    for (let i = coins.length - 1; i >= 0; i--) {
      if (coins[i].z > DESPAWN_Z) {
        scene.remove(coins[i].mesh);
        coins.splice(i, 1);
      }
    }
    for (let i = heartPickups.length - 1; i >= 0; i--) {
      if (heartPickups[i].z > DESPAWN_Z) {
        scene.remove(heartPickups[i].mesh);
        heartPickups.splice(i, 1);
      }
    }
    state.distanceToSpawn += move;
    const gap = Math.max(9.5, 17 - state.speed * 0.22);
    if (state.distanceToSpawn >= gap) {
      state.distanceToSpawn = 0;
      spawnEvent();
    }
    state.speed = Math.min(MAX_SPEED, state.speed + ACCEL * dt);
    state.score += move * 1.4;
  }

  function updateCamera() {
    camera.position.x = player.position.x * 0.4;
    camera.lookAt(player.position.x * 0.5, 1.4, -6);
  }

  let lastTime = performance.now();
  function tick(now) {
    requestAnimationFrame(tick);
    const dt = Math.min(0.05, (now - lastTime) / 1000);
    lastTime = now;
    if (state.mode === "playing") {
      updateWorld(dt);
      updatePlayer(dt);
      handleCollisions();
      $("hud-score").textContent = `${Math.floor(state.score)} 分`;
    } else if (state.mode === "crash") {
      state.crashTimer += dt;
      state.speed = Math.max(0, state.speed - 34 * dt);
      updateWorld(dt);
      player.rotation.x -= dt * 6;
      player.position.y = Math.max(0.3, player.position.y - dt * 2);
      if (state.crashTimer > 0.9) finishGame();
    } else if (state.mode === "menu") {
      // 菜单里让奶龙原地小跑热身。
      state.runTime += dt;
      player.position.y = Math.abs(Math.sin(state.runTime * 6)) * 0.12;
      ground.material.map.offset.y += START_SPEED * dt / GROUND_TILE;
    }
    updateCamera();
    renderer.render(scene, camera);
  }

  /* ---------- 操作 ---------- */
  function moveLane(direction) {
    if (state.mode !== "playing") return;
    state.lane = Math.max(0, Math.min(2, state.lane + direction));
  }

  function jump() {
    if (state.mode !== "playing" || state.playerY > 0) return;
    state.vy = JUMP_VY;
    state.sliding = 0;
    playSound("jump");
  }

  function slide() {
    if (state.mode !== "playing") return;
    if (state.playerY > 0) {
      state.vy = -18; // 空中按下直接砸下来接滑铲
    }
    state.sliding = SLIDE_SECONDS;
  }

  window.addEventListener("keydown", (event) => {
    const key = event.key;
    if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", " "].includes(key)) {
      event.preventDefault();
    }
    if (key === "ArrowLeft" || key === "a" || key === "A") moveLane(-1);
    else if (key === "ArrowRight" || key === "d" || key === "D") moveLane(1);
    else if (key === "ArrowUp" || key === " " || key === "w" || key === "W") jump();
    else if (key === "ArrowDown" || key === "s" || key === "S") slide();
  });

  let touchStart = null;
  canvas.addEventListener("pointerdown", (event) => {
    if (!event.isPrimary) return;
    touchStart = { id: event.pointerId, x: event.clientX, y: event.clientY };
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener("pointerup", (event) => {
    if (!touchStart || touchStart.id !== event.pointerId) return;
    const dx = event.clientX - touchStart.x;
    const dy = event.clientY - touchStart.y;
    touchStart = null;
    if (state.mode !== "playing") return;
    if (Math.max(Math.abs(dx), Math.abs(dy)) < 24) {
      jump(); // 轻点当跳
    } else if (Math.abs(dx) > Math.abs(dy)) {
      moveLane(dx > 0 ? 1 : -1);
    } else if (dy < 0) {
      jump();
    } else {
      slide();
    }
  });
  canvas.addEventListener("pointercancel", (event) => {
    if (touchStart?.id === event.pointerId) touchStart = null;
  });

  /* ---------- 界面按钮 ---------- */
  $("start-button").addEventListener("click", resetGame);
  $("retry-button").addEventListener("click", resetGame);

  function resize() {
    const width = window.innerWidth;
    const height = window.innerHeight;
    renderer.setSize(width, height, false);
    camera.aspect = width / Math.max(1, height);
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", resize);
  resize();
  requestAnimationFrame(tick);
})();
