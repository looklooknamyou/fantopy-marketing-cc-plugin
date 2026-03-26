import React from "react";
import { Composition } from "remotion";
import { ProductHero } from "./components/ProductHero";
import { SocialClip } from "./components/SocialClip";
import { StatsVideo } from "./components/StatsVideo";
import type {
  ProductHeroProps,
  SocialClipProps,
  StatsVideoProps,
} from "./types";

const defaultProductHero: ProductHeroProps = {
  title: "Your Product",
  subtitle: "The future of productivity",
  features: [
    "AI-Powered Workflows",
    "Real-Time Collaboration",
    "Smart Analytics Dashboard",
  ],
  ctaText: "Get Started Free",
  primaryColor: "#6366f1",
  accentColor: "#06b6d4",
};

const defaultSocialClip: SocialClipProps = {
  headline: "Transform Your Workflow",
  points: [
    "10x faster than manual processes",
    "Trusted by 5,000+ teams",
    "Free 14-day trial — no credit card",
  ],
  ctaText: "Try It Free →",
  primaryColor: "#6366f1",
  accentColor: "#06b6d4",
};

const defaultStatsVideo: StatsVideoProps = {
  title: "Market at a Glance",
  stats: [
    { label: "Market Size", value: "$12.8B", numericValue: 12.8, unit: "B" },
    { label: "Annual Growth", value: "24%", numericValue: 24, unit: "%" },
    { label: "Teams Using AI", value: "67%", numericValue: 67, unit: "%" },
    { label: "Productivity Gain", value: "3.2x", numericValue: 3.2, unit: "x" },
  ],
  source: "Industry Report 2026",
  primaryColor: "#6366f1",
  accentColor: "#06b6d4",
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="ProductHero"
        component={ProductHero}
        durationInFrames={900}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={defaultProductHero}
      />
      <Composition
        id="SocialClip"
        component={SocialClip}
        durationInFrames={450}
        fps={30}
        width={1080}
        height={1080}
        defaultProps={defaultSocialClip}
      />
      <Composition
        id="StatsVideo"
        component={StatsVideo}
        durationInFrames={600}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={defaultStatsVideo}
      />
    </>
  );
};
