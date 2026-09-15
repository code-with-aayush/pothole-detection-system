import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "PotholeAlert — Road Operations Dashboard",
    short_name: "PotholeAlert",
    description: "Real-time AI pothole detection, authority dispatch, and incident management",
    start_url: "/detect",
    display: "standalone",
    background_color: "#020617",
    theme_color: "#f59e0b",
    orientation: "portrait",
    icons: [
      {
        src: "/icon.png",
        sizes: "192x192",
        type: "image/png",
      },
    ],
  };
}
