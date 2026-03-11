import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { useMemo } from "react";

function HeightMesh({ heightmap, resolution, maxHeight, mode }) {
  const geometry = useMemo(() => {
    if (!heightmap) {
      return null;
    }

    const geo = new THREE.PlaneGeometry(120, 120, resolution - 1, resolution - 1);
    const pos = geo.attributes.position.array;

    for (let i = 0; i < resolution * resolution; i += 1) {
      const z = heightmap[i] - maxHeight / 2;
      pos[i * 3 + 2] = z;
    }

    geo.computeVertexNormals();
    geo.rotateX(-Math.PI / 2);
    return geo;
  }, [heightmap, resolution, maxHeight]);

  if (!geometry) {
    return null;
  }

  return (
    <mesh geometry={geometry} castShadow receiveShadow>
      <meshStandardMaterial
        color={mode === "lithophane" ? "#f2e4c6" : "#d8d7d2"}
        roughness={0.45}
        metalness={0.1}
      />
    </mesh>
  );
}

export default function Preview3D({ heightmap, resolution, maxHeight, mode, loading }) {
  return (
    <div className="preview-container">
      <Canvas shadows camera={{ position: [90, 90, 90], fov: 45 }}>
        <color attach="background" args={["#0d1015"]} />
        <ambientLight intensity={0.4} />
        <directionalLight castShadow position={[120, 160, 90]} intensity={1.25} />
        <gridHelper args={[180, 18, "#3d495d", "#273242"]} />
        <HeightMesh heightmap={heightmap} resolution={resolution} maxHeight={maxHeight} mode={mode} />
        <OrbitControls enableDamping dampingFactor={0.06} />
      </Canvas>
      {loading ? (
        <div className="preview-overlay">
          <div className="spinner" />
          <span>Generating preview...</span>
        </div>
      ) : null}
    </div>
  );
}
