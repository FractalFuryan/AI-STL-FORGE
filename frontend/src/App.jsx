import { useEffect, useMemo, useRef, useState } from "react";
import Preview3D from "./components/Preview3D";
import PresetSelector from "./components/reconstruct/PresetSelector";
import ProgressIndicator from "./components/reconstruct/ProgressIndicator";
import { useDebouncedWorker } from "./hooks/useDebouncedWorker";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

const PRESETS = {
  custom: null,
  ender3_v3: { target_width_mm: 140, max_height: 10, base_thickness: 2, resolution: 192 },
  prusa_mk4: { target_width_mm: 160, max_height: 10, base_thickness: 2, resolution: 256 },
  bambu_a1_mini: { target_width_mm: 120, max_height: 8, base_thickness: 1.8, resolution: 192 },
};

const MODE_TABS = [
  { id: "heightmap", label: "Heightmap" },
  { id: "lithophane", label: "Lithophane" },
  { id: "emboss", label: "Emboss" },
  { id: "relief", label: "Relief" },
  { id: "ai-depth", label: "AI Depth", tag: "AI" },
  { id: "cookie-cutter", label: "Cookie Cutter" },
  { id: "reconstruct", label: "AI Reconstruct", tag: "AI" },
  { id: "statue", label: "AI Statue", tag: "AI" },
  { id: "bust", label: "Bust Gen", tag: "New" },
];

const BUST_STYLES = [
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

export default function App() {
  const fileInputRef = useRef(null);
  const workerRef = useRef(null);
  const pollRef = useRef(null);
  const [worker, setWorker] = useState(null);

  const [activeMode, setActiveMode] = useState("heightmap");
  const [imageFile, setImageFile] = useState(null);
  const [imageUrl, setImageUrl] = useState("");
  const [heightmap, setHeightmap] = useState(null);
  const [stlPreviewUrl, setStlPreviewUrl] = useState("");

  const [busy, setBusy] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [error, setError] = useState("");

  const [params, setParams] = useState({
    mode: "heightmap",
    preset: "custom",
    max_height: 8,
    base_thickness: 2,
    gamma: 1,
    smooth_sigma: 0.5,
    resolution: 192,
    target_width_mm: 100,
    adaptive_remesh: true,
  });

  const [bustStyle, setBustStyle] = useState("classical");
  const [fantasyRace, setFantasyRace] = useState("human");
  const [bustHeight, setBustHeight] = useState(80);
  const [bustResolution, setBustResolution] = useState(96);
  const [bustIncludeBase, setBustIncludeBase] = useState(true);
  const [bustHelmet, setBustHelmet] = useState(false);
  const [bustCrown, setBustCrown] = useState(false);
  const [bustBeard, setBustBeard] = useState(false);
  const [bustBusy, setBustBusy] = useState(false);
  const [bustError, setBustError] = useState("");

  const [reconstructPreset, setReconstructPreset] = useState("balanced");
  const [reconstructModel, setReconstructModel] = useState("auto");
  const [statueBaseType, setStatueBaseType] = useState("pedestal");
  const [reconstructHeightMm, setReconstructHeightMm] = useState(150);
  const [reconstructFormat, setReconstructFormat] = useState("stl");
  const [reconstructRepair, setReconstructRepair] = useState(true);
  const [reconstructDecimate, setReconstructDecimate] = useState(0.6);
  const [reconstructRemoveBg, setReconstructRemoveBg] = useState(false);
  const [reconstructJobId, setReconstructJobId] = useState("");
  const [reconstructStatus, setReconstructStatus] = useState("");
  const [reconstructProgress, setReconstructProgress] = useState(0);
  const [reconstructBusy, setReconstructBusy] = useState(false);
  const [reconstructDownloadUrl, setReconstructDownloadUrl] = useState("");
  const [reconstructPreviewUrl, setReconstructPreviewUrl] = useState("");

  const {
    loading: previewBusy,
    scheduleWork,
    clearPendingWork,
    latestRequestIdRef,
    setLoading: setPreviewBusy,
  } = useDebouncedWorker(worker, 180);

  const isBustMode = activeMode === "bust";
  const isReconstructMode = activeMode === "reconstruct";
  const isStatueMode = activeMode === "statue";
  const forgeBusy = busy || bustBusy || reconstructBusy;
  const canGenerate = isBustMode ? !forgeBusy : (!!imageFile && !forgeBusy);

  const vertexCount = useMemo(() => {
    const base = params.resolution * params.resolution;
    return isBustMode ? Math.round((bustResolution * bustResolution * 2.4)) : Math.round(base * 1.1);
  }, [isBustMode, params.resolution, bustResolution]);

  const triangleCount = useMemo(() => Math.round(vertexCount * 2), [vertexCount]);
  const estimatedSize = useMemo(() => ((triangleCount * 50) / (1024 * 1024)).toFixed(1), [triangleCount]);

  function safeRevokeObjectUrl(url) {
    if (url && url.startsWith("blob:")) {
      URL.revokeObjectURL(url);
    }
  }

  useEffect(() => {
    const nextWorker = new Worker(new URL("./workers/previewWorker.js", import.meta.url), { type: "module" });

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

  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
      }
      safeRevokeObjectUrl(stlPreviewUrl);
      safeRevokeObjectUrl(imageUrl);
    };
  }, [imageUrl, stlPreviewUrl]);

  useEffect(() => {
    if (activeMode !== "bust" && activeMode !== "reconstruct") {
      setParams((prev) => ({ ...prev, mode: activeMode }));
    }
  }, [activeMode]);

  async function updatePreview(file, nextParams = params) {
    if (!workerRef.current || !worker || activeMode === "bust") {
      return;
    }
    const imageBuffer = await file.arrayBuffer();
    scheduleWork({ imageBuffer, params: nextParams }, [imageBuffer]);
  }

  async function onFileChange(event) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setError("");
    setPreviewError("");
    setReconstructStatus("");
    setReconstructProgress(0);
    setReconstructJobId("");
    setReconstructDownloadUrl("");
    setReconstructPreviewUrl("");
    safeRevokeObjectUrl(stlPreviewUrl);
    safeRevokeObjectUrl(imageUrl);
    setStlPreviewUrl("");
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
      ? { ...params, preset: presetKey, ...selected }
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
      const response = await fetch(`${API_BASE}/api/generate-stl`, { method: "POST", body: formData });
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
    const payload = { include_base: bustIncludeBase };
    if (["fantasy", "villainous", "gothic", "alien", "steampunk"].includes(bustStyle)) {
      payload.race = fantasyRace;
      payload.has_helmet = bustHelmet;
      payload.has_crown = bustCrown;
      payload.has_beard = bustBeard;
    }
    return payload;
  }

  async function generateBust(random = false) {
    setBustBusy(true);
    setBustError("");
    try {
      const seed = Math.floor(Math.random() * 10000);
      const endpoint = random
        ? `${API_BASE}/api/busts/random/${bustStyle}?seed=${seed}&resolution=${bustResolution}&height=${bustHeight}`
        : `${API_BASE}/api/busts/generate/${bustStyle}?resolution=${bustResolution}&height=${bustHeight}`;
      const response = await fetch(endpoint, {
        method: "POST",
        headers: random ? undefined : { "Content-Type": "application/json" },
        body: random ? undefined : JSON.stringify(getBustParams()),
      });
      if (!response.ok) {
        throw new Error(`Bust request failed with status ${response.status}`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      safeRevokeObjectUrl(stlPreviewUrl);
      setStlPreviewUrl(url);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = random ? `${bustStyle}_random_${seed}.stl` : `${bustStyle}_bust.stl`;
      anchor.click();
    } catch (e) {
      setBustError(e instanceof Error ? e.message : "Bust generation failed");
    } finally {
      setBustBusy(false);
    }
  }

  async function pollReconstructionStatus(jobId) {
    if (pollRef.current) {
      clearInterval(pollRef.current);
    }

    let active = true;

    pollRef.current = setInterval(async () => {
      if (!active) {
        return;
      }
      try {
        const statusResponse = await fetch(`${API_BASE}/api/reconstruct/3d/status/${jobId}`);
        if (!statusResponse.ok) {
          throw new Error(`Status request failed: ${statusResponse.status}`);
        }

        const statusData = await statusResponse.json();
        setReconstructStatus(statusData.status || "processing");
        setReconstructProgress(statusData.progress ?? 0);
        if (statusData.download_url) {
          setReconstructDownloadUrl(`${API_BASE}${statusData.download_url}`);
        }
        if (statusData.preview_url) {
          const fullPreviewUrl = `${API_BASE}${statusData.preview_url}`;
          setReconstructPreviewUrl(fullPreviewUrl);
          setStlPreviewUrl(fullPreviewUrl);
        }

        if (statusData.status === "completed") {
          clearInterval(pollRef.current);
          pollRef.current = null;

          if (reconstructFormat === "stl" && statusData.download_url) {
            const anchor = document.createElement("a");
            anchor.href = `${API_BASE}${statusData.download_url}`;
            anchor.download = `reconstruct_${jobId}.stl`;
            anchor.click();
          }

          setReconstructBusy(false);
        } else if (statusData.status === "failed") {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setError(statusData.error || "AI reconstruction failed");
          setReconstructBusy(false);
        }
      } catch (e) {
        clearInterval(pollRef.current);
        pollRef.current = null;
        setError(e instanceof Error ? e.message : "Reconstruction status polling failed");
        setReconstructBusy(false);
      }
    }, 1500);

    return () => {
      active = false;
      if (pollRef.current) {
        clearInterval(pollRef.current);
      }
    };
  }

  async function startReconstruction() {
    if (!imageFile) {
      setError("Upload an image before starting AI reconstruction");
      return;
    }

    setError("");
    setReconstructBusy(true);
    setReconstructStatus("processing");
    setReconstructProgress(2);
    setReconstructDownloadUrl("");
    setReconstructPreviewUrl("");

    try {
      const formData = new FormData();
      formData.append("image", imageFile);
      formData.append("model", reconstructModel);
      formData.append("preset", reconstructPreset);
      if (isStatueMode) {
        formData.append("base_type", statueBaseType);
      }
      formData.append("target_height_mm", String(reconstructHeightMm));
      formData.append("output_format", reconstructFormat);
      formData.append("repair", String(reconstructRepair));
      formData.append("decimate_ratio", String(reconstructDecimate));
      formData.append("remove_bg", String(reconstructRemoveBg));

      const endpoint = isStatueMode ? `${API_BASE}/api/statue/generate` : `${API_BASE}/api/reconstruct/3d`;
      const response = await fetch(endpoint, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error(`Reconstruction request failed with status ${response.status}`);
      }

      const data = await response.json();
      setReconstructJobId(data.job_id);
      await pollReconstructionStatus(data.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start AI reconstruction");
      setReconstructBusy(false);
    }
  }

  function onForgeClick() {
    if (isBustMode) {
      generateBust(false);
      return;
    }
    if (isReconstructMode || isStatueMode) {
      startReconstruction();
      return;
    }
    generateStl();
  }

  function downloadReconstructOutput(kind) {
    if (!reconstructJobId || reconstructStatus !== "completed") {
      return;
    }

    const href = kind === "glb"
      ? (reconstructPreviewUrl || `${API_BASE}/api/reconstruct/3d/preview/${reconstructJobId}`)
      : (reconstructDownloadUrl || `${API_BASE}/api/reconstruct/3d/download/${reconstructJobId}`);
    const extension = kind === "glb" ? "glb" : reconstructFormat;

    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = `reconstruct_${reconstructJobId}.${extension}`;
    anchor.click();
  }

  return (
    <>
      <div className="corner-deco tl" />
      <div className="corner-deco tr" />
      <div className="corner-deco bl" />
      <div className="corner-deco br" />

      <header>
        <div className="logo">
          <div className="logo-icon">
            <svg viewBox="0 0 44 44" fill="none" xmlns="http://www.w3.org/2000/svg">
              <polygon points="22,2 42,34 2,34" fill="none" stroke="#00d4ff" strokeWidth="1.5" />
              <polygon points="22,10 36,34 8,34" fill="rgba(0,212,255,0.08)" stroke="#0099cc" strokeWidth="1" />
              <line x1="22" y1="2" x2="22" y2="34" stroke="#ff6b1a" strokeWidth="1" opacity="0.6" />
              <circle cx="22" cy="20" r="3" fill="#ff6b1a" opacity="0.9" />
            </svg>
          </div>
          <div>
            <div className="logo-text">AI·STL·<span>FORGE</span></div>
            <div className="logo-sub">3D Print Engine v2.4.1</div>
          </div>
        </div>
        <div className="header-status">
          <div className="nav-links">
            <a className="nav-link active">Generator</a>
            <a className="nav-link">Tabletop</a>
            <a className="nav-link">Busts</a>
            <a className="nav-link">Creatures</a>
            <a className="nav-link">Library</a>
          </div>
          <div className="status-pill online"><div className="status-dot" />System Online</div>
        </div>
      </header>

      <div className="app">
        <div className="mode-bar">
          {MODE_TABS.map((tab) => (
            <button
              type="button"
              key={tab.id}
              className={`mode-tab ${activeMode === tab.id ? "active" : ""}`}
              onClick={() => setActiveMode(tab.id)}
            >
              {tab.label}
              {tab.tag ? <span className={`mode-tag ${tab.tag === "AI" ? "ai" : "new"}`}>{tab.tag}</span> : null}
            </button>
          ))}
        </div>

        <aside className="panel-left">
          <div className="panel-section">
            <div className="panel-section-title">Source Image</div>
            <div className="upload-zone" onClick={() => fileInputRef.current?.click()}>
              <span className="upload-icon">⬡</span>
              <div className="upload-text">Drop image or click</div>
              <div className="upload-sub">PNG · JPG · WEBP · up to 20MB</div>
              <input ref={fileInputRef} className="hidden-input" type="file" accept="image/*" onChange={onFileChange} />
            </div>
            {imageUrl ? <img className="thumb" src={imageUrl} alt="source" /> : null}
          </div>

          {!isBustMode && !isReconstructMode && !isStatueMode ? (
            <>
              <div className="panel-section">
                <div className="panel-section-title">Mesh Parameters</div>
                <label className="param-row">
                  <div className="param-label"><span className="param-name">Printer Preset</span></div>
                  <select value={params.preset} onChange={(e) => onPresetChange(e.target.value)}>
                    <option value="custom">Custom</option>
                    <option value="ender3_v3">Creality Ender 3 V3</option>
                    <option value="prusa_mk4">Prusa MK4</option>
                    <option value="bambu_a1_mini">Bambu A1 Mini</option>
                  </select>
                </label>

                <div className="param-row">
                  <div className="param-label"><span className="param-name">Max Height</span><span className="param-value">{params.max_height.toFixed(1)} mm</span></div>
                  <input type="range" min="1" max="30" step="0.5" value={params.max_height} onChange={(e) => onParamChange("max_height", Number(e.target.value))} />
                </div>
                <div className="param-row">
                  <div className="param-label"><span className="param-name">Base Thickness</span><span className="param-value">{params.base_thickness.toFixed(1)} mm</span></div>
                  <input type="range" min="0.5" max="10" step="0.1" value={params.base_thickness} onChange={(e) => onParamChange("base_thickness", Number(e.target.value))} />
                </div>
                <div className="param-row">
                  <div className="param-label"><span className="param-name">Resolution</span><span className="param-value">{params.resolution} px</span></div>
                  <input type="range" min="64" max="512" step="32" value={params.resolution} onChange={(e) => onParamChange("resolution", Number(e.target.value))} />
                </div>
                <div className="param-row">
                  <div className="param-label"><span className="param-name">Smooth Sigma</span><span className="param-value">{params.smooth_sigma.toFixed(2)}</span></div>
                  <input type="range" min="0" max="3" step="0.1" value={params.smooth_sigma} onChange={(e) => onParamChange("smooth_sigma", Number(e.target.value))} />
                </div>
                <div className="param-row">
                  <div className="param-label"><span className="param-name">Gamma</span><span className="param-value">{params.gamma.toFixed(2)}</span></div>
                  <input type="range" min="0.3" max="3" step="0.1" value={params.gamma} onChange={(e) => onParamChange("gamma", Number(e.target.value))} />
                </div>
                <div className="param-row">
                  <div className="param-label"><span className="param-name">Target Width</span><span className="param-value">{params.target_width_mm} mm</span></div>
                  <input type="range" min="20" max="300" step="5" value={params.target_width_mm} onChange={(e) => onParamChange("target_width_mm", Number(e.target.value))} />
                </div>
              </div>

              <div className="panel-section">
                <div className="panel-section-title">Output Options</div>
                <label className="checkbox-row"><input type="checkbox" checked={params.adaptive_remesh} onChange={(e) => onParamChange("adaptive_remesh", e.target.checked)} /><span className="checkbox-label">Adaptive Remesh</span></label>
              </div>
            </>
          ) : isBustMode ? (
            <div className="panel-section">
              <div className="panel-section-title">Bust Parameters</div>
              <label className="param-row">
                <div className="param-label"><span className="param-name">Style</span></div>
                <select value={bustStyle} onChange={(e) => setBustStyle(e.target.value)}>
                  {BUST_STYLES.map((style) => <option key={style} value={style}>{style.replaceAll("_", " ")}</option>)}
                </select>
              </label>
              <label className="param-row">
                <div className="param-label"><span className="param-name">Race</span></div>
                <select value={fantasyRace} onChange={(e) => setFantasyRace(e.target.value)}>
                  <option value="human">human</option>
                  <option value="elf">elf</option>
                  <option value="dwarf">dwarf</option>
                  <option value="orc">orc</option>
                </select>
              </label>
              <div className="param-row">
                <div className="param-label"><span className="param-name">Bust Height</span><span className="param-value">{bustHeight} mm</span></div>
                <input type="range" min="20" max="300" step="1" value={bustHeight} onChange={(e) => setBustHeight(Number(e.target.value))} />
              </div>
              <div className="param-row">
                <div className="param-label"><span className="param-name">Resolution</span><span className="param-value">{bustResolution}</span></div>
                <input type="range" min="24" max="192" step="8" value={bustResolution} onChange={(e) => setBustResolution(Number(e.target.value))} />
              </div>
              <label className="checkbox-row"><input type="checkbox" checked={bustIncludeBase} onChange={(e) => setBustIncludeBase(e.target.checked)} /><span className="checkbox-label">Include Display Base</span></label>
              <label className="checkbox-row"><input type="checkbox" checked={bustHelmet} onChange={(e) => setBustHelmet(e.target.checked)} /><span className="checkbox-label">Helmet</span></label>
              <label className="checkbox-row"><input type="checkbox" checked={bustCrown} onChange={(e) => setBustCrown(e.target.checked)} /><span className="checkbox-label">Crown</span></label>
              <label className="checkbox-row"><input type="checkbox" checked={bustBeard} onChange={(e) => setBustBeard(e.target.checked)} /><span className="checkbox-label">Beard</span></label>
              <div className="button-stack">
                <button type="button" className="vp-btn full" onClick={() => generateBust(true)} disabled={forgeBusy}>Random Bust</button>
              </div>
            </div>
          ) : (
            <div className="panel-section">
              <div className="panel-section-title">{isStatueMode ? "AI Statue" : "AI Reconstruct"}</div>

              <PresetSelector value={reconstructPreset} onChange={setReconstructPreset} />

              <label className="param-row">
                <div className="param-label"><span className="param-name">Model</span></div>
                <select value={reconstructModel} onChange={(e) => setReconstructModel(e.target.value)}>
                  <option value="auto">Auto</option>
                  <option value="sf3d">SF3D</option>
                  <option value="triposr">TripoSR</option>
                </select>
              </label>

              {isStatueMode ? (
                <label className="param-row">
                  <div className="param-label"><span className="param-name">Base</span></div>
                  <select value={statueBaseType} onChange={(e) => setStatueBaseType(e.target.value)}>
                    <option value="none">none</option>
                    <option value="pedestal">pedestal</option>
                    <option value="miniature">miniature</option>
                  </select>
                </label>
              ) : null}

              <label className="param-row">
                <div className="param-label"><span className="param-name">Output</span></div>
                <select value={reconstructFormat} onChange={(e) => setReconstructFormat(e.target.value)}>
                  <option value="stl">stl</option>
                  <option value="glb">glb</option>
                </select>
              </label>

              <div className="param-row">
                <div className="param-label"><span className="param-name">Target Height</span><span className="param-value">{reconstructHeightMm} mm</span></div>
                <input type="range" min="40" max="300" step="5" value={reconstructHeightMm} onChange={(e) => setReconstructHeightMm(Number(e.target.value))} />
              </div>

              <div className="param-row">
                <div className="param-label"><span className="param-name">Decimate Ratio</span><span className="param-value">{reconstructDecimate.toFixed(2)}</span></div>
                <input type="range" min="0.2" max="1" step="0.05" value={reconstructDecimate} onChange={(e) => setReconstructDecimate(Number(e.target.value))} />
              </div>

              <label className="checkbox-row"><input type="checkbox" checked={reconstructRepair} onChange={(e) => setReconstructRepair(e.target.checked)} /><span className="checkbox-label">Repair Mesh</span></label>
              <label className="checkbox-row"><input type="checkbox" checked={reconstructRemoveBg} onChange={(e) => setReconstructRemoveBg(e.target.checked)} /><span className="checkbox-label">Remove Background</span></label>

              {reconstructJobId ? <div className="job-pill">JOB {reconstructJobId.slice(0, 8)} · {reconstructStatus || "processing"} · {reconstructProgress}%</div> : null}
              {reconstructJobId ? <ProgressIndicator progress={reconstructProgress} status={reconstructStatus} /> : null}
              {reconstructStatus === "completed" ? (
                <div className="button-stack">
                  <button type="button" className="vp-btn full" onClick={() => downloadReconstructOutput("stl")}>Download Output</button>
                  <button type="button" className="vp-btn full" onClick={() => downloadReconstructOutput("glb")}>Download GLB Preview</button>
                </div>
              ) : null}
            </div>
          )}
        </aside>

        <main className="viewport">
          <div className="viewport-header">
            <span className="viewport-title">◈ 3D Preview — {isBustMode ? "Bust" : (isStatueMode ? "AI Statue" : (isReconstructMode ? "AI Reconstruct" : params.mode))} Mode</span>
            <div className="viewport-controls">
              <button type="button" className="vp-btn">Wireframe</button>
              <button type="button" className="vp-btn">Top</button>
              <button type="button" className="vp-btn">Reset View</button>
            </div>
          </div>

          <div className="viewport-canvas">
            <Preview3D
              heightmap={heightmap}
              resolution={params.resolution}
              maxHeight={params.max_height}
              mode={params.mode}
              loading={previewBusy || bustBusy || reconstructBusy}
              modelUrl={(isBustMode || isReconstructMode || isStatueMode) ? stlPreviewUrl : ""}
            />
            {(isBustMode || isReconstructMode || isStatueMode) && !stlPreviewUrl ? (
              <div className="bust-preview-hint">{isBustMode ? "Generate a bust to view the real STL mesh here." : (isStatueMode ? "Start AI statue generation to preview the generated bust mesh." : "Start AI reconstruction to load the generated 3D mesh here.")}</div>
            ) : null}
            <span className="axis-label axis-x">X+</span>
            <span className="axis-label axis-y">Y+</span>
            <span className="axis-label axis-z">Z+</span>
          </div>

          <div className="forge-zone">
            <button type="button" className={`forge-btn ${forgeBusy ? "forge-btn-running" : ""}`} onClick={onForgeClick} disabled={!canGenerate}>
              ⬡ {forgeBusy ? "FORGING..." : (isBustMode ? "FORGE BUST STL" : (isStatueMode ? "GENERATE STATUE" : (isReconstructMode ? "RECONSTRUCT 3D" : "FORGE STL")))}
            </button>
            <div className={`progress-container ${forgeBusy ? "visible" : ""}`}>
              <div className="progress-bar-bg"><div className="progress-bar-fill" /></div>
              <div className="progress-label">{forgeBusy ? "PROCESSING REQUEST..." : "READY"}</div>
            </div>
            {error ? <p className="error">{error}</p> : null}
            {bustError ? <p className="error">{bustError}</p> : null}
            {previewError ? <p className="error">{previewError}</p> : null}
          </div>
        </main>

        <aside className="panel-right">
          <div className="panel-section">
            <div className="panel-section-title">Mesh Stats</div>
            <div className="stat-card"><div><div className="stat-name">Vertex Count</div><div className="stat-val">{vertexCount.toLocaleString()}</div></div><div className="stat-unit">verts</div></div>
            <div className="stat-card"><div><div className="stat-name">Triangle Count</div><div className="stat-val">{triangleCount.toLocaleString()}</div></div><div className="stat-unit">tris</div></div>
            <div className="stat-card"><div><div className="stat-name">Estimated Size</div><div className="stat-val forge-col">{estimatedSize}</div></div><div className="stat-unit">MB</div></div>
            <div className="stat-card"><div><div className="stat-name">Mode</div><div className="stat-val mode-val">{isBustMode ? bustStyle : ((isReconstructMode || isStatueMode) ? reconstructPreset : activeMode)}</div></div><div className="stat-unit">profile</div></div>
          </div>

          <div className="panel-section">
            <div className="panel-section-title">System Log</div>
            <div className="terminal-log">
              <div className="log-line ok">{"[OK] Backend ready"}</div>
              <div className="log-line info">{"[--] Redis limiter active"}</div>
              <div className="log-line ok">{"[OK] Worker preview online"}</div>
              <div className="log-line forge">{"[>>] Awaiting forge command"}</div>
              <div className="log-line info">{"[--] Mode: "}{isBustMode ? "bust" : (isStatueMode ? "statue" : (isReconstructMode ? "reconstruct" : activeMode))}</div>
            </div>
          </div>
        </aside>
      </div>
    </>
  );
}
