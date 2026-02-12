export interface PoseMetrics {
  confidence: number;
  body: {
    height: number;
    shoulderWidth: number;
    hipWidth: number;
  };
  distances: Record<string, number>;
}
