import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";

import { ClimbRenderer, IH, IW } from "../game/renderer";

export interface ClimbHandle {
  playScore: (points: number, tier: number) => void;
  setReducedMotion: (v: boolean) => void;
}

interface Props {
  maxScore: number;
  reducedMotion: boolean;
}

// Fixed 180x320 internal buffer scaled by integer factor with pixelated smoothing
// disabled (R37). We pick the largest integer scale that fits the container.
export const ClimbCanvas = forwardRef<ClimbHandle, Props>(function ClimbCanvas(
  { maxScore, reducedMotion },
  ref,
) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<ClimbRenderer | null>(null);

  useImperativeHandle(ref, () => ({
    playScore: (points, tier) => rendererRef.current?.playScore(points, tier),
    setReducedMotion: (v) => rendererRef.current?.setReducedMotion(v),
  }));

  useEffect(() => {
    const canvas = canvasRef.current!;
    canvas.width = IW;
    canvas.height = IH;
    const ctx = canvas.getContext("2d")!;
    ctx.imageSmoothingEnabled = false;

    const renderer = new ClimbRenderer(ctx, reducedMotion);
    renderer.setMaxScore(maxScore);
    renderer.start();
    rendererRef.current = renderer;

    return () => renderer.stop();
    // Renderer is created once; maxScore/reducedMotion updates handled via methods.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    rendererRef.current?.setReducedMotion(reducedMotion);
  }, [reducedMotion]);

  return (
    <canvas
      ref={canvasRef}
      aria-label="Fame climb animation"
      role="img"
      className="h-full max-h-full w-auto"
      style={{
        imageRendering: "pixelated",
        aspectRatio: `${IW} / ${IH}`,
      }}
    />
  );
});
