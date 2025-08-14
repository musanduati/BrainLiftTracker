/**
 * Shared color utilities for mapping lists to consistent colors
 */

// Vibrant gradient colors for lists (same as ListActivityRankings)
export const LIST_GRADIENTS = [
  'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', // Purple to Pink
  'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)', // Pink to Red
  'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)', // Blue to Cyan
  'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)', // Green to Teal
  'linear-gradient(135deg, #fa709a 0%, #fee140 100%)', // Pink to Yellow
  'linear-gradient(135deg, #30cfd0 0%, #330867 100%)', // Cyan to Purple
  'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)', // Light Blue to Pink
  'linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)', // Coral to Pink
  'linear-gradient(135deg, #fbc2eb 0%, #a6c1ee 100%)', // Pink to Blue
  'linear-gradient(135deg, #fdcbf1 0%, #e6dee9 100%)', // Light Pink to Gray
];

// Solid colors extracted from gradients (for simple progress bars)
export const LIST_SOLID_COLORS = [
  '#764ba2', // Purple
  '#f5576c', // Red
  '#00f2fe', // Cyan
  '#38f9d7', // Teal
  '#fee140', // Yellow
  '#330867', // Dark Purple
  '#fed6e3', // Light Pink
  '#fecfef', // Pink
  '#a6c1ee', // Light Blue
  '#e6dee9', // Light Gray
];

// Shadow colors for enhanced visual effects
export const LIST_SHADOWS = [
  'rgba(102, 126, 234, 0.4)', // Purple
  'rgba(245, 87, 108, 0.4)',  // Red
  'rgba(79, 172, 254, 0.4)',  // Blue
  'rgba(67, 233, 123, 0.4)',  // Green
  'rgba(254, 225, 64, 0.4)',  // Yellow
  'rgba(51, 8, 103, 0.4)',    // Dark Purple
  'rgba(168, 237, 234, 0.4)', // Light Blue
  'rgba(255, 154, 158, 0.4)', // Coral
  'rgba(251, 194, 235, 0.4)', // Pink
  'rgba(253, 203, 241, 0.4)', // Light Pink
];

/**
 * Maps list IDs to consistent color indices
 */
const listColorMap = new Map<string, number>();

/**
 * Get a consistent gradient color for a list
 */
export function getListGradient(listId: string | number): string {
  const id = String(listId);
  
  if (!listColorMap.has(id)) {
    // Assign the next available color index
    const index = listColorMap.size % LIST_GRADIENTS.length;
    listColorMap.set(id, index);
  }
  
  const colorIndex = listColorMap.get(id)!;
  return LIST_GRADIENTS[colorIndex];
}

/**
 * Get a consistent solid color for a list
 */
export function getListSolidColor(listId: string | number): string {
  const id = String(listId);
  
  if (!listColorMap.has(id)) {
    // Assign the next available color index
    const index = listColorMap.size % LIST_SOLID_COLORS.length;
    listColorMap.set(id, index);
  }
  
  const colorIndex = listColorMap.get(id)!;
  return LIST_SOLID_COLORS[colorIndex];
}

/**
 * Get a consistent shadow color for a list
 */
export function getListShadow(listId: string | number): string {
  const id = String(listId);
  
  if (!listColorMap.has(id)) {
    // Assign the next available color index
    const index = listColorMap.size % LIST_SHADOWS.length;
    listColorMap.set(id, index);
  }
  
  const colorIndex = listColorMap.get(id)!;
  return LIST_SHADOWS[colorIndex];
}

/**
 * Initialize the color map with a specific order of list IDs
 * This ensures consistent colors across components
 */
export function initializeListColors(listIds: (string | number)[]): void {
  listColorMap.clear();
  listIds.forEach((id, index) => {
    listColorMap.set(String(id), index % LIST_GRADIENTS.length);
  });
}

/**
 * Get color index for a list (useful for matching logic)
 */
export function getListColorIndex(listId: string | number): number {
  const id = String(listId);
  
  if (!listColorMap.has(id)) {
    // Assign the next available color index
    const index = listColorMap.size % LIST_GRADIENTS.length;
    listColorMap.set(id, index);
  }
  
  return listColorMap.get(id)!;
}

/**
 * Get gradient by index (for direct access)
 */
export function getGradientByIndex(index: number): string {
  return LIST_GRADIENTS[index % LIST_GRADIENTS.length];
}

/**
 * Get solid color by index (for direct access)
 */
export function getSolidColorByIndex(index: number): string {
  return LIST_SOLID_COLORS[index % LIST_SOLID_COLORS.length];
}

/**
 * Get shadow by index (for direct access)
 */
export function getShadowByIndex(index: number): string {
  return LIST_SHADOWS[index % LIST_SHADOWS.length];
}