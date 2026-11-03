export interface Item {
  id: string;
  name: string;
  brand: string;
  category: "ultraportable" | "performance" | "budget" | "creator";
  price: number;
  rating: number;
  ramGb: number;
  batteryHours: number;
  weightKg: number;
  tags: string[];
  summary: string;
}

/** Local mock catalog so every demo runs offline. The "items" are student laptops. */
export const ITEMS: readonly Item[] = [
  { id: "air-13", name: "Aurora Air 13", brand: "Aurora", category: "ultraportable", price: 1099, rating: 4.6, ramGb: 16, batteryHours: 18, weightKg: 1.2, tags: ["light", "battery"], summary: "Featherweight daily driver with all-day battery." },
  { id: "pro-14", name: "Aurora Pro 14", brand: "Aurora", category: "creator", price: 1799, rating: 4.7, ramGb: 32, batteryHours: 14, weightKg: 1.6, tags: ["display", "creator"], summary: "Colour-accurate display for design and video work." },
  { id: "forge-16", name: "Forge Titan 16", brand: "Forge", category: "performance", price: 2199, rating: 4.4, ramGb: 32, batteryHours: 7, weightKg: 2.4, tags: ["gpu", "gaming", "ml"], summary: "Discrete GPU powerhouse for ML coursework and games." },
  { id: "forge-14", name: "Forge Edge 14", brand: "Forge", category: "performance", price: 1499, rating: 4.3, ramGb: 16, batteryHours: 9, weightKg: 1.8, tags: ["gpu", "value"], summary: "Balanced GPU laptop for under fifteen hundred dollars." },
  { id: "nimbus-15", name: "Nimbus Study 15", brand: "Nimbus", category: "budget", price: 649, rating: 4.0, ramGb: 8, batteryHours: 10, weightKg: 1.7, tags: ["budget", "student"], summary: "Reliable essentials for notes, browsing and writing." },
  { id: "nimbus-14", name: "Nimbus Lite 14", brand: "Nimbus", category: "budget", price: 799, rating: 4.2, ramGb: 16, batteryHours: 12, weightKg: 1.4, tags: ["budget", "light"], summary: "Light budget pick with generous memory." },
  { id: "vertex-13", name: "Vertex Slim 13", brand: "Vertex", category: "ultraportable", price: 1349, rating: 4.5, ramGb: 16, batteryHours: 16, weightKg: 1.1, tags: ["light", "premium"], summary: "Premium magnesium chassis under 1.1 kg." },
  { id: "vertex-16", name: "Vertex Studio 16", brand: "Vertex", category: "creator", price: 2499, rating: 4.8, ramGb: 64, batteryHours: 11, weightKg: 2.1, tags: ["creator", "ml", "display"], summary: "Workstation-class laptop for heavy creative and ML work." },
];

export const getItemById = (id: string): Item | undefined => ITEMS.find((i) => i.id === id);
