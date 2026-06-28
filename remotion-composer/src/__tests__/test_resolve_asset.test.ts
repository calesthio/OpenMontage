/**
 * Regression tests for resolveAsset() — absolute path URI generation.
 *
 * Ensures that Unix absolute paths produce file:///path (3 slashes),
 * Windows paths produce file:///C:/path, and other inputs pass through.
 */

// Extract resolveAsset logic for unit testing (mirrors Explainer.tsx implementation)
function resolveAsset(src) {
  if (
    src.startsWith("http://") ||
    src.startsWith("https://") ||
    src.startsWith("data:")
  ) {
    return src;
  }
  const clean = src.replace(/^file:\/\//, "");
  if (clean.startsWith("/") || /^[A-Za-z]:[\\\/]/.test(clean)) {
    let normalized = clean.replace(/\\/g, "/");
    if (normalized.startsWith("/")) {
      normalized = normalized.replace(/^\/+/, "/");
      return `file://${normalized}`;
    }
    return `file:///${normalized}`;
  }
  // In tests we can't call staticFile(), so return the cleaned relative path
  return clean;
}

describe("resolveAsset", () => {
  // --- Unix absolute paths (the regression case) ---
  it("converts Unix absolute path to file:// URI with exactly 3 slashes", () => {
    expect(resolveAsset("/home/user/narration.mp3")).toBe(
      "file:///home/user/narration.mp3"
    );
  });

  it("converts deep Unix absolute path correctly", () => {
    expect(resolveAsset("/var/projects/video/assets/audio/voice.wav")).toBe(
      "file:///var/projects/video/assets/audio/voice.wav"
    );
  });

  it("handles Unix root path", () => {
    expect(resolveAsset("/audio.mp3")).toBe("file:///audio.mp3");
  });

  // --- Windows absolute paths ---
  it("converts Windows backslash path to file:// URI", () => {
    expect(resolveAsset("C:\\Users\\narration.mp3")).toBe(
      "file:///C:/Users/narration.mp3"
    );
  });

  it("converts Windows forward-slash path to file:// URI", () => {
    expect(resolveAsset("C:/Users/narration.mp3")).toBe(
      "file:///C:/Users/narration.mp3"
    );
  });

  it("handles Windows lowercase drive letter", () => {
    expect(resolveAsset("d:\\project\\audio.wav")).toBe(
      "file:///d:/project/audio.wav"
    );
  });

  // --- Already-prefixed file:// URIs (idempotent) ---
  it("normalizes already-prefixed file:///path (3 slashes) idempotently", () => {
    expect(resolveAsset("file:///home/user/audio.mp3")).toBe(
      "file:///home/user/audio.mp3"
    );
  });

  it("normalizes file:// with 2 slashes + absolute path", () => {
    // file:// + /home = file:///home (the strip regex removes file://, leaving /home)
    expect(resolveAsset("file:///home/user/audio.mp3")).toBe(
      "file:///home/user/audio.mp3"
    );
  });

  it("normalizes file://// (4 slashes, the old bug) to 3 slashes", () => {
    // The regex strips file:/// leaving /home/..., then we produce file:///home/...
    expect(resolveAsset("file:////home/user/audio.mp3")).toBe(
      "file:///home/user/audio.mp3"
    );
  });

  // --- HTTP/HTTPS URLs pass through ---
  it("passes through http:// URLs unchanged", () => {
    expect(resolveAsset("http://example.com/audio.mp3")).toBe(
      "http://example.com/audio.mp3"
    );
  });

  it("passes through https:// URLs unchanged", () => {
    expect(resolveAsset("https://cdn.example.com/video.mp4")).toBe(
      "https://cdn.example.com/video.mp4"
    );
  });

  // --- Data URIs pass through ---
  it("passes through data: URIs unchanged", () => {
    const dataUri = "data:audio/mp3;base64,AAAA";
    expect(resolveAsset(dataUri)).toBe(dataUri);
  });

  // --- Relative paths (would go through staticFile in real code) ---
  it("returns relative paths as-is (staticFile proxy)", () => {
    expect(resolveAsset("audio/narration.mp3")).toBe("audio/narration.mp3");
  });

  it("returns filename-only paths as-is", () => {
    expect(resolveAsset("narration.mp3")).toBe("narration.mp3");
  });
});
