/**
 * Shared color utilities for mapping lists to consistent colors
 */

// Enhanced vibrant gradient colors for lists - more visually appealing
export const LIST_GRADIENTS = [
  'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', // Purple to Violet - keep as is (good for Academics)
  'linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%)', // Bright Red to Orange
  'linear-gradient(135deg, #4ecdc4 0%, #44a08d 100%)', // Teal to Sea Green  
  'linear-gradient(135deg, #45b7d1 0%, #96c93d 100%)', // Sky Blue to Lime
  'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)', // Hot Pink to Coral
  'linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)', // Peach to Light Orange
  'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)', // Mint to Blush
  'linear-gradient(135deg, #d299c2 0%, #fef9d7 100%)', // Mauve to Cream
  'linear-gradient(135deg, #89f7fe 0%, #66a6ff 100%)', // Cyan to Blue
  'linear-gradient(135deg, #fdcbf1 0%, #e6dee9 100%)', // Pink to Lavender
];

// Solid colors extracted from enhanced gradients (for simple progress bars)
export const LIST_SOLID_COLORS = [
  '#764ba2', // Purple
  '#ee5a24', // Orange Red
  '#44a08d', // Sea Green
  '#96c93d', // Lime Green
  '#f5576c', // Hot Coral
  '#fcb69f', // Peach
  '#fed6e3', // Blush Pink
  '#fef9d7', // Cream
  '#66a6ff', // Sky Blue
  '#e6dee9', // Lavender
];

// Enhanced shadow colors for better visual effects
export const LIST_SHADOWS = [
  'rgba(102, 126, 234, 0.5)', // Purple - slightly stronger
  'rgba(255, 107, 107, 0.5)', // Bright Red
  'rgba(78, 205, 196, 0.5)',  // Teal
  'rgba(69, 183, 209, 0.5)',  // Sky Blue
  'rgba(240, 147, 251, 0.5)', // Hot Pink
  'rgba(252, 182, 159, 0.5)', // Peach
  'rgba(168, 237, 234, 0.4)', // Mint
  'rgba(210, 153, 194, 0.5)', // Mauve
  'rgba(137, 247, 254, 0.5)', // Cyan
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