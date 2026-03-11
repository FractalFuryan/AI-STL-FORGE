export function imageToHeightmap(imageBitmap, resolution, maxHeight, gamma, mode) {
  const canvas = document.createElement("canvas");
  canvas.width = resolution;
  canvas.height = resolution;
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
    const depth = mode === "lithophane" ? (1 - mapped) * maxHeight : mapped * maxHeight;
    values[i] = depth;
  }

  return values;
}
