'use client'

import { useEffect, useRef } from 'react'
import * as THREE from 'three'

// Ashima simplex noise (MIT) — displaces the orb surface.
const SIMPLEX_NOISE = `
vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
float snoise(vec3 v) {
    const vec2 C = vec2(1.0/6.0, 1.0/3.0);
    const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
    vec3 i = floor(v + dot(v, C.yyy));
    vec3 x0 = v - i + dot(i, C.xxx);
    vec3 g = step(x0.yzx, x0.xyz);
    vec3 l = 1.0 - g;
    vec3 i1 = min(g.xyz, l.zxy);
    vec3 i2 = max(g.xyz, l.zxy);
    vec3 x1 = x0 - i1 + C.xxx;
    vec3 x2 = x0 - i2 + C.yyy;
    vec3 x3 = x0 - D.yyy;
    i = mod289(i);
    vec4 p = permute(permute(permute(
                i.z + vec4(0.0, i1.z, i2.z, 1.0))
            + i.y + vec4(0.0, i1.y, i2.y, 1.0))
            + i.x + vec4(0.0, i1.x, i2.x, 1.0));
    float n_ = 0.142857142857;
    vec3 ns = n_ * D.wyz - D.xzx;
    vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
    vec4 x_ = floor(j * ns.z);
    vec4 y_ = floor(j - 7.0 * x_);
    vec4 x = x_ * ns.x + ns.yyyy;
    vec4 y = y_ * ns.x + ns.yyyy;
    vec4 h = 1.0 - abs(x) - abs(y);
    vec4 b0 = vec4(x.xy, y.xy);
    vec4 b1 = vec4(x.zw, y.zw);
    vec4 s0 = floor(b0) * 2.0 + 1.0;
    vec4 s1 = floor(b1) * 2.0 + 1.0;
    vec4 sh = -step(h, vec4(0.0));
    vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
    vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
    vec3 p0 = vec3(a0.xy, h.x);
    vec3 p1 = vec3(a0.zw, h.y);
    vec3 p2 = vec3(a1.xy, h.z);
    vec3 p3 = vec3(a1.zw, h.w);
    vec4 norm = taylorInvSqrt(vec4(dot(p0, p0), dot(p1, p1), dot(p2, p2), dot(p3, p3)));
    p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
    vec4 m = max(0.6 - vec4(dot(x0, x0), dot(x1, x1), dot(x2, x2), dot(x3, x3)), 0.0);
    m = m * m;
    return 42.0 * dot(m * m, vec4(dot(p0, x0), dot(p1, x1), dot(p2, x2), dot(p3, x3)));
}`

const VERTEX_SHADER = `
uniform float uTime;
uniform float uActivity;
varying vec3 vNormal;
varying vec3 vPosition;
${SIMPLEX_NOISE}
void main() {
    vNormal = normal;
    vPosition = position;
    float amp = 0.10 + uActivity * 0.22;
    float speed = 0.35 + uActivity * 0.9;
    float displacement = snoise(position * 2.0 + uTime * speed) * amp;
    vec3 newPosition = position + normal * displacement;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(newPosition, 1.0);
}`

const FRAGMENT_SHADER = `
uniform vec3 uColor;
uniform vec3 uLightPos;
uniform float uActivity;
varying vec3 vNormal;
varying vec3 vPosition;
void main() {
    vec3 normal = normalize(vNormal);
    vec3 lightDir = normalize(uLightPos - vPosition);
    float diffuse = max(dot(normal, lightDir), 0.0);
    float fresnel = pow(1.0 - abs(dot(normal, vec3(0.0, 0.0, 1.0))), 2.0);
    float energy = 0.55 + uActivity * 0.65;
    vec3 finalColor = uColor * (diffuse * 0.6 + fresnel * 0.9) * energy;
    float alpha = clamp(diffuse * 0.35 + fresnel * 0.85, 0.06, 1.0);
    gl_FragColor = vec4(finalColor, alpha);
}`

/**
 * The diagnostic engine core — a noise-displaced wireframe orb in the brand
 * accent, lit from the cursor. `active` spins it up while analysis runs.
 */
export default function EngineOrb({ active = false }: { active?: boolean }) {
  const mountRef = useRef<HTMLDivElement>(null)
  const activityTarget = useRef(0)

  useEffect(() => {
    activityTarget.current = active ? 1 : 0
  }, [active])

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(75, mount.clientWidth / mount.clientHeight, 0.1, 1000)
    camera.position.z = 3

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setSize(mount.clientWidth, mount.clientHeight)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    mount.appendChild(renderer.domElement)

    const geometry = new THREE.IcosahedronGeometry(1.35, 28)
    const material = new THREE.ShaderMaterial({
      uniforms: {
        uTime: { value: 0 },
        uActivity: { value: 0 },
        uLightPos: { value: new THREE.Vector3(0, 0, 5) },
        uColor: { value: new THREE.Color('#e0e0e0') },
      },
      vertexShader: VERTEX_SHADER,
      fragmentShader: FRAGMENT_SHADER,
      wireframe: true,
      transparent: true,
    })
    const mesh = new THREE.Mesh(geometry, material)
    scene.add(mesh)

    let frameId = 0
    const animate = (t: number) => {
      material.uniforms.uTime.value = t * 0.001
      // ease activity toward its target so idle→analyzing ramps smoothly
      const current = material.uniforms.uActivity.value
      material.uniforms.uActivity.value = current + (activityTarget.current - current) * 0.03
      mesh.rotation.y += 0.0011 + current * 0.004
      mesh.rotation.x += 0.0004
      renderer.render(scene, camera)
      frameId = requestAnimationFrame(animate)
    }

    if (reducedMotion) {
      renderer.render(scene, camera)
    } else {
      frameId = requestAnimationFrame(animate)
    }

    const handleResize = () => {
      camera.aspect = mount.clientWidth / mount.clientHeight
      camera.updateProjectionMatrix()
      renderer.setSize(mount.clientWidth, mount.clientHeight)
    }

    // Project the cursor onto the z=0 plane and light the orb from there
    const handleMouseMove = (e: MouseEvent) => {
      const x = (e.clientX / window.innerWidth) * 2 - 1
      const y = -(e.clientY / window.innerHeight) * 2 + 1
      const vec = new THREE.Vector3(x, y, 0.5).unproject(camera)
      const dir = vec.sub(camera.position).normalize()
      const dist = -camera.position.z / dir.z
      const pos = camera.position.clone().add(dir.multiplyScalar(dist))
      pos.z = 2.5
      material.uniforms.uLightPos.value.copy(pos)
    }

    window.addEventListener('resize', handleResize)
    if (!reducedMotion) window.addEventListener('mousemove', handleMouseMove)

    return () => {
      cancelAnimationFrame(frameId)
      window.removeEventListener('resize', handleResize)
      window.removeEventListener('mousemove', handleMouseMove)
      mount.removeChild(renderer.domElement)
      geometry.dispose()
      material.dispose()
      renderer.dispose()
    }
  }, [])

  return (
    <div
      ref={mountRef}
      className="absolute inset-0 w-full h-full opacity-40"
      aria-hidden="true"
    />
  )
}
