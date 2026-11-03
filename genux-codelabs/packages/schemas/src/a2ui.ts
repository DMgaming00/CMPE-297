import { z } from "zod";

/**
 * A2UI v0.9.x wire format (subset of the Basic Catalog).
 * Server → client: createSurface | updateComponents | updateDataModel | deleteSurface.
 * Client → server: action (see `ActionMessage`).
 */
export const A2UI_VERSIONS = ["v0.9", "v0.9.1"] as const;
export const BASIC_CATALOG_ID = "https://a2ui.org/specification/v0_9_1/catalogs/basic/catalog.json";

const pathRef = z.object({ path: z.string().startsWith("/") }).strict();
const str = z.union([z.string().max(2000), pathRef]);
const bool = z.union([z.boolean(), pathRef]);
const ctxValue = z.union([z.string().max(500), z.number(), z.boolean(), pathRef]);
const id = z.string().regex(/^[A-Za-z0-9_-]{1,64}$/);

const base = { id };
export const a2uiComponentSchema = z.discriminatedUnion("component", [
  z.object({ ...base, component: z.literal("Text"), text: str, variant: z.enum(["h1", "h2", "h3", "h4", "h5", "caption", "body"]).optional() }).strict(),
  z.object({ ...base, component: z.literal("Column"), children: z.array(id).max(50), align: z.enum(["start", "center", "end", "stretch"]).optional(), justify: z.string().optional(), weight: z.number().optional() }).strict(),
  z.object({ ...base, component: z.literal("Row"), children: z.array(id).max(50), align: z.enum(["start", "center", "end", "stretch"]).optional(), justify: z.string().optional(), weight: z.number().optional() }).strict(),
  z.object({ ...base, component: z.literal("Card"), child: id }).strict(),
  z.object({ ...base, component: z.literal("Divider"), axis: z.enum(["horizontal", "vertical"]).optional() }).strict(),
  z.object({
    ...base,
    component: z.literal("TextField"),
    label: str,
    value: str,
    variant: z.enum(["shortText", "longText", "number", "obscured"]).optional(),
    checks: z.array(z.object({ call: z.enum(["required", "email", "regex"]), args: z.record(z.string(), z.unknown()).optional(), message: z.string().max(200) })).max(5).optional(),
  }).strict(),
  z.object({ ...base, component: z.literal("CheckBox"), label: str, value: bool }).strict(),
  z.object({
    ...base,
    component: z.literal("ChoicePicker"),
    options: z.array(z.object({ label: z.string().max(80), value: z.string().max(80) })).max(20),
    value: pathRef,
    variant: z.enum(["mutuallyExclusive", "multipleSelection"]).optional(),
  }).strict(),
  z.object({
    ...base,
    component: z.literal("Button"),
    child: id,
    variant: z.enum(["primary", "borderless", "default"]).optional(),
    action: z.object({ event: z.object({ name: z.string().regex(/^[A-Za-z][A-Za-z0-9_]{0,40}$/), context: z.record(z.string(), ctxValue).optional() }).strict() }).strict(),
  }).strict(),
]);
export type A2uiComponent = z.infer<typeof a2uiComponentSchema>;

const ver = z.enum(A2UI_VERSIONS);
export const a2uiMessageSchema = z.union([
  z.object({ version: ver, createSurface: z.object({ surfaceId: id, catalogId: z.string(), sendDataModel: z.boolean().optional() }).strict() }).strict(),
  z.object({ version: ver, updateComponents: z.object({ surfaceId: id, components: z.array(a2uiComponentSchema).min(1).max(300) }).strict() }).strict(),
  z.object({ version: ver, updateDataModel: z.object({ surfaceId: id, path: z.string().startsWith("/").optional(), value: z.unknown() }).strict() }).strict(),
  z.object({ version: ver, deleteSurface: z.object({ surfaceId: id }).strict() }).strict(),
]);
export type A2uiMessage = z.infer<typeof a2uiMessageSchema>;

export const actionMessageSchema = z.object({
  version: ver,
  action: z.object({
    name: z.string(),
    surfaceId: z.string(),
    sourceComponentId: z.string(),
    timestamp: z.string(),
    context: z.record(z.string(), z.unknown()),
  }),
  dataModel: z.unknown().optional(),
});
export type ActionMessage = z.infer<typeof actionMessageSchema>;
