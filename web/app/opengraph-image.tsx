import { ImageResponse } from "next/og";

import { BrandMark, BRAND_CANVAS, BRAND_CREAM } from "@/lib/brand-image";
import { SITE_TITLE } from "@/lib/site";

export const alt = SITE_TITLE;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          width: "100%",
          height: "100%",
          alignItems: "center",
          background: BRAND_CANVAS,
          padding: "80px",
          gap: "64px",
        }}
      >
        <BrandMark size={320} />
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            width: 680,
            color: BRAND_CREAM,
            fontSize: 48,
            fontWeight: 600,
            lineHeight: 1.2,
            letterSpacing: "-0.02em",
          }}
        >
          {SITE_TITLE}
        </div>
      </div>
    ),
    size,
  );
}
