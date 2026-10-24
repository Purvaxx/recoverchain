import { useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { useSpring } from '@react-spring/three';
import * as THREE from 'three';

/**
 * Ambient brand motion for the guided workflow — NOT a data visualisation.
 * A field of points that starts scattered and contracts / brightens as the
 * run progresses (0 = step 1, 1 = step 11). Purely decorative; sits behind the
 * content, ignores pointer events, and is skipped entirely for users who
 * prefer reduced motion.
 */

const COUNT = 2600;

const VERT = /* glsl */ `
  uniform float uProgress;
  uniform float uTime;
  attribute float aSeed;
  varying float vGlow;
  void main() {
    vec3 p = position;
    float contract = mix(1.0, 0.34, uProgress);
    p *= contract;
    // gentle drift
    p.x += sin(uTime * 0.15 + aSeed * 6.2831) * 0.06 * (1.0 - uProgress);
    p.y += cos(uTime * 0.12 + aSeed * 6.2831) * 0.06 * (1.0 - uProgress);
    vGlow = mix(0.18, 0.7, uProgress) * (0.35 + 0.65 * aSeed);
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    gl_PointSize = (mix(1.0, 1.7, uProgress) + aSeed * 0.9) * (300.0 / -mv.z);
    gl_Position = projectionMatrix * mv;
  }
`;

const FRAG = /* glsl */ `
  precision mediump float;
  varying float vGlow;
  void main() {
    vec2 d = gl_PointCoord - 0.5;
    float a = smoothstep(0.5, 0.0, length(d));
    // --accent-ish blue, warming very slightly as it resolves
    vec3 col = mix(vec3(0.30, 0.47, 1.0), vec3(0.45, 0.85, 0.78), vGlow * 0.35);
    gl_FragColor = vec4(col, a * vGlow * 0.35);
  }
`;

function Field({ progress }: { progress: number }) {
    const mat = useRef<THREE.ShaderMaterial>(null);
    const grp = useRef<THREE.Points>(null);

    const { geo, uniforms } = useMemo(() => {
        const pos = new Float32Array(COUNT * 3);
        const seed = new Float32Array(COUNT);
        for (let i = 0; i < COUNT; i++) {
            // loose spherical shell
            const r = 3.4 * Math.cbrt(0.35 + 0.65 * Math.random());
            const t = Math.random() * Math.PI * 2;
            const u = Math.random() * 2 - 1;
            const s = Math.sqrt(1 - u * u);
            pos[i * 3] = r * s * Math.cos(t) * 1.6;
            pos[i * 3 + 1] = r * s * Math.sin(t);
            pos[i * 3 + 2] = r * u;
            seed[i] = Math.random();
        }
        const g = new THREE.BufferGeometry();
        g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
        g.setAttribute('aSeed', new THREE.BufferAttribute(seed, 1));
        return { geo: g, uniforms: { uProgress: { value: 0 }, uTime: { value: 0 } } };
    }, []);

    // physics-eased progress
    const spring = useSpring({ p: progress, config: { mass: 1, tension: 90, friction: 26 } });

    useFrame((_, dt) => {
        if (mat.current) {
            mat.current.uniforms.uTime.value += dt;
            mat.current.uniforms.uProgress.value = spring.p.get();
        }
        if (grp.current) grp.current.rotation.y += dt * 0.03;
    });

    return (
        <points ref={grp}>
            <primitive object={geo} attach="geometry" />
            <shaderMaterial
                ref={mat}
                vertexShader={VERT}
                fragmentShader={FRAG}
                uniforms={uniforms}
                transparent
                depthWrite={false}
                blending={THREE.AdditiveBlending}
            />
        </points>
    );
}

export default function Backdrop({ progress }: { progress: number }) {
    return (
        <Canvas
            className="!absolute inset-0 -z-10"
            camera={{ position: [0, 0, 8], fov: 55 }}
            gl={{ antialias: true, alpha: true }}
            dpr={[1, 1.75]}
        >
            <Field progress={progress} />
        </Canvas>
    );
}
