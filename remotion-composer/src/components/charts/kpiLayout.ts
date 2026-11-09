// KPIGrid positions its cards with absolute coordinates, so shrinking its parent
// does not move them. The space to keep free has to be part of the calculation.

export interface KPIGridLayoutInput {
  count: number;
  columns: number;
  hasTitle: boolean;
  width: number;
  height: number;
  /** Pixels to keep free at the bottom of the frame, e.g. for burned captions. */
  bottomInset: number;
}

export function kpiGridLayout({
  count,
  columns,
  hasTitle,
  width,
  height,
  bottomInset,
}: KPIGridLayoutInput) {
  const cols = Math.min(columns, count);
  const rows = Math.ceil(count / cols);

  const gridPadding = 100;
  const cardGap = 28;
  const titleHeight = hasTitle ? 120 : 0;
  const gridTop = 80 + titleHeight;
  // The reserved band is already empty space, so the margin above it can be small.
  const bottomMargin = bottomInset > 0 ? 20 : 80;
  const gridWidth = width - gridPadding * 2;
  const gridHeight = height - bottomInset - gridTop - bottomMargin;
  const cardWidth = (gridWidth - cardGap * (cols - 1)) / cols;
  const cardHeight = Math.min((gridHeight - cardGap * (rows - 1)) / rows, 320);

  // Center grid vertically
  const totalGridHeight = rows * cardHeight + (rows - 1) * cardGap;
  const gridTopOffset = gridTop + (gridHeight - totalGridHeight) / 2;

  const cards = Array.from({ length: count }, (_, idx) => ({
    left: gridPadding + (idx % cols) * (cardWidth + cardGap),
    top: gridTopOffset + Math.floor(idx / cols) * (cardHeight + cardGap),
  }));

  return { cardWidth, cardHeight, cards };
}
