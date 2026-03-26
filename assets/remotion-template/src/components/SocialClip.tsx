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
import type { SocialClipProps } from "../types";

export const SocialClip: React.FC<SocialClipProps> = ({
  headline,
  points,
  ctaText,
  primaryColor,
  accentColor,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames, width, height } = useVideoConfig();

  // Scene timing (30fps, 450 frames = 15s)
  const HEADLINE_END = 120; // 0-4s
  const POINTS_START = 100;
  const POINTS_END = 330; // ~4-11s
  const CTA_START = 310; // ~10-15s

  // Fade out
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 20, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <Background primaryColor={primaryColor} accentColor={accentColor}>
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
          color: "#ffffff",
          opacity: fadeOut,
          padding: 60,
        }}
      >
        {/* Top accent line */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: 6,
            background: `linear-gradient(90deg, ${primaryColor}, ${accentColor})`,
            transform: `scaleX(${interpolate(frame, [0, 20], [0, 1], {
              extrapolateRight: "clamp",
              easing: Easing.out(Easing.cubic),
            })})`,
            transformOrigin: "left",
          }}
        />

        {/* Headline */}
        <Sequence from={0} durationInFrames={HEADLINE_END + 30}>
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              width: "85%",
            }}
          >
            <AnimatedText
              text={headline}
              startFrame={10}
              duration={30}
              animation="typewriter"
              style={{
                fontSize: 64,
                fontWeight: 800,
                textAlign: "center",
                lineHeight: 1.2,
              }}
            />
          </div>
        </Sequence>

        {/* Key Points */}
        <Sequence from={POINTS_START} durationInFrames={POINTS_END - POINTS_START}>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "flex-start",
              justifyContent: "center",
              position: "absolute",
              inset: 0,
              padding: "60px 70px",
              gap: 30,
            }}
          >
            {points.map((point, i) => {
              const pointStart = 20 + i * 50;
              return (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 20,
                    opacity: interpolate(
                      frame - POINTS_START,
                      [pointStart, pointStart + 20],
                      [0, 1],
                      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
                    ),
                    transform: `translateX(${interpolate(
                      frame - POINTS_START,
                      [pointStart, pointStart + 20],
                      [i % 2 === 0 ? -40 : 40, 0],
                      {
                        extrapolateLeft: "clamp",
                        extrapolateRight: "clamp",
                        easing: Easing.out(Easing.cubic),
                      }
                    )}px)`,
                  }}
                >
                  <div
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      backgroundColor: accentColor,
                      flexShrink: 0,
                      boxShadow: `0 0 10px ${accentColor}`,
                    }}
                  />
                  <div style={{ fontSize: 36, fontWeight: 600, lineHeight: 1.3 }}>
                    {point}
                  </div>
                </div>
              );
            })}
          </div>
        </Sequence>

        {/* CTA */}
        <Sequence from={CTA_START} durationInFrames={durationInFrames - CTA_START}>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              position: "absolute",
              inset: 0,
              gap: 30,
            }}
          >
            <div
              style={{
                padding: "24px 64px",
                borderRadius: 16,
                background: `linear-gradient(135deg, ${primaryColor}, ${accentColor})`,
                fontSize: 42,
                fontWeight: 800,
                color: "#fff",
                opacity: interpolate(
                  frame - CTA_START,
                  [0, 20],
                  [0, 1],
                  { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
                ),
                transform: `scale(${interpolate(
                  frame - CTA_START,
                  [0, 15, 20],
                  [0.8, 1.05, 1],
                  {
                    extrapolateLeft: "clamp",
                    extrapolateRight: "clamp",
                    easing: Easing.out(Easing.cubic),
                  }
                )})`,
              }}
            >
              {ctaText}
            </div>
          </div>
        </Sequence>

        {/* Bottom accent line */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            height: 6,
            background: `linear-gradient(90deg, ${accentColor}, ${primaryColor})`,
            transform: `scaleX(${interpolate(frame, [0, 20], [0, 1], {
              extrapolateRight: "clamp",
              easing: Easing.out(Easing.cubic),
            })})`,
            transformOrigin: "right",
          }}
        />
      </div>
    </Background>
  );
};
