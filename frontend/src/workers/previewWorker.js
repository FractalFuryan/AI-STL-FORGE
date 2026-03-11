function imageToHeightmap(imageBitmap, resolution, maxHeight, gamma, mode) {
  const canvas = new OffscreenCanvas(resolution, resolution);
  const ctx = canvas.getContext("2d", { willReadFrequently: true });

  const aspect = imageBitmap.width / imageBitmap.height;
  let drawW = resolution;
  let drawH = resolution;
  if (aspect > 1) {
    drawH = Math.max(1, Math.round(resolution / aspect));
  } else {
    drawW = Math.max(1, Math.round(resolution * aspect));
  }

  const x = Math.floor((resolution - drawW) / 2);
  const y = Math.floor((resolution - drawH) / 2);

  ctx.fillStyle = "black";
  ctx.fillRect(0, 0, resolution, resolution);
  ctx.drawImage(imageBitmap, x, y, drawW, drawH);

  const { data } = ctx.getImageData(0, 0, resolution, resolution);
  const values = new Float32Array(resolution * resolution);

  for (let i = 0; i < values.length; i += 1) {
    const p = i * 4;
    const gray = (0.299 * data[p] + 0.587 * data[p + 1] + 0.114 * data[p + 2]) / 255;
    const mapped = Math.pow(gray, gamma);

    if (mode === "lithophane") {
      values[i] = (1 - mapped) * maxHeight;
      continue;
    }

    if (mode === "ai-depth") {
      // Frontend preview fallback; server-side model provides true depth estimation.
      values[i] = mapped * maxHeight;
      continue;
    }

    if (mode === "emboss") {
      values[i] = Math.max(0, (mapped - 0.38) / 0.62) * maxHeight;
      continue;
    }

    if (mode === "relief") {
      values[i] = 0.18 * maxHeight + mapped * (0.82 * maxHeight);
      continue;
    }

    if (mode === "cookie-cutter") {
      values[i] = mapped > 0.45 ? maxHeight * 0.7 : 0;
      continue;
    }

    values[i] = mapped * maxHeight;
  }

  return values;
}

self.onmessage = async (event) => {
  const { imageBuffer, params, requestId } = event.data;

  try {
    const blob = new Blob([imageBuffer]);
    const bitmap = await createImageBitmap(blob);
    const map = imageToHeightmap(
      bitmap,
      params.resolution,
      params.max_height,
      params.gamma,
      params.mode,
    );

    self.postMessage({ requestId, heightmapBuffer: map.buffer }, [map.buffer]);
  } catch (error) {
    self.postMessage({ requestId, error: error instanceof Error ? error.message : "Preview failed" });
  }
};
