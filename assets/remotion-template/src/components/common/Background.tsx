import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";

interface BackgroundProps {
  primaryColor: string;
  accentColor: string;
  children: React.ReactNode;
}

export const Background: React.FC<BackgroundProps> = ({
  primaryColor,
  accentColor,
  children,
}) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  const orbX = interpolate(frame, [0, 300, 600, 900], [20, 70, 30, 20], {
    extrapolateRight: "clamp",
  });
  const orbY = interpolate(frame, [0, 300, 600, 900], [20, 40, 70, 20], {
    extrapolateRight: "clamp",
  });
  const orb2X = interpolate(frame, [0, 300, 600, 900], [80, 30, 70, 80], {
    extrapolateRight: "clamp",
  });
  const orb2Y = interpolate(frame, [0, 300, 600, 900], [70, 50, 20, 70], {
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        width,
        height,
        backgroundColor: "#0a0a0f",
        position: "relative",
        overflow: "hidden",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Gradient orb 1 */}
      <div
        style={{
          position: "absolute",
          left: `${orbX}%`,
          top: `${orbY}%`,
          width: 600,
          height: 600,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${primaryColor}22 0%, transparent 70%)`,
          transform: "translate(-50%, -50%)",
          filter: "blur(80px)",
        }}
      />
      {/* Gradient orb 2 */}
      <div
        style={{
          position: "absolute",
          left: `${orb2X}%`,
          top: `${orb2Y}%`,
          width: 500,
          height: 500,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${accentColor}22 0%, transparent 70%)`,
          transform: "translate(-50%, -50%)",
          filter: "blur(80px)",
        }}
      />
      {/* Subtle grid overlay */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
                            linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)`,
          backgroundSize: "60px 60px",
        }}
      />
      {/* Content */}
      <div style={{ position: "relative", zIndex: 1, width: "100%", height: "100%" }}>
        {children}
      </div>
    </div>
  );
};
