import { defineCatalog, validateSpec } from "@json-render/core";
import { defineRegistry, JSONUIProvider, Renderer } from "@json-render/react";
import { schema as reactSchema } from "@json-render/react/schema";
import {
  Badge,
  Button,
  Card,
  FormField,
  Input,
  ProjectSettingsPage,
  SettingsForm,
  SettingsTemplate,
} from "@itl/design-system";
import { z } from "zod";

export const UI_SPEC_VERSION = "itl.ui/v1";

export const buttonAppearanceValues = {
  recipe: ["primary", "secondary", "outline", "ghost"],
  size: ["compact", "regular"],
  radius: ["square", "soft", "pill"],
  density: ["compact", "comfortable"],
  fontWeight: ["regular", "semibold"],
} as const;

export const formFieldAppearanceValues = {
  labelPlacement: ["above", "inline"],
  gap: ["tight", "regular", "loose"],
  hintTone: ["quiet", "strong"],
} as const;

/**
 * Every editable Taste Loop subject and its finite visual vocabulary. A
 * component is refinable if and only if it appears here.
 */
export const componentAppearanceValues = {
  Button: buttonAppearanceValues,
  FormField: formFieldAppearanceValues,
} as const;
export type EditableComponentType = keyof typeof componentAppearanceValues;
export const editableComponentTypes = Object.keys(componentAppearanceValues) as EditableComponentType[];

export const buttonCatalogManifest = {
  version: "itl.catalog/button.v1",
  component: "Button",
  semantic: {
    role: ["primary-action", "secondary-action"],
    state: ["default", "disabled", "loading"],
  },
  appearance: buttonAppearanceValues,
} as const;

const buttonContentSchema = z.object({ label: z.string().min(1) }).strict();
const buttonSemanticSchema = z.object({
  role: z.enum(["primary-action", "secondary-action"]),
  state: z.enum(["default", "disabled", "loading"]),
}).strict();
const buttonAppearanceSchema = z.object({
  recipe: z.enum(buttonAppearanceValues.recipe),
  size: z.enum(buttonAppearanceValues.size),
  radius: z.enum(buttonAppearanceValues.radius),
  density: z.enum(buttonAppearanceValues.density),
  fontWeight: z.enum(buttonAppearanceValues.fontWeight),
}).strict();

const buttonPropsSchema = z
  .object({
    content: buttonContentSchema,
    semantic: buttonSemanticSchema,
    appearance: buttonAppearanceSchema,
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

const formFieldAppearanceSchema = z.object({
  labelPlacement: z.enum(formFieldAppearanceValues.labelPlacement),
  gap: z.enum(formFieldAppearanceValues.gap),
  hintTone: z.enum(formFieldAppearanceValues.hintTone),
}).strict();

const formFieldPropsSchema = z.object({
  label: z.string().min(1),
  // The API materializes an absent hint as null, so both spellings validate.
  hint: z.string().min(1).nullish(),
  appearance: formFieldAppearanceSchema,
}).strict();

const settingsFormPropsSchema = z.object({
  title: z.string().min(1),
  description: z.string(),
}).strict();

const settingsTemplatePropsSchema = z.object({ title: z.string().min(1) }).strict();
const projectSettingsPagePropsSchema = z.object({ title: z.string().min(1) }).strict();

const elementIdSchema = z.string().regex(/^[a-z][a-z0-9-]*$/, "Element IDs must be stable kebab-case strings.");

const elementSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("Button"), props: buttonPropsSchema, children: z.array(elementIdSchema).default([]) }).strict(),
  z.object({ type: z.literal("Input"), props: inputPropsSchema, children: z.array(elementIdSchema).default([]) }).strict(),
  z.object({ type: z.literal("Badge"), props: badgePropsSchema, children: z.array(elementIdSchema).default([]) }).strict(),
  z.object({ type: z.literal("Card"), props: cardPropsSchema, children: z.array(elementIdSchema).default([]) }).strict(),
  z.object({ type: z.literal("FormField"), props: formFieldPropsSchema, children: z.array(elementIdSchema).default([]) }).strict(),
  z.object({ type: z.literal("SettingsForm"), props: settingsFormPropsSchema, children: z.array(elementIdSchema).default([]) }).strict(),
  z.object({ type: z.literal("SettingsTemplate"), props: settingsTemplatePropsSchema, children: z.array(elementIdSchema).default([]) }).strict(),
  z.object({ type: z.literal("ProjectSettingsPage"), props: projectSettingsPagePropsSchema, children: z.array(elementIdSchema).default([]) }).strict(),
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

/**
 * Foundations are design decisions rather than renderable components. The
 * remaining names are the five Atomic Design levels. Keeping the full
 * vocabulary in the catalog makes it available to session and prompt tooling
 * before every future component is implemented.
 */
export const atomicDesignLevels = [
  "foundation",
  "atom",
  "molecule",
  "organism",
  "template",
  "page",
] as const;

export type AtomicDesignLevel = (typeof atomicDesignLevels)[number];
type RenderableAtomicDesignLevel = Exclude<AtomicDesignLevel, "foundation">;

/**
 * The legal render-tree edges for Atomic Design. A foundation is a token/value
 * source and is therefore deliberately absent: it informs every node but is
 * never itself a DOM/render-spec node.
 */
export const atomicChildLevels: Record<RenderableAtomicDesignLevel, readonly RenderableAtomicDesignLevel[]> = {
  atom: [],
  molecule: ["atom"],
  organism: ["atom", "molecule"],
  template: ["molecule", "organism"],
  page: ["template"],
};

const atomicNodeIdSchema = z.string().regex(/^[a-z][a-z0-9-]*$/, "Atomic node IDs must be stable kebab-case strings.");
const atomicNodeSchema = z.object({
  level: z.enum(["atom", "molecule", "organism", "template", "page"]),
  children: z.array(atomicNodeIdSchema).default([]),
}).strict();
const atomicCompositionSchema = z.object({
  root: atomicNodeIdSchema,
  nodes: z.record(atomicNodeIdSchema, atomicNodeSchema),
}).strict();

export type AtomicComposition = z.infer<typeof atomicCompositionSchema>;
export type AtomicCompositionIssue = {
  code: "shape" | "reference" | "cycle" | "level" | "root";
  message: string;
  path?: string;
};
export type AtomicCompositionValidation =
  | { valid: true; composition: AtomicComposition }
  | { valid: false; issues: AtomicCompositionIssue[] };

/**
 * Validate the layer graph before a component registry ever attempts to render
 * it. This is intentionally generic: concrete component/slot validation is
 * performed by the UI catalog metadata below.
 */
export function validateAtomicComposition(input: unknown): AtomicCompositionValidation {
  const shape = atomicCompositionSchema.safeParse(input);
  if (!shape.success) {
    return {
      valid: false,
      issues: shape.error.issues.map((issue) => ({ code: "shape", message: issue.message, path: `/${issue.path.join("/")}` })),
    };
  }

  const composition = shape.data;
  const rootNode = composition.nodes[composition.root];
  if (!rootNode || rootNode.level !== "page") {
    return {
      valid: false,
      issues: [{ code: "root", message: "An Atomic Design composition must have a registered page root.", path: "/root" }],
    };
  }

  const issues: AtomicCompositionIssue[] = [];
  const visiting = new Set<string>();
  const visited = new Set<string>();
  function visit(nodeId: string) {
    if (visiting.has(nodeId)) {
      issues.push({ code: "cycle", message: `Cycle detected at atomic node '${nodeId}'.`, path: `/nodes/${nodeId}` });
      return;
    }
    if (visited.has(nodeId)) return;
    const node = composition.nodes[nodeId];
    if (!node) {
      issues.push({ code: "reference", message: `Atomic node '${nodeId}' does not exist.`, path: `/nodes/${nodeId}` });
      return;
    }

    visiting.add(nodeId);
    for (const childId of node.children) {
      const child = composition.nodes[childId];
      if (!child) {
        issues.push({ code: "reference", message: `Atomic node '${nodeId}' references missing child '${childId}'.`, path: `/nodes/${nodeId}/children` });
        continue;
      }
      if (!atomicChildLevels[node.level].includes(child.level)) {
        issues.push({
          code: "level",
          message: `${node.level} cannot compose ${child.level}.`,
          path: `/nodes/${nodeId}/children`,
        });
      }
      visit(childId);
    }
    visiting.delete(nodeId);
    visited.add(nodeId);
  }
  visit(composition.root);
  return issues.length ? { valid: false, issues } : { valid: true, composition };
}

type CatalogMetadata = {
  level: RenderableAtomicDesignLevel;
  editablePropPaths: readonly string[];
  allowedChildTypes: readonly ComponentType[];
};

export const componentMetadata: Record<ComponentType, CatalogMetadata> = {
  Button: {
    level: "atom",
    editablePropPaths: ["/appearance/recipe", "/appearance/size", "/appearance/radius", "/appearance/density", "/appearance/fontWeight"],
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
    level: "molecule",
    editablePropPaths: ["/title", "/description", "/emphasis"],
    allowedChildTypes: ["Button", "Input", "Badge"],
  },
  FormField: {
    level: "molecule",
    editablePropPaths: ["/appearance/labelPlacement", "/appearance/gap", "/appearance/hintTone"],
    allowedChildTypes: ["Input"],
  },
  SettingsForm: {
    level: "organism",
    editablePropPaths: ["/title", "/description"],
    allowedChildTypes: ["FormField", "Button", "Badge"],
  },
  SettingsTemplate: {
    level: "template",
    editablePropPaths: ["/title"],
    allowedChildTypes: ["SettingsForm"],
  },
  ProjectSettingsPage: {
    level: "page",
    editablePropPaths: ["/title"],
    allowedChildTypes: ["SettingsTemplate"],
  },
};

export const jsonRenderCatalog = defineCatalog(reactSchema, {
  components: {
    Button: { props: buttonPropsSchema, description: "A controlled native button. It never accepts actions, styles, or URLs." },
    Input: { props: inputPropsSchema, description: "A controlled native text input." },
    Badge: { props: badgePropsSchema, description: "A controlled status badge." },
    Card: { props: cardPropsSchema, description: "A molecule that composes registered atom element IDs into a bounded surface." },
    FormField: { props: formFieldPropsSchema, description: "A molecule that owns a field label, help text and one registered Input atom." },
    SettingsForm: { props: settingsFormPropsSchema, description: "An organism for a bounded settings task." },
    SettingsTemplate: { props: settingsTemplatePropsSchema, description: "A template with a named settings layout region." },
    ProjectSettingsPage: { props: projectSettingsPagePropsSchema, description: "A concrete page that renders a reviewed settings template." },
  },
  actions: {},
});

const { registry } = defineRegistry(jsonRenderCatalog, {
  components: {
    Button: ({ props }) => <Button {...props} />,
    Input: ({ props }) => <Input {...props} />,
    Badge: ({ props }) => <Badge {...props} />,
    Card: ({ props, children }) => <Card {...props}>{children}</Card>,
    FormField: ({ props, children }) => <FormField {...props}>{children}</FormField>,
    SettingsForm: ({ props, children }) => <SettingsForm {...props}>{children}</SettingsForm>,
    SettingsTemplate: ({ props, children }) => <SettingsTemplate {...props}>{children}</SettingsTemplate>,
    ProjectSettingsPage: ({ props, children }) => <ProjectSettingsPage {...props}>{children}</ProjectSettingsPage>,
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
      props: {
        content: { label: "Continue" },
        semantic: { role: "primary-action", state: "default" },
        appearance: { recipe: "primary", size: "regular", radius: "soft", density: "comfortable", fontWeight: "semibold" },
      },
      children: [],
    },
  },
};

export const buttonFixtureSpec: UISpec = {
  version: UI_SPEC_VERSION,
  root: "continue-button",
  elements: { "continue-button": fixtureSpec.elements["continue-button"] },
};

/**
 * The refinement canvas needs more than one editable subject in one spec, at
 * two Atomic levels, so a session can move between them without reloading.
 */
export const refineFixtureSpec: UISpec = {
  version: UI_SPEC_VERSION,
  root: "account-settings",
  elements: {
    "account-settings": {
      type: "SettingsForm",
      props: { title: "Account", description: "Choose where project updates are sent." },
      children: ["email-field", "continue-button"],
    },
    "email-field": {
      type: "FormField",
      props: {
        label: "Account email",
        hint: "We use this address for essential project notifications.",
        appearance: { labelPlacement: "above", gap: "regular", hintTone: "quiet" },
      },
      children: ["account-email"],
    },
    "account-email": {
      type: "Input",
      props: { label: "Email address", placeholder: "you@example.com", value: "", tone: "quiet", state: "default" },
      children: [],
    },
    "continue-button": fixtureSpec.elements["continue-button"],
  },
};

export function isEditableComponentType(type: string): type is EditableComponentType {
  return type in componentAppearanceValues;
}

/** The visual vocabulary of one element, or undefined when it is structure. */
export function appearanceValuesFor(spec: UISpec, elementId: string) {
  const element = spec.elements[elementId];
  if (!element || !isEditableComponentType(element.type)) return undefined;
  return componentAppearanceValues[element.type];
}

export const projectSettingsFixtureSpec: UISpec = {
  version: UI_SPEC_VERSION,
  root: "project-settings-page",
  elements: {
    "project-settings-page": {
      type: "ProjectSettingsPage",
      props: { title: "Project settings" },
      children: ["settings-template"],
    },
    "settings-template": {
      type: "SettingsTemplate",
      props: { title: "Project settings" },
      children: ["account-settings"],
    },
    "account-settings": {
      type: "SettingsForm",
      props: { title: "Account", description: "Choose where project updates are sent." },
      children: ["email-field", "save-settings"],
    },
    "email-field": {
      type: "FormField",
      props: {
        label: "Account email",
        hint: "We use this address for essential project notifications.",
        appearance: { labelPlacement: "above", gap: "regular", hintTone: "quiet" },
      },
      children: ["account-email"],
    },
    "account-email": {
      type: "Input",
      props: { label: "Email address", placeholder: "you@example.com", value: "", tone: "quiet", state: "default" },
      children: [],
    },
    "save-settings": {
      type: "Button",
      props: {
        content: { label: "Save changes" },
        semantic: { role: "primary-action", state: "default" },
        appearance: { recipe: "primary", size: "regular", radius: "soft", density: "comfortable", fontWeight: "semibold" },
      },
      children: [],
    },
  },
};
