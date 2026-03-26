import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Easing,
  Sequence,
} from "remotion";
import { Background } from "./common/Background";
import { AnimatedText } from "./common/AnimatedText";
import { ProgressBar } from "./common/ProgressBar";
import type { StatsVideoProps } from "../types";

const CountingNumber: React.FC<{
  value: number;
  unit: string;
  displayValue: string;
  startFrame: number;
  duration?: number;
  color: string;
}> = ({ value, unit, displayValue, startFrame, duration = 40, color }) => {
  const frame = useCurrentFrame();
  const relativeFrame = frame - startFrame;

  if (relativeFrame < 0) return null;

  const progress = interpolate(relativeFrame, [0, duration], [0, 1], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  const currentValue = value * progress;

  // Format based on the display value pattern
  let formatted: string;
  if (displayValue.startsWith("$")) {
    formatted = `$${currentValue.toFixed(1)}${unit}`;
  } else if (unit === "%") {
    formatted = `${Math.round(currentValue)}%`;
  } else if (unit === "x") {
    formatted = `${currentValue.toFixed(1)}x`;
  } else {
    formatted = `${currentValue.toFixed(1)}${unit}`;
  }

  return (
    <div
      style={{
        fontSize: 72,
        fontWeight: 800,
        color,
        fontVariantNumeric: "tabular-nums",
        lineHeight: 1,
      }}
    >
      {formatted}
    </div>
  );
};

export const StatsVideo: React.FC<StatsVideoProps> = ({
  title,
  stats,
  source,
  primaryColor,
  accentColor,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // Scene timing (30fps, 600 frames = 20s)
  const TITLE_FRAMES = 90; // 0-3s
  const STATS_START = 70;
  const STATS_STAGGER = 80; // Each stat appears 80 frames apart
  const SOURCE_START = durationInFrames - 90;

  // Fade out
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 25, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const maxNumericValue = Math.max(...stats.map((s) => s.numericValue));

  return (
    <Background primaryColor={primaryColor} accentColor={accentColor}>
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          color: "#ffffff",
          opacity: fadeOut,
          padding: "60px 80px",
        }}
      >
        {/* Title */}
        <Sequence from={0} durationInFrames={TITLE_FRAMES + 30}>
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
            }}
          >
            <AnimatedText
              text={title}
              startFrame={10}
              duration={25}
              animation="slideUp"
              style={{
                fontSize: 64,
                fontWeight: 800,
                textAlign: "center",
                background: `linear-gradient(135deg, ${primaryColor}, ${accentColor})`,
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            />
          </div>
        </Sequence>

        {/* Stats Grid */}
        <Sequence from={STATS_START} durationInFrames={durationInFrames - STATS_START}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: stats.length <= 2 ? "1fr 1fr" : "1fr 1fr",
              gap: "50px 80px",
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              width: "80%",
            }}
          >
            {stats.map((stat, i) => {
              const statStart = i * STATS_STAGGER;
              const cardOpacity = interpolate(
                frame - STATS_START,
                [statStart, statStart + 15],
                [0, 1],
                { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
              );
              const cardSlide = interpolate(
                frame - STATS_START,
                [statStart, statStart + 20],
                [30, 0],
                {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                  easing: Easing.out(Easing.cubic),
                }
              );

              return (
                <div
                  key={i}
                  style={{
                    opacity: cardOpacity,
                    transform: `translateY(${cardSlide}px)`,
                    display: "flex",
                    flexDirection: "column",
                    gap: 12,
                    padding: "30px 35px",
                    borderRadius: 16,
                    backgroundColor: "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(255,255,255,0.08)",
                  }}
                >
                  <div
                    style={{
                      fontSize: 16,
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: 2,
                      color: accentColor,
                    }}
                  >
                    {stat.label}
                  </div>
                  <CountingNumber
                    value={stat.numericValue}
                    unit={stat.unit}
                    displayValue={stat.value}
                    startFrame={STATS_START + statStart + 10}
                    duration={45}
                    color={primaryColor}
                  />
                  <ProgressBar
                    value={stat.numericValue}
                    maxValue={maxNumericValue * 1.2}
                    startFrame={STATS_START + statStart + 15}
                    duration={50}
                    color={accentColor}
                    width={320}
                    height={8}
                  />
                </div>
              );
            })}
          </div>
        </Sequence>

        {/* Source */}
        <Sequence from={SOURCE_START} durationInFrames={durationInFrames - SOURCE_START}>
          <div
            style={{
              position: "absolute",
              bottom: 40,
              right: 80,
            }}
          >
            <AnimatedText
              text={`Source: ${source}`}
              startFrame={0}
              duration={20}
              animation="fade"
              style={{
                fontSize: 16,
                color: "rgba(255,255,255,0.4)",
                fontStyle: "italic",
              }}
            />
          </div>
        </Sequence>
      </div>
    </Background>
  );
};
