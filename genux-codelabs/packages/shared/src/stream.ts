export const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

export function* chunkText(text: string, size = 24): Generator<string> {
  for (let i = 0; i < text.length; i += size) yield text.slice(i, i + size);
}

/** Rough token estimate (≈4 chars/token). Labelled as an estimate everywhere it is shown. */
export const estimateTokens = (text: string): number => Math.ceil(text.length / 4);
