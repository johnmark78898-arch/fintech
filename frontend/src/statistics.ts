export type NumericVariable = {
  id: string;
  label: string;
  values: (number | null)[];
};

export type DescriptiveStatistics = {
  count: number;
  mean: number;
  median: number;
  standardDeviation: number | null;
  variance: number | null;
  minimum: number;
  firstQuartile: number;
  thirdQuartile: number;
  maximum: number;
  skewness: number | null;
};

export type Correlation = {
  coefficient: number | null;
  count: number;
};

export function describe(values: (number | null)[]): DescriptiveStatistics | null {
  const observations = values.filter((value): value is number =>
    value !== null && Number.isFinite(value),
  );
  if (!observations.length) return null;

  const sorted = [...observations].sort((left, right) => left - right);
  const count = sorted.length;
  const mean = sorted.reduce((sum, value) => sum + value, 0) / count;
  const quantile = (probability: number) => {
    const position = (count - 1) * probability;
    const lower = Math.floor(position);
    const fraction = position - lower;
    return sorted[lower] + (sorted[Math.min(lower + 1, count - 1)] - sorted[lower]) * fraction;
  };
  const squaredDeviations = observations.reduce((sum, value) => sum + (value - mean) ** 2, 0);
  const variance = count > 1 ? squaredDeviations / (count - 1) : null;
  const standardDeviation = variance === null ? null : Math.sqrt(variance);
  const skewness = standardDeviation !== null && standardDeviation > 0 && count > 2
    ? count / ((count - 1) * (count - 2))
      * observations.reduce((sum, value) => sum + ((value - mean) / standardDeviation) ** 3, 0)
    : null;

  return {
    count,
    mean,
    median: quantile(0.5),
    standardDeviation,
    variance,
    minimum: sorted[0],
    firstQuartile: quantile(0.25),
    thirdQuartile: quantile(0.75),
    maximum: sorted[count - 1],
    skewness,
  };
}

export function pearsonCorrelation(
  leftValues: (number | null)[],
  rightValues: (number | null)[],
): Correlation {
  const pairs = leftValues.flatMap((left, index) => {
    const right = rightValues[index];
    return left !== null && right !== null && Number.isFinite(left) && Number.isFinite(right)
      ? [{ left, right }]
      : [];
  });
  const count = pairs.length;
  if (count < 3) return { coefficient: null, count };

  const leftMean = pairs.reduce((sum, pair) => sum + pair.left, 0) / count;
  const rightMean = pairs.reduce((sum, pair) => sum + pair.right, 0) / count;
  const leftSquares = pairs.reduce((sum, pair) => sum + (pair.left - leftMean) ** 2, 0);
  const rightSquares = pairs.reduce((sum, pair) => sum + (pair.right - rightMean) ** 2, 0);
  if (leftSquares === 0 || rightSquares === 0) return { coefficient: null, count };

  const crossProducts = pairs.reduce(
    (sum, pair) => sum + (pair.left - leftMean) * (pair.right - rightMean),
    0,
  );
  return {
    coefficient: Math.max(-1, Math.min(1, crossProducts / Math.sqrt(leftSquares * rightSquares))),
    count,
  };
}
