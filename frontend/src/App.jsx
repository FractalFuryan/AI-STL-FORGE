import { useEffect, useMemo, useRef, useState } from "react";
import Preview3D from "./components/Preview3D";
import { useDebouncedWorker } from "./hooks/useDebouncedWorker";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

const PRESETS = {
  custom: null,
  ender3_v3: {
    label: "Creality Ender 3 V3",
    target_width_mm: 140,
    max_height: 10,
    base_thickness: 2,
    resolution: 192,
  },
  prusa_mk4: {
    label: "Prusa MK4",
    target_width_mm: 160,
    max_height: 10,
    base_thickness: 2,
    resolution: 256,
  },
  bambu_a1_mini: {
    label: "Bambu A1 Mini",
    target_width_mm: 120,
    max_height: 8,
    base_thickness: 1.8,
    resolution: 192,
  },
};

export default function App() {
  const [imageFile, setImageFile] = useState(null);
  const [imageUrl, setImageUrl] = useState("");
  const [heightmap, setHeightmap] = useState(null);
  const [busy, setBusy] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [error, setError] = useState("");
  const workerRef = useRef(null);
  const [worker, setWorker] = useState(null);
  const [params, setParams] = useState({
    mode: "heightmap",
    preset: "custom",
    max_height: 8,
    base_thickness: 2,
    gamma: 1,
    smooth_sigma: 0,
    resolution: 128,
    target_width_mm: 100,
    adaptive_remesh: false,
  });
  const [bustStyle, setBustStyle] = useState("classical");
  const [bustHeight, setBustHeight] = useState(80);
  const [bustResolution, setBustResolution] = useState(96);
  const [bustBusy, setBustBusy] = useState(false);
  const [bustError, setBustError] = useState("");
  const [fantasyRace, setFantasyRace] = useState("human");
  const [bustIncludeBase, setBustIncludeBase] = useState(true);
  const [bustHelmet, setBustHelmet] = useState(false);
  const [bustCrown, setBustCrown] = useState(false);
  const [bustBeard, setBustBeard] = useState(false);

  const bustStyles = [
    "classical",
    "fantasy",
    "sci_fi",
    "steampunk",
    "gothic",
    "cartoon",
    "anime",
    "realistic",
    "heroic",
    "villainous",
    "alien",
    "robot",
  ];

  const canGenerate = useMemo(() => !!imageFile && !busy, [imageFile, busy]);
  const {
    loading: previewBusy,
    scheduleWork,
    clearPendingWork,
    latestRequestIdRef,
    setLoading: setPreviewBusy,
  } = useDebouncedWorker(worker, 180);

  useEffect(() => {
    const nextWorker = new Worker(new URL("./workers/previewWorker.js", import.meta.url), {
      type: "module",
    });

    nextWorker.onmessage = (event) => {
      const { requestId, heightmapBuffer, error: workerError } = event.data;
      if (requestId !== latestRequestIdRef.current) {
        return;
      }

      if (workerError) {
        setPreviewError(workerError);
        setPreviewBusy(false);
        return;
      }

      setPreviewError("");
      setHeightmap(new Float32Array(heightmapBuffer));
      setPreviewBusy(false);
    };

    workerRef.current = nextWorker;
    setWorker(nextWorker);

    return () => {
      clearPendingWork();
      nextWorker.terminate();
    };
  }, [clearPendingWork, latestRequestIdRef, setPreviewBusy]);

  async function updatePreview(file, nextParams = params) {
    if (!workerRef.current || !worker) {
      return;
    }

    const imageBuffer = await file.arrayBuffer();

    scheduleWork(
      {
      imageBuffer,
      params: nextParams,
      },
      [imageBuffer],
    );
  }

  async function onFileChange(event) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setError("");
    setPreviewError("");
    setImageFile(file);
    setImageUrl(URL.createObjectURL(file));
    await updatePreview(file);
  }

  async function onParamChange(key, value) {
    const next = { ...params, [key]: value };
    setParams(next);
    if (imageFile) {
      await updatePreview(imageFile, next);
    }
  }

  async function onPresetChange(presetKey) {
    const selected = PRESETS[presetKey];
    const next = selected
      ? {
          ...params,
          preset: presetKey,
          target_width_mm: selected.target_width_mm,
          max_height: selected.max_height,
          base_thickness: selected.base_thickness,
          resolution: selected.resolution,
        }
      : { ...params, preset: "custom" };

    setParams(next);
    if (imageFile) {
      await updatePreview(imageFile, next);
    }
  }

  async function generateStl() {
    if (!imageFile) {
      return;
    }

    setBusy(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("image", imageFile);
      formData.append("params", JSON.stringify(params));

      const response = await fetch(`${API_BASE}/api/generate-stl`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "ai-stl-forge-model.stl";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setBusy(false);
    }
  }

  function getBustParams() {
    const payload = {
      include_base: bustIncludeBase,
    };

    if (bustStyle === "fantasy" || bustStyle === "villainous" || bustStyle === "gothic" || bustStyle === "alien" || bustStyle === "steampunk") {
      payload.race = fantasyRace;
      payload.has_helmet = bustHelmet;
      payload.has_crown = bustCrown;
      payload.has_beard = bustBeard;
    }

    return payload;
  }

  async function generateBust() {
    setBustBusy(true);
    setBustError("");

    try {
      const response = await fetch(
        `${API_BASE}/api/busts/generate/${bustStyle}?resolution=${bustResolution}&height=${bustHeight}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(getBustParams()),
        },
      );

      if (!response.ok) {
        throw new Error(`Bust request failed with status ${response.status}`);
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${bustStyle}_bust.stl`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setBustError(e instanceof Error ? e.message : "Bust generation failed");
    } finally {
      setBustBusy(false);
    }
  }

  async function randomBust() {
    setBustBusy(true);
    setBustError("");

    const seed = Math.floor(Math.random() * 10000);
    try {
      const response = await fetch(
        `${API_BASE}/api/busts/random/${bustStyle}?seed=${seed}&resolution=${bustResolution}&height=${bustHeight}`,
        { method: "POST" },
      );

      if (!response.ok) {
        throw new Error(`Random bust request failed with status ${response.status}`);
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${bustStyle}_random_${seed}.stl`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setBustError(e instanceof Error ? e.message : "Random bust generation failed");
    } finally {
      setBustBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <section className="left-panel">
        <h1>AI STL Forge</h1>
        <p className="subtitle">Turn any image into a printable relief or lithophane STL.</p>

        <label className="upload">
          <span>Upload Image</span>
          <input type="file" accept="image/*" onChange={onFileChange} />
        </label>

        <div className="grid-controls">
          <label>
            Printer Preset
            <select value={params.preset} onChange={(e) => onPresetChange(e.target.value)}>
              <option value="custom">Custom</option>
              <option value="ender3_v3">Creality Ender 3 V3</option>
              <option value="prusa_mk4">Prusa MK4</option>
              <option value="bambu_a1_mini">Bambu A1 Mini</option>
            </select>
          </label>

          <label>
            Mode
            <select value={params.mode} onChange={(e) => onParamChange("mode", e.target.value)}>
              <option value="heightmap">Heightmap</option>
              <option value="ai-depth">AI Depth</option>
              <option value="lithophane">Lithophane</option>
              <option value="emboss">Emboss</option>
              <option value="relief">Relief</option>
              <option value="cookie-cutter">Cookie Cutter</option>
            </select>
          </label>

          {params.mode === "ai-depth" ? (
            <p className="subtitle">AI Depth uses a server-side depth model; preview is an approximate local heightmap.</p>
          ) : null}

          {params.mode === "cookie-cutter" ? (
            <p className="subtitle">Cookie Cutter uses edge extraction on the server; preview shows a simplified shape mask.</p>
          ) : null}

          <label>
            Resolution
            <select
              value={params.resolution}
              onChange={(e) => onParamChange("resolution", Number(e.target.value))}
            >
              <option value={96}>Draft 96</option>
              <option value={128}>Balanced 128</option>
              <option value={192}>Quality 192</option>
              <option value={256}>High 256</option>
            </select>
          </label>

          <label>
            Max Height (mm)
            <input
              type="range"
              min="2"
              max="25"
              step="0.5"
              value={params.max_height}
              onChange={(e) => onParamChange("max_height", Number(e.target.value))}
            />
            <strong>{params.max_height.toFixed(1)}</strong>
          </label>

          <label>
            Base Thickness (mm)
            <input
              type="range"
              min="0.5"
              max="10"
              step="0.1"
              value={params.base_thickness}
              onChange={(e) => onParamChange("base_thickness", Number(e.target.value))}
            />
            <strong>{params.base_thickness.toFixed(1)}</strong>
          </label>

          <label>
            Gamma
            <input
              type="range"
              min="0.4"
              max="2.5"
              step="0.1"
              value={params.gamma}
              onChange={(e) => onParamChange("gamma", Number(e.target.value))}
            />
            <strong>{params.gamma.toFixed(1)}</strong>
          </label>

          <label>
            Smooth Sigma
            <input
              type="range"
              min="0"
              max="3"
              step="0.1"
              value={params.smooth_sigma}
              onChange={(e) => onParamChange("smooth_sigma", Number(e.target.value))}
            />
            <strong>{params.smooth_sigma.toFixed(1)}</strong>
          </label>

          <label>
            Target Width (mm)
            <input
              type="range"
              min="40"
              max="220"
              step="5"
              value={params.target_width_mm}
              onChange={(e) => onParamChange("target_width_mm", Number(e.target.value))}
            />
            <strong>{params.target_width_mm.toFixed(0)}</strong>
          </label>

          <label>
            Adaptive Remeshing
            <input
              type="checkbox"
              checked={params.adaptive_remesh}
              onChange={(e) => onParamChange("adaptive_remesh", e.target.checked)}
            />
          </label>
        </div>

        <button disabled={!canGenerate} onClick={generateStl} className="cta">
          {busy ? "Generating..." : "Generate STL"}
        </button>

        {previewBusy && <p className="subtitle">Refreshing preview...</p>}
        {previewError && <p className="error">{previewError}</p>}

        {error && <p className="error">{error}</p>}

        {imageUrl && <img className="thumb" src={imageUrl} alt="input preview" />}

        <div className="bust-panel">
          <h2>Bust Generator</h2>
          <p className="subtitle">Generate collectible bust STLs without uploading an image.</p>

          <div className="grid-controls bust-controls">
            <label>
              Style
              <select value={bustStyle} onChange={(e) => setBustStyle(e.target.value)}>
                {bustStyles.map((style) => (
                  <option key={style} value={style}>
                    {style.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </label>

            {(bustStyle === "fantasy" || bustStyle === "villainous" || bustStyle === "gothic" || bustStyle === "alien" || bustStyle === "steampunk") ? (
              <>
                <label>
                  Race
                  <select value={fantasyRace} onChange={(e) => setFantasyRace(e.target.value)}>
                    <option value="human">human</option>
                    <option value="elf">elf</option>
                    <option value="dwarf">dwarf</option>
                    <option value="orc">orc</option>
                  </select>
                </label>
                <label>
                  Helmet
                  <input type="checkbox" checked={bustHelmet} onChange={(e) => setBustHelmet(e.target.checked)} />
                </label>
                <label>
                  Crown
                  <input type="checkbox" checked={bustCrown} onChange={(e) => setBustCrown(e.target.checked)} />
                </label>
                <label>
                  Beard
                  <input type="checkbox" checked={bustBeard} onChange={(e) => setBustBeard(e.target.checked)} />
                </label>
              </>
            ) : null}

            <label>
              Height (mm)
              <input
                type="range"
                min="20"
                max="300"
                step="1"
                value={bustHeight}
                onChange={(e) => setBustHeight(Number(e.target.value))}
              />
              <strong>{bustHeight}</strong>
            </label>

            <label>
              Quality
              <select value={bustResolution} onChange={(e) => setBustResolution(Number(e.target.value))}>
                <option value={48}>Draft 48</option>
                <option value={64}>Balanced 64</option>
                <option value={96}>Quality 96</option>
                <option value={128}>High 128</option>
              </select>
            </label>

            <label>
              Include Base
              <input
                type="checkbox"
                checked={bustIncludeBase}
                onChange={(e) => setBustIncludeBase(e.target.checked)}
              />
            </label>
          </div>

          <div className="button-row">
            <button className="cta" disabled={bustBusy} onClick={generateBust}>
              {bustBusy ? "Generating..." : "Generate Bust STL"}
            </button>
            <button className="cta secondary" disabled={bustBusy} onClick={randomBust}>
              {bustBusy ? "Generating..." : "Random Bust"}
            </button>
          </div>

          {bustError ? <p className="error">{bustError}</p> : null}
        </div>
      </section>

      <section className="preview-panel">
        <Preview3D
          heightmap={heightmap}
          resolution={params.resolution}
          maxHeight={params.max_height}
          mode={params.mode}
          loading={previewBusy}
        />
      </section>
    </div>
  );
}
