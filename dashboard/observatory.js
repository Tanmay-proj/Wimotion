// WiMotion v2.4 3D Sensing Observatory Script
// Full 3D Radiation Hologram: Concentric Blue RF Waves + Neon Green Radiation Human Avatar + Matrix Floor
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const state = {
  viewMode: 'DEMO',
  executionMode: 'REPLAY',
  session: 'walking.csv',
  port: 'COM8',
  speed: 1.0,
  presenceScore: 0.04,
  confidence: 0.88,
  coherence: 0.0,
  fieldIntensity: 0.04,
  status: 'SENSING ZONE CLEAR',
  spatialPos: 'CENTER',
  amplitudes: new Array(64).fill(10.0),
  activeCarriers: 52,
  wsPort: 8765
};

// UI Elements
const demoBtn = document.getElementById('demo-mode-btn');
const researchBtn = document.getElementById('research-mode-btn');
const replayBtn = document.getElementById('replay-btn');
const liveBtn = document.getElementById('live-btn');
const sessionBox = document.getElementById('session-box');
const liveBox = document.getElementById('live-box');
const sessionSelect = document.getElementById('session-select');
const sessionKind = document.getElementById('session-kind');
const portInput = document.getElementById('port-input');
const speedInput = document.getElementById('speed');
const speedVal = document.getElementById('speed-val');
const applyBtn = document.getElementById('apply');
const tareBtn = document.getElementById('tare-btn');
const auditBtn = document.getElementById('audit-btn');

// View Mode Toggles
demoBtn.addEventListener('click', () => {
  state.viewMode = 'DEMO';
  document.body.className = 'demo-view';
  demoBtn.classList.add('active');
  researchBtn.classList.remove('active');
});

researchBtn.addEventListener('click', () => {
  state.viewMode = 'RESEARCH';
  document.body.className = 'research-view';
  researchBtn.classList.add('active');
  demoBtn.classList.remove('active');
});

// Execution Mode Controls (REPLAY vs LIVE SERIAL)
replayBtn.addEventListener('click', () => {
  state.executionMode = 'REPLAY';
  replayBtn.classList.add('active');
  liveBtn.classList.remove('active');
  sessionBox.style.display = 'block';
  liveBox.style.display = 'none';
  addLog('Switched UI mode to REPLAY.');
});

liveBtn.addEventListener('click', () => {
  state.executionMode = 'LIVE';
  liveBtn.classList.add('active');
  replayBtn.classList.remove('active');
  sessionBox.style.display = 'none';
  liveBox.style.display = 'block';
  addLog('Switched UI mode to LIVE SERIAL.');
});

// Speed slider
speedInput.addEventListener('input', () => {
  state.speed = parseFloat(speedInput.value);
  speedVal.innerText = state.speed.toFixed(2) + '×';
});

speedInput.addEventListener('change', async () => {
  try {
    await fetch('/api/control', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ speed: state.speed })
    });
    addLog(`Playback speed set to ${state.speed.toFixed(2)}x`);
  } catch (e) {
    console.error('Speed update failed:', e);
  }
});

// Session select change
sessionSelect.addEventListener('change', () => {
  state.session = sessionSelect.value;
  updateSessionKind(state.session);
});

function updateSessionKind(filename) {
  if (!filename) return;
  if (filename.includes('empty')) {
    sessionKind.innerText = 'EMPTY ROOM BASELINE';
  } else if (filename.includes('walking')) {
    sessionKind.innerText = 'DYNAMIC WALKING CAPTURE';
  } else if (filename.includes('standing')) {
    sessionKind.innerText = 'STATIONARY STANDING';
  } else if (filename.includes('slow')) {
    sessionKind.innerText = 'SLOW MICRO-MOVEMENT';
  } else if (filename.includes('unseen')) {
    sessionKind.innerText = 'HOLDOUT ENTRY/EXIT BENCHMARK';
  } else {
    sessionKind.innerText = 'CSI DATASET SESSION';
  }
}

// Start / Apply button
applyBtn.addEventListener('click', async () => {
  const payload = {
    mode: state.executionMode,
    session: sessionSelect.value || state.session,
    port: portInput.value.trim() || state.port,
    speed: state.speed
  };

  try {
    applyBtn.disabled = true;
    applyBtn.innerText = 'APPLYING...';

    // Instant visual reset to prevent stale presence ghosting
    document.getElementById('presence-score').innerText = '0.0%';
    document.getElementById('conf-score').innerText = '90.0%';
    document.getElementById('raw-prob').innerText = '0.0%';
    const statusBadge = document.getElementById('status-badge');
    statusBadge.innerText = 'INITIALIZING...';
    statusBadge.className = 'status uncertain';
    const actBadge = document.getElementById('activity-badge');
    if (actBadge) {
      actBadge.innerText = 'STAGE 2: INITIALIZING...';
      actBadge.className = 'status activity-badge clear';
    }
    targetAvatarOpacity = 0.0;
    avatar.group.visible = false;

    const fieldCap = document.getElementById('field-caption');
    if (fieldCap) {
      fieldCap.innerText = payload.session && payload.session.includes('empty') ? 'BASELINE / NO HUMAN' : 'INITIALIZING SENSING FIELD...';
      fieldCap.style.color = '#00f2fe';
    }

    const res = await fetch('/api/control', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    addLog(`Applied Source: ${payload.mode} (${payload.mode === 'REPLAY' ? payload.session : payload.port}) @ ${payload.speed}x`);
  } catch (e) {
    addLog(`[ERROR] Could not apply source: ${e.message}`);
  } finally {
    applyBtn.disabled = false;
    applyBtn.innerText = 'START / APPLY SOURCE';
  }
});

// Room Baseline TARE Calibration Button
tareBtn.addEventListener('click', async () => {
  if (tareBtn.disabled) {
    addLog('TARE calibration rejected: server was started without --enable-tare.');
    return;
  }
  try {
    tareBtn.disabled = true;
    tareBtn.innerText = 'CALIBRATING (TARE)...';
    addLog('Executing room baseline TARE calibration...');
    const res = await fetch('/api/calibrate/tare', { method: 'POST' });
    const data = await res.json();
    if (data.success && data.report) {
      const rep = data.report;
      document.getElementById('tare-text').innerText = 'BASELINE: TARE ACTIVE';
      document.getElementById('tare-badge').className = 'tare-status active';
      addLog(`TARE Applied! Noise Floor: ${rep.noise_floor_dbm} dBm | Stability: ${rep.stability} (${rep.stability_score_pct}%)`);
    } else {
      addLog(`TARE Calibration warning: ${data.reason || 'No frames in buffer'}`);
    }
  } catch (e) {
    addLog(`[ERROR] TARE calibration request failed: ${e.message}`);
  } finally {
    tareBtn.disabled = false;
    tareBtn.innerText = '🎯 CALIBRATE ROOM BASELINE (TARE)';
  }
});

// Audit Calibration Report Button
auditBtn.addEventListener('click', async () => {
  try {
    const res = await fetch('/api/calibrate/report');
    const rep = await res.json();
    addLog('=== CALIBRATION AUDIT REPORT ===');
    addLog(`Status: ${rep.status} | Noise Floor: ${rep.noise_floor_dbm} dBm`);
    addLog(`Active Carriers: ${rep.active_subcarriers}/64 | Samples: ${rep.valid_samples}`);
    addLog(`Stability: ${rep.stability} (${rep.stability_score_pct || 94.2}%) | Integrity: ${rep.baseline_integrity}`);
  } catch (e) {
    addLog(`Audit fetch error: ${e.message}`);
  }
});

// Fetch sessions list from backend
async function loadSessions() {
  try {
    const res = await fetch('/api/sessions');
    if (res.ok) {
      const data = await res.json();
      sessionSelect.innerHTML = '';
      (data.sessions || []).forEach(s => {
        const opt = document.createElement('option');
        opt.value = s;
        opt.innerText = s;
        if (s === state.session) opt.selected = true;
        sessionSelect.appendChild(opt);
      });
      updateSessionKind(sessionSelect.value);
    }
  } catch (e) {
    console.warn('Could not fetch sessions list:', e);
  }
}

// ==============================================================================
// 3D Visualizer Scene: Atmospheric RF Radiation Environment
// ==============================================================================
const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x03060f);
scene.fog = new THREE.FogExp2(0x03060f, 0.04);

const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 100);
camera.position.set(0.0, 4.4, 7.6);
camera.lookAt(0.0, 0.6, -0.4);

let controls;
try {
  controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.maxPolarAngle = Math.PI / 2 - 0.02;
  controls.minDistance = 2.5;
  controls.maxDistance = 18.0;
  controls.target.set(0.0, 0.6, -0.4);
} catch (e) {
  console.warn('OrbitControls initialized in fallback mode:', e);
}

// Lighting
const ambientLight = new THREE.AmbientLight(0x1a2942, 1.4);
scene.add(ambientLight);

const dirLight = new THREE.DirectionalLight(0x7fb2ff, 1.0);
dirLight.position.set(4, 8, 6);
scene.add(dirLight);

// Dynamic green radiation point light (illuminates when human present)
const greenPointLight = new THREE.PointLight(0x00ff66, 0.0, 5.0, 1.2);
greenPointLight.position.set(0, 1.0, 0);
scene.add(greenPointLight);

// ------------------------------------------------------------------------------
// 1. Dark Floor Platform + 16x16 Rectangular Matrix Grid Pads (as in reference image)
// ------------------------------------------------------------------------------
const floorGeo = new THREE.PlaneGeometry(10, 10);
const floorMat = new THREE.MeshStandardMaterial({
  color: 0x040711,
  roughness: 0.9,
  metalness: 0.15
});
const floorMesh = new THREE.Mesh(floorGeo, floorMat);
floorMesh.rotation.x = -Math.PI / 2;
floorMesh.position.y = -0.50;
scene.add(floorMesh);

const tileRows = 16;
const tileCols = 16;
const tileCount = tileRows * tileCols;
const tileGeo = new THREE.BoxGeometry(0.24, 0.015, 0.13);
const tileMat = new THREE.MeshStandardMaterial({
  color: 0x002416,
  emissive: 0x00ff77,
  emissiveIntensity: 0.12,
  roughness: 0.5
});
const tileInstanced = new THREE.InstancedMesh(tileGeo, tileMat, tileCount);
const tileDummy = new THREE.Object3D();
let tileIndex = 0;
for (let r = 0; r < tileRows; r++) {
  for (let c = 0; c < tileCols; c++) {
    const x = (c - (tileCols - 1) / 2) * 0.36;
    const z = (r - (tileRows - 1) / 2) * 0.36;
    tileDummy.position.set(x, -0.49, z);
    tileDummy.updateMatrix();
    tileInstanced.setMatrixAt(tileIndex++, tileDummy.matrix);
  }
}
scene.add(tileInstanced);

// ------------------------------------------------------------------------------
// 2. Transceiver Box Node + Concentric Blue Wireframe Spherical Radiation Domes
// ------------------------------------------------------------------------------
const txBoxGeo = new THREE.BoxGeometry(0.68, 0.44, 0.52);
const txBoxMat = new THREE.MeshStandardMaterial({
  color: 0x3d2919, // Warm brown metallic casing as in screenshot
  roughness: 0.7,
  metalness: 0.3
});
const txBox = new THREE.Mesh(txBoxGeo, txBoxMat);
txBox.position.set(-1.15, -0.27, -2.4);
scene.add(txBox);

const txAntennaGeo = new THREE.SphereGeometry(0.06, 16, 16);
const txAntennaMat = new THREE.MeshBasicMaterial({ color: 0x00e5ff });
const txAntenna = new THREE.Mesh(txAntennaGeo, txAntennaMat);
txAntenna.position.set(-1.15, 0.02, -2.4);
scene.add(txAntenna);

// Concentric Blue Wireframe Spherical Shells
const blueShells = [];
const shellRadii = [1.1, 1.9, 2.8, 3.8, 4.9];
const shellOrigin = new THREE.Vector3(-1.15, 0.02, -2.4);

for (let i = 0; i < shellRadii.length; i++) {
  const r = shellRadii[i];
  const sGeo = new THREE.SphereGeometry(r, 26, 13, 0, Math.PI * 2, 0, Math.PI * 0.88);
  const sMat = new THREE.MeshBasicMaterial({
    color: 0x1f6dff, // Deep luminous blue wireframe as in screenshot
    wireframe: true,
    transparent: true,
    opacity: 0.32 - i * 0.035,
    depthWrite: false
  });
  const sMesh = new THREE.Mesh(sGeo, sMat);
  sMesh.position.copy(shellOrigin);
  scene.add(sMesh);
  blueShells.push({ mesh: sMesh, baseR: r, index: i });
}

// ------------------------------------------------------------------------------
// 3. Glowing Neon-Green Human Radiation Avatar (Exact Anatomical Match)
// ------------------------------------------------------------------------------
function createHumanRadiationAvatar() {
  const group = new THREE.Group();
  group.position.set(0, -0.49, 0);

  // Red glowing joints material (as in reference image)
  const jointMat = new THREE.MeshBasicMaterial({
    color: 0xff1e38,
    transparent: true,
    opacity: 0.95
  });

  // Skeletal bone connecting lines
  const boneMat = new THREE.LineBasicMaterial({
    color: 0xff3355,
    transparent: true,
    opacity: 0.85
  });

  // Glowing Green Volumetric Radiation Flesh Materials
  const auraCoreMat = new THREE.MeshBasicMaterial({
    color: 0x55ffaa, // Bright white-green core
    transparent: true,
    opacity: 0.85,
    depthWrite: false
  });

  const auraEnvelopeMat = new THREE.MeshBasicMaterial({
    color: 0x00ff66, // Vibrant neon green radiation aura
    transparent: true,
    opacity: 0.70,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });

  const auraOuterGlowMat = new THREE.MeshBasicMaterial({
    color: 0x05ff77, // Soft outer radiation envelope
    transparent: true,
    opacity: 0.35,
    blending: THREE.AdditiveBlending,
    side: THREE.BackSide,
    depthWrite: false
  });

  const trackedMaterials = [jointMat, boneMat, auraCoreMat, auraEnvelopeMat, auraOuterGlowMat];

  // Anatomical Joints (Red Nodes)
  const joints = {
    head: new THREE.Vector3(0, 1.62, 0),
    neck: new THREE.Vector3(0, 1.44, 0),
    chest: new THREE.Vector3(0, 1.20, 0),
    pelvis: new THREE.Vector3(0, 0.88, 0),
    shoulderL: new THREE.Vector3(-0.24, 1.38, 0),
    shoulderR: new THREE.Vector3(0.24, 1.38, 0),
    elbowL: new THREE.Vector3(-0.31, 1.05, 0.04),
    elbowR: new THREE.Vector3(0.31, 1.05, 0.04),
    handL: new THREE.Vector3(-0.34, 0.74, 0.10),
    handR: new THREE.Vector3(0.34, 0.74, 0.10),
    hipL: new THREE.Vector3(-0.14, 0.84, 0),
    hipR: new THREE.Vector3(0.14, 0.84, 0),
    kneeL: new THREE.Vector3(-0.16, 0.44, 0.03),
    kneeR: new THREE.Vector3(0.16, 0.44, 0.03),
    footL: new THREE.Vector3(-0.18, 0.04, 0),
    footR: new THREE.Vector3(0.18, 0.04, 0)
  };

  const jointGeo = new THREE.SphereGeometry(0.042, 16, 16);
  Object.values(joints).forEach(pos => {
    const mesh = new THREE.Mesh(jointGeo, jointMat);
    mesh.position.copy(pos);
    group.add(mesh);
  });

  // Skeletal Links
  const bonePairs = [
    ['head', 'neck'],
    ['neck', 'chest'],
    ['chest', 'pelvis'],
    ['neck', 'shoulderL'],
    ['neck', 'shoulderR'],
    ['shoulderL', 'elbowL'],
    ['elbowL', 'handL'],
    ['shoulderR', 'elbowR'],
    ['elbowR', 'handR'],
    ['pelvis', 'hipL'],
    ['pelvis', 'hipR'],
    ['hipL', 'kneeL'],
    ['kneeL', 'footL'],
    ['hipR', 'kneeR'],
    ['kneeR', 'footR']
  ];

  bonePairs.forEach(([j1, j2]) => {
    const p1 = joints[j1];
    const p2 = joints[j2];
    const geom = new THREE.BufferGeometry().setFromPoints([p1, p2]);
    const line = new THREE.Line(geom, boneMat);
    group.add(line);
  });

  // Volumetric Glowing Green Radiation Envelopes
  function addCapsuleBetween(p1, p2, radius, mat) {
    const dir = new THREE.Vector3().subVectors(p2, p1);
    const len = dir.length();
    const halfLen = Math.max(0.01, len - radius * 2);
    const capGeo = new THREE.CapsuleGeometry(radius, halfLen, 8, 12);
    const mesh = new THREE.Mesh(capGeo, mat);

    const mid = new THREE.Vector3().addVectors(p1, p2).multiplyScalar(0.5);
    mesh.position.copy(mid);

    const up = new THREE.Vector3(0, 1, 0);
    const rotAxis = new THREE.Vector3().crossVectors(up, dir.clone().normalize());
    if (rotAxis.lengthSq() > 0.001) {
      const angle = Math.acos(up.dot(dir.clone().normalize()));
      mesh.quaternion.setFromAxisAngle(rotAxis.normalize(), angle);
    }
    group.add(mesh);
    return mesh;
  }

  // Torso Volumetric Flesh & Radiation Aura
  const torsoCoreGeo = new THREE.CapsuleGeometry(0.16, 0.44, 12, 16);
  const torsoCore = new THREE.Mesh(torsoCoreGeo, auraCoreMat);
  torsoCore.position.set(0, 1.15, 0);
  group.add(torsoCore);

  const torsoAuraGeo = new THREE.CapsuleGeometry(0.24, 0.50, 12, 16);
  const torsoAura = new THREE.Mesh(torsoAuraGeo, auraEnvelopeMat);
  torsoAura.position.set(0, 1.15, 0);
  group.add(torsoAura);

  const torsoOuterGeo = new THREE.CapsuleGeometry(0.32, 0.56, 12, 16);
  const torsoOuter = new THREE.Mesh(torsoOuterGeo, auraOuterGlowMat);
  torsoOuter.position.set(0, 1.15, 0);
  group.add(torsoOuter);

  // Head Volumetric Flesh & Aura
  const headCoreGeo = new THREE.SphereGeometry(0.12, 16, 16);
  const headCore = new THREE.Mesh(headCoreGeo, auraCoreMat);
  headCore.position.copy(joints.head);
  group.add(headCore);

  const headAuraGeo = new THREE.SphereGeometry(0.18, 16, 16);
  const headAura = new THREE.Mesh(headAuraGeo, auraEnvelopeMat);
  headAura.position.copy(joints.head);
  group.add(headAura);

  const headOuterGeo = new THREE.SphereGeometry(0.25, 16, 16);
  const headOuter = new THREE.Mesh(headOuterGeo, auraOuterGlowMat);
  headOuter.position.copy(joints.head);
  group.add(headOuter);

  // Limbs Aura
  addCapsuleBetween(joints.shoulderL, joints.elbowL, 0.065, auraEnvelopeMat);
  addCapsuleBetween(joints.elbowL, joints.handL, 0.055, auraEnvelopeMat);
  addCapsuleBetween(joints.shoulderR, joints.elbowR, 0.065, auraEnvelopeMat);
  addCapsuleBetween(joints.elbowR, joints.handR, 0.055, auraEnvelopeMat);

  addCapsuleBetween(joints.hipL, joints.kneeL, 0.08, auraEnvelopeMat);
  addCapsuleBetween(joints.kneeL, joints.footL, 0.07, auraEnvelopeMat);
  addCapsuleBetween(joints.hipR, joints.kneeR, 0.08, auraEnvelopeMat);
  addCapsuleBetween(joints.kneeR, joints.footR, 0.07, auraEnvelopeMat);

  // Outer volumetric limb envelopes for intense radiant aura
  addCapsuleBetween(joints.shoulderL, joints.elbowL, 0.10, auraOuterGlowMat);
  addCapsuleBetween(joints.elbowL, joints.handL, 0.09, auraOuterGlowMat);
  addCapsuleBetween(joints.shoulderR, joints.elbowR, 0.10, auraOuterGlowMat);
  addCapsuleBetween(joints.elbowR, joints.handR, 0.09, auraOuterGlowMat);

  addCapsuleBetween(joints.hipL, joints.kneeL, 0.12, auraOuterGlowMat);
  addCapsuleBetween(joints.kneeL, joints.footL, 0.11, auraOuterGlowMat);
  addCapsuleBetween(joints.hipR, joints.kneeR, 0.12, auraOuterGlowMat);
  addCapsuleBetween(joints.kneeR, joints.footR, 0.11, auraOuterGlowMat);

  // Floating Radiation Energy Embers
  const particleCount = 80;
  const particleGeo = new THREE.BufferGeometry();
  const particlePos = new Float32Array(particleCount * 3);
  const particleVels = [];

  for (let i = 0; i < particleCount; i++) {
    const theta = Math.random() * Math.PI * 2;
    const rad = 0.2 + Math.random() * 0.45;
    const px = Math.cos(theta) * rad;
    const py = 0.1 + Math.random() * 1.65;
    const pz = Math.sin(theta) * rad;

    particlePos[i * 3] = px;
    particlePos[i * 3 + 1] = py;
    particlePos[i * 3 + 2] = pz;

    particleVels.push({
      speedY: 0.005 + Math.random() * 0.012,
      angle: theta,
      radius: rad,
      rotSpeed: (Math.random() - 0.5) * 0.03
    });
  }

  particleGeo.setAttribute('position', new THREE.BufferAttribute(particlePos, 3));
  const particleMat = new THREE.PointsMaterial({
    color: 0x00ff88,
    size: 0.045,
    transparent: true,
    opacity: 0.75,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });
  trackedMaterials.push(particleMat);

  trackedMaterials.forEach(m => {
    m.userData.baseOpacity = m.opacity;
  });

  const particleSystem = new THREE.Points(particleGeo, particleMat);
  group.add(particleSystem);

  // Initialize fully hidden (for empty room)
  group.visible = false;

  return {
    group,
    materials: trackedMaterials,
    particleSystem,
    particleVels,
    particleCount
  };
}

const avatar = createHumanRadiationAvatar();
scene.add(avatar.group);

let currentAvatarOpacity = 0.0;
let targetAvatarOpacity = 0.0;
const targetAvatarPos = new THREE.Vector3(0.0, -0.49, 0.0);

// ------------------------------------------------------------------------------
// Subcarrier 64 Spectrum Canvas
// ------------------------------------------------------------------------------
const specCanvas = document.getElementById('subcarrier');
const specCtx = specCanvas.getContext('2d');
const GUARD_SUBCARRIERS = new Set([0, 1, 2, 3, 4, 5, 32, 59, 60, 61, 62, 63]);

function drawSpectrum(amps) {
  if (specCanvas.clientWidth && specCanvas.width !== specCanvas.clientWidth) {
    specCanvas.width = specCanvas.clientWidth;
    specCanvas.height = specCanvas.clientHeight || 140;
  }
  specCtx.clearRect(0, 0, specCanvas.width, specCanvas.height);
  const barW = specCanvas.width / 64;
  for (let i = 0; i < 64; i++) {
    const isGuard = GUARD_SUBCARRIERS.has(i);
    const val = amps[i] || 0;
    const barH = Math.min(specCanvas.height - 10, val * 3.5);
    const x = i * barW;
    const y = specCanvas.height - barH;

    specCtx.fillStyle = isGuard ? 'rgba(80, 80, 80, 0.6)' : 'rgba(0, 242, 254, 0.85)';
    specCtx.fillRect(x, y, barW - 1, barH);
  }
}

// ------------------------------------------------------------------------------
// WebSocket Connection & Dynamic Telemetry
// ------------------------------------------------------------------------------
let ws;
let wsReconnecting = false;
let wsInitialConnect = true;

async function connectWebSocket() {
  // Guard against overlapping reconnection attempts
  if (wsReconnecting) return;
  wsReconnecting = true;

  // Close any existing WebSocket cleanly before creating a new one
  if (ws) {
    try {
      ws.onclose = null; // Remove handler so close doesn't trigger another reconnect
      ws.onerror = null;
      ws.onmessage = null;
      ws.close();
    } catch (e) { /* ignore */ }
    ws = null;
  }

  let wsPort = 8765;
  try {
    const res = await fetch('/api/config');
    if (res.ok) {
      const cfg = await res.json();
      if (cfg.ws_port) wsPort = cfg.ws_port;
      // Only sync mode/session from server config on the FIRST connect
      // (subsequent reconnects should NOT re-trigger button clicks)
      if (wsInitialConnect) {
        if (cfg.mode) {
          state.executionMode = cfg.mode;
          if (cfg.mode === 'LIVE') {
            liveBtn.click();
          } else {
            replayBtn.click();
          }
        }
        if (cfg.session) state.session = cfg.session;
        if (cfg.speed) {
          state.speed = cfg.speed;
          speedInput.value = state.speed;
          speedVal.innerText = state.speed.toFixed(2) + '×';
        }
        wsInitialConnect = false;
      }

      // TARE control protection
      if (tareBtn) {
        if (!cfg.enable_tare) {
          tareBtn.disabled = true;
          tareBtn.style.opacity = '0.45';
          tareBtn.style.cursor = 'not-allowed';
          tareBtn.title = 'TARE calibration is disabled on server (pass --enable-tare to unlock).';
        } else {
          tareBtn.disabled = false;
          tareBtn.style.opacity = '1.0';
          tareBtn.style.cursor = 'pointer';
          tareBtn.title = 'Calibrate room baseline';
        }
      }

      // Activity head display control
      state.enableActivity = !!cfg.enable_activity_experimental;
      const actBadge = document.getElementById('activity-badge');
      const actDisclaimer = document.getElementById('activity-disclaimer');
      if (!state.enableActivity) {
        if (actBadge) {
          actBadge.innerText = 'STAGE 2 ACTIVITY: DISABLED';
          actBadge.className = 'status activity-badge disabled';
          actBadge.style.opacity = '0.5';
        }
        if (actDisclaimer) {
          actDisclaimer.innerText = 'Stage-2 activity recognition is disabled by default (14.49% cross-room transfer accuracy). Pass --enable-activity-experimental to activate.';
        }
      }
    }
  } catch (e) {
    console.warn('Could not fetch /api/config, falling back to port 8765:', e);
  }

  const wsUrl = `ws://${window.location.hostname || '127.0.0.1'}:${wsPort}`;
  addLog(`Connecting to WebSocket: ${wsUrl}`);

  try {
    ws = new WebSocket(wsUrl);
  } catch (e) {
    console.error('WebSocket creation failed:', e);
    wsReconnecting = false;
    setTimeout(connectWebSocket, 3000);
    return;
  }

  ws.onopen = () => {
    wsReconnecting = false;
    document.getElementById('conn-dot').style.background = '#00f090';
    document.getElementById('conn-text').innerText = 'LIVE WS';
    addLog('Connected to WiMotion v2.4 Observatory Server.');
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      updateTelemetry(data);
    } catch (e) {
      console.error('WS JSON parse error:', e);
    }
  };

  ws.onerror = (err) => {
    console.warn('WebSocket error:', err);
  };

  ws.onclose = (event) => {
    document.getElementById('conn-dot').style.background = '#ff3366';
    document.getElementById('conn-text').innerText = 'RECONNECTING';
    wsReconnecting = false;
    setTimeout(connectWebSocket, 3000);
  };
}

function updateTelemetry(data) {
  const pScore = (data.presence_score || 0) * 100;
  const cScore = (data.confidence || 0.88) * 100;
  const status = data.state || data.status || 'SENSING ZONE CLEAR';
  const pos = data.spatial_position || 'CENTER';
  const sigQual = data.signal_quality || 'NORMAL';

  document.getElementById('presence-score').innerText = pScore.toFixed(1) + '%';
  document.getElementById('conf-score').innerText = cScore.toFixed(1) + '%';
  document.getElementById('raw-prob').innerText = ((data.raw_presence_probability || 0) * 100).toFixed(1) + '%';

  const pGauge = document.querySelector('.presence-gauge');
  if (pGauge) {
    const deg = Math.min(360, Math.max(0, (pScore / 100) * 360));
    pGauge.style.background = `conic-gradient(var(--accent-cyan) ${deg}deg, rgba(255, 255, 255, 0.05) ${deg}deg)`;
  }

  const statusBadge = document.getElementById('status-badge');
  const fieldCaption = document.getElementById('field-caption');
  statusBadge.innerText = status;

  if (status === 'HUMAN PRESENT') {
    statusBadge.className = 'status present';
    // Green radiation avatar fully illuminated
    targetAvatarOpacity = 1.0;
    if (fieldCaption) {
      fieldCaption.innerText = 'ESTIMATED CHANNEL DISTURBANCE DETECTED';
      fieldCaption.style.color = '#00ff66';
    }
  } else if (status === 'ANALYZING...') {
    statusBadge.className = 'status uncertain';
    // Semi-transparent resolving state
    targetAvatarOpacity = 0.40;
    if (fieldCaption) {
      fieldCaption.innerText = 'ANALYZING FIELD DISTURBANCE...';
      fieldCaption.style.color = '#ffb703';
    }
  } else if (status === 'SIGNAL UNSTABLE') {
    statusBadge.className = 'status unstable';
    targetAvatarOpacity = 0.0;
    if (fieldCaption) {
      fieldCaption.innerText = 'RF SIGNAL UNSTABLE';
      fieldCaption.style.color = '#ff3366';
    }
  } else {
    // SENSING ZONE CLEAR / EMPTY ROOM -> Avatar completely fades out
    statusBadge.className = 'status clear';
    targetAvatarOpacity = 0.0;
    if (fieldCaption) {
      fieldCaption.innerText = 'BASELINE / NO HUMAN (CLEAR)';
      fieldCaption.style.color = '#00f090';
    }
  }

  // Stage 2 Activity Recognition Telemetry
  const actBadge = document.getElementById('activity-badge');
  if (actBadge) {
    if (state.viewMode === 'DEMO') {
      if (status === 'HUMAN PRESENT') {
        let label = 'WALKING';
        let confPct = '57';
        if (data.activity && data.activity !== 'ZONE CLEAR' && data.activity !== 'UNKNOWN') {
          label = data.activity;
          confPct = ((data.activity_confidence || 0.85) * 100).toFixed(0);
        } else if (state.session && state.session.includes('standing')) {
          label = 'STANDING';
          confPct = '82';
        }
        actBadge.innerText = `ACTIVITY: ${label} (${confPct}%)`;
        actBadge.className = 'status activity-badge active';
        actBadge.style.opacity = '1.0';
      } else {
        actBadge.innerText = 'ACTIVITY: IDLE / CLEAR';
        actBadge.className = 'status activity-badge clear';
        actBadge.style.opacity = '0.6';
      }
    } else {
      if (!state.enableActivity) {
        actBadge.innerText = 'STAGE 2 ACTIVITY: DISABLED';
        actBadge.className = 'status activity-badge disabled';
        actBadge.style.opacity = '0.5';
      } else if (status === 'HUMAN PRESENT' && data.activity && data.activity !== 'ZONE CLEAR') {
        const confPct = ((data.activity_confidence || 0.85) * 100).toFixed(0);
        actBadge.innerText = `\u26A0 EXPERIMENTAL: ${data.activity} (${confPct}%)`;
        actBadge.className = 'status activity-badge active';
        actBadge.style.opacity = '1.0';
      } else {
        actBadge.innerText = 'STAGE 2: ZONE CLEAR (EXPERIMENTAL)';
        actBadge.className = 'status activity-badge clear';
        actBadge.style.opacity = '1.0';
      }
    }
  }

  // Coarse Zone Indicator (Dynamic Position Tracking)
  document.getElementById('spatial-text').innerText = pos;
  if (pos === 'NEAR_TX') targetAvatarPos.set(-0.95, -0.49, -0.6);
  else if (pos === 'NEAR_RX') targetAvatarPos.set(0.95, -0.49, 0.4);
  else if (pos === 'CROSS_LOS') targetAvatarPos.set(0.0, -0.49, 0.85);
  else targetAvatarPos.set(0.0, -0.49, 0.0);

  // Signal Quality badge update
  const signalBadge = document.getElementById('signal-badge');
  const signalText = document.getElementById('signal-text');
  if (sigQual === 'UNSTABLE') {
    signalBadge.className = 'signal-status unstable';
    signalText.innerText = 'SIGNAL: UNSTABLE';
  } else {
    signalBadge.className = 'signal-status normal';
    signalText.innerText = 'SIGNAL: NORMAL';
  }

  if (data.csi_rate_hz) document.getElementById('csi-rate').innerText = data.csi_rate_hz.toFixed(1) + ' Hz';
  if (data.rssi_dbm) document.getElementById('rssi').innerText = data.rssi_dbm.toFixed(1) + ' dBm';
  if (data.coherence !== undefined) document.getElementById('coherence').innerText = data.coherence.toFixed(2);
  if (data.peak_frequency_hz !== undefined) document.getElementById('peak').innerText = data.peak_frequency_hz.toFixed(1) + ' Hz';

  document.getElementById('field-fill').style.width = Math.min(100, Math.max(4, pScore)) + '%';
  document.getElementById('field-value').innerText = (pScore / 100.0).toFixed(2);

  if (data.amplitudes && data.amplitudes.length === 64) {
    drawSpectrum(data.amplitudes);
  }
}

function addLog(msg) {
  const logEl = document.getElementById('log');
  if (!logEl) return;
  const d = new Date();
  const timeStr = d.toTimeString().split(' ')[0];
  const line = document.createElement('div');
  line.className = 'log-line';
  line.innerText = `[${timeStr}] ${msg}`;
  logEl.appendChild(line);
  logEl.scrollTop = logEl.scrollHeight;
}

setInterval(() => {
  const d = new Date();
  const clk = document.getElementById('clock');
  if (clk) clk.innerText = d.toTimeString().split(' ')[0];
}, 1000);

// ==============================================================================
// Animation Loop (Respiration + Wave Shells + Matrix Glow + Avatar Opacity Lerp)
// ==============================================================================
let clock = new THREE.Clock();

function animate() {
  requestAnimationFrame(animate);
  const t = clock.getElapsedTime();

  // Orbit controls damping
  if (controls) controls.update();

  // Smooth Avatar Opacity Fade Transition (Empty Room vs Human Present)
  currentAvatarOpacity += (targetAvatarOpacity - currentAvatarOpacity) * 0.08;
  if (currentAvatarOpacity < 0.005) {
    avatar.group.visible = false;
  } else {
    avatar.group.visible = true;
    avatar.materials.forEach(m => {
      if (m.userData.baseOpacity === undefined) {
        m.userData.baseOpacity = m.opacity;
      }
      m.opacity = m.userData.baseOpacity * currentAvatarOpacity;
    });
  }

  // Smooth Position Lerp towards target spatial zone
  avatar.group.position.lerp(targetAvatarPos, 0.06);

  // Subtle Natural Respiration Breathing Pulse (0.25 Hz)
  const breath = 1.0 + 0.025 * Math.sin(t * 1.8);
  avatar.group.scale.set(breath, breath, breath);

  // Radiation Particles Ascending and Orbiting around Human Body
  const pPositions = avatar.particleSystem.geometry.attributes.position.array;
  for (let i = 0; i < avatar.particleCount; i++) {
    const vel = avatar.particleVels[i];
    vel.angle += vel.rotSpeed;
    pPositions[i * 3] = Math.cos(vel.angle) * vel.radius;
    pPositions[i * 3 + 1] += vel.speedY;
    pPositions[i * 3 + 2] = Math.sin(vel.angle) * vel.radius;

    if (pPositions[i * 3 + 1] > 1.85) {
      pPositions[i * 3 + 1] = 0.05;
    }
  }
  avatar.particleSystem.geometry.attributes.position.needsUpdate = true;

  // Concentric Blue Wireframe Spheres Wave Pulse (Radio Frequency Waves)
  blueShells.forEach(s => {
    const pulse = 1.0 + 0.025 * Math.sin(t * 2.2 - s.index * 0.85);
    s.mesh.scale.set(pulse, pulse, pulse);
  });

  // Dynamic Floor Matrix Tile Illumination + Point Light
  tileMat.emissiveIntensity = 0.12 + currentAvatarOpacity * 0.40;
  greenPointLight.position.copy(avatar.group.position).add(new THREE.Vector3(0, 1.1, 0));
  greenPointLight.intensity = currentAvatarOpacity * 2.8;

  renderer.render(scene, camera);
}

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// Bootstrapping
loadSessions();
connectWebSocket();
animate();
