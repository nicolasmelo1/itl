import { Badge, Button, Card, Input, type ButtonProps } from "@itl/design-system";
import type { Meta, StoryObj } from "@storybook/react";

const buttonMeta = {
  component: Button,
  title: "Controlled UI/Button",
} satisfies Meta<typeof Button>;

export default buttonMeta;

type ButtonStory = StoryObj<typeof buttonMeta>;

const baseButton: ButtonProps = {
  content: { label: "Continue" },
  semantic: { role: "primary-action", state: "default" },
  appearance: { recipe: "primary", density: "comfortable", fontWeight: "semibold", radius: "soft", size: "regular" },
};

export const TechnicalSquare: ButtonStory = {
  args: { ...baseButton, appearance: { ...baseButton.appearance, radius: "square" } },
};

export const Subtle: ButtonStory = {
  args: { ...baseButton, appearance: { ...baseButton.appearance, recipe: "secondary" } },
};

export const Outline: ButtonStory = {
  args: { ...baseButton, appearance: { ...baseButton.appearance, recipe: "outline" } },
};

export const Compact: ButtonStory = {
  args: { ...baseButton, appearance: { ...baseButton.appearance, density: "compact", size: "compact" } },
};

export const Disabled: ButtonStory = {
  args: { ...baseButton, semantic: { ...baseButton.semantic, state: "disabled" } },
};

export const Loading: ButtonStory = {
  args: { ...baseButton, semantic: { ...baseButton.semantic, state: "loading" } },
};

export const FocusVisible: ButtonStory = {
  args: { ...baseButton, content: { label: "Tab to inspect focus" } },
  play: async ({ canvas }) => {
    canvas.getByRole("button").focus();
  },
};

export const RegisteredAtoms: StoryObj = {
  render: () => (
    <Card description="The catalog registry uses these shared components." emphasis="raised" title="Registered atoms">
      <Badge label="Ready" tone="success" />
      <Input label="Name" placeholder="Ada Lovelace" state="default" tone="quiet" value="" />
    </Card>
  ),
};
