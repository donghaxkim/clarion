// ─── Layout Utilities for Evidence Canvas ─────────────────────────────────────

export interface Point {
  x: number;
  y: number;
}

export interface ClusterNodePosition {
  id: string;
  type?: string;
  x: number;
  y: number;
  data?: Record<string, unknown>;
}

/** Distribute N points evenly on a circle, starting from top (–π/2) */
export function distributeOnCircle(
  count: number,
  radius: number,
  center: Point
): Point[] {
  if (count === 0) return [];
  if (count === 1) return [{ x: center.x, y: center.y }];

  return Array.from({ length: count }, (_, i) => {
    const angle = (i / count) * 2 * Math.PI - Math.PI / 2;
    return {
      x: center.x + radius * Math.cos(angle),
      y: center.y + radius * Math.sin(angle),
    };
  });
}

/** Group an array of items by a key function */
export function groupBy<T>(
  items: T[],
  keyFn: (item: T) => string
): Record<string, T[]> {
  return items.reduce(
    (acc, item) => {
      const key = keyFn(item);
      if (!acc[key]) acc[key] = [];
      acc[key].push(item);
      return acc;
    },
    {} as Record<string, T[]>
  );
}

/** Format evidence type key to human-readable plural label */
export function formatTypeName(type: string): string {
  const overrides: Record<string, string> = {
    police_report: 'Police Reports',
    medical_record: 'Medical Records',
    witness_statement: 'Witness Statements',
    photo: 'Photos',
    video: 'Video',
    audio: 'Audio',
    legal_document: 'Legal Documents',
    other: 'Other Evidence',
  };
  return overrides[type] ?? type
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

/** Compute clustered positions for evidence nodes + cluster label nodes */
export function computeClusterLayout(
  evidenceNodes: Array<{ id: string; data: { evidenceType: string; pinned?: boolean }; position?: Point }>,
  options: {
    circleRadius?: number;
    center?: Point;
    colSpacing?: number;
    rowSpacing?: number;
  } = {}
): ClusterNodePosition[] {
  const {
    circleRadius = 420,
    center = { x: 0, y: 0 },
    colSpacing = 300,
    rowSpacing = 380,
  } = options;

  const groups = groupBy(evidenceNodes, (n) => n.data.evidenceType);
  const groupKeys = Object.keys(groups);

  if (groupKeys.length === 0) return [];

  const clusterCenters = distributeOnCircle(groupKeys.length, circleRadius, center);

  const positions: ClusterNodePosition[] = [];

  groupKeys.forEach((type, groupIndex) => {
    const clusterCenter = clusterCenters[groupIndex];
    const groupNodes = groups[type];
    const cols = Math.max(1, Math.ceil(Math.sqrt(groupNodes.length)));

    groupNodes.forEach((node, i) => {
      // Respect pinned nodes — don't move them
      if (node.data.pinned && node.position) {
        positions.push({ id: node.id, x: node.position.x, y: node.position.y });
        return;
      }

      const row = Math.floor(i / cols);
      const col = i % cols;
      const totalWidth = (Math.min(cols, groupNodes.length) - 1) * colSpacing;

      positions.push({
        id: node.id,
        x: clusterCenter.x + (col - (cols - 1) / 2) * colSpacing - totalWidth / 2 + 130,
        y: clusterCenter.y + row * rowSpacing,
      });
    });

    // Cluster label: centered above the group
    const labelX = clusterCenter.x;
    const labelY = clusterCenter.y - rowSpacing * 0.55;

    positions.push({
      id: `cluster-label-${type}`,
      type: 'clusterLabel',
      x: labelX,
      y: labelY,
      data: { label: formatTypeName(type), childIds: groupNodes.map((n) => n.id) },
    });
  });

  return positions;
}
