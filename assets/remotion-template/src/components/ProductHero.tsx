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
import type { ProductHeroProps } from "../types";

export const ProductHero: React.FC<ProductHeroProps> = ({
  title,
  subtitle,
  features,
  ctaText,
  primaryColor,
  accentColor,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // Scene timing (30fps, 900 frames = 30s)
  const SCENE1_START = 0; // Brand intro: 0-3s (frames 0-90)
  const SCENE2_START = 90; // Features: 3-18s (frames 90-540)
  const SCENE3_START = 540; // Value prop: 18-25s (frames 540-750)
  const SCENE4_START = 750; // CTA: 25-30s (frames 750-900)

  // Global fade out at the end
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 30, durationInFrames],
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
          padding: 80,
        }}
      >
        {/* Scene 1: Brand / Title */}
        <Sequence from={SCENE1_START} durationInFrames={SCENE2_START + 60}>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              width: "80%",
            }}
          >
            <AnimatedText
              text={title}
              startFrame={0}
              duration={25}
              animation="slideUp"
              style={{
                fontSize: 86,
                fontWeight: 800,
                background: `linear-gradient(135deg, ${primaryColor}, ${accentColor})`,
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                textAlign: "center",
                lineHeight: 1.1,
              }}
            />
            <AnimatedText
              text={subtitle}
              startFrame={20}
              duration={25}
              animation="fade"
              style={{
                fontSize: 32,
                color: "rgba(255,255,255,0.7)",
                marginTop: 20,
                textAlign: "center",
                letterSpacing: 2,
              }}
            />
          </div>
        </Sequence>

        {/* Scene 2: Features */}
        <Sequence from={SCENE2_START} durationInFrames={SCENE3_START - SCENE2_START}>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              position: "absolute",
              inset: 0,
              padding: 80,
              gap: 40,
            }}
          >
            <div
              style={{
                fontSize: 28,
                letterSpacing: 4,
                textTransform: "uppercase",
                color: accentColor,
                opacity: interpolate(frame - SCENE2_START, [0, 15], [0, 1], {
                  extrapolateRight: "clamp",
                }),
              }}
            >
              Key Features
            </div>
            {features.map((feature, i) => {
              const featureStart = 30 + i * 90;
              return (
                <AnimatedText
                  key={i}
                  text={feature}
                  startFrame={featureStart}
                  duration={25}
                  animation={i % 2 === 0 ? "slideLeft" : "slideRight"}
                  style={{
                    fontSize: 52,
                    fontWeight: 700,
                    textAlign: "center",
                    opacity: interpolate(
                      frame - SCENE2_START,
                      [featureStart + 80, featureStart + 90],
                      [1, 0],
                      {
                        extrapolateLeft: "clamp",
                        extrapolateRight: "clamp",
                      }
                    ),
                  }}
                />
              );
            })}
          </div>
        </Sequence>

        {/* Scene 3: Value Proposition */}
        <Sequence from={SCENE3_START} durationInFrames={SCENE4_START - SCENE3_START}>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              position: "absolute",
              inset: 0,
              padding: 100,
            }}
          >
            <AnimatedText
              text={subtitle}
              startFrame={0}
              duration={30}
              animation="typewriter"
              style={{
                fontSize: 56,
                fontWeight: 700,
                textAlign: "center",
                color: "#ffffff",
                lineHeight: 1.3,
              }}
            />
            {/* Underline animation */}
            <div
              style={{
                marginTop: 20,
                height: 4,
                borderRadius: 2,
                background: `linear-gradient(90deg, ${primaryColor}, ${accentColor})`,
                width: interpolate(
                  frame - SCENE3_START,
                  [30, 60],
                  [0, 500],
                  { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
                ),
              }}
            />
          </div>
        </Sequence>

        {/* Scene 4: Call to Action */}
        <Sequence from={SCENE4_START} durationInFrames={durationInFrames - SCENE4_START}>
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
            <AnimatedText
              text={title}
              startFrame={0}
              duration={20}
              animation="fade"
              style={{
                fontSize: 64,
                fontWeight: 800,
                background: `linear-gradient(135deg, ${primaryColor}, ${accentColor})`,
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                textAlign: "center",
              }}
            />
            <div
              style={{
                marginTop: 20,
                padding: "20px 60px",
                borderRadius: 50,
                background: `linear-gradient(135deg, ${primaryColor}, ${accentColor})`,
                fontSize: 32,
                fontWeight: 700,
                color: "#fff",
                opacity: interpolate(
                  frame - SCENE4_START,
                  [10, 30],
                  [0, 1],
                  { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
                ),
                transform: `scale(${interpolate(
                  frame - SCENE4_START,
                  [30, 45, 60, 75, 90, 105, 120],
                  [1, 1.05, 1, 1.05, 1, 1.05, 1],
                  { extrapolateRight: "clamp" }
                )})`,
              }}
            >
              {ctaText}
            </div>
          </div>
        </Sequence>
      </div>
    </Background>
  );
};
