function getStatusMessage(status, progress) {
  if (status === "processing") {
    if (progress < 30) return "Analyzing input image";
    if (progress < 55) return "Estimating depth map";
    if (progress < 72) return "Reconstructing 3D mesh";
    if (progress < 92) return "Repairing and optimizing mesh";
    return "Exporting final outputs";
  }
  if (status === "completed") return "Reconstruction complete";
  if (status === "failed") return "Reconstruction failed";
  return "Starting reconstruction";
}

export default function ProgressIndicator({ progress, status }) {
  const safeProgress = Math.max(0, Math.min(100, Number(progress || 0)));

  return (
    <div className="reconstruct-progress">
      <div className="reconstruct-progress-bar-bg">
        <div className="reconstruct-progress-bar-fill" style={{ width: `${safeProgress}%` }} />
      </div>
      <div className="reconstruct-progress-meta">
        <span>{getStatusMessage(status, safeProgress)}</span>
        <span>{safeProgress}%</span>
      </div>
    </div>
  );
}
