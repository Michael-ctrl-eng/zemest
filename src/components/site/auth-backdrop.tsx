"use client";

/**
 * Instant-paint auth backdrop (login / register / reset).
 * Plain <img> with pre-optimized AVIF (31KB, no /_next/image hop),
 * preloaded via <head> link, LQIP-blurred base64 painted with first render.
 */
const AUTH_LQIP =
  "data:image/jpeg;base64,/9j/2wBDABQODxIPDRQSEBIXFRQYHjIhHhwcHj0sLiQySUBMS0dARkVQWnNiUFVtVkVGZIhlbXd7gYKBTmCNl4x9lnN+gXz/2wBDARUXFx4aHjshITt8U0ZTfHx8fHx8fHx8fHx8fHx8fHx8fHx8fHx8fHx8fHx8fHx8fHx8fHx8fHx8fHx8fHx8fHz/wAARCAAQABgDASIAAhEBAxEB/8QAGAAAAwEBAAAAAAAAAAAAAAAAAAEDAgX/xAAXEAEBAQEAAAAAAAAAAAAAAAAAAgED/8QAFwEAAwEAAAAAAAAAAAAAAAAAAQIDBP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AOfnJmuamdCq8a00dgHVgSv/2Q==";

export function AuthBackdrop() {
  return (
    <>
      <link rel="preload" as="image" href="/zemest-auth-bg.avif" fetchPriority="high" />
      <img
        src="/zemest-auth-bg.avif"
        alt=""
        aria-hidden="true"
        width={1200}
        height={800}
        fetchPriority="high"
        decoding="async"
        sizes="100vw"
        className="absolute inset-0 w-full h-full object-cover"
        style={{ backgroundImage: `url(${AUTH_LQIP})`, backgroundSize: "cover", backgroundPosition: "center" }}
      />
      {/* Dark overlay for legibility */}
      <div className="absolute inset-0 bg-[var(--tavus-terminal-black)]/70" />
      {/* Premium bitmap dot grain texture */}
      <div
        className="absolute inset-0 opacity-20 pointer-events-none mix-blend-overlay"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, rgba(255, 255, 255, 0.4) 1px, transparent 0)",
          backgroundSize: "8px 8px",
        }}
      />
    </>
  );
}
