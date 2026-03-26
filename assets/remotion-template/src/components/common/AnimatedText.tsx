import React from "react";
import { useCurrentFrame, interpolate, Easing } from "remotion";

interface AnimatedTextProps {
  text: string;
  startFrame: number;
  style?: React.CSSProperties;
  animation?: "fade" | "slideUp" | "slideLeft" | "slideRight" | "typewriter";
  duration?: number;
}

export const AnimatedText: React.FC<AnimatedTextProps> = ({
  text,
  startFrame,
  style = {},
  animation = "fade",
  duration = 20,
}) => {
  const frame = useCurrentFrame();
  const relativeFrame = frame - startFrame;

  if (relativeFrame < 0) return null;

  let opacity = 1;
  let transform = "none";

  switch (animation) {
    case "fade":
      opacity = interpolate(relativeFrame, [0, duration], [0, 1], {
        extrapolateRight: "clamp",
        easing: Easing.out(Easing.cubic),
      });
      break;

    case "slideUp":
      opacity = interpolate(relativeFrame, [0, duration], [0, 1], {
        extrapolateRight: "clamp",
        easing: Easing.out(Easing.cubic),
      });
      transform = `translateY(${interpolate(
        relativeFrame,
        [0, duration],
        [40, 0],
        { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) }
      )}px)`;
      break;

    case "slideLeft":
      opacity = interpolate(relativeFrame, [0, duration], [0, 1], {
        extrapolateRight: "clamp",
        easing: Easing.out(Easing.cubic),
      });
      transform = `translateX(${interpolate(
        relativeFrame,
        [0, duration],
        [-60, 0],
        { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) }
      )}px)`;
      break;

    case "slideRight":
      opacity = interpolate(relativeFrame, [0, duration], [0, 1], {
        extrapolateRight: "clamp",
        easing: Easing.out(Easing.cubic),
      });
      transform = `translateX(${interpolate(
        relativeFrame,
        [0, duration],
        [60, 0],
        { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) }
      )}px)`;
      break;

    case "typewriter": {
      const charsVisible = Math.floor(
        interpolate(relativeFrame, [0, duration], [0, text.length], {
          extrapolateRight: "clamp",
        })
      );
      return (
        <div style={{ ...style, opacity: 1 }}>
          {text.slice(0, charsVisible)}
          {charsVisible < text.length && (
            <span style={{ opacity: relativeFrame % 10 < 5 ? 1 : 0 }}>|</span>
          )}
        </div>
      );
    }
  }

  return <div style={{ ...style, opacity, transform }}>{text}</div>;
};
