import { useRef, useState } from "react";
import { api, photoUrl } from "../api";

// Shrink on the phone before uploading: faster on kitchen Wi-Fi, and it turns
// iPhone HEIC photos into JPEGs the server can read.
async function shrink(file: File, maxSide = 2000): Promise<Blob> {
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" } as ImageBitmapOptions);
    const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    return await new Promise((resolve) => canvas.toBlob((b) => resolve(b || file), "image/jpeg", 0.88));
  } catch {
    return file; // older browsers: let the server do it
  }
}

type Props = {
  photoId: number | null;
  onChange: (id: number | null) => void;
  label: string;
  small?: boolean;
};

export default function PhotoPicker({ photoId, onChange, label, small }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function picked(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const { id } = await api.uploadPhoto(await shrink(file));
      onChange(id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        className={`photo-slot ${small ? "small" : ""} ${photoId ? "filled" : ""}`}
        style={photoId ? { backgroundImage: `url(${photoUrl(photoId)})` } : undefined}
        onClick={() => !busy && input.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && input.current?.click()}
      >
        {!photoId && (
          <>
            <span style={{ fontSize: small ? 22 : 32 }}>📷</span>
            <span>{busy ? "Uploading…" : label}</span>
          </>
        )}
        {photoId && (
          <button
            type="button"
            className="remove"
            onClick={(e) => {
              e.stopPropagation();
              onChange(null);
            }}
          >
            Remove
          </button>
        )}
      </div>
      {error && <div className="error" style={{ marginTop: 6 }}>{error}</div>}
      <input ref={input} type="file" accept="image/*" hidden onChange={picked} />
    </div>
  );
}
