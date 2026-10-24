import * as THREE from "/run/three.module.js";
import { GLTFLoader } from "/run/loaders/GLTFLoader.js";

window.THREE = THREE;
window.GLTFLoader = GLTFLoader;
await import("/run/app.js");
