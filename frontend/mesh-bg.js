/**
 * 21st.dev Mesh Drift WebGL1 Background
 * AuditTrail AP — Palette: Nightshift (#10131A) & Laser Lemon (#EFFF4F)
 * Settings: speed=67, zoom=40, intensity=56, warp=32, contrast=63, brightness=50, vignette=15, grain=28
 * Cursor: swirl, strength=73, radius=36
 */
(function() {
  const canvas = document.createElement('canvas');
  canvas.id = 'mesh-drift-canvas';
  canvas.style.position = 'fixed';
  canvas.style.top = '0';
  canvas.style.left = '0';
  canvas.style.width = '100vw';
  canvas.style.height = '100vh';
  canvas.style.zIndex = '-1';
  canvas.style.pointerEvents = 'none';
  canvas.style.opacity = '0.9';
  document.body.prepend(canvas);

  const gl = canvas.getContext('webgl', { alpha: false, depth: false, antialias: false, powerPreference: 'low-power' }) ||
             canvas.getContext('experimental-webgl');

  if (!gl) {
    console.warn('WebGL not supported for Mesh Drift background.');
    return;
  }

  const vsSource = `
    attribute vec2 a_position;
    varying vec2 v_uv;
    void main() {
      v_uv = (a_position + 1.0) * 0.5;
      gl_Position = vec4(a_position, 0.0, 1.0);
    }
  `;

  const fsSource = `
    precision highp float;
    varying vec2 v_uv;

    uniform vec2 u_resolution;
    uniform float u_time;
    uniform vec2 u_mouse;
    uniform float u_motion_allowed;

    // Palette: Nightshift dominant, Laser Lemon subtle accents
    const vec3 c_nightshift = vec3(0.0627, 0.0745, 0.102);  // #10131A
    const vec3 c_laserlemon  = vec3(0.937, 1.0, 0.310);     // #EFFF4F
    const vec3 c_deepslate   = vec3(0.086, 0.106, 0.145);  // #161B25

    // Simplex Noise Hash
    vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec2 mod289(vec2 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec3 permute(vec3 x) { return mod289(((x*34.0)+1.0)*x); }

    float snoise(vec2 v) {
      const vec4 C = vec4(0.211324865405187, 0.366025403784439,
                         -0.577350269189626, 0.024390243902439);
      vec2 i  = floor(v + dot(v, C.yy) );
      vec2 x0 = v -   i + dot(i, C.xx);
      vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
      vec4 x12 = x0.xyxy + C.xxzz;
      x12.xy -= i1;
      i = mod289(i);
      vec3 p = permute( permute( i.y + vec3(0.0, i1.y, 1.0 ))
            + i.x + vec3(0.0, i1.x, 1.0 ));
      vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
      m = m*m ;
      m = m*m ;
      vec3 x = 2.0 * fract(p * C.www) - 1.0;
      vec3 h = abs(x) - 0.5;
      vec3 ox = floor(x + 0.5);
      vec3 a0 = x - ox;
      m *= 1.79284291400159 - 0.85373472095314 * ( a0*a0 + h*h );
      vec3 g;
      g.x  = a0.x  * x0.x  + h.x  * x0.y;
      g.yz = a0.yz * x12.xz + h.yz * x12.yw;
      return 130.0 * dot(m, g);
    }

    // Pseudo-random grain
    float rand(vec2 co) {
      return fract(sin(dot(co.xy ,vec2(12.9898,78.233))) * 43758.5453);
    }

    void main() {
      vec2 st = gl_FragCoord.xy / u_resolution.xy;
      float aspect = u_resolution.x / u_resolution.y;
      vec2 uv = st;
      uv.x *= aspect;

      // Mouse swirl effect (strength=73, radius=36)
      vec2 mouse = u_mouse;
      mouse.x *= aspect;
      vec2 toMouse = uv - mouse;
      float distToMouse = length(toMouse);
      float swirlRadius = 0.36;
      if (distToMouse < swirlRadius && u_motion_allowed > 0.5) {
        float angle = (1.0 - distToMouse / swirlRadius) * 0.73 * 3.14159;
        float s = sin(angle);
        float c = cos(angle);
        toMouse = vec2(toMouse.x * c - toMouse.y * s, toMouse.x * s + toMouse.y * c);
        uv = mouse + toMouse;
      }

      // Settings: speed=67, zoom=40, warp=32, intensity=56
      float t = u_time * 0.067 * u_motion_allowed;
      vec2 q = uv * 1.4; // zoom

      // Domain warping
      vec2 warp = vec2(
        snoise(q + vec2(t * 0.3, t * 0.2)),
        snoise(q + vec2(-t * 0.2, t * 0.4))
      ) * 0.32; // warp=32

      vec2 p = q + warp;
      float n1 = snoise(p + vec2(t * 0.15, -t * 0.1)) * 0.5 + 0.5;
      float n2 = snoise(p * 1.5 - vec2(t * 0.2, t * 0.25)) * 0.5 + 0.5;

      float pattern = mix(n1, n2, 0.5);

      // Contrast (63) & Brightness (50)
      pattern = clamp((pattern - 0.5) * 1.63 + 0.5, 0.0, 1.0);

      // Color mapping: Dominant Nightshift with controlled Laser Lemon energy bands
      vec3 col = c_nightshift;
      // Soft ambient depth
      col = mix(col, c_deepslate, smoothstep(0.1, 0.6, pattern));
      // Laser lemon accents (intensity 56, controlled and subtle)
      float accentMask = smoothstep(0.68, 0.95, pattern) * 0.38;
      col = mix(col, c_laserlemon, accentMask);

      // Vignette (15)
      vec2 vigUV = st * (1.0 - st.yx);
      float vig = vigUV.x * vigUV.y * 15.0;
      vig = clamp(pow(vig, 0.15), 0.0, 1.0);
      col *= vig;

      // Subtle grain (28)
      float grain = (rand(gl_FragCoord.xy + fract(u_time * 10.0)) - 0.5) * 0.028;
      col += vec3(grain);

      gl_FragColor = vec4(col, 1.0);
    }
  `;

  function createShader(gl, type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      console.error('Shader compile failed:', gl.getShaderInfoLog(shader));
      gl.deleteShader(shader);
      return null;
    }
    return shader;
  }

  const vs = createShader(gl, gl.VERTEX_SHADER, vsSource);
  const fs = createShader(gl, gl.FRAGMENT_SHADER, fsSource);
  if (!vs || !fs) return;

  const program = gl.createProgram();
  gl.attachShader(program, vs);
  gl.attachShader(program, fs);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    console.error('Program link failed:', gl.getProgramInfoLog(program));
    return;
  }

  const positionBuffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
    -1.0, -1.0,
     1.0, -1.0,
    -1.0,  1.0,
    -1.0,  1.0,
     1.0, -1.0,
     1.0,  1.0,
  ]), gl.STATIC_DRAW);

  const aPosition = gl.getAttribLocation(program, 'a_position');
  const uResolution = gl.getUniformLocation(program, 'u_resolution');
  const uTime = gl.getUniformLocation(program, 'u_time');
  const uMouse = gl.getUniformLocation(program, 'u_mouse');
  const uMotionAllowed = gl.getUniformLocation(program, 'u_motion_allowed');

  let mouseX = 0.5;
  let mouseY = 0.5;
  let targetMouseX = 0.5;
  let targetMouseY = 0.5;

  window.addEventListener('mousemove', (e) => {
    targetMouseX = e.clientX / window.innerWidth;
    targetMouseY = 1.0 - (e.clientY / window.innerHeight);
  }, { passive: true });

  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let motionAllowed = prefersReducedMotion.matches ? 0.0 : 1.0;
  prefersReducedMotion.addEventListener('change', (e) => {
    motionAllowed = e.matches ? 0.0 : 1.0;
  });

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = window.innerWidth;
    const height = window.innerHeight;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    gl.viewport(0, 0, canvas.width, canvas.height);
  }
  window.addEventListener('resize', resize, { passive: true });
  resize();

  let startTime = performance.now();
  let animationId = null;

  function render(now) {
    if (document.hidden) {
      animationId = null;
      return;
    }

    const elapsed = (now - startTime) * 0.001;

    // Smooth mouse lerp
    mouseX += (targetMouseX - mouseX) * 0.05;
    mouseY += (targetMouseY - mouseY) * 0.05;

    gl.useProgram(program);
    gl.enableVertexAttribArray(aPosition);
    gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
    gl.vertexAttribPointer(aPosition, 2, gl.FLOAT, false, 0, 0);

    gl.uniform2f(uResolution, canvas.width, canvas.height);
    gl.uniform1f(uTime, elapsed);
    gl.uniform2f(uMouse, mouseX, mouseY);
    gl.uniform1f(uMotionAllowed, motionAllowed);

    gl.drawArrays(gl.TRIANGLES, 0, 6);

    animationId = requestAnimationFrame(render);
  }

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && !animationId) {
      startTime = performance.now();
      animationId = requestAnimationFrame(render);
    }
  });

  animationId = requestAnimationFrame(render);
})();
