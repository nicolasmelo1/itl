import { defineCatalog, validateSpec } from "@json-render/core";
import { defineRegistry, JSONUIProvider, Renderer } from "@json-render/react";
import { schema as reactSchema } from "@json-render/react/schema";
import { Badge, Button, Card, Input } from "@itl/design-system";
import { z } from "zod";

export const UI_SPEC_VERSION = "itl.ui/v1";

const buttonPropsSchema = z
  .object({
    label: z.string().min(1),
    variant: z.enum(["solid", "subtle", "outline"]),
    size: z.enum(["compact", "regular"]),
    radius: z.enum(["square", "soft", "pill"]),
    density: z.enum(["compact", "comfortable"]),
    background: z.enum(["accent", "surface", "transparent"]),
    foreground: z.enum(["light", "dark"]),
    border: z.enum(["none", "subtle", "strong"]),
    fontWeight: z.enum(["regular", "semibold"]),
    state: z.enum(["default", "disabled", "loading"]),
  })
  .strict();

const inputPropsSchema = z
  .object({
    label: z.string().min(1),
    placeholder: z.string(),
    value: z.string(),
    tone: z.enum(["quiet", "strong"]),
    state: z.enum(["default", "disabled"]),
  })
  .strict();

const badgePropsSchema = z
  .object({
    label: z.string().min(1),
    tone: z.enum(["neutral", "accent", "success"]),
  })
  .strict();

const cardPropsSchema = z
  .object({
    title: z.string().min(1),
    description: z.string(),
    emphasis: z.enum(["quiet", "raised"]),
  })
  .strict();

const elementIdSchema = z.string().regex(/^[a-z][a-z0-9-]*$/, "Element IDs must be stable kebab-case strings.");

const elementSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("Button"), props: buttonPropsSchema, children: z.array(elementIdSchema).default([]) }).strict(),
  z.object({ type: z.literal("Input"), props: inputPropsSchema, children: z.array(elementIdSchema).default([]) }).strict(),
  z.object({ type: z.literal("Badge"), props: badgePropsSchema, children: z.array(elementIdSchema).default([]) }).strict(),
  z.object({ type: z.literal("Card"), props: cardPropsSchema, children: z.array(elementIdSchema).default([]) }).strict(),
]);

export const uiSpecSchema = z
  .object({
    version: z.literal(UI_SPEC_VERSION),
    root: elementIdSchema,
    elements: z.record(elementIdSchema, elementSchema),
  })
  .strict();

export type UISpec = z.infer<typeof uiSpecSchema>;
export type UIElement = UISpec["elements"][string];
export type ComponentType = UIElement["type"];

type CatalogMetadata = {
  level: "atom";
  editablePropPaths: readonly string[];
  allowedChildTypes: readonly ComponentType[];
};

export const componentMetadata: Record<ComponentType, CatalogMetadata> = {
  Button: {
    level: "atom",
    editablePropPaths: ["/label", "/variant", "/size", "/radius", "/density", "/background", "/foreground", "/border", "/fontWeight", "/state"],
    allowedChildTypes: [],
  },
  Input: {
    level: "atom",
    editablePropPaths: ["/label", "/placeholder", "/value", "/tone", "/state"],
    allowedChildTypes: [],
  },
  Badge: {
    level: "atom",
    editablePropPaths: ["/label", "/tone"],
    allowedChildTypes: [],
  },
  Card: {
    level: "atom",
    editablePropPaths: ["/title", "/description", "/emphasis"],
    allowedChildTypes: ["Button", "Input", "Badge", "Card"],
  },
};

export const jsonRenderCatalog = defineCatalog(reactSchema, {
  components: {
    Button: { props: buttonPropsSchema, description: "A controlled native button. It never accepts actions, styles, or URLs." },
    Input: { props: inputPropsSchema, description: "A controlled native text input." },
    Badge: { props: badgePropsSchema, description: "A controlled status badge." },
    Card: { props: cardPropsSchema, description: "An atom-level card that may host registered child element IDs." },
  },
  actions: {},
});

const { registry } = defineRegistry(jsonRenderCatalog, {
  components: {
    Button: ({ props }) => <Button {...props} />,
    Input: ({ props }) => <Input {...props} />,
    Badge: ({ props }) => <Badge {...props} />,
    Card: ({ props, children }) => <Card {...props}>{children}</Card>,
  },
});

export type UISpecIssue = {
  code: "shape" | "catalog" | "reference" | "cycle" | "parent-child";
  message: string;
  path?: string;
};

export type UISpecValidation =
  | { valid: true; spec: UISpec }
  | { valid: false; issues: UISpecIssue[] };

function graphIssues(spec: UISpec): UISpecIssue[] {
  const issues: UISpecIssue[] = [];
  const visiting = new Set<string>();
  const visited = new Set<string>();

  function visit(elementId: string) {
    if (visiting.has(elementId)) {
      issues.push({ code: "cycle", message: `Cycle detected at element '${elementId}'.`, path: `/elements/${elementId}` });
      return;
    }
    if (visited.has(elementId)) return;

    const element = spec.elements[elementId];
    if (!element) {
      issues.push({ code: "reference", message: `Element '${elementId}' does not exist.`, path: `/elements/${elementId}` });
      return;
    }

    visiting.add(elementId);
    for (const childId of element.children) {
      const child = spec.elements[childId];
      if (!child) {
        issues.push({ code: "reference", message: `Element '${elementId}' references missing child '${childId}'.`, path: `/elements/${elementId}/children` });
        continue;
      }
      if (!componentMetadata[element.type].allowedChildTypes.includes(child.type)) {
        issues.push({ code: "parent-child", message: `${element.type} cannot host ${child.type}.`, path: `/elements/${elementId}/children` });
      }
      visit(childId);
    }
    visiting.delete(elementId);
    visited.add(elementId);
  }

  visit(spec.root);
  return issues;
}

export function validateUISpec(input: unknown): UISpecValidation {
  const shape = uiSpecSchema.safeParse(input);
  if (!shape.success) {
    return {
      valid: false,
      issues: shape.error.issues.map((issue) => ({ code: "shape", message: issue.message, path: `/${issue.path.join("/")}` })),
    };
  }

  const catalog = jsonRenderCatalog.validate(shape.data);
  if (!catalog.success) {
    return { valid: false, issues: [{ code: "catalog", message: "The UI spec is not registered in the controlled catalog." }] };
  }

  const structural = validateSpec(shape.data);
  const structuralIssues = structural.issues
    .filter((issue) => issue.severity === "error")
    .map((issue) => ({ code: "reference" as const, message: issue.message, path: issue.elementKey ? `/elements/${issue.elementKey}` : undefined }));
  const issues = [...structuralIssues, ...graphIssues(shape.data)];

  return issues.length > 0 ? { valid: false, issues } : { valid: true, spec: shape.data };
}

export function ControlledRenderer({ spec }: { spec: unknown }) {
  const validation = validateUISpec(spec);
  if (!validation.valid) {
    return <p role="alert">Invalid controlled UI spec: {validation.issues.map((issue) => issue.message).join(" ")}</p>;
  }

  return (
    <JSONUIProvider registry={registry}>
      <Renderer registry={registry} spec={validation.spec} />
    </JSONUIProvider>
  );
}

export const fixtureSpec: UISpec = {
  version: UI_SPEC_VERSION,
  root: "welcome-card",
  elements: {
    "welcome-card": {
      type: "Card",
      props: { title: "Controlled components", description: "Every visual choice is a finite token.", emphasis: "raised" },
      children: ["status-badge", "name-input", "continue-button"],
    },
    "status-badge": { type: "Badge", props: { label: "Ready", tone: "success" }, children: [] },
    "name-input": { type: "Input", props: { label: "Name", placeholder: "Ada Lovelace", value: "", tone: "quiet", state: "default" }, children: [] },
    "continue-button": {
      type: "Button",
      props: { label: "Continue", variant: "solid", size: "regular", radius: "soft", density: "comfortable", background: "accent", foreground: "light", border: "none", fontWeight: "semibold", state: "default" },
      children: [],
    },
  },
};
