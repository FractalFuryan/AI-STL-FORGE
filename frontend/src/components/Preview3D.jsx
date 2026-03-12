import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import * as THREE from "three";
import { useLoader } from "@react-three/fiber";
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

function STLMesh({ stlUrl }) {
  const geometry = useLoader(STLLoader, stlUrl);

  const preparedGeometry = useMemo(() => {
    if (!geometry) {
      return null;
    }

    const g = geometry.clone();
    g.computeVertexNormals();
    g.computeBoundingBox();

    const box = g.boundingBox;
    if (!box) {
      return g;
    }

    const center = new THREE.Vector3();
    box.getCenter(center);
    g.translate(-center.x, -box.min.y, -center.z);

    const size = new THREE.Vector3();
    box.getSize(size);
    const maxDim = Math.max(size.x, size.y, size.z, 1e-6);
    const scale = 90 / maxDim;
    g.scale(scale, scale, scale);

    return g;
  }, [geometry]);

  if (!preparedGeometry) {
    return null;
  }

  return (
    <mesh geometry={preparedGeometry} castShadow receiveShadow>
      <meshStandardMaterial color="#d8d7d2" roughness={0.42} metalness={0.08} />
    </mesh>
  );
}

function GLBMesh({ glbUrl }) {
  const gltf = useLoader(GLTFLoader, glbUrl);

  const model = useMemo(() => {
    if (!gltf?.scene) {
      return null;
    }

    const cloned = gltf.scene.clone(true);
    const box = new THREE.Box3().setFromObject(cloned);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z, 1e-6);
    const scale = 90 / maxDim;

    cloned.position.sub(center);
    cloned.position.y -= box.min.y;
    cloned.scale.setScalar(scale);

    cloned.traverse((node) => {
      if (node.isMesh) {
        node.castShadow = true;
        node.receiveShadow = true;
      }
    });

    return cloned;
  }, [gltf]);

  if (!model) {
    return null;
  }

  return <primitive object={model} />;
}

export default function Preview3D({ heightmap, resolution, maxHeight, mode, loading, modelUrl }) {
  const isGLB = Boolean(modelUrl && modelUrl.toLowerCase().includes("/preview/"));

  return (
    <div className="preview-container">
      <Canvas shadows camera={{ position: [90, 90, 90], fov: 45 }}>
        <color attach="background" args={["#0d1015"]} />
        <ambientLight intensity={0.4} />
        <directionalLight castShadow position={[120, 160, 90]} intensity={1.25} />
        <gridHelper args={[180, 18, "#3d495d", "#273242"]} />
        {modelUrl ? (
          isGLB ? <GLBMesh glbUrl={modelUrl} /> : <STLMesh stlUrl={modelUrl} />
        ) : (
          <HeightMesh heightmap={heightmap} resolution={resolution} maxHeight={maxHeight} mode={mode} />
        )}
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
