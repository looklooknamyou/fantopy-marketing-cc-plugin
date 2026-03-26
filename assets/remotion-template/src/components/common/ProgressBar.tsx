import React from "react";
import { useCurrentFrame, interpolate, Easing } from "remotion";

interface ProgressBarProps {
  value: number;
  maxValue: number;
  startFrame: number;
  duration?: number;
  color: string;
  backgroundColor?: string;
  height?: number;
  width?: number;
  borderRadius?: number;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  value,
  maxValue,
  startFrame,
  duration = 40,
  color,
  backgroundColor = "rgba(255,255,255,0.1)",
  height = 12,
  width = 400,
  borderRadius = 6,
}) => {
  const frame = useCurrentFrame();
  const relativeFrame = frame - startFrame;

  const percentage = (value / maxValue) * 100;
  const animatedWidth = interpolate(
    relativeFrame,
    [0, duration],
    [0, percentage],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.cubic),
    }
  );

  const glowOpacity = interpolate(
    relativeFrame,
    [duration * 0.8, duration],
    [0, 0.6],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <div
      style={{
        width,
        height,
        backgroundColor,
        borderRadius,
        overflow: "hidden",
        position: "relative",
      }}
    >
      <div
        style={{
          width: `${animatedWidth}%`,
          height: "100%",
          backgroundColor: color,
          borderRadius,
          boxShadow: `0 0 ${12 * glowOpacity}px ${color}`,
          transition: "none",
        }}
      />
    </div>
  );
};
